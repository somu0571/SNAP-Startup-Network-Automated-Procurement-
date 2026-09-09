"""
Ranker.
Computes final weighted score from dimension scores, applies consistency flag penalties,
sorts descending, and returns top N solutions.
"""
from config import SCORING_WEIGHTS, CONSISTENCY_FLAG_PENALTY, TOP_N_SHORTLIST


def compute_final_score(scores: dict, consistency_flags: list, is_doable: bool = True) -> float:
    """
    Compute weighted final score across 8 evaluation dimensions:
    1. technical_fit (25%)
    2. expected_impact (20%)
    3. feasibility (15%)
    4. cost_effectiveness (10%)
    5. scalability (10%)
    6. security_privacy (10%)
    7. team_capability (5%)
    8. innovation (5%)
    Total: 100%
    """
    dimensions = [
        "technical_fit", "expected_impact", "feasibility", "cost_effectiveness",
        "scalability", "security_privacy", "team_capability", "innovation"
    ]

    raw_score = 0.0
    total_weight = 0.0

    for dim in dimensions:
        weight = SCORING_WEIGHTS.get(dim, 0.0)
        score = scores.get(dim)
        if score is None:
            # Fallback to legacy names
            if dim == "technical_fit":
                score = scores.get("relevance", 1)
            elif dim == "team_capability":
                score = scores.get("team_credibility", 1)
            elif dim == "expected_impact":
                score = scores.get("relevance", 1)
            elif dim == "cost_effectiveness":
                score = scores.get("feasibility", 1)
            elif dim == "scalability":
                score = scores.get("feasibility", 1)
            elif dim == "security_privacy":
                score = 3
            else:
                score = 1
        raw_score += weight * score
        total_weight += weight

    # Normalize to 0-10 scale (raw is 1-5 weighted avg)
    if total_weight > 0:
        weighted_avg = raw_score / total_weight  # 1.0 - 5.0
        normalized = (weighted_avg - 1) / 4 * 10  # 0 - 10
    else:
        normalized = 0.0

    # Penalty per consistency flag
    penalty = len(consistency_flags) * CONSISTENCY_FLAG_PENALTY
    final = max(0.0, normalized - penalty)

    # If marked as logically impossible / not doable
    if not is_doable:
        final = max(0.0, final - 3.0)

    return round(final, 2)


def rank_solutions(scored_solutions: list[dict], top_n: int = TOP_N_SHORTLIST) -> list[dict]:
    """
    Rank a list of scored solutions across 8 dimensions.
    """
    ranked = []

    for item in scored_solutions:
        scores = {
            "technical_fit": item.get("technical_fit", item.get("relevance", 1)),
            "expected_impact": item.get("expected_impact", item.get("relevance", 1)),
            "feasibility": item.get("feasibility", 1),
            "cost_effectiveness": item.get("cost_effectiveness", item.get("feasibility", 1)),
            "scalability": item.get("scalability", 3),
            "security_privacy": item.get("security_privacy", 3),
            "team_capability": item.get("team_capability", item.get("team_credibility", 1)),
            "innovation": item.get("innovation", 1),
            # Synonyms & aliases
            "problem_technical_fit": item.get("technical_fit", item.get("relevance", 1)),
            "feasibility_of_implementation": item.get("feasibility", 1),
            "security_data_privacy": item.get("security_privacy", 3),
            "startup_capability_team": item.get("team_capability", item.get("team_credibility", 1)),
            # Legacy aliases
            "relevance": item.get("technical_fit", item.get("relevance", 1)),
            "team_credibility": item.get("team_capability", item.get("team_credibility", 1)),
            "pilot_readiness": item.get("feasibility", 1),
        }

        import json
        flags_raw = item.get("consistency_flags", "[]")
        if isinstance(flags_raw, str):
            try:
                flags = json.loads(flags_raw)
            except Exception:
                flags = []
        else:
            flags = flags_raw or []

        is_doable = item.get("is_doable", True)
        final_score = compute_final_score(scores, flags, is_doable=is_doable)

        jus_raw = item.get("justification_json", "{}")
        if isinstance(jus_raw, str):
            try:
                justification = json.loads(jus_raw)
            except Exception:
                justification = {}
        else:
            justification = jus_raw or {}

        # Ensure justifications mirror alias keys
        if "technical_fit" in justification and "problem_technical_fit" not in justification:
            justification["problem_technical_fit"] = justification["technical_fit"]
        if "feasibility" in justification and "feasibility_of_implementation" not in justification:
            justification["feasibility_of_implementation"] = justification["feasibility"]
        if "security_privacy" in justification and "security_data_privacy" not in justification:
            justification["security_data_privacy"] = justification["security_privacy"]
        if "team_capability" in justification and "startup_capability_team" not in justification:
            justification["startup_capability_team"] = justification["team_capability"]

        ranked.append({
            "solution_id": item.get("solution_id") or item.get("id"),
            "rank": 0,  # filled after sort
            "startup_name": item.get("startup_name", "Unknown"),
            "filename": item.get("filename", ""),
            "final_score": final_score,
            "scores": scores,
            "justification": justification,
            "is_doable": is_doable,
            "doability_reason": item.get("doability_reason", "Logical and technical feasibility verified."),
            "consistency_flags": flags,
            "flag_count": len(flags),
            "penalty_applied": len(flags) * CONSISTENCY_FLAG_PENALTY,
        })

    # Sort descending
    ranked.sort(key=lambda x: x["final_score"], reverse=True)

    # Assign ranks
    for i, item in enumerate(ranked):
        item["rank"] = i + 1

    return ranked[:top_n]


if __name__ == "__main__":
    import json

    sample_solutions = [
        {
            "solution_id": 1,
            "startup_name": "TechSense Solutions",
            "filename": "techsense.pdf",
            "relevance": 5, "feasibility": 4, "innovation": 4,
            "team_credibility": 4, "pilot_readiness": 5,
            "justification_json": json.dumps({
                "relevance": "Directly addresses pipeline leak detection",
                "feasibility": "Realistic cost and timeline",
                "innovation": "Novel acoustic sensor approach",
                "team_credibility": "Experienced IIT alumni team",
                "pilot_readiness": "Ready to deploy in 30 days"
            }),
            "consistency_flags": "[]"
        },
        {
            "solution_id": 2,
            "startup_name": "SmartWater AI",
            "filename": "smartwater.pdf",
            "relevance": 4, "feasibility": 3, "innovation": 5,
            "team_credibility": 3, "pilot_readiness": 3,
            "justification_json": json.dumps({
                "relevance": "Addresses leak detection with AI",
                "feasibility": "Cost is slightly high",
                "innovation": "Cutting-edge ML approach",
                "team_credibility": "Small team, limited track record",
                "pilot_readiness": "Needs 2 months setup"
            }),
            "consistency_flags": json.dumps(["TRL claims deployed but only prototype exists"])
        },
    ]

    results = rank_solutions(sample_solutions, top_n=10)
    for r in results:
        print(f"#{r['rank']} {r['startup_name']}: {r['final_score']}/10 "
              f"(flags: {r['flag_count']}, penalty: -{r['penalty_applied']})")
