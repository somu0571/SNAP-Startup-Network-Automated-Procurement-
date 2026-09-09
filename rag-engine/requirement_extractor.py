"""
Requirement Extractor.
Input: raw text of a government problem statement
Output: structured JSON with outcomes, constraints, and criteria
"""
from llm_client import call_claude_json

SYSTEM_PROMPT = """You are a senior government procurement analyst and technical architect.
Read the in-depth government operational problem statement and extract structured requirements.
Define explicit parameters and evaluation criteria across the 8-dimension procurement framework:
- Problem/Technical Fit (25%)
- Expected Impact (20%)
- Feasibility of Implementation (15%)
- Cost Effectiveness (10%)
- Scalability (10%)
- Security & Data Privacy (10%)
- Startup Capability / Team (5%)
- Innovation (5%)

Output ONLY valid JSON matching this exact schema — no markdown, no explanation:
{
  "domain": "sector/domain (e.g. municipal water, healthcare, traffic, border security)",
  "problem_severity": "low/medium/high",
  "target_users": "primary government beneficiaries and ground operators",
  "evaluation_rubric": {
    "technical_fit_criteria": ["specific technical capabilities and specs solution must fulfill (25%)"],
    "expected_impact_metrics": ["quantifiable KPI improvements and targets (20%)"],
    "feasibility_constraints": ["implementation timeline, engineering prerequisites, site dependencies (15%)"],
    "cost_budget_thresholds": ["pilot budget limit, cost per unit, financial constraints (10%)"],
    "scalability_parameters": ["expansion readiness from pilot to city/state/national coverage (10%)"],
    "security_privacy_requirements": ["data telemetry encryption, privacy compliance, SCADA/on-prem needs (10%)"],
    "team_competency_needs": ["required engineering expertise, credentials, past pilot experience (5%)"],
    "innovation_expectations": ["preferred novel technologies replacing conventional legacy methods (5%)"]
  },
  "outcomes_wanted": ["list of desired operational outcomes"],
  "constraints": ["budget, timeline, regulatory constraints"],
  "must_have_criteria": ["mandatory technical capabilities"],
  "nice_to_have_criteria": ["optional value-add features"]
}"""


def extract_requirements(problem_text: str) -> dict:
    """
    Parse in-depth government problem statement into structured requirements and evaluation parameters.
    Returns structured dict with 8-dimension evaluation rubric.
    """
    user_prompt = f"""Government Problem Statement:
---
{problem_text}
---
Extract structured requirements and define evaluation parameters across the 8 dimensions as JSON."""

    fallback = {
        "domain": "Smart Governance & Public Infrastructure",
        "problem_severity": "medium",
        "target_users": "Government officials and field operations teams",
        "evaluation_rubric": {
            "technical_fit_criteria": ["Direct capability alignment with core operational challenge"],
            "expected_impact_metrics": ["Measurable efficiency improvement and operational turnaround"],
            "feasibility_constraints": ["Deployable within standard pilot timeline (3-6 months)"],
            "cost_budget_thresholds": ["Within allocated departmental budget allocations"],
            "scalability_parameters": ["Modular architecture capable of multi-location expansion"],
            "security_privacy_requirements": ["Standard data encryption and government privacy compliance"],
            "team_competency_needs": ["Demonstrated technical engineering qualifications"],
            "innovation_expectations": ["Differentiated modern technology over conventional methods"]
        },
        "outcomes_wanted": ["Operational workflow automation with verified KPI benchmarks"],
        "constraints": ["Standard departmental procurement regulations"],
        "must_have_criteria": ["Real-time telemetry and reporting dashboard"],
        "nice_to_have_criteria": ["Predictive AI forecasting and mobile notifications"]
    }

    result = call_claude_json(SYSTEM_PROMPT, user_prompt, fallback=fallback)

    # Ensure all required keys exist
    for key in fallback:
        if key not in result:
            result[key] = fallback[key]

    return result


if __name__ == "__main__":
    # Quick test
    sample = """
    The Municipal Corporation faces difficulty in monitoring 500+ km of water pipelines for 
    leaks in real time. Current manual inspection takes 3 weeks and leaks cause 40% water loss.
    Budget is limited to Rs 2 crore for pilot. Solution must integrate with existing SCADA systems.
    DPIIT-registered startups only. Must be deployable within 6 months.
    """
    import json
    result = extract_requirements(sample)
    print(json.dumps(result, indent=2))
