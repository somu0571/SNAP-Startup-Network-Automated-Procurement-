"""
Consistency Checker.
Uses Claude to detect internal contradictions within a solution JSON.
Returns a list of flag strings, never a hard reject.
"""
from llm_client import call_claude_json

SYSTEM_PROMPT = """You are a technical reviewer checking a startup's solution document for internal contradictions.
Given a structured JSON of a startup solution, identify any logical inconsistencies or contradictions.
Output ONLY valid JSON matching this schema — no markdown, no explanation:
{
  "flags": [
    "one-line description of each contradiction found"
  ]
}
If no contradictions found, return: {"flags": []}

Examples of flags to look for:
- TRL claims 'deployed at scale' but approach describes only a prototype
- Cost estimate is very low but team size and complexity suggest much higher cost
- Claims 6-month delivery but pilot_readiness says 'not ready'
- Tech stack mentions AI/ML but team has no ML experience
- Claims DPIIT registered but turnover exceeds Rs 100 crore (disqualifies startup status)
"""


def check_consistency(solution_json: dict) -> list[str]:
    """
    Check solution JSON for internal contradictions.
    Returns list of flag strings (empty list = no issues).
    """
    import json

    user_prompt = f"""Review this startup solution JSON for internal contradictions:
---
{json.dumps(solution_json, indent=2)}
---
Return flags as JSON."""

    fallback = {"flags": []}
    result = call_claude_json(SYSTEM_PROMPT, user_prompt, fallback=fallback)

    flags = result.get("flags", [])
    if not isinstance(flags, list):
        flags = []

    return flags


if __name__ == "__main__":
    import json
    sample = {
        "startup_name": "TechSense Solutions",
        "approach_summary": "We will build a prototype IoT system over 12 months",
        "trl_level": "TRL 9 - fully deployed and scaled across 50 cities",
        "team_experience": "2 interns, 6 months experience",
        "pilot_readiness": "Not ready, need funding first",
        "cost_estimate": "Rs 10,000 only",
        "claimed_outcomes": ["Replace all manual inspections globally in 3 months"],
        "dpiit_registered": "yes",
        "annual_turnover": "Rs 500 crore"
    }
    flags = check_consistency(sample)
    print("Flags found:")
    for f in flags:
        print(f"  - {f}")
