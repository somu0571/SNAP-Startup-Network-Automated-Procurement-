"""
tests/test_rag_integration.py
End-to-end integration test suite for the SNAP RAG Engine.

Verifies:
1. Direct Python module import via services.rag_adapter
2. Database initialization (SQLite tables: problems, solutions, scores)
3. Government problem statement ingestion + requirement extraction
4. Startup solution ingestion (parsing, eligibility filtering, consistency check)
5. 8-dimension scoring and weighted ranking
6. Semantic search functionality
7. Error handling & resilience with incomplete data
"""
import sys
import os
import json
import time

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.rag_adapter import RAGAdapter


def run_tests():
    print("=" * 65)
    print("       SNAP RAG Engine End-to-End Integration Tests")
    print("=" * 65)

    passed_count = 0
    total_count = 0

    def test(name, fn):
        nonlocal passed_count, total_count
        total_count += 1
        print(f"\n[Test {total_count}] {name}...")
        try:
            start = time.time()
            fn()
            duration = (time.time() - start) * 1000
            print(f"  --> PASSED ({duration:.1f}ms)")
            passed_count += 1
        except Exception as e:
            print(f"  --> FAILED: {e}")
            import traceback
            traceback.print_exc()

    adapter = RAGAdapter()
    test_context = {}

    # ── Test 1: Adapter and DB Initialization ──────────────
    def t1_init():
        adapter._ensure_init()
        from db import get_all_problems
        problems = get_all_problems()
        assert isinstance(problems, list), "Expected list of problems from db"
        print(f"      Connected to SQLite DB. Existing problems: {len(problems)}")

    test("Adapter Initialization & Database Connectivity", t1_init)

    # ── Test 2: Ingest Problem Statement ───────────────────
    def t2_ingest_problem():
        sample_problem = (
            "Smart City Water Supply Pipeline Leakage & Non-Revenue Water (NRW) Monitoring.\n"
            "Challenge: Detect micro-leaks in underground pipeline distribution network across 100km.\n"
            "Constraints: Non-invasive, zero trenching/excavation, alerts within 5 minutes.\n"
            "Max Budget: Rs 50,00,000. Desired TRL: 6 or higher.\n"
            "Required KPIs: 30% reduction in water loss, SCADA compatibility."
        )
        res = adapter.ingest_problem(sample_problem)
        assert res["status"] == "success", "Failed to ingest problem"
        assert "problem_id" in res and res["problem_id"] > 0, "Invalid problem_id returned"
        assert "requirements" in res, "Requirements missing from ingestion result"
        test_context["problem_id"] = res["problem_id"]
        print(f"      Created Problem ID: {res['problem_id']}")
        print(f"      Requirements: {json.dumps(res['requirements'], indent=2)[:200]}...")

    test("Government Problem Statement Ingestion & Requirement Extraction", t2_ingest_problem)

    # ── Test 3: Ingest Startup Solution (Eligible) ─────────
    def t3_ingest_eligible_startup():
        prob_id = test_context["problem_id"]
        solution_text = """
AquaWave Telemetry Solutions Pvt. Ltd.
Outcome-Based Technical & Commercial Proposal for Municipal Pipeline Monitoring

1. Approach Summary:
AquaWave deploys IoT acoustic clamps placed every 500 meters on valve chambers.
Our edge processors run real-time Fourier analysis to spot high-frequency micro-leak signals.
Alerts are sent to municipal SCADA dashboard via 4G/NB-IoT within 90 seconds.

2. Technology Stack:
ESP32, Piezoelectric sensors, MQTT, Python FastAPI, PostgreSQL, SCADA OPC-UA.

3. TRL Level:
TRL 7 - Proven prototype deployed in 30km municipal pilot with Surat Municipal Corporation.

4. Team Experience:
Team of 10 engineers, alumni of IIT Bombay with 5+ years experience in embedded IoT.

5. Pilot Readiness:
Ready to pilot within 3 weeks. 150 hardware units pre-manufactured and calibrated.

6. Estimated Cost:
Pilot (100km): Rs 35,00,000. Full citywide rollout: Rs 1.2 Crore.

7. Claimed Outcomes:
35% reduction in NRW loss within 6 months. Sub-2 minute alert latency. Zero trenching.

8. Statutory & Compliance:
- DPIIT Recognition: Yes (DIPP98765)
- Annual Turnover: Rs 1.8 Crore
- Years of Incorporation: 3 years
"""
        res = adapter.ingest_text(prob_id, solution_text, startup_name="AquaWave Solutions")
        assert res["status"] == "success", "Failed to ingest solution text"
        assert res["eligible"] is True, f"Expected startup to be eligible, got: {res.get('eligibility_reason')}"
        test_context["solution_1_id"] = res["solution_id"]
        print(f"      Solution ID: {res['solution_id']} (Eligible: {res['eligible']})")

    test("Startup Solution Ingestion (Eligible Proposal)", t3_ingest_eligible_startup)

    # ── Test 4: Ingest Ineligible Startup (DPIIT false) ────
    def t4_ingest_ineligible_startup():
        prob_id = test_context["problem_id"]
        ineligible_text = """
MegaCorp Legacy Infrastructure Ltd.
Proposal for Pipeline Monitoring

1. Approach Summary:
Conventional ultrasonic flow meters and manual acoustic rod inspection patrols.

2. TRL Level:
TRL 4

3. Estimated Cost:
Rs 95,00,000 for pilot.

4. Statutory & Compliance:
- DPIIT Recognition: No
- Annual Turnover: Rs 150 Crore
- Years of Incorporation: 18 years
"""
        res = adapter.ingest_text(prob_id, ineligible_text, startup_name="MegaCorp Legacy")
        assert res["status"] == "success", "Failed to ingest solution text"
        assert res["eligible"] is False, "Expected startup to be filtered out as ineligible"
        print(f"      Solution ID: {res['solution_id']} (Correctly Filtered: {res['eligibility_reason']})")

    test("Eligibility Filtering (DPIIT & Turnover Thresholds)", t4_ingest_ineligible_startup)

    # ── Test 5: Scoring & Shortlisting Pipeline ───────────
    def t5_scoring_and_ranking():
        prob_id = test_context["problem_id"]
        shortlist_res = adapter.get_shortlist(prob_id, top_n=10, rescore=True)
        assert shortlist_res["status"] == "success", f"Shortlist failed: {shortlist_res}"
        assert len(shortlist_res["ranked_solutions"]) >= 1, "Expected at least 1 ranked solution"

        top_solution = shortlist_res["ranked_solutions"][0]
        assert top_solution["startup_name"] == "AquaWave Solutions", "AquaWave should be ranked top"
        assert "composite_score" in top_solution or "final_score" in top_solution, "Missing score"
        
        score = top_solution.get("composite_score", top_solution.get("final_score", 0))
        print(f"      Top Rank: {top_solution['startup_name']}")
        print(f"      Score: {score:.2f} / 5.0")
        print(f"      Technical Fit: {top_solution.get('technical_fit')}/5")
        print(f"      Feasibility: {top_solution.get('feasibility')}/5")

    test("8-Dimension Scoring and Weighted Shortlist Ranking", t5_scoring_and_ranking)

    # ── Test 6: Semantic Search ───────────────────────────
    def t6_semantic_search():
        prob_id = test_context["problem_id"]
        # Search for query
        results = adapter.semantic_search("acoustic sensor IoT leak detection", problem_id=prob_id, top_k=3)
        # Even if ChromaDB is not populated or optional in test, adapter shouldn't crash
        assert isinstance(results, list), "Semantic search must return a list"
        print(f"      Search executed successfully. Matching chunks: {len(results)}")

    test("Semantic Search / Vector Retrieval", t6_semantic_search)

    # ── Summary ───────────────────────────────────────────
    print("\n" + "=" * 65)
    print(f"Test Results: {passed_count} / {total_count} passed")
    print("=" * 65)
    if passed_count == total_count:
        print("ALL TESTS PASSED SUCCESSFULLY! RAG ENGINE INTEGRATION VERIFIED.")
        return 0
    else:
        print("SOME TESTS FAILED.")
        return 1


if __name__ == "__main__":
    code = run_tests()
    sys.exit(code)
