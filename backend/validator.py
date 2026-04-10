import re
from typing import Any
from rapidfuzz import fuzz, utils as fuzz_utils


def _get_field(extractions: dict, path: str) -> Any:
    """Resolve dot-notation path like 'application_form.full_name' from extractions dict."""
    doc, field = path.split(".", 1)
    return (extractions.get(doc) or {}).get(field)


def _normalize_numeric(value: Any) -> float | None:
    """Strip currency symbols, commas, spaces and convert to float."""
    if value is None:
        return None
    cleaned = re.sub(r"[^\d.]", "", str(value))
    try:
        return float(cleaned)
    except ValueError:
        return None


VALIDATION_RULES = [
    {
        "check": "name_match_form_vs_id",
        "fields": ["application_form.full_name", "government_id.full_name"],
        "method": "fuzzy",
        "threshold": 85,
        "severity": "critical",
        "pass_msg": "Names match across application form and ID",
        "fail_msg": "Name mismatch between application form and government ID",
    },
    {
        "check": "name_match_form_vs_policy",
        "fields": ["application_form.full_name", "policy_illustration.applicant_name"],
        "method": "fuzzy",
        "threshold": 85,
        "severity": "critical",
        "pass_msg": "Names match across application form and policy illustration",
        "fail_msg": "Name mismatch between application form and policy illustration",
    },
    {
        "check": "dob_match_form_vs_id",
        "fields": ["application_form.date_of_birth", "government_id.date_of_birth"],
        "method": "exact",
        "severity": "critical",
        "pass_msg": "Date of birth matches across application form and ID",
        "fail_msg": "Date of birth mismatch between application form and government ID",
    },
    {
        "check": "dob_match_form_vs_policy",
        "fields": ["application_form.date_of_birth", "policy_illustration.applicant_dob"],
        "method": "exact",
        "severity": "critical",
        "pass_msg": "Date of birth matches across application form and policy illustration",
        "fail_msg": "Date of birth mismatch between application form and policy illustration",
    },
    {
        "check": "pincode_match_form_vs_id",
        "fields": ["application_form.pincode", "government_id.pincode"],
        "method": "exact",
        "severity": "warning",
        "pass_msg": "Pincode matches across application form and ID",
        "fail_msg": "Pincode mismatch between application form and government ID",
    },
    {
        "check": "sum_assured_match_form_vs_policy",
        "fields": ["application_form.sum_assured", "policy_illustration.sum_assured"],
        "method": "numeric_tolerance",
        "tolerance": 0.01,
        "severity": "warning",
        "pass_msg": "Sum assured matches across application form and policy illustration",
        "fail_msg": "Sum assured mismatch between application form and policy illustration",
    },
    {
        "check": "plan_name_match",
        "fields": ["application_form.plan_name", "policy_illustration.plan_name"],
        "method": "fuzzy",
        "threshold": 80,
        "severity": "warning",
        "pass_msg": "Plan name matches across application form and policy illustration",
        "fail_msg": "Plan name mismatch between application form and policy illustration",
    },
    {
        "check": "fund_direction_match",
        "fields": ["application_form.fund_direction", "policy_illustration.fund_direction"],
        "method": "fuzzy",
        "threshold": 80,
        "severity": "warning",
        "pass_msg": "Fund direction matches across application form and policy illustration",
        "fail_msg": "Fund direction mismatch between application form and policy illustration",
    },
]


def _run_check(rule: dict, extractions: dict) -> dict:
    field_a_path, field_b_path = rule["fields"]
    val_a = _get_field(extractions, field_a_path)
    val_b = _get_field(extractions, field_b_path)

    label_a = field_a_path.split(".", 1)[0].replace("_", " ").title()
    label_b = field_b_path.split(".", 1)[0].replace("_", " ").title()

    values = {label_a: val_a, label_b: val_b}

    # If either value is missing, mark as "unverified" — severity is preserved
    # so callers can distinguish an unverifiable critical check from a warning one.
    if val_a is None or val_b is None:
        missing_parts = []
        if val_a is None:
            missing_parts.append(f"{field_a_path.replace('.', ' › ')}")
        if val_b is None:
            missing_parts.append(f"{field_b_path.replace('.', ' › ')}")
        missing_str = " and ".join(missing_parts)
        return {
            "check": rule["check"],
            "status": "unverified",
            "values": values,
            "score": None,
            "severity": rule["severity"],
            "message": f"Could not compare — missing: {missing_str}",
        }

    method = rule["method"]

    if method == "exact":
        passed = str(val_a).strip().lower() == str(val_b).strip().lower()
        score = 100 if passed else 0
        status = "pass" if passed else "fail"

    elif method == "fuzzy":
        # Normalize: strip punctuation (commas, dots), lowercase, then sort tokens.
        # This makes "JUAN, PEDRO" == "PEDRO JUAN" == "Juan Pedro" all score 100.
        def _norm(s: str) -> str:
            return re.sub(r"[^a-z0-9\s]", "", str(s).strip().lower())

        score = fuzz.token_sort_ratio(_norm(val_a), _norm(val_b))
        threshold = rule.get("threshold", 85)
        passed = score >= threshold
        status = "pass" if passed else "fail"

    elif method == "numeric_tolerance":
        num_a = _normalize_numeric(val_a)
        num_b = _normalize_numeric(val_b)
        if num_a is None or num_b is None:
            return {
                "check": rule["check"],
                "status": "warning",
                "values": values,
                "score": None,
                "severity": rule["severity"],
                "message": "Could not compare — one or both numeric values could not be parsed",
            }
        tolerance = rule.get("tolerance", 0.01)
        if num_a == 0 and num_b == 0:
            passed = True
            score = 100
        elif num_a == 0:
            passed = False
            score = 0
        else:
            diff = abs(num_a - num_b) / abs(num_a)
            passed = diff <= tolerance
            score = max(0, round((1 - diff) * 100))
        status = "pass" if passed else "fail"

    else:
        raise ValueError(f"Unknown validation method: {method}")

    return {
        "check": rule["check"],
        "status": status,
        "values": values,
        "score": score,
        "severity": rule["severity"],
        "message": rule["pass_msg"] if passed else rule["fail_msg"],
    }


def run_validations(extractions: dict) -> list[dict]:
    """Run all cross-document validation checks against the extracted data."""
    results = []
    for rule in VALIDATION_RULES:
        results.append(_run_check(rule, extractions))
    return results
