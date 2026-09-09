"""
Solution Extractor.
Input: raw text of a startup solution document
Output: structured JSON with approach, tech stack, TRL, team, cost, etc.
"""
from llm_client import call_claude_json

SYSTEM_PROMPT = """You are a startup solution analyst for government procurement.
Extract structured information from a startup's solution document.
Output ONLY valid JSON matching this exact schema — no markdown, no explanation:
{
  "startup_name": "name of the startup if mentioned, else 'Unknown'",
  "approach_summary": "2-3 sentence summary of the proposed solution approach",
  "tech_stack": ["list of technologies, tools, platforms used"],
  "trl_level": "Technology Readiness Level as stated or inferred (TRL 1-9 or description like 'prototype', 'deployed', 'pilot-ready')",
  "team_experience": "summary of team background, years of experience, past projects",
  "pilot_readiness": "description of how ready the startup is to begin a pilot (timeline, resources needed)",
  "cost_estimate": "estimated cost for pilot or full deployment as stated in doc",
  "claimed_outcomes": ["list of outcomes/impact the startup claims their solution will achieve"],
  "dpiit_registered": "yes/no/not_mentioned",
  "annual_turnover": "stated turnover or 'not_mentioned'",
  "deployment_geography": "where solution has been deployed or 'not_mentioned'"
}"""


def extract_solution(doc_text: str) -> dict:
    """
    Parse startup solution document into structured JSON.
    For short docs, passes full text. Returns fallback on error.
    """
    # Truncate very long docs to fit context window (~100k chars = ~25k tokens)
    max_chars = 80000
    if len(doc_text) > max_chars:
        doc_text = doc_text[:max_chars] + "\n[...document truncated for extraction...]"

    user_prompt = f"""Startup Solution Document:
---
{doc_text}
---
Extract solution details as JSON."""

    fallback = {
        "startup_name": "Unknown",
        "approach_summary": "Could not extract approach",
        "tech_stack": [],
        "trl_level": "not_mentioned",
        "team_experience": "not_mentioned",
        "pilot_readiness": "not_mentioned",
        "cost_estimate": "not_mentioned",
        "claimed_outcomes": [],
        "dpiit_registered": "not_mentioned",
        "annual_turnover": "not_mentioned",
        "deployment_geography": "not_mentioned"
    }

    result = call_claude_json(SYSTEM_PROMPT, user_prompt, fallback=fallback)

    # Ensure all keys present
    for key in fallback:
        if key not in result:
            result[key] = fallback[key]

    return result


if __name__ == "__main__":
    import json
    sample = """
    TechSense Solutions Pvt. Ltd. — Smart Pipeline Monitoring System
    
    Our IoT-based leak detection system uses acoustic sensors installed on pipelines to detect
    vibration patterns indicative of leaks in real time. The data is processed on edge devices
    and streamed to our cloud dashboard with <2 minute alert latency.
    
    Technology: Raspberry Pi edge nodes, MQTT protocol, AWS IoT Core, React dashboard.
    TRL Level: 7 - demonstrated in real operational environment (Pune Municipal Corporation pilot, 2023).
    Team: 12 engineers, 5 years average experience. IIT Bombay alumni.
    Cost: Rs 45 lakhs for 100km pipeline pilot. Full deployment Rs 1.8 crore.
    DPIIT Registered: Yes (Certificate No. DIPP12345)
    Annual Turnover: Rs 3.2 crore (FY 2023-24)
    Expected outcomes: 30% reduction in water loss, real-time leak alerts, integration with SCADA.
    """
    result = extract_solution(sample)
    print(json.dumps(result, indent=2))
