"""
FastAPI main application.
4 endpoints: POST /problem, POST /startup/upload, GET /shortlist/{problem_id}, GET /search
"""
import os
import json
import shutil
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional

from config import UPLOAD_DIR, TOP_N_SHORTLIST, DEFAULT_ELIGIBILITY_RULES
from db import (
    init_db, insert_problem, get_problem,
    insert_solution, get_solutions_for_problem, get_solution,
    insert_score, get_scores_for_problem, delete_scores_for_problem
)
from doc_parser import parse_document, get_doc_metadata
from requirement_extractor import extract_requirements
from solution_extractor import extract_solution
from eligibility_filter import check_eligibility
from consistency_checker import check_consistency
from rag_indexer import index_solution, search_solutions
from scorer import score_solution
from ranker import rank_solutions

# ── App Setup ─────────────────────────────────────────────
app = FastAPI(
    title="SNAP RAG Engine",
    description="AI-powered startup solution shortlisting for government procurement",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(UPLOAD_DIR, exist_ok=True)

# Mount frontend static files
frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


@app.on_event("startup")
def startup_event():
    init_db()
    print("[SNAP] Database initialized.")


# ── Schemas ───────────────────────────────────────────────
class ProblemRequest(BaseModel):
    problem_text: str
    eligibility_rules: Optional[dict] = None


# ── Routes ────────────────────────────────────────────────

@app.get("/")
def serve_frontend():
    """Serve the single-page frontend."""
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "SNAP RAG Engine running. See /docs for API."}


@app.get("/health")
def health_check():
    """Health check endpoint for the Node.js adapter bridge."""
    return {"status": "ok", "service": "SNAP RAG Engine"}


@app.post("/problem")
def upload_problem(body: ProblemRequest):
    """
    Upload a government problem statement.
    Extracts structured requirements using Claude and stores in DB.
    Returns problem_id for subsequent uploads.
    """
    if not body.problem_text.strip():
        raise HTTPException(status_code=400, detail="Problem text cannot be empty.")

    requirements = extract_requirements(body.problem_text)
    problem_id = insert_problem(body.problem_text, requirements)

    return {
        "status": "success",
        "problem_id": problem_id,
        "requirements": requirements,
        "message": f"Problem statement stored with ID {problem_id}. Now upload startup solution docs."
    }


@app.post("/startup/upload")
async def upload_startup_solution(
    problem_id: int = Form(...),
    file: UploadFile = File(...),
    startup_name: Optional[str] = Form(None)
):
    """
    Upload a startup solution document (PDF or DOCX).
    Runs: doc_parser → eligibility_filter → solution_extractor → consistency_checker → rag_indexer
    Returns solution_id and processing result.
    """
    # Validate problem exists
    problem = get_problem(problem_id)
    if not problem:
        raise HTTPException(status_code=404, detail=f"Problem ID {problem_id} not found.")

    # Validate file type
    filename = file.filename or "upload"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in (".pdf", ".docx", ".doc", ".txt", ".text"):
        raise HTTPException(status_code=400, detail="Only PDF, DOCX, and TXT files are supported.")

    # Save uploaded file
    save_path = os.path.join(UPLOAD_DIR, f"p{problem_id}_{filename}")
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        # Step 1: Parse document
        raw_text = parse_document(save_path)
        if not raw_text.strip():
            raise HTTPException(status_code=422, detail="Could not extract text from document.")

        # Step 2: Eligibility filter FIRST (saves LLM cost)
        # Quick pre-extraction eligibility check using filename/basic text scan
        # Full eligibility runs after extraction
        basic_check = _quick_dpiit_scan(raw_text)

        # Step 3: Extract solution details (LLM call)
        solution_json = extract_solution(raw_text)

        # Override startup name if provided
        if startup_name:
            solution_json["startup_name"] = startup_name
        detected_name = solution_json.get("startup_name", "Unknown")

        # Step 4: Full eligibility filter
        rules = json.loads(problem.get("requirements_json") or "{}")
        eligible, eligibility_reason = check_eligibility(solution_json, DEFAULT_ELIGIBILITY_RULES)

        # Step 5: Consistency check (LLM call)
        consistency_flags = check_consistency(solution_json) if eligible else []

        # Step 6: Store in DB
        solution_id = insert_solution(
            problem_id=problem_id,
            startup_name=detected_name,
            filename=filename,
            raw_text=raw_text,
            solution_json=solution_json,
            eligible=eligible,
            eligibility_reason=eligibility_reason,
            consistency_flags=consistency_flags
        )

        # Step 7: Index in ChromaDB if eligible
        if eligible:
            index_solution(
                problem_id=problem_id,
                solution_id=solution_id,
                startup_name=detected_name,
                doc_text=raw_text
            )

        return {
            "status": "success",
            "solution_id": solution_id,
            "startup_name": detected_name,
            "eligible": eligible,
            "eligibility_reason": eligibility_reason,
            "consistency_flags": consistency_flags,
            "solution_summary": {
                "approach": solution_json.get("approach_summary", ""),
                "trl_level": solution_json.get("trl_level", ""),
                "cost_estimate": solution_json.get("cost_estimate", ""),
                "pilot_readiness": solution_json.get("pilot_readiness", ""),
            },
            "message": (
                f"Solution uploaded and {'indexed for scoring' if eligible else 'REJECTED (ineligible)'}."
            )
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")


@app.get("/shortlist/{problem_id}")
def get_shortlist(problem_id: int, top_n: int = TOP_N_SHORTLIST, rescore: bool = False):
    """
    Score and rank all eligible solutions for a problem.
    Returns ranked shortlist with per-dimension scores and justifications.
    Set rescore=true to force re-scoring (costs LLM calls).
    """
    problem = get_problem(problem_id)
    if not problem:
        raise HTTPException(status_code=404, detail=f"Problem ID {problem_id} not found.")

    requirements = json.loads(problem.get("requirements_json") or "{}")

    # Check if scores already exist
    existing_scores = get_scores_for_problem(problem_id)
    if existing_scores and not rescore:
        ranked = rank_solutions(existing_scores, top_n=top_n)
        return {
            "status": "success",
            "problem_id": problem_id,
            "total_eligible": len(get_solutions_for_problem(problem_id, eligible_only=True)),
            "shortlisted": len(ranked),
            "ranked_solutions": ranked,
            "note": "Cached scores. Use ?rescore=true to re-score."
        }

    # Score all eligible solutions
    solutions = get_solutions_for_problem(problem_id, eligible_only=True)
    if not solutions:
        return {
            "status": "no_solutions",
            "problem_id": problem_id,
            "message": "No eligible solutions uploaded yet."
        }

    if rescore:
        delete_scores_for_problem(problem_id)

    scored_rows = []
    for sol in solutions:
        sol_json = json.loads(sol.get("solution_json") or "{}")
        scores = score_solution(requirements, sol_json)

        score_id = insert_score(
            solution_id=sol["id"],
            problem_id=problem_id,
            scores=scores,
            justification=scores.get("justification", {}),
            final_score=0  # will be computed by ranker
        )

        scored_rows.append({
            "solution_id": sol["id"],
            "startup_name": sol["startup_name"],
            "filename": sol["filename"],
            "consistency_flags": sol.get("consistency_flags", "[]"),
            "technical_fit": scores.get("technical_fit", scores.get("relevance", 1)),
            "expected_impact": scores.get("expected_impact", scores.get("relevance", 1)),
            "feasibility": scores.get("feasibility", 1),
            "cost_effectiveness": scores.get("cost_effectiveness", scores.get("feasibility", 1)),
            "scalability": scores.get("scalability", 3),
            "security_privacy": scores.get("security_privacy", 3),
            "team_capability": scores.get("team_capability", scores.get("team_credibility", 1)),
            "innovation": scores.get("innovation", 1),
            "is_doable": scores.get("is_doable", True),
            "doability_reason": scores.get("doability_reason", "Technical and practical feasibility confirmed."),
            "justification_json": json.dumps(scores.get("justification", {})),
            # Legacy aliases
            "relevance": scores.get("technical_fit", scores.get("relevance", 1)),
            "team_credibility": scores.get("team_capability", scores.get("team_credibility", 1)),
            "pilot_readiness": scores.get("feasibility", 1),
        })

    ranked = rank_solutions(scored_rows, top_n=top_n)

    return {
        "status": "success",
        "problem_id": problem_id,
        "total_eligible": len(solutions),
        "shortlisted": len(ranked),
        "ranked_solutions": ranked
    }


@app.get("/shortlist/{problem_id}/all")
def get_all_solutions(problem_id: int):
    """Get all solutions (eligible + ineligible) for a problem with status."""
    problem = get_problem(problem_id)
    if not problem:
        raise HTTPException(status_code=404, detail=f"Problem ID {problem_id} not found.")

    from db import get_connection
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, startup_name, filename, eligible, eligibility_reason, "
        "consistency_flags, created_at FROM solutions WHERE problem_id = ?",
        (problem_id,)
    ).fetchall()
    conn.close()

    return {
        "problem_id": problem_id,
        "solutions": [dict(r) for r in rows]
    }


@app.get("/search")
def semantic_search(query: str, problem_id: Optional[str] = None, top_k: int = 10):
    """
    Cross-document semantic search across indexed solutions.
    Supports specific problem_id (int or string) or searches all indexed problems if omitted.
    Example: /search?query=IoT+sensors&problem_id=1
    """
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    results = search_solutions(problem_id=problem_id, query=query, top_k=top_k)
    return {
        "query": query,
        "problem_id": problem_id,
        "results": results
    }


@app.get("/problems")
def list_problems():
    """List all uploaded problem statements."""
    from db import get_connection
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, substr(raw_text, 1, 200) as preview, created_at FROM problems ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return {"problems": [dict(r) for r in rows]}


@app.delete("/problem/{problem_id}")
def delete_problem(problem_id: int):
    """Delete a problem and all associated solutions/scores."""
    from db import get_connection
    conn = get_connection()
    conn.execute("DELETE FROM scores WHERE problem_id = ?", (problem_id,))
    conn.execute("DELETE FROM solutions WHERE problem_id = ?", (problem_id,))
    conn.execute("DELETE FROM problems WHERE id = ?", (problem_id,))
    conn.commit()
    conn.close()
    return {"status": "deleted", "problem_id": problem_id}


# ── Health Check ─────────────────────────────────────────

@app.get("/health")
@app.get("/rag/health")
def health_check():
    """Health check endpoint for Render and load balancers."""
    return {"status": "ok", "service": "SNAP RAG Engine", "version": "1.0.0"}


# ── Helpers ───────────────────────────────────────────────

def _quick_dpiit_scan(text: str) -> bool:
    """Quick text scan to see if DPIIT is mentioned (before LLM extraction)."""
    return "dpiit" in text.lower() or "dipp" in text.lower() or "startup india" in text.lower()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
