import base64
import json
import os
import re
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# Load .env from the backend directory (works regardless of cwd)
load_dotenv(Path(__file__).parent / ".env")

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set — add it to backend/.env")
        raw = OpenAI(api_key=api_key)
        # Wrap with LangSmith tracing when LANGCHAIN_API_KEY is set.
        # wrap_openai patches the client in-place so every chat.completions.create
        # call (vision passes, classify, illustration parsing) is captured with
        # token counts and cost — no other code changes needed.
        if os.getenv("LANGCHAIN_API_KEY"):
            try:
                from langsmith import wrappers
                raw = wrappers.wrap_openai(raw)
            except ImportError:
                pass  # langsmith not installed — tracing silently disabled
        _client = raw
    return _client

# ── Prompts ────────────────────────────────────────────────────────────────────
# Tailored to Allianz PNB Life Insurance forms (Philippine market).

PROMPTS = {
    "application_form": """You are extracting data from an Allianz PNB Life Insurance Application Form
(Simplified Issuance Offer / SIO). The form is in English and uses Philippine address conventions.

Extract the following fields and return ONLY a valid JSON object with these exact keys:
{
  "full_name": "",
  "date_of_birth": "YYYY-MM-DD",
  "gender": "",
  "civil_status": "",
  "address": "",
  "pincode": "",
  "phone": "",
  "email": "",
  "place_of_birth": "",
  "nationality": "",
  "is_us_person": null,
  "height_cm": "",
  "weight_kg": "",
  "health_declaration_answered": null,
  "question_14_answer": "",
  "payout_option": "",
  "payment_method": "",
  "insured_signature_present": null,
  "payor_signature_present": null,
  "nominee_name": "",
  "nominee_relationship": "",
  "sum_assured": "",
  "plan_name": "",
  "premium_amount": "",
  "payment_frequency": ""
}

Field extraction rules:
- full_name: "Name (last name, first name, middle name)" field in the Proposed Insured section. Return exactly as printed on the form.
- date_of_birth: "Date of Birth (mm/dd/yyyy)" field. The form explicitly labels this as mm/dd/yyyy,
  so the FIRST number is always the MONTH and the SECOND is the DAY.
  Example: 09/04/1994 → month=09 (September), day=04 → return "1994-09-04".
  Convert to YYYY-MM-DD.
- gender: "Male" or "Female" — check the ticked/filled circle.
- civil_status: check which circle is ticked: Single, Married, Widowed, Annulled, Separated, Divorced.
- address: concatenate the Present Address fields: Street, Barangay/Subdivision, City/Municipality (omit blank fields).
- pincode: "Zip Code" field (4-digit Philippine postal code).
- phone: "Mobile Number" field.
- email: "Email" field.
- place_of_birth: "Place of Birth" field for the Proposed Insured.
- nationality: "Nationality" or "Citizenship" field for the Proposed Insured.
- is_us_person: true if any US indicia found (US place of birth, US nationality/citizenship, US address,
  US phone number, or US-issued ID indicated on the form); false if explicitly declared as non-US person;
  null if not determinable from the form.
- height_cm: Height field — return as numeric string in cm. If given in feet/inches convert to cm. Null if not found.
- weight_kg: Weight field — return as numeric string in kg. If given in pounds convert to kg. Null if not found.
- health_declaration_answered: true if the Non-Medical Questions / Health Declaration section appears to be
  filled in (at least one yes/no answer present); false if the section is blank; null if not visible.
- question_14_answer: The answer to question #14 in the declaration / intermediary section of the form.
  Return "Yes", "No", or null if question 14 is not present or not answered.
- payout_option: The selected payout or dividend option (e.g., "Automatic transfer to my account",
  "Cash dividend", "Paid-up addition"). Return exactly as printed; null if not present.
- payment_method: How the premium is paid — e.g., "Direct Debit", "Check", "Cash", "Post-dated Checks".
  Null if not stated.
- insured_signature_present: true if a signature or initials appear in the Insured signature block; false if
  the signature block exists but is blank; null if the signature area is not visible.
- payor_signature_present: true if a signature or initials appear in the Payor / Applicant Owner signature
  block; false if blank; null if not visible.
- nominee_name: Beneficiary 1 "Name (last name, first name, middle name)" field.
- nominee_relationship: "Relationship to Proposed Insured" for Beneficiary 1.
- sum_assured: "Sum Assured" field — return as numeric string only (no PHP, commas, or spaces).
- plan_name: "Plan Name" field.
- premium_amount: return null — premium is shown in the Sales Illustration, not the application form.
- payment_frequency: "Mode of Payment" field — Annual, Semi Annual, Quarterly, or Monthly.

If a field is not found or is blank, return null for that key. No explanation, no markdown, no code fences.""",

    "policy_illustration": """You are extracting data from an Allianz PNB Life Insurance Sales Illustration document
(also called a Benefit Illustration). This is a Philippine insurance product document.

Extract the following fields and return ONLY a valid JSON object with these exact keys:
{
  "plan_name": "",
  "policy_term": "",
  "premium_payment_term": "",
  "sum_assured": "",
  "annual_premium": "",
  "applicant_name": "",
  "applicant_dob": "YYYY-MM-DD",
  "insured_age": "",
  "insured_gender": "",
  "is_substandard": null,
  "maturity_benefit": "",
  "death_benefit": ""
}

Field extraction rules:
- plan_name: The insurance plan name shown as the document title (e.g., "Allianz eAZy Health Silver").
- policy_term: Policy term in years if stated; null if the plan renews every 5 years without a fixed term.
- premium_payment_term: Chosen Mode of Payment (e.g., "Annual").
- sum_assured: The Death Benefit amount — numeric string only (no PHP, commas).
- annual_premium: Total annual premium for Policy Year 1 to 5 (the first row in the premiums table) — numeric string only.
- applicant_name: The proposed insured's name shown at the top of the document.
- applicant_dob: Date of birth if explicitly shown; null if only age is displayed (do NOT guess from age).
- insured_age: Age of the insured as shown in the illustration (e.g. "37"). Return as numeric string. Null if not shown.
- insured_gender: Gender of the insured — "Male" or "Female". Null if not stated.
- is_substandard: true if the illustration is marked as "Substandard" or shows a rating/extra premium; false if standard; null if not stated.
- maturity_benefit: Any maturity or endowment benefit amount; for health/term plans this is often null.
- death_benefit: The Death Benefit amount — numeric string only.

If a field is not found, return null. No explanation, no markdown, no code fences.""",
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _pdf_first_page_base64(file_bytes: bytes) -> str:
    """Convert first page of a PDF to a base64-encoded PNG."""
    from pdf2image import convert_from_bytes

    images = convert_from_bytes(file_bytes, first_page=1, last_page=1, dpi=200)
    if not images:
        raise ValueError("Could not convert PDF to image")
    buf = BytesIO()
    images[0].save(buf, format="PNG")
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def _parse_json(text: str) -> dict:
    """Strip accidental markdown fences and parse JSON."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text.strip())


# Date fields per doc type that must be in YYYY-MM-DD
_DATE_FIELDS = {
    "application_form":   ["date_of_birth"],
    "policy_illustration": ["applicant_dob"],
}

# For application form the source format is always mm/dd/yyyy (form label).
# If GPT returns YYYY-DD-MM instead of YYYY-MM-DD the month and day are swapped —
# we detect this by checking whether the "month" part exceeds 12.
def _normalize_dates(data: dict, doc_type: str) -> dict:
    fields = _DATE_FIELDS.get(doc_type, [])
    for field in fields:
        val = data.get(field)
        if not val or not re.match(r"^\d{4}-\d{2}-\d{2}$", str(val)):
            continue
        year, m, d = val.split("-")
        # If month > 12 the values were swapped — swap back
        if int(m) > 12 and int(d) <= 12:
            data[field] = f"{year}-{d}-{m}"
    return data


# ── Public interface ───────────────────────────────────────────────────────────

def extract_document(file_base64: str, file_type: str, doc_type: str) -> dict:
    """
    Extract structured fields from a document.

    - government_id  → local Tesseract OCR (no data sent externally)
    - application_form / policy_illustration → OpenAI GPT-4o vision

    Args:
        file_base64: Base64-encoded file content
        file_type:   MIME type ("image/jpeg", "image/png", "application/pdf")
        doc_type:    "application_form" | "government_id" | "policy_illustration"
    """
    if doc_type == "government_id":
        from ocr_extractor import extract_government_id
        raw_bytes = base64.b64decode(file_base64)
        return extract_government_id(raw_bytes, file_type)

    if doc_type not in PROMPTS:
        raise ValueError(f"Unknown doc_type: {doc_type}")

    # Policy illustration PDFs → chunked text pipeline (better accuracy, lower cost)
    if doc_type == "policy_illustration" and file_type == "application/pdf":
        from illustration_extractor import extract_policy_illustration
        raw_bytes = base64.b64decode(file_base64)
        return extract_policy_illustration(raw_bytes)

    # Application form PDFs → multi-pass vision pipeline (avoids lost-in-middle)
    if doc_type == "application_form" and file_type == "application/pdf":
        from application_form_extractor import extract_application_form
        raw_bytes = base64.b64decode(file_base64)
        return extract_application_form(raw_bytes)

    # Convert PDF to image — OpenAI vision does not accept PDFs directly
    if file_type == "application/pdf":
        raw_bytes = base64.b64decode(file_base64)
        image_b64 = _pdf_first_page_base64(raw_bytes)
        media_type = "image/png"
    else:
        image_b64 = file_base64
        media_type = file_type

    response = _get_client().chat.completions.create(
        model="gpt-4o",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type};base64,{image_b64}",
                            "detail": "high",
                        },
                    },
                    {
                        "type": "text",
                        "text": PROMPTS[doc_type],
                    },
                ],
            }
        ],
    )

    result = _parse_json(response.choices[0].message.content)
    return _normalize_dates(result, doc_type)
