"""
rag_adapter.py
Clean Python wrapper that encapsulates the RAG engine's core functions.
Provides a high-level interface for direct Python-to-Python usage
(CLI tools, test scripts, notebooks).

Usage:
    from services.rag_adapter import RAGAdapter

    adapter = RAGAdapter()
    problem_id = adapter.ingest_problem("Municipal water pipeline leak detection...")
    result = adapter.ingest_document(problem_id, "proposal.pdf", "TechSense Solutions")
    shortlist = adapter.get_shortlist(problem_id)
    results = adapter.semantic_search("IoT sensors", problem_id)
"""
import sys
import os

# Add the rag-engine directory to Python path
_rag_engine_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'rag-engine')
if _rag_engine_dir not in sys.path:
    sys.path.insert(0, _rag_engine_dir)


class RAGAdapter:
    """
    High-level adapter wrapping the RAG engine's core modules.
    Encapsulates: retriever, generator, document ingestion, scoring, and ranking pipelines.
    All methods include defensive error handling with meaningful fallbacks.
    """

    def __init__(self):
        """Initialize the RAG adapter — lazy-loads heavy modules on first use."""
        self._initialized = False

    def _ensure_init(self):
        """Lazy initialization of the database and modules."""
        if self._initialized:
            return

        try:
            from db import init_db
            init_db()
            self._initialized = True
            print("[RAG Adapter] Database initialized successfully.")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize RAG engine database: {e}")

    # ── Problem Statement Ingestion ─────────────────────────

    def ingest_problem(self, problem_text: str) -> dict:
        """
        Ingest a government problem statement.
        Extracts structured requirements using LLM (or heuristic fallback).

        Args:
            problem_text: Raw text of the government problem statement.

        Returns:
            dict with 'problem_id' and 'requirements'

        Raises:
            ValueError: If problem_text is empty
            RuntimeError: If database operations fail
        """
        if not problem_text or not problem_text.strip():
            raise ValueError("Problem text cannot be empty.")

        self._ensure_init()

        try:
            from requirement_extractor import extract_requirements
            from db import insert_problem

            requirements = extract_requirements(problem_text)
            problem_id = insert_problem(problem_text, requirements)

            return {
                "status": "success",
                "problem_id": problem_id,
                "requirements": requirements,
                "message": f"Problem stored with ID {problem_id}."
            }
        except Exception as e:
            raise RuntimeError(f"Failed to ingest problem statement: {e}")

    # ── Document Ingestion ──────────────────────────────────

    def ingest_document(self, problem_id: int, file_path: str, startup_name: str = None) -> dict:
        """
        Ingest a startup solution document (PDF, DOCX, or TXT).
        Pipeline: parse → eligibility filter → extract → consistency check → index in ChromaDB.

        Args:
            problem_id: ID of the problem this solution addresses.
            file_path: Path to the document file.
            startup_name: Optional override for the startup's name.

        Returns:
            dict with solution_id, eligibility status, consistency flags, and extracted data.

        Raises:
            FileNotFoundError: If file_path doesn't exist
            ValueError: If file format is unsupported or text extraction fails
            RuntimeError: If processing pipeline fails
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Document not found: {file_path}")

        self._ensure_init()

        try:
            import json
            from db import get_problem, insert_solution
            from doc_parser import parse_document
            from solution_extractor import extract_solution
            from eligibility_filter import check_eligibility
            from consistency_checker import check_consistency
            from config import DEFAULT_ELIGIBILITY_RULES

            # Validate problem exists
            problem = get_problem(problem_id)
            if not problem:
                raise ValueError(f"Problem ID {problem_id} not found in database.")

            # Step 1: Parse document
            raw_text = parse_document(file_path)
            if not raw_text.strip():
                raise ValueError("Could not extract text from document.")

            # Step 2: Extract solution details (LLM call)
            solution_json = extract_solution(raw_text)

            # Override startup name if provided
            if startup_name:
                solution_json["startup_name"] = startup_name
            detected_name = solution_json.get("startup_name", "Unknown")

            # Step 3: Eligibility filter (rule-based, no LLM cost)
            eligible, eligibility_reason = check_eligibility(
                solution_json, DEFAULT_ELIGIBILITY_RULES
            )

            # Step 4: Consistency check (LLM call, only if eligible)
            consistency_flags = check_consistency(solution_json) if eligible else []

            # Step 5: Store in SQLite
            filename = os.path.basename(file_path)
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

            # Step 6: Index in ChromaDB (vector embeddings) if eligible
            if eligible:
                try:
                    from rag_indexer import index_solution
                    index_solution(
                        problem_id=problem_id,
                        solution_id=solution_id,
                        startup_name=detected_name,
                        doc_text=raw_text
                    )
                except Exception as idx_err:
                    print(f"[RAG Adapter] Warning: ChromaDB indexing failed: {idx_err}")
                    # Non-fatal — solution is still stored in SQLite

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
                    "tech_stack": solution_json.get("tech_stack", []),
                }
            }

        except (FileNotFoundError, ValueError):
            raise
        except Exception as e:
            raise RuntimeError(f"Document ingestion failed: {e}")

    # ── Ingestion from Raw Text ─────────────────────────────

    def ingest_text(self, problem_id: int, text: str, startup_name: str = "Unknown") -> dict:
        """
        Ingest a startup solution from raw text (no file needed).
        Useful for testing and programmatic ingestion.

        Args:
            problem_id: ID of the problem this solution addresses.
            text: Raw text content of the startup solution.
            startup_name: Name of the startup.

        Returns:
            dict with solution_id, eligibility, and extracted data.
        """
        if not text or not text.strip():
            raise ValueError("Solution text cannot be empty.")

        self._ensure_init()

        try:
            import json
            from db import get_problem, insert_solution
            from solution_extractor import extract_solution
            from eligibility_filter import check_eligibility
            from consistency_checker import check_consistency
            from config import DEFAULT_ELIGIBILITY_RULES

            # Validate problem exists
            problem = get_problem(problem_id)
            if not problem:
                raise ValueError(f"Problem ID {problem_id} not found in database.")

            # Extract solution details
            solution_json = extract_solution(text)
            solution_json["startup_name"] = startup_name

            # Eligibility filter
            eligible, eligibility_reason = check_eligibility(
                solution_json, DEFAULT_ELIGIBILITY_RULES
            )

            # Consistency check
            consistency_flags = check_consistency(solution_json) if eligible else []

            # Store in SQLite
            solution_id = insert_solution(
                problem_id=problem_id,
                startup_name=startup_name,
                filename="(text_input)",
                raw_text=text,
                solution_json=solution_json,
                eligible=eligible,
                eligibility_reason=eligibility_reason,
                consistency_flags=consistency_flags
            )

            # Index in ChromaDB
            if eligible:
                try:
                    from rag_indexer import index_solution
                    index_solution(
                        problem_id=problem_id,
                        solution_id=solution_id,
                        startup_name=startup_name,
                        doc_text=text
                    )
                except Exception as idx_err:
                    print(f"[RAG Adapter] Warning: ChromaDB indexing failed: {idx_err}")

            return {
                "status": "success",
                "solution_id": solution_id,
                "startup_name": startup_name,
                "eligible": eligible,
                "eligibility_reason": eligibility_reason,
                "consistency_flags": consistency_flags,
                "solution_json": solution_json
            }

        except ValueError:
            raise
        except Exception as e:
            raise RuntimeError(f"Text ingestion failed: {e}")

    # ── Shortlist / Ranking ─────────────────────────────────

    def get_shortlist(self, problem_id: int, top_n: int = 15, rescore: bool = False) -> dict:
        """
        Score and rank all eligible solutions for a problem.
        Uses the 8-dimension evaluation framework.

        Args:
            problem_id: ID of the problem to shortlist.
            top_n: Maximum number of results.
            rescore: Force re-scoring (costs LLM calls).

        Returns:
            dict with ranked_solutions, each containing scores and justifications.
        """
        self._ensure_init()

        try:
            import json
            from db import get_problem, get_solutions_for_problem, get_scores_for_problem
            from db import insert_score, delete_scores_for_problem
            from scorer import score_solution
            from ranker import rank_solutions

            problem = get_problem(problem_id)
            if not problem:
                raise ValueError(f"Problem ID {problem_id} not found.")

            requirements = json.loads(problem.get("requirements_json") or "{}")

            # Check for cached scores
            existing_scores = get_scores_for_problem(problem_id)
            if existing_scores and not rescore:
                ranked = rank_solutions(existing_scores, top_n=top_n)
                return {
                    "status": "success",
                    "problem_id": problem_id,
                    "total_eligible": len(get_solutions_for_problem(problem_id, eligible_only=True)),
                    "shortlisted": len(ranked),
                    "ranked_solutions": ranked,
                    "note": "Cached scores. Use rescore=True to re-score."
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

                insert_score(
                    solution_id=sol["id"],
                    problem_id=problem_id,
                    scores=scores,
                    justification=scores.get("justification", {}),
                    final_score=0
                )

                scored_rows.append({
                    "solution_id": sol["id"],
                    "startup_name": sol["startup_name"],
                    "filename": sol["filename"],
                    "consistency_flags": sol.get("consistency_flags", "[]"),
                    "technical_fit": scores.get("technical_fit", 1),
                    "expected_impact": scores.get("expected_impact", 1),
                    "feasibility": scores.get("feasibility", 1),
                    "cost_effectiveness": scores.get("cost_effectiveness", 1),
                    "scalability": scores.get("scalability", 3),
                    "security_privacy": scores.get("security_privacy", 3),
                    "team_capability": scores.get("team_capability", 1),
                    "innovation": scores.get("innovation", 1),
                    "is_doable": scores.get("is_doable", True),
                    "doability_reason": scores.get("doability_reason", ""),
                    "justification_json": json.dumps(scores.get("justification", {})),
                })

            ranked = rank_solutions(scored_rows, top_n=top_n)
            return {
                "status": "success",
                "problem_id": problem_id,
                "total_eligible": len(solutions),
                "shortlisted": len(ranked),
                "ranked_solutions": ranked
            }

        except ValueError:
            raise
        except Exception as e:
            raise RuntimeError(f"Shortlisting failed: {e}")

    # ── Semantic Search ─────────────────────────────────────

    def semantic_search(self, query: str, problem_id: int = None, top_k: int = 10) -> list:
        """
        Cross-document semantic search using sentence-transformer embeddings + ChromaDB.

        Args:
            query: Natural language search query.
            problem_id: Optional — scope search to a specific problem.
            top_k: Maximum number of results.

        Returns:
            List of matching chunks with similarity scores.
        """
        if not query or not query.strip():
            return []

        self._ensure_init()

        try:
            from rag_indexer import search_solutions
            return search_solutions(
                problem_id=problem_id,
                query=query,
                top_k=top_k
            )
        except Exception as e:
            print(f"[RAG Adapter] Semantic search error: {e}")
            return []
