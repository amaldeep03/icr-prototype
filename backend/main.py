import base64
import os
import uuid
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from langgraph.types import Command
from pydantic import BaseModel

load_dotenv()

app = FastAPI(title="ICR Intelligent Onboarding API")

cors_origins = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:5173,http://localhost:3000")
allowed_origins = [o.strip() for o in cors_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Graph is built once at startup and reused across requests
from graph import icr_graph


# ── Helpers ────────────────────────────────────────────────────────────────────

def _thread_config(case_id: str) -> dict:
    """LangGraph thread config — binds a case_id to a checkpointer thread."""
    return {"configurable": {"thread_id": case_id}}


def _state_to_response(state: dict, case_id: str) -> dict:
    """Shape the graph state into the API response the frontend expects."""
    # Check if the graph is paused at human_review
    needs_attention = state.get("needs_attention", False)
    open_findings = [
        f for f in (state.get("findings") or []) if f.get("status") == "open"
    ]
    is_paused = needs_attention and bool(open_findings)

    return {
        "case_id": case_id,
        "status": "needs_attention" if is_paused else "complete",
        "product_type": state.get("product_type", "UNKNOWN"),
        "extractions": state.get("extractions", {}),
        "nb_requirements": state.get("nb_requirements", {}),
        "validations": state.get("validations", []),
        "completeness": state.get("completeness", {}),
        "case_score": state.get("case_score"),
        "case_status": state.get("case_status"),
        "findings": state.get("findings", []),
        "critical_flags": state.get("critical_flags", []),
        "warnings": state.get("warnings", []),
        # Presented to the reviewer when status == "needs_attention"
        "open_findings": open_findings if is_paused else [],
    }


# ── Request / Response models ──────────────────────────────────────────────────

class ReviewerAction(BaseModel):
    finding_rule_id: str
    action: str                        # "confirm" | "override" | "waive"
    corrected_value: Optional[str] = None
    reason: Optional[str] = None


class ResumeRequest(BaseModel):
    reviewer_actions: list[ReviewerAction]


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.post("/api/evaluate-case")
async def evaluate_case(
    application_form: Optional[UploadFile] = File(None),
    government_id: Optional[UploadFile] = File(None),
    policy_illustration: Optional[UploadFile] = File(None),
):
    """
    Start a new ICR case.

    Accepts up to 3 documents, runs the LangGraph pipeline:
      classify → extract → rules → [needs_attention? → human_review] → finalize

    If the case needs human attention the response has status="needs_attention"
    and includes open_findings for the reviewer. Call /api/resume-case/{case_id}
    to continue after review.

    If the case is clean the response has status="complete" with full results.
    """
    case_id = str(uuid.uuid4())

    # Build document list from uploaded files
    documents = []
    upload_map = {
        "application_form": application_form,
        "government_id": government_id,
        "policy_illustration": policy_illustration,
    }
    for doc_type, upload in upload_map.items():
        if upload is not None:
            content = await upload.read()
            documents.append({
                "doc_type": doc_type,
                "file_bytes_b64": base64.b64encode(content).decode("utf-8"),
                "content_type": upload.content_type or "application/octet-stream",
                "filename": upload.filename or doc_type,
            })

    if not documents:
        raise HTTPException(status_code=400, detail="At least one document must be uploaded.")

    initial_state = {
        "case_id": case_id,
        "documents": documents,
        "product_type": "UNKNOWN",
        "extractions": {},
        "nb_requirements": {},
        "validations": [],
        "completeness": {},
        "case_score": 0,
        "case_status": "Incomplete / Refer Back",
        "needs_attention": False,
        "critical_flags": [],
        "warnings": [],
        "findings": [],
        "reviewer_actions": [],
        "error": None,
    }

    # Run graph synchronously in a thread to avoid blocking the event loop
    import asyncio
    state = await asyncio.to_thread(
        icr_graph.invoke, initial_state, _thread_config(case_id)
    )

    return _state_to_response(state, case_id)


@app.post("/api/resume-case/{case_id}")
async def resume_case(case_id: str, body: ResumeRequest):
    """
    Resume a paused case after human review.

    The reviewer submits a list of actions (confirm / override / waive) for
    each open finding. The graph continues from the human_review interrupt,
    re-runs the rules engine with any corrections applied, then finalizes.
    """
    import asyncio

    actions = [a.model_dump() for a in body.reviewer_actions]

    try:
        state = await asyncio.to_thread(
            icr_graph.invoke,
            Command(resume=actions),
            _thread_config(case_id),
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Case not found or already complete: {exc}")

    return _state_to_response(state, case_id)


@app.get("/api/case-status/{case_id}")
async def get_case_status(case_id: str):
    """
    Retrieve the current state of an existing case from the checkpointer.
    Useful for polling or re-rendering the review UI after a page refresh.
    """
    try:
        state = icr_graph.get_state(_thread_config(case_id))
        if state is None or state.values is None:
            raise HTTPException(status_code=404, detail="Case not found.")
        return _state_to_response(state.values, case_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ── Debug / test endpoints (unchanged) ────────────────────────────────────────

@app.post("/api/test-id-ocr")
async def test_id_ocr(government_id: UploadFile = File(...)):
    """
    Debug endpoint — returns raw Tesseract OCR text, detected ID type,
    and the structured extraction result.
    """
    from ocr_extractor import (
        _detect_type, _load_image, _best_ocr, _MIME_TO_EXT,
        extract_government_id,
    )

    content = await government_id.read()
    ext = _MIME_TO_EXT.get(government_id.content_type, ".png")
    raw_img = _load_image(content, government_id.content_type)
    raw_text = _best_ocr(raw_img, raw_bytes=content, ext=ext)
    detected_type = _detect_type(raw_text)
    extraction = extract_government_id(content, government_id.content_type)

    return {
        "filename": government_id.filename,
        "detected_type": detected_type,
        "raw_ocr_text": raw_text,
        "ocr_lines": [l for l in raw_text.splitlines() if l.strip()],
        "extraction": extraction,
    }


@app.post("/api/test-illustration-extraction")
async def test_illustration_extraction(policy_illustration: UploadFile = File(...)):
    """
    Debug endpoint for the chunked policy illustration pipeline.
    """
    from illustration_extractor import get_extraction_debug, extract_policy_illustration

    content = await policy_illustration.read()

    if policy_illustration.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="This endpoint only accepts PDF files.")

    debug = get_extraction_debug(content)
    extraction = extract_policy_illustration(content)

    return {
        "filename": policy_illustration.filename,
        **debug,
        "extraction": extraction,
    }


@app.get("/api/mock-evaluation")
async def mock_evaluation():
    """
    Demo response matching the attached GAE demo documents.
    Insured: JUAN, PEDRO — Allianz PNB Life OPTIMAX GOLD (UL GAE), Application No. 581550770.
    """
    return {
        "case_id": "mock-581550770",
        "status": "complete",
        "product_type": "UL_GAE",
        "extractions": {
            "application_form": {
                "application_number": "581550770",
                "full_name": "JUAN, PEDRO",
                "date_of_birth": "1987-10-04",
                "gender": "Male",
                "civil_status": "Married",
                "place_of_birth": "MUNTINLUPA CITY",
                "nationality": "Filipino",
                "is_us_person": False,
                "address": "123 AREA 34 BRGY. TORO, PASIG CITY",
                "pincode": None,
                "preferred_mailing_address": "Present",
                "phone": "09123987654",
                "email": "juan.pedro@123.com",
                "occupation_title": "Supervisor",
                "occupation_duties": None,
                "employer_name": "BCDF CORP., PHIL",
                "employer_address": "ANDRITS BRGY. TAMO, PASAY CITY",
                "source_of_funds": "Salary/Commission",
                "estimated_annual_income": "640000",
                "nominee_name": "JUAN, CHRISTIANA",
                "nominee_relationship": "Child",
                "sum_assured": "2250000",
                "plan_name": "OPTIMAX GOLD",
                "premium_amount": None,
                "payment_frequency": None,
                "payment_method": "Cash/Check",
                "question_14_answer": "No",
                "payout_option": "Check",
                "fund_direction": None,
                "height_cm": None,
                "weight_kg": None,
                "health_declaration_answered": None,
                "insured_signature_present": True,
                "payor_signature_present": False,
                "fa_signature_present": True,
                "signing_place": "Philippines",
                "signing_date": "2025-07-15",
            },
            "government_id": {
                "id_type": "LTO Driver's License",
                "id_number": "N03-12-123434",
                "full_name": "JUAN, PEDRO",
                "date_of_birth": "1987-10-04",
                "address": "UNIT/HOUSE NO. BUILDING, STREET NAME, BARANGAY, CITY/MUNICIPALITY",
                "pincode": None,
                "gender": "Male",
            },
            "policy_illustration": {
                "plan_name": "Optimax Gold",
                "policy_term": None,
                "premium_payment_term": "Single Pay",
                "sum_assured": "2250000",
                "annual_premium": "1500000",
                "applicant_name": "Juan, Pedro",
                "applicant_dob": "1987-10-04",
                "insured_age": 37,
                "insured_gender": "Male",
                "is_substandard": False,
                "maturity_benefit": None,
                "death_benefit": "2250000",
                "fund_direction": "Peso Balanced Fund",
            },
        },
        "nb_requirements": {
            "insured_age": 37,
            "is_legal_age": True,
            "product_type": "UL_GAE",
            "form_category": "life_gae",
            "crucial": [
                {"requirement": "Application number present", "source": "Application Form", "status": "present", "note": "Application No: 581550770"},
                {"requirement": "Insured age (Date of Birth)", "source": "Application Form / Sales Illustration", "status": "present", "note": "Affects premium calculation. Resolved age: 37."},
                {"requirement": "Insured gender", "source": "Application Form / Sales Illustration", "status": "present", "note": "Required for premium calculation."},
                {"requirement": "Question #14 answer", "source": "Application Form", "status": "present", "note": "Answer recorded: No."},
                {"requirement": "Payout option", "source": "Application Form", "status": "present", "note": "Selected: Check."},
                {"requirement": "US person / FATCA check", "source": "Application Form", "status": "present", "note": "No US indicia detected. ACIF / W-9 not required.", "values": {"place_of_birth": "MUNTINLUPA CITY", "nationality": "Filipino", "is_us_person": False}},
                {"requirement": "Email address", "source": "Application Form", "status": "present", "note": "juan.pedro@123.com"},
                {"requirement": "Mobile / contact number", "source": "Application Form", "status": "present", "note": "09123987654"},
                {"requirement": "Preferred mailing address", "source": "Application Form", "status": "present", "note": "Selected: Present."},
                {"requirement": "Source of funds", "source": "Application Form", "status": "present", "note": "Declared: Salary/Commission."},
                {"requirement": "Estimated annual income", "source": "Application Form", "status": "present", "note": "Declared: 640000."},
                {"requirement": "Fund direction declared", "source": "Application Form / Sales Illustration", "status": "present", "note": "Fund direction: Peso Balanced Fund. Ensure this matches the Sales Illustration."},
                {"requirement": "Place of signing", "source": "Application Form — Signature page", "status": "present", "note": "Location recorded: Philippines."},
                {"requirement": "Date of signing", "source": "Application Form — Signature page", "status": "present", "note": "Date recorded: 2025-07-15."},
                {"requirement": "Payor / Applicant Owner signature", "source": "Application Form — Signature page", "status": "present", "note": "Applicant Owner signature present."},
                {"requirement": "Financial Advisor signature", "source": "Application Form — Signature page", "status": "present", "note": "FA signature present."},
                {"requirement": "Insured (Proposed Insured) signature", "source": "Application Form — Signature page", "status": "present", "note": "Insured is of legal age (37) — signature is required. Signature present."},
                {"requirement": "Designated beneficiary name", "source": "Application Form", "status": "present", "note": "Beneficiary name is required."},
                {"requirement": "Beneficiary relationship to insured", "source": "Application Form", "status": "present", "note": "Relationship: Child."},
            ],
            "minor": [
                {"requirement": "Height / Weight / Health declaration", "source": "Application Form", "status": "not_required", "note": "Not required for UL_GAE (Guaranteed Acceptance — no medical underwriting)."},
                {"requirement": "Occupation title", "source": "Application Form", "status": "present", "note": "Occupation: Supervisor."},
                {"requirement": "Employer / business name", "source": "Application Form", "status": "present", "note": "Employer: BCDF CORP., PHIL."},
                {"requirement": "Payment method", "source": "Application Form", "status": "present", "note": "Payment method: Cash/Check."},
                {"requirement": "Valid government ID", "source": "Government ID", "status": "present", "note": "Detected: LTO Driver's License."},
                {"requirement": "Financial Needs Analysis (FNA)", "source": "Not submitted", "status": "external_document_required", "note": "FNA is required for UL_GAE products. Not included in the current submission."},
                {"requirement": "Investor Risk Profile Questionnaire (IRPQ)", "source": "Not submitted", "status": "external_document_required", "note": "IRPQ is required for Unit-Linked products (UL_GAE). Not included in the current submission."},
            ],
        },
        "validations": [
            {"check": "name_match_form_vs_id", "status": "pass", "values": {"Application Form": "JUAN, PEDRO", "Government Id": "JUAN, PEDRO"}, "score": 100, "severity": "critical", "message": "Names match across application form and ID"},
            {"check": "name_match_form_vs_policy", "status": "pass", "values": {"Application Form": "JUAN, PEDRO", "Policy Illustration": "Juan, Pedro"}, "score": 100, "severity": "critical", "message": "Names match across application form and policy illustration"},
            {"check": "dob_match_form_vs_id", "status": "pass", "values": {"Application Form": "1987-10-04", "Government Id": "1987-10-04"}, "score": 100, "severity": "critical", "message": "Date of birth matches across application form and ID"},
            {"check": "dob_match_form_vs_policy", "status": "pass", "values": {"Application Form": "1987-10-04", "Policy Illustration": "1987-10-04"}, "score": 100, "severity": "critical", "message": "Date of birth matches across application form and policy illustration"},
            {"check": "pincode_match_form_vs_id", "status": "unverified", "values": {"Application Form": None, "Government Id": None}, "score": None, "severity": "warning", "message": "Could not compare — pincode not found on either document"},
            {"check": "sum_assured_match_form_vs_policy", "status": "pass", "values": {"Application Form": "2250000", "Policy Illustration": "2250000"}, "score": 100, "severity": "warning", "message": "Sum assured matches across application form and policy illustration"},
            {"check": "plan_name_match", "status": "pass", "values": {"Application Form": "OPTIMAX GOLD", "Policy Illustration": "Optimax Gold"}, "score": 100, "severity": "warning", "message": "Plan name matches across application form and policy illustration"},
            {"check": "fund_direction_match", "status": "unverified", "values": {"Application Form": None, "Policy Illustration": "Peso Balanced Fund"}, "score": None, "severity": "warning", "message": "Could not compare — fund direction not declared on application form (check Sales Illustration)"},
        ],
        "completeness": {
            "application_form": {"score": 95, "missing": ["pincode"]},
            "government_id":    {"score": 90, "missing": ["pincode"]},
            "policy_illustration": {"score": 100, "missing": []},
        },
        "case_score": 92,
        "case_status": "Ready for Review",
        "findings": [],
        "critical_flags": [],
        "warnings": [],
        "open_findings": [],
    }
