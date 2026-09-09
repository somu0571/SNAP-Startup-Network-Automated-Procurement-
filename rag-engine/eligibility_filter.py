"""
Eligibility Filter.
Pure rule-based Python — no LLM calls, runs first to save API cost.
Input: solution JSON + eligibility rules
Output: (pass: bool, reason: str)
"""
from config import DEFAULT_ELIGIBILITY_RULES


def check_eligibility(solution_json: dict, rules: dict = None) -> tuple[bool, str]:
    """
    Check if a startup solution passes eligibility criteria.
    Returns (eligible: bool, reason: str).
    """
    if rules is None:
        rules = DEFAULT_ELIGIBILITY_RULES

    reasons = []

    # ── DPIIT Registration Check ─────────────────────────
    if rules.get("dpiit_required", True):
        dpiit = solution_json.get("dpiit_registered", "not_mentioned").lower()
        if dpiit == "no":
            return False, "DPIIT registration required but startup is not DPIIT registered."
        elif dpiit == "not_mentioned":
            reasons.append("DPIIT registration status not mentioned (flagged, not rejected)")

    # ── Annual Turnover Check ────────────────────────────
    max_turnover = rules.get("max_turnover_cr", None)
    if max_turnover is not None:
        turnover_str = solution_json.get("annual_turnover", "not_mentioned")
        if turnover_str not in ("not_mentioned", "", "N/A"):
            turnover_val = _parse_turnover_crores(turnover_str)
            if turnover_val is not None and turnover_val > max_turnover:
                return False, (
                    f"Annual turnover Rs {turnover_val} Cr exceeds cap of Rs {max_turnover} Cr. "
                    "This startup does not qualify as a startup under DPIIT norms."
                )

    # ── Sector Match Check ───────────────────────────────
    allowed_sectors = rules.get("allowed_sectors", [])
    if allowed_sectors:
        # This is a soft check since sector isn't reliably extracted
        # In a real scenario you'd cross-check with startup's declared sector
        pass

    if reasons:
        return True, "Eligible with flags: " + "; ".join(reasons)

    return True, "All eligibility criteria met."


def _parse_turnover_crores(turnover_str: str) -> float | None:
    """
    Try to parse a turnover string like 'Rs 3.2 crore', '₹50 lakh', '2.5 Cr' into crores.
    Returns None if unparseable.
    """
    import re
    s = turnover_str.lower().replace(",", "").replace("rs", "").replace("₹", "").strip()

    # Find numeric value
    match = re.search(r"(\d+(\.\d+)?)", s)
    if not match:
        return None

    value = float(match.group(1))

    # Convert units to crores
    if "lakh" in s or "lac" in s:
        value = value / 100.0
    elif "crore" in s or " cr" in s:
        pass  # already in crores
    elif "million" in s:
        value = value / 10.0  # 1 million ≈ 0.1 crore
    elif "k" in s or "thousand" in s:
        value = value / 10000.0
    elif value > 1000:
        # Raw INR without denomination (e.g. 50000 -> 0.005 Cr)
        value = value / 10000000.0

    return value


if __name__ == "__main__":
    sol = {
        "startup_name": "TechSense Solutions",
        "dpiit_registered": "yes",
        "annual_turnover": "Rs 3.2 crore",
    }
    eligible, reason = check_eligibility(sol)
    print(f"Eligible: {eligible} | Reason: {reason}")

    sol2 = {
        "startup_name": "BigCorp Ltd",
        "dpiit_registered": "no",
        "annual_turnover": "Rs 500 crore",
    }
    eligible2, reason2 = check_eligibility(sol2)
    print(f"Eligible: {eligible2} | Reason: {reason2}")
