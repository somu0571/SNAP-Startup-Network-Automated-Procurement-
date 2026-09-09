# SNAP RAG Engine — Startup Solution Shortlisting System

> **Built for Smart India Hackathon (SIH)**: AI-powered RAG pipeline to evaluate, screen, score, and rank startup proposals against government problem statements.

---

## Architecture & Flow

```
Government Problem Statement
            ↓
   requirement_extractor.py (Claude JSON-only extraction)
            ↓
   Stored in SQLite (problems table)
            ↓
Upload Startup Solution Document (PDF / DOCX)
            ↓
       doc_parser.py (PyMuPDF / python-docx plain text)
            ↓
    eligibility_filter.py (Rule-based: DPIIT & Turnover cap)
      ├── [FAIL] -> Marked ineligible in DB (saves API costs)
      └── [PASS] -> Continue pipeline:
            ↓
    solution_extractor.py (Claude JSON-only field extraction)
            ↓
   consistency_checker.py (Claude contradiction audit & flag list)
            ↓
       rag_indexer.py (SentenceTransformers + ChromaDB vector store)
            ↓
Get Shortlist / Scoring:
            ↓
         scorer.py (Claude LLM-Judge: 5 dimensions + justifications)
            ↓
         ranker.py (Weighted sum - consistency penalties -> top N)
```

---

## Tech Stack

- **Backend**: Python 3.10+ & FastAPI
- **Document Parsing**: PyMuPDF (`fitz`) for PDF, `python-docx` for Word
- **Embeddings**: `sentence-transformers` (`all-MiniLM-L6-v2`, local, no external key needed)
- **Vector Store**: ChromaDB (local persistence)
- **LLM**: Claude API (`claude-sonnet-4-6`), strictly structured JSON outputs with fallback handling
- **Database**: SQLite (`snap_rag.db`) with full intermediate JSON trace
- **Frontend**: Clean dark-mode single dashboard (`frontend/index.html`)

---

## Getting Started

### 1. Install Dependencies

```bash
cd rag-engine
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and insert your Anthropic API Key:

```bash
cp .env.example .env
```

Edit `.env`:
```env
ANTHROPIC_API_KEY=sk-ant-api03-...
CLAUDE_MODEL=claude-sonnet-4-6
EMBEDDING_MODEL=all-MiniLM-L6-v2
CHROMA_PERSIST_DIR=./chroma_data
SQLITE_DB_PATH=./snap_rag.db
UPLOAD_DIR=./uploads
```

### 3. Generate Test Samples (Optional)

```bash
python create_sample_docs.py
```
This generates test proposals in `sample_docs/` (e.g. eligible IoT startup, remote sensing startup, and an ineligible conglomerate).

### 4. Run the Server

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

- **Dashboard UI**: [http://localhost:8000](http://localhost:8000)
- **Interactive Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## API Endpoints

| Method | Route | Description |
|---|---|---|
| `POST` | `/problem` | Ingest government problem statement, extract structured criteria |
| `POST` | `/startup/upload` | Upload PDF/DOCX solution document, parse, verify eligibility, extract metadata, index |
| `GET` | `/shortlist/{problem_id}` | LLM-judge scoring across 5 dimensions, rank top solutions, return explainable justifications |
| `GET` | `/search?query=...&problem_id=...` | Cross-document semantic RAG search across indexed startup solutions |
| `GET` | `/problems` | List all registered problems |
| `GET` | `/shortlist/{problem_id}/all` | View all solutions (eligible and rejected) with eligibility reasons |

---

## Scoring Dimensions (1-5 Scale)

- **Relevance (30%)**: Alignment with government problem statement outcomes
- **Feasibility (25%)**: Realism of approach, cost vs budget, deployment timeline
- **Innovation (20%)**: Novelty compared to conventional off-the-shelf procurement
- **Team Credibility (15%)**: Technical depth, pedigree, domain experience
- **Pilot Readiness (10%)**: TRL level, speed to deploy initial controlled sandbox
- **Penalty deduction**: Each consistency flag deducts 0.5 points from final score (0-10 scale)
