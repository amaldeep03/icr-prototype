"""
form_type.py — Maps product_type to a form category and drives conditional validation.

Four form categories:
  health        EAZY_HEALTH, IHP
                - Section E health declaration, height/weight, dependents
                - No Question #14, no fund direction, no FNA/IRPQ
  life_non_gae  UL_NON_GAE, TRAD_NON_GAE
                - Full underwriting: height/weight, health declaration, Question #14
                - Fund direction if UL; FNA + IRPQ if UL, FNA if TRAD
  life_gae      UL_GAE, TRAD_GAE
                - Guaranteed acceptance: NO medical UW, no height/weight
                - Question #14 still applies; fund direction if UL_GAE
  unknown       Product type not determined — run maximum checks, flag for review
"""

FORM_CATEGORY_MAP = {
    "EAZY_HEALTH": "health",
    "IHP":         "health",
    "UL_NON_GAE":  "life_non_gae",
    "TRAD_NON_GAE":"life_non_gae",
    "UL_GAE":      "life_gae",
    "TRAD_GAE":    "life_gae",
    "UNKNOWN":     "unknown",
}

def form_category(product_type: str) -> str:
    return FORM_CATEGORY_MAP.get(product_type, "unknown")

def requires_medical_uw(product_type: str) -> bool:
    """Height, weight, and health declaration are only required when full underwriting applies."""
    return form_category(product_type) in ("health", "life_non_gae", "unknown")

def requires_question_14(product_type: str) -> bool:
    """Question #14 (AID/PEP trigger) applies to all life products, not health."""
    return form_category(product_type) in ("life_non_gae", "life_gae", "unknown")

def requires_fund_direction(product_type: str) -> bool:
    """Fund direction only applies to Unit-Linked products."""
    return product_type in ("UL_NON_GAE", "UL_GAE")

def requires_payout_option(product_type: str) -> bool:
    """Payout option (dividend/ATA) is a life product concept, not applicable for health."""
    return form_category(product_type) in ("life_non_gae", "life_gae", "unknown")

def requires_fna(product_type: str) -> bool:
    return product_type in ("UL_NON_GAE", "TRAD_NON_GAE", "UL_GAE", "TRAD_GAE")

def requires_irpq(product_type: str) -> bool:
    return product_type in ("UL_NON_GAE", "UL_GAE")

# Fields that go into completeness scoring per product_type
# Government ID and policy_illustration fields are the same for all types.
_APP_FORM_BASE = [
    "application_number",
    "full_name",
    "date_of_birth",
    "gender",
    "civil_status",
    "address",
    "phone",
    "email",
    "place_of_birth",
    "nationality",
    "preferred_mailing_address",
    "occupation_title",
    "employer_name",
    "source_of_funds",
    "estimated_annual_income",
    "payment_method",
    "insured_signature_present",
    "payor_signature_present",
    "fa_signature_present",
    "signing_place",
    "signing_date",
    "nominee_name",
    "nominee_relationship",
    "sum_assured",
    "plan_name",
    "payment_frequency",
]

_MEDICAL_UW_FIELDS = ["height_cm", "weight_kg", "health_declaration_answered"]
_QUESTION_14_FIELDS = ["question_14_answer"]
_PAYOUT_FIELDS = ["payout_option"]
_FUND_DIR_FIELDS = ["fund_direction"]


def required_app_form_fields(product_type: str) -> list[str]:
    fields = list(_APP_FORM_BASE)
    if requires_medical_uw(product_type):
        fields += _MEDICAL_UW_FIELDS
    if requires_question_14(product_type):
        fields += _QUESTION_14_FIELDS
    if requires_payout_option(product_type):
        fields += _PAYOUT_FIELDS
    if requires_fund_direction(product_type):
        fields += _FUND_DIR_FIELDS
    return fields
