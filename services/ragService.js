/**
 * ragService.js
 * HTTP adapter bridge between SNAP (Node.js/Express) and the RAG Engine (Python/FastAPI).
 * 
 * All RAG interactions go through this single service file.
 * The RAG engine runs as a separate FastAPI process on port 8000.
 * 
 * Provides defensive error handling — if the RAG engine is down,
 * methods return graceful fallbacks instead of crashing the app.
 */
const fs = require('fs');
const path = require('path');

const RAG_BASE_URL = process.env.RAG_ENGINE_URL || 'http://127.0.0.1:8000';

class RagService {

  // ── Health Check ─────────────────────────────────────────

  /**
   * Check if the RAG microservice is running and reachable.
   * @returns {Promise<boolean>}
   */
  async isAvailable() {
    try {
      const res = await fetch(`${RAG_BASE_URL}/health`, {
        method: 'GET',
        signal: AbortSignal.timeout(2000)
      });
      return res.ok;
    } catch {
      return false;
    }
  }

  // ── Problem Statement Sync ───────────────────────────────

  /**
   * Register or synchronize a challenge/problem statement in the RAG Engine.
   * Converts a Mongoose Challenge document into the RAG Engine's expected text format.
   * 
   * @param {Object} challenge - Mongoose Challenge document
   * @returns {Promise<number>} problem_id from the RAG engine's SQLite DB
   * @throws {Error} if RAG engine is unreachable or returns an error
   */
  async syncProblem(challenge) {
    const problemText = [
      `Challenge Title: ${challenge.title}`,
      challenge.problemStatement ? `Problem Statement: ${challenge.problemStatement}` : '',
      challenge.rawProblem ? `Raw Problem Context: ${challenge.rawProblem}` : '',
      challenge.desiredOutcome ? `Desired Outcome: ${challenge.desiredOutcome}` : '',
      challenge.target ? `Target KPI: ${challenge.target}` : '',
      challenge.constraints && challenge.constraints.length
        ? `Constraints: ${challenge.constraints.join(', ')}` : '',
      challenge.budgetMax ? `Max Budget: Rs ${challenge.budgetMax}` : '',
      challenge.technologies && challenge.technologies.length
        ? `Preferred Tech: ${challenge.technologies.join(', ')}` : '',
      challenge.kpis && challenge.kpis.length
        ? `KPIs: ${challenge.kpis.join(', ')}` : '',
      challenge.sector ? `Sector: ${challenge.sector}` : ''
    ].filter(Boolean).join('\n\n');

    try {
      const res = await fetch(`${RAG_BASE_URL}/problem`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ problem_text: problemText }),
        signal: AbortSignal.timeout(60000)
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `RAG Engine returned HTTP ${res.status}`);
      }

      const data = await res.json();
      return data.problem_id;
    } catch (err) {
      if (err.name === 'TimeoutError' || err.name === 'AbortError') {
        throw new Error('RAG Engine request timed out after 60s');
      }
      throw err;
    }
  }

  // ── Document Upload ──────────────────────────────────────

  /**
   * Upload a startup's proposal document to the RAG Engine.
   * The RAG Engine will: parse → filter eligibility → extract solution → check consistency → index in ChromaDB.
   * 
   * @param {number} problemId - RAG Engine problem_id
   * @param {string} startupName - Name of the startup
   * @param {string} filePath - Absolute path to the uploaded file (PDF, DOCX, or TXT)
   * @returns {Promise<Object>} Processing result with solution_id, eligibility, scores
   * @throws {Error} if file not found or RAG engine errors
   */
  async uploadSolutionDoc(problemId, startupName, filePath) {
    if (!fs.existsSync(filePath)) {
      throw new Error(`File not found: ${filePath}`);
    }

    const fileBuffer = fs.readFileSync(filePath);
    const fileName = path.basename(filePath);
    const blob = new Blob([fileBuffer]);

    const formData = new FormData();
    formData.append('problem_id', String(problemId));
    formData.append('startup_name', startupName || 'Unknown');
    formData.append('file', blob, fileName);

    try {
      const res = await fetch(`${RAG_BASE_URL}/startup/upload`, {
        method: 'POST',
        body: formData,
        signal: AbortSignal.timeout(120000)
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `RAG upload failed with HTTP ${res.status}`);
      }

      return await res.json();
    } catch (err) {
      if (err.name === 'TimeoutError' || err.name === 'AbortError') {
        throw new Error('RAG Engine upload timed out after 120s (large document?)');
      }
      throw err;
    }
  }

  // ── Shortlist / Ranking ──────────────────────────────────

  /**
   * Fetch the AI-scored and ranked shortlist for a problem.
   * Uses the RAG Engine's 8-dimension evaluation framework.
   * 
   * @param {number} problemId - RAG Engine problem_id
   * @param {boolean} [rescore=false] - Force re-scoring (costs LLM API calls)
   * @param {number} [topN=15] - Max number of results
   * @returns {Promise<Object>} Ranked solutions with scores and justifications
   */
  async getShortlist(problemId, rescore = false, topN = 15) {
    try {
      const url = `${RAG_BASE_URL}/shortlist/${problemId}?rescore=${rescore}&top_n=${topN}`;
      const res = await fetch(url, {
        method: 'GET',
        signal: AbortSignal.timeout(180000)
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Shortlist request failed with HTTP ${res.status}`);
      }

      return await res.json();
    } catch (err) {
      if (err.name === 'TimeoutError' || err.name === 'AbortError') {
        throw new Error('RAG shortlist request timed out (scoring many solutions?)');
      }
      throw err;
    }
  }

  // ── Semantic Search ──────────────────────────────────────

  /**
   * Cross-document semantic search using sentence-transformers embeddings + ChromaDB.
   * Example: "Find all startups using IoT sensors for water management"
   * 
   * @param {number|string|null} problemId - Scope search to a specific problem, or null for all
   * @param {string} query - Natural language search query
   * @param {number} [topK=10] - Max results
   * @returns {Promise<Object>} Search results with similarity scores
   */
  async searchSolutions(problemId, query, topK = 10) {
    try {
      const params = new URLSearchParams({ query, top_k: String(topK) });
      if (problemId != null) params.set('problem_id', String(problemId));

      const url = `${RAG_BASE_URL}/search?${params.toString()}`;
      const res = await fetch(url, {
        method: 'GET',
        signal: AbortSignal.timeout(30000)
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Search request failed with HTTP ${res.status}`);
      }

      return await res.json();
    } catch (err) {
      if (err.name === 'TimeoutError' || err.name === 'AbortError') {
        throw new Error('RAG search request timed out');
      }
      throw err;
    }
  }

  // ── List Problems ────────────────────────────────────────

  /**
   * List all problem statements stored in the RAG engine.
   * @returns {Promise<Object>} List of problems with previews
   */
  async listProblems() {
    try {
      const res = await fetch(`${RAG_BASE_URL}/problems`, {
        method: 'GET',
        signal: AbortSignal.timeout(10000)
      });
      if (!res.ok) return { problems: [] };
      return await res.json();
    } catch {
      return { problems: [] };
    }
  }
}

module.exports = new RagService();
