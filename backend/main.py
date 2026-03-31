import base64
import uuid
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from ocr_extractor import extract_government_id
from scorer import score_case, score_completeness
from validator import run_validations

# NOTE: extractor (OpenAI) is imported lazily inside evaluate_case only,
# so the server starts cleanly even without a valid API key.

load_dotenv()

app = FastAPI(title="ICR Intelligent Onboarding API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _read_and_extract(upload: Optional[UploadFile], doc_type: str) -> Optional[dict]:
    if upload is None:
        return None
    # Import here so the server starts even when OPENAI_API_KEY is not set
    from extractor import extract_document
    content = await upload.read()
    file_b64 = base64.b64encode(content).decode("utf-8")
    return extract_document(file_b64, upload.content_type, doc_type)


@app.post("/api/test-id-ocr")
async def test_id_ocr(government_id: UploadFile = File(...)):
    """
    Debug endpoint — returns raw Tesseract OCR text, detected ID type,
    and the structured extraction result. Use this to inspect exactly what
    Tesseract reads before any parsing logic runs.
    """
    from ocr_extractor import (
        _detect_type, _load_image, _best_ocr, _MIME_TO_EXT,
        extract_government_id,
    )

    content = await government_id.read()
    ext = _MIME_TO_EXT.get(government_id.content_type, ".png")

    # Run OCR independently so we can expose the raw text
    raw_img = _load_image(content, government_id.content_type)
    raw_text = _best_ocr(raw_img, raw_bytes=content, ext=ext)
    detected_type = _detect_type(raw_text)

    extraction = extract_government_id(content, government_id.content_type)

    return {
        "filename": government_id.filename,
        "detected_type": detected_type,
        "raw_ocr_text": raw_text,           # ← key: see exactly what Tesseract read
        "ocr_lines": [l for l in raw_text.splitlines() if l.strip()],
        "extraction": extraction,
    }


@app.post("/api/evaluate-case")
async def evaluate_case(
    application_form: Optional[UploadFile] = File(None),
    government_id: Optional[UploadFile] = File(None),
    policy_illustration: Optional[UploadFile] = File(None),
):
    # Extract all provided documents
    extractions = {}

    if application_form:
        extractions["application_form"] = await _read_and_extract(application_form, "application_form")
    if government_id:
        extractions["government_id"] = await _read_and_extract(government_id, "government_id")
    if policy_illustration:
        extractions["policy_illustration"] = await _read_and_extract(policy_illustration, "policy_illustration")

    # Validation (only runs checks where both documents exist)
    validations = run_validations(extractions)

    # Completeness scoring
    completeness = score_completeness(extractions)

    # Overall case score
    case_score, case_status = score_case(completeness, validations)

    # Split validations into critical flags and warnings.
    # "unverified" on a critical check is surfaced as a flag — inability to
    # confirm a critical field is itself a case concern.
    critical_flags = [
        v for v in validations
        if v["severity"] == "critical" and v["status"] in ("fail", "unverified")
    ]
    warnings = [
        v for v in validations
        if v["severity"] == "warning" and v["status"] in ("fail", "unverified")
    ]

    return {
        "case_id": str(uuid.uuid4()),
        "extractions": extractions,
        "validations": validations,
        "completeness": completeness,
        "case_score": case_score,
        "case_status": case_status,
        "critical_flags": critical_flags,
        "warnings": warnings,
    }


@app.get("/api/mock-evaluation")
async def mock_evaluation():
    """
    Hardcoded demo response based on a real Allianz PNB Life case.
    Insured: LORENCO, MARIA CRISTINA — Allianz eAZy Health Silver.
    Illustrates a realistic result: all critical checks pass, one warning
    (applicant DOB absent from the sales illustration).
    """
    return {
        "case_id": "mock-58155079",
        "extractions": {
            "application_form": {
                "full_name": "LORENCO, MARIA CRISTINA",
                "date_of_birth": "1989-01-16",
                "gender": "Female",
                "civil_status": "Single",
                "address": "517 GEN. TUAZON BLVD, BRGY. RIVERA, PASAY CITY",
                "pincode": "1717",
                "phone": "09345678901",
                "email": "lorenco.mc@123.com",
                "nominee_name": "LORENCO, JAMESON",
                "nominee_relationship": "Brother",
                "sum_assured": "300000",
                "plan_name": "EAZY HEALTH SILVER",
                "premium_amount": None,
                "payment_frequency": "Annual",
            },
            "government_id": {
                # Postal Identity Card (PhlPost) — extracted via local OCR
                "id_type": "Postal ID",
                "id_number": "100041034067",
                "full_name": "MARIA CRISTINA LORENCO",
                "date_of_birth": "1989-01-16",
                "address": "517 GEN. TUAZON BLVD, BRGY. RIVERA, 1717 PASAY CITY",
                "pincode": "1717",
                "gender": None,
            },
            "policy_illustration": {
                # Allianz eAZy Health Silver — Sales Illustration dated July 17, 2025
                "plan_name": "Allianz eAZy Health Silver",
                "policy_term": None,
                "premium_payment_term": "Annual",
                "sum_assured": "300000",
                "annual_premium": "15600",
                "applicant_name": "Lorenco, Maria Cristina",
                "applicant_dob": None,           # illustration shows age 37, not exact DOB
                "maturity_benefit": None,
                "death_benefit": "300000",
            },
        },
        "validations": [
            {
                "check": "name_match_form_vs_id",
                "status": "pass",
                # Form: "LORENCO, MARIA CRISTINA"  ↔  ID: "MARIA CRISTINA LORENCO"
                # Same tokens, different order — fuzzy ratio ~88 (above 85 threshold)
                "values": {
                    "Application Form": "LORENCO, MARIA CRISTINA",
                    "Government Id": "MARIA CRISTINA LORENCO",
                },
                "score": 88,
                "severity": "critical",
                "message": "Names match across application form and ID",
            },
            {
                "check": "name_match_form_vs_policy",
                "status": "pass",
                "values": {
                    "Application Form": "LORENCO, MARIA CRISTINA",
                    "Policy Illustration": "Lorenco, Maria Cristina",
                },
                "score": 100,
                "severity": "critical",
                "message": "Names match across application form and policy illustration",
            },
            {
                "check": "dob_match_form_vs_id",
                "status": "pass",
                "values": {
                    "Application Form": "1989-01-16",
                    "Government Id": "1989-01-16",
                },
                "score": 100,
                "severity": "critical",
                "message": "Date of birth matches across application form and ID",
            },
            {
                "check": "dob_match_form_vs_policy",
                "status": "unverified",
                # Sales illustration shows age 37, not exact DOB — cannot confirm
                "values": {
                    "Application Form": "1989-01-16",
                    "Policy Illustration": None,
                },
                "score": None,
                "severity": "critical",
                "message": "Could not compare — one or both values are missing",
            },
            {
                "check": "pincode_match_form_vs_id",
                "status": "pass",
                "values": {
                    "Application Form": "1717",
                    "Government Id": "1717",
                },
                "score": 100,
                "severity": "warning",
                "message": "Pincode matches across application form and ID",
            },
            {
                "check": "sum_assured_match_form_vs_policy",
                "status": "pass",
                "values": {
                    "Application Form": "300000",
                    "Policy Illustration": "300000",
                },
                "score": 100,
                "severity": "warning",
                "message": "Sum assured matches across application form and policy illustration",
            },
            {
                "check": "plan_name_match",
                "status": "pass",
                # "EAZY HEALTH SILVER" vs "Allianz eAZy Health Silver" — fuzzy ~82
                "values": {
                    "Application Form": "EAZY HEALTH SILVER",
                    "Policy Illustration": "Allianz eAZy Health Silver",
                },
                "score": 82,
                "severity": "warning",
                "message": "Plan name matches across application form and policy illustration",
            },
        ],
        "completeness": {
            "application_form": {"score": 100, "missing": []},
            "government_id": {"score": 100, "missing": []},
            "policy_illustration": {"score": 80, "missing": ["applicant_dob"]},
        },
        "case_score": 86,
        "case_status": "Ready for Review",
        "critical_flags": [
            {
                "check": "dob_match_form_vs_policy",
                "status": "unverified",
                "values": {"Application Form": "1989-01-16", "Policy Illustration": None},
                "score": None,
                "severity": "critical",
                "message": "Could not compare — applicant DOB not on sales illustration (age 37 shown instead)",
            }
        ],
        "warnings": [],
    }
