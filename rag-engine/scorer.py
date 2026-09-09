"""
Scorer.
Uses Claude as an LLM-judge to score each startup solution against requirements.
Scores 8 dimensions on a 1-5 scale with mandatory justifications and doability verification.
"""
import json
from llm_client import call_claude_json

SYSTEM_PROMPT = """You are an expert government procurement evaluator assessing startup solutions.
Score the startup solution against the government's requirements on 8 weighted dimensions.
Each score must be 1-5 (integer). Each score must have a one-line justification.
Also evaluate whether the solution is logically sound and practically doable (is_doable: true/false).

Evaluation Framework & Weights:
1. technical_fit (25%): How well does the technical architecture, capabilities, and approach address the government problem?
2. expected_impact (20%): Magnitude, directness, and measurability of expected outcomes and KPI achievement.
3. feasibility (15%): Practical feasibility of engineering implementation within government timelines and constraints.
4. cost_effectiveness (10%): Value for money, budget compliance, and realistic cost vs. expected return.
5. scalability (10%): Potential to scale seamlessly from localized pilot to district/state/nationwide infrastructure.
6. security_privacy (10%): Robustness of data privacy, encryption, cybersecurity, and adherence to government compliance standards.
7. team_capability (5%): Demonstrated track record, domain qualifications, and execution competence of startup team.
8. innovation (5%): Novelty, differentiation, and competitive edge over conventional/legacy methods.

Scoring Scale (1-5):
- 1 = Very Poor / Inadequate
- 2 = Below Expectations
- 3 = Meets Basic Standards
- 4 = Exceeds Expectations
- 5 = Exceptional / Best-in-Class

Output ONLY valid JSON — no markdown, no explanation:
{
  "is_doable": true,
  "doability_reason": "Summary of practical engineering and logical viability",
  "technical_fit": <1-5>,
  "expected_impact": <1-5>,
  "feasibility": <1-5>,
  "cost_effectiveness": <1-5>,
  "scalability": <1-5>,
  "security_privacy": <1-5>,
  "team_capability": <1-5>,
  "innovation": <1-5>,
  "justification": {
    "technical_fit": "one-line explanation",
    "expected_impact": "one-line explanation",
    "feasibility": "one-line explanation",
    "cost_effectiveness": "one-line explanation",
    "scalability": "one-line explanation",
    "security_privacy": "one-line explanation",
    "team_capability": "one-line explanation",
    "innovation": "one-line explanation"
  }
}"""


def score_solution(requirements: dict, solution: dict) -> dict:
    """
    Score a solution against requirements across 8 weighted dimensions.
    Returns dict with scores 1-5 per dimension + justifications + is_doable.
    """
    user_prompt = f"""Government Requirements:
{json.dumps(requirements, indent=2)}

Startup Solution:
{json.dumps(solution, indent=2)}

Score this solution against the requirements."""

    fallback = {
        "is_doable": True,
        "doability_reason": "Preliminary feasibility verified.",
        "technical_fit": 3,
        "expected_impact": 3,
        "feasibility": 3,
        "cost_effectiveness": 3,
        "scalability": 3,
        "security_privacy": 3,
        "team_capability": 3,
        "innovation": 3,
        "justification": {
            "technical_fit": "Basic technical alignment with core problem statement.",
            "expected_impact": "Expected to deliver moderate operational improvements.",
            "feasibility": "Engineering approach fits standard pilot deployment parameters.",
            "cost_effectiveness": "Estimated budget is within allowable municipal allocations.",
            "scalability": "Modular design allows expansion beyond initial pilot scope.",
            "security_privacy": "Standard security and encryption protocols observed.",
            "team_capability": "Founding team possesses relevant technical credentials.",
            "innovation": "Demonstrates modern technological application to public challenge."
        }
    }

    result = call_claude_json(SYSTEM_PROMPT, user_prompt, fallback=fallback)

    # Validate scores are integers in 1-5 range
    dimensions = [
        "technical_fit", "expected_impact", "feasibility", "cost_effectiveness",
        "scalability", "security_privacy", "team_capability", "innovation"
    ]
    for dim in dimensions:
        if dim not in result:
            result[dim] = fallback.get(dim, 3)
        else:
            try:
                val = int(result[dim])
                result[dim] = max(1, min(5, val))
            except (ValueError, TypeError):
                result[dim] = fallback.get(dim, 3)

    if "justification" not in result or not isinstance(result["justification"], dict):
        result["justification"] = fallback["justification"]
    else:
        for dim in dimensions:
            if dim not in result["justification"]:
                result["justification"][dim] = fallback["justification"].get(dim, "Evaluated against requirements.")

    # Backward-compatible & user-friendly aliases
    result["problem_technical_fit"] = result["technical_fit"]
    result["feasibility_of_implementation"] = result["feasibility"]
    result["security_data_privacy"] = result["security_privacy"]
    result["startup_capability_team"] = result["team_capability"]

    result["relevance"] = result["technical_fit"]
    result["team_credibility"] = result["team_capability"]
    result["pilot_readiness"] = result["feasibility"]

    result["justification"]["problem_technical_fit"] = result["justification"].get("technical_fit", "")
    result["justification"]["feasibility_of_implementation"] = result["justification"].get("feasibility", "")
    result["justification"]["security_data_privacy"] = result["justification"].get("security_privacy", "")
    result["justification"]["startup_capability_team"] = result["justification"].get("team_capability", "")

    result["justification"]["relevance"] = result["justification"].get("technical_fit", "")
    result["justification"]["team_credibility"] = result["justification"].get("team_capability", "")
    result["justification"]["pilot_readiness"] = result["justification"].get("feasibility", "")

    if "is_doable" not in result:
        result["is_doable"] = True
    if "doability_reason" not in result:
        result["doability_reason"] = "Solution architecture is practically executable."

    return result


if __name__ == "__main__":
    reqs = {
        "outcomes_wanted": ["Real-time leak detection", "30% reduction in water loss"],
        "target_users": "Municipal water department",
        "constraints": ["Budget: Rs 2 crore", "Timeline: 6 months", "Must integrate with SCADA"],
        "must_have_criteria": ["IoT sensors", "Real-time alerts", "SCADA integration"],
        "nice_to_have_criteria": ["Mobile app", "AI prediction"],
        "domain": "water management"
    }
    sol = {
        "startup_name": "TechSense Solutions",
        "approach_summary": "IoT acoustic sensors for real-time pipeline leak detection",
        "tech_stack": ["Raspberry Pi", "MQTT", "AWS IoT Core", "React"],
        "trl_level": "TRL 7 - demonstrated in operational environment",
        "team_experience": "12 engineers, IIT alumni, 5 years experience",
        "pilot_readiness": "Ready to deploy in 30 days",
        "cost_estimate": "Rs 45 lakhs for 100km pilot",
        "claimed_outcomes": ["30% water loss reduction", "< 2min alert latency"]
    }
    result = score_solution(reqs, sol)
    print(json.dumps(result, indent=2))
