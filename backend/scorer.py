from form_type import required_app_form_fields

_GOV_ID_FIELDS = [
    "id_type",
    "id_number",
    "full_name",
    "date_of_birth",
]

_POLICY_ILLUSTRATION_FIELDS = [
    "plan_name",
    "sum_assured",
    "annual_premium",
    "applicant_name",
    "insured_age",
    "insured_gender",
    "death_benefit",
]

WEIGHTS = {
    "application_form": 0.5,
    "government_id": 0.3,
    "policy_illustration": 0.2,
}

CRITICAL_PENALTY = 15
WARNING_PENALTY = 5


def _required_fields(product_type: str) -> dict:
    return {
        "application_form": required_app_form_fields(product_type),
        "government_id": _GOV_ID_FIELDS,
        "policy_illustration": _POLICY_ILLUSTRATION_FIELDS,
    }


def score_completeness(extractions: dict, product_type: str = "UNKNOWN") -> dict:
    """
    Score completeness for each document individually, using only the fields
    that are actually required for the identified product type.

    Returns:
        Dict keyed by doc_type with {"score": int, "missing": [str]}
    """
    required = _required_fields(product_type)
    results = {}
    for doc_type, fields in required.items():
        doc_data = extractions.get(doc_type) or {}
        missing = [f for f in fields if not doc_data.get(f)]
        present = len(fields) - len(missing)
        score = round((present / len(fields)) * 100) if fields else 100
        results[doc_type] = {"score": score, "missing": missing}
    return results


def score_case(completeness: dict, validations: list[dict]) -> tuple[int, str]:
    """
    Compute overall case score with validation penalties.

    Returns:
        (case_score: int, case_status: str)
    """
    weighted = sum(
        completeness[doc]["score"] * WEIGHTS[doc]
        for doc in WEIGHTS
        if doc in completeness
    )
    base_score = round(weighted)

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
