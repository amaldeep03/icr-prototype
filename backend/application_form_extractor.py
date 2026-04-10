"""
Multi-pass extraction pipeline for Allianz PNB Life Application for Life Insurance
(Guaranteed Acceptance Endorsement / GAE) PDFs.

The GAE form is 7 pages:
  Pages 1–2: Section A (PI Information), Section B (Beneficiaries),
             Section C (Policy Applied For), Section D (Payout Option),
             Section E (Replacement Declaration)
  Page 3:    Section F (Variability), Section G (General Declaration),
             Section H (Signatures — PI and AO)
  Page 4:    Intermediary Declarations (FA/agent signature)

Since there is no health/medical declaration (GAE = Guaranteed Acceptance, no medical UW),
we use 2 targeted vision passes:

  Pass 1 — Pages 1–2: Applicant identity, plan info, beneficiary, Q14, payout option
  Pass 2 — Pages 3–4: Signatures (PI, AO, and FA/Intermediary)
"""

import base64
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")


# ── Page-to-image helpers ──────────────────────────────────────────────────────

def _pages_to_base64(file_bytes: bytes, first_page: int, last_page: int) -> str:
    """
    Convert a page range from a PDF into a single stitched PNG, base64-encoded.
    If last_page exceeds the document length, silently renders up to the last page.
    """
    from pdf2image import convert_from_bytes
    from PIL import Image

    images = convert_from_bytes(
        file_bytes, first_page=first_page, last_page=last_page, dpi=200
    )
    if not images:
        # last_page may exceed the document — retry without the upper bound
        images = convert_from_bytes(file_bytes, first_page=first_page, dpi=200)
    if not images:
        raise ValueError(f"No pages rendered starting at page {first_page}")

    if len(images) == 1:
        combined = images[0]
    else:
        total_height = sum(img.height for img in images)
        max_width = max(img.width for img in images)
        combined = Image.new("RGB", (max_width, total_height), color=(255, 255, 255))
        y_offset = 0
        for img in images:
            combined.paste(img, (0, y_offset))
            y_offset += img.height

    buf = BytesIO()
    combined.save(buf, format="PNG")
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


# ── Prompts ────────────────────────────────────────────────────────────────────

_PROMPT_IDENTITY = """You are extracting data from pages 1–2 of an Allianz PNB Life
APPLICATION FOR LIFE INSURANCE — GUARANTEED ACCEPTANCE ENDORSEMENT (GAE) form.
The form is handwritten/filled in by hand.

Page 1 — Section A: Proposed Insured (PI) Information
  1. Name (last name, first name, middle name)
  2. Date of Birth (mm/dd/yyyy)
  3. Gender (Male / Female)
  4. Place of Birth (city/mun, prov, country)
  5. Civil Status (Single / Widowed / Annulled / Married / Separated / Divorced)
  6. Nationality
  7. Are you a US Person? (Yes / No)
  8. Mobile Number
  9. Email
  10. Preferred Mailing Address (Present or Work checkbox)
  11. Present Address (Unit/Building, Lot/Block, Street, Barangay/Subdivision,
      City/Municipality, Province, Country)
  12. Work Information: Occupation (Title and/or Duties), Employer/Nature of Business,
      Estimated Annual Income
  13. Source of Funds (checkboxes: Business, Salary/Commission, Donations/Contributions,
      Remittances/Allowances/Pension, Investments, Others)
  14. Question 14: PEP check — "Are/have you or any of your immediate family members or
      close relationships and associates been entrusted with prominent public position/s..."
      Answer: Yes or No.

Pages 1–2 — Section B: Beneficiaries
  Up to 3 beneficiaries. Each has: Name, Date of Birth, Place of Birth, Nationality,
  Relationship to PI, Address, Contact Information, Gender,
  Primary % Share, Contingent % Share, Irrevocable / Revocable designation.
  (Extract the first beneficiary for nominee_name and nominee_relationship.)

Page 2 — Section C: Information on the Policy Applied For
  1. Plan Name
  2. Sum Assured
  3. Purpose of Insurance (checkboxes: Income Continuation, Estate Creation, Mortgage,
     Keyman Insurance, Others)
  4. Payment Scheme (Auto-Debit, Cash/Check, Credit Card, Others)

Page 2 — Section D: Payout Option for All Living Benefits
  Two radio options:
  - "Automatic Transfer to My Account" (with bank details fields)
  - "Check (to be mailed to my mailing address)"

Return ONLY a valid JSON object with these exact keys:

{
  "application_number": null,
  "full_name": "",
  "date_of_birth": "YYYY-MM-DD",
  "gender": "",
  "civil_status": "",
  "place_of_birth": "",
  "nationality": "",
  "is_us_person": null,
  "address": "",
  "pincode": null,
  "preferred_mailing_address": null,
  "phone": "",
  "email": "",
  "occupation_title": null,
  "occupation_duties": null,
  "employer_name": null,
  "employer_address": null,
  "source_of_funds": null,
  "estimated_annual_income": null,
  "nominee_name": "",
  "nominee_relationship": "",
  "sum_assured": "",
  "plan_name": "",
  "premium_amount": null,
  "payment_frequency": null,
  "payment_method": "",
  "question_14_answer": null,
  "payout_option": "",
  "fund_direction": null
}

Extraction rules:
- application_number: Pre-printed or stamped reference number (labelled "Application No."
  or near the top). Return as string; null if not found.
- full_name: Field 1 in Section A.
- date_of_birth: Field 2. Month is FIRST, day SECOND.
  E.g. 10 / 04 / 1987 → return "1987-10-04".
- gender: Field 3 — "Male" or "Female".
- civil_status: Field 5 — whichever circle is ticked.
- place_of_birth: Field 4.
- nationality: Field 6.
- is_us_person: Field 7 — true, false, or null.
- address: Field 11 — concatenate all non-blank sub-fields.
- pincode: Zip code in address block; null if not present.
- preferred_mailing_address: Field 10 — "Present" or "Work"; null if not answered.
- phone: Field 8 Mobile Number.
- email: Field 9.
- occupation_title: "Occupation (Title and/or Duties)" in Field 12. Null if blank.
- occupation_duties: Return null (duties merged with title in this form).
- employer_name: "Employer / Nature of Business" in Field 12. Null if blank.
- employer_address: null — not a separate field on this form.
- source_of_funds: Field 13 — ticked option(s) joined by ", ". Null if none.
- estimated_annual_income: "Estimated Annual Income" in Field 12 — numeric string only.
  Null if blank.
- nominee_name: First beneficiary's full name from Section B. Null if blank.
- nominee_relationship: Relationship of Beneficiary 1 to PI (e.g. "Child", "Spouse").
  Null if blank.
- sum_assured: Field 2 of Section C — numeric string only (no PHP, no commas).
- plan_name: Field 1 of Section C.
- premium_amount: null — not on this form.
- payment_frequency: null — this is a single-pay product.
- payment_method: Field 4 of Section C — ticked option: "Auto-Debit", "Cash/Check",
  "Credit Card", or "Others".
- question_14_answer: Field 14 — "Yes" or "No"; null if blank.
- payout_option: Section D — "Automatic transfer to my account" if that circle is ticked,
  "Check" if the Check option is ticked, null if neither.
- fund_direction: null — fund allocation is on the Sales Illustration, not this form.

Return null for any field not found or blank. No explanation, no markdown, no code fences."""


_PROMPT_SIGNATURES = """You are extracting data from pages 3–4 of an Allianz PNB Life
Application for Life Insurance (Guaranteed Acceptance Endorsement) form.

Page 3 — Section H: Signatures
  Contains the declaration text and two signature lines for the client:
  1. "Signature over Printed Name of Proposed Insured" — left block
  2. "Signature over Printed Name of Applicant Owner, if other than Proposed Insured"
     — separate block (blank if PI = AO)
  Also contains: "Signed in the Philippines on Date (mm/dd/yyyy)"

Page 4 — Intermediary Declarations, Section B: Signature
  The Financial Advisor / agent signs here:
  "Signature over Printed Name of Intermediary" with Code and Date fields.

Return ONLY a valid JSON object with these exact keys:

{
  "insured_signature_present": null,
  "payor_signature_present": null,
  "fa_signature_present": null,
  "signing_place": null,
  "signing_date": null
}

Extraction rules:
- insured_signature_present: true if there is a visible handwritten signature or
  printed name in the "Proposed Insured" block on page 3; false if blank; null if unclear.
- payor_signature_present: true if there is a visible signature in the separate
  "Applicant Owner, if other than Proposed Insured" block on page 3; false if blank.
  If PI and AO are the same person the AO block is typically left blank — return false.
- fa_signature_present: true if there is a visible signature in the Intermediary block
  on page 4; false if blank; null if page 4 is not visible.
- signing_place: City/location written near "Signed in the Philippines" on page 3.
  Null if not found.
- signing_date: Date from the signing area in YYYY-MM-DD format (month FIRST if
  written as mm/dd/yyyy). Null if blank.

Return null for any field not determinable. No explanation, no markdown, no code fences."""


# ── LLM call helper ────────────────────────────────────────────────────────────

def _vision_call(image_b64: str, prompt: str) -> dict:
    from extractor import _get_client, _parse_json

    response = _get_client().chat.completions.create(
        model="gpt-4o",
        max_tokens=512,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_b64}",
                            "detail": "high",
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )
    return _parse_json(response.choices[0].message.content)


# ── Public interface ───────────────────────────────────────────────────────────

def extract_application_form(file_bytes: bytes) -> dict:
    """
    Extract all NB-required fields from a GAE application form PDF using 2 targeted
    vision calls:
      Pass 1 (pages 1–2): identity, plan info, beneficiary, Q14, payout option
      Pass 2 (pages 3–4): signatures (PI, AO, FA/intermediary)

    Returns a single merged dict in the application_form extraction schema.
    Height/weight/health_declaration are always None (not applicable for GAE).
    """
    import concurrent.futures
    from extractor import _normalize_dates

    img_identity = _pages_to_base64(file_bytes, first_page=1, last_page=2)
    img_sigs     = _pages_to_base64(file_bytes, first_page=3, last_page=4)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        f_identity = pool.submit(_vision_call, img_identity, _PROMPT_IDENTITY)
        f_sigs     = pool.submit(_vision_call, img_sigs,     _PROMPT_SIGNATURES)

        result_identity = f_identity.result()
        result_sigs     = f_sigs.result()

    # GAE has no health declaration section — always N/A
    health_fields = {
        "height_cm": None,
        "weight_kg": None,
        "health_declaration_answered": None,
    }

    # Merge: identity is base; health N/A fields; signature fields overlay
    merged = {**result_identity, **health_fields, **result_sigs}

    return _normalize_dates(merged, "application_form")
