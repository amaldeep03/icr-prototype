REQUIRED_FIELDS = {
    # Based on Allianz PNB Life SIO Application Form
    "application_form": [
        "full_name",
        "date_of_birth",
        "gender",
        "civil_status",
        "address",
        "phone",
        "email",
        "nominee_name",
        "nominee_relationship",
        "sum_assured",
        "plan_name",
        "payment_frequency",
    ],
    "government_id": [
        "id_type",
        "id_number",
        "full_name",
        "date_of_birth",
    ],
    # Based on Allianz eAZy Health Sales Illustration
    "policy_illustration": [
        "plan_name",
        "sum_assured",
        "annual_premium",
        "applicant_name",
        "death_benefit",
    ],
}

WEIGHTS = {
    "application_form": 0.5,
    "government_id": 0.3,
    "policy_illustration": 0.2,
}

CRITICAL_PENALTY = 15
WARNING_PENALTY = 5


def score_completeness(extractions: dict) -> dict:
    """
    Score completeness for each document individually.

    Returns:
        Dict keyed by doc_type with {"score": int, "missing": [str]}
    """
    results = {}
    for doc_type, required in REQUIRED_FIELDS.items():
        doc_data = extractions.get(doc_type) or {}
        missing = [f for f in required if not doc_data.get(f)]
        present = len(required) - len(missing)
        score = round((present / len(required)) * 100) if required else 100
        results[doc_type] = {"score": score, "missing": missing}
    return results


def score_case(completeness: dict, validations: list[dict]) -> tuple[int, str]:
    """
    Compute overall case score with validation penalties.

    Returns:
        (case_score: int, case_status: str)
    """
    # Weighted completeness baseline
    weighted = sum(
        completeness[doc]["score"] * WEIGHTS[doc]
        for doc in WEIGHTS
        if doc in completeness
    )
    base_score = round(weighted)

    # Apply penalties
    # "fail"       → full penalty for the severity tier
    # "unverified" on a critical check → half penalty (can't confirm, not a proven mismatch)
    penalties = 0
    for v in validations:
        if v["status"] == "fail":
            if v["severity"] == "critical":
                penalties += CRITICAL_PENALTY
            elif v["severity"] == "warning":
                penalties += WARNING_PENALTY
        elif v["status"] == "unverified" and v["severity"] == "critical":
            penalties += CRITICAL_PENALTY // 2

    final = max(0, min(100, base_score - penalties))

    if final >= 85:
        status = "Ready for Review"
    elif final >= 60:
        status = "Needs Attention"
    else:
        status = "Incomplete / Refer Back"

    return final, status
