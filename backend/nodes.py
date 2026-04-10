"""
LangGraph node implementations for the ICR pipeline.

Each function takes a CaseState and returns a partial dict that LangGraph
merges into the running state. Existing extractors, rules engine, validator,
and scorer are all called as pure functions — nodes are thin wrappers.

Node execution order:
  classify_documents → extract_documents → run_rules
      → [conditional] → human_review → run_rules (loop)
                      → finalize → END
"""

import asyncio
import base64
import concurrent.futures
from typing import Any

from state import CaseState, Finding


# ── Helpers ────────────────────────────────────────────────────────────────────

def _b64_to_bytes(b64: str) -> bytes:
    return base64.b64decode(b64)


def _get(extractions: dict, doc: str, field: str) -> Any:
    return (extractions.get(doc) or {}).get(field)


# ── Node 1: classify_documents ─────────────────────────────────────────────────

_CLASSIFY_PROMPT = """You are identifying the type of an Allianz PNB Life Insurance form.
Look at the document title, section headers, and the form code printed at the bottom of page 1.

Common form codes and their product types:
- FDAS-NBUW-FRM-AFHI  → EAZY_HEALTH  (Application for Health Insurance)
- IHP or "Individual Health Plan" in title → IHP
- "Unit-Linked" or "VUL" or "ULAM" in title → UL_NON_GAE (assume Non-GAE unless "Guaranteed Acceptance" is stated)
- "Guaranteed Acceptance" or "GAE" in title or header → UL_GAE or TRAD_GAE
- "Traditional" life insurance without GAE → TRAD_NON_GAE

Return ONLY a valid JSON object:
{
  "product_type": "<one of: EAZY_HEALTH | IHP | UL_GAE | UL_NON_GAE | TRAD_GAE | TRAD_NON_GAE | UNKNOWN>",
  "form_code": "<form code from bottom of page if visible, else null>",
  "confidence": "<high | medium | low>"
}
No explanation, no markdown."""


def classify_documents(state: CaseState) -> dict:
    """
    Identify the product type from the application form's first page.
    Falls back to UNKNOWN if no application form is present.
    """
    from extractor import _get_client, _parse_json

    app_doc = next(
        (d for d in state["documents"] if d["doc_type"] == "application_form"), None
    )
    if not app_doc:
        return {"product_type": "UNKNOWN"}

    # Use the application form extractor's page renderer for just page 1
    try:
        from application_form_extractor import _pages_to_base64
        img_b64 = _pages_to_base64(_b64_to_bytes(app_doc["file_bytes_b64"]), 1, 1)

        response = _get_client().chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=128,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{img_b64}",
                                "detail": "low",
                            },
                        },
                        {"type": "text", "text": _CLASSIFY_PROMPT},
                    ],
                }
            ],
        )
        result = _parse_json(response.choices[0].message.content)
        return {"product_type": result.get("product_type", "UNKNOWN")}
    except Exception:
        return {"product_type": "UNKNOWN"}


# ── Node 2: extract_documents ──────────────────────────────────────────────────

def _extract_one(doc: dict) -> tuple[str, dict]:
    """Extract a single document. Returns (doc_type, extraction_result)."""
    doc_type = doc["doc_type"]
    file_bytes = _b64_to_bytes(doc["file_bytes_b64"])
    content_type = doc["content_type"]

    try:
        if doc_type == "application_form":
            from application_form_extractor import extract_application_form
            result = extract_application_form(file_bytes)

        elif doc_type == "government_id":
            from ocr_extractor import extract_government_id
            result = extract_government_id(file_bytes, content_type)

        elif doc_type == "policy_illustration":
            from illustration_extractor import extract_policy_illustration
            result = extract_policy_illustration(file_bytes)

        else:
            result = {"error": f"No extractor for doc_type: {doc_type}"}

    except Exception as exc:
        result = {"error": str(exc)}

    return doc_type, result


def extract_documents(state: CaseState) -> dict:
    """
    Run all document extractors in parallel using a thread pool.
    Each extractor is a blocking call (OpenAI API / OCR / pdfplumber).
    """
    documents = state.get("documents") or []
    if not documents:
        return {"extractions": {}}

    extractions: dict = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(documents)) as pool:
        futures = {pool.submit(_extract_one, doc): doc for doc in documents}
        for future in concurrent.futures.as_completed(futures):
            doc_type, result = future.result()
            extractions[doc_type] = result

    return {"extractions": extractions}


# ── Node 3: run_rules ──────────────────────────────────────────────────────────

def run_rules(state: CaseState) -> dict:
    """
    Run NB requirements check, cross-document validations, and scoring.
    Also builds the findings list used by the human-review node.
    Re-runs after human corrections so reviewer_actions are applied first.
    """
    from nb_requirements import evaluate_nb_requirements
    from validator import run_validations
    from scorer import score_case, score_completeness

    extractions = state.get("extractions") or {}
    reviewer_actions = state.get("reviewer_actions") or []

    # Apply any reviewer corrections to the extractions before re-evaluating
    if reviewer_actions:
        extractions = _apply_reviewer_corrections(extractions, reviewer_actions)

    product_type = state.get("product_type", "UNKNOWN")
    nb_reqs = evaluate_nb_requirements(extractions, product_type=product_type)
    validations = run_validations(extractions)
    completeness = score_completeness(extractions, product_type=product_type)
    case_score, case_status = score_case(completeness, validations)

    critical_flags = [
        v for v in validations
        if v["severity"] == "critical" and v["status"] in ("fail", "unverified")
    ]
    warnings = [
        v for v in validations
        if v["severity"] == "warning" and v["status"] in ("fail", "unverified")
    ]

    # Build findings list from NB requirements misses + validation failures
    findings = _build_findings(nb_reqs, critical_flags, warnings)

    # Preserve reviewed/waived status from previous reviewer actions
    findings = _merge_finding_statuses(findings, reviewer_actions)

    open_blocking = any(
        f["severity"] == "blocking" and f["status"] == "open"
        for f in findings
    )
    open_attention = any(
        f["severity"] == "attention" and f["status"] == "open"
        for f in findings
    )
    needs_attention = open_blocking or open_attention

    return {
        "extractions": extractions,
        "nb_requirements": nb_reqs,
        "validations": validations,
        "completeness": completeness,
        "case_score": case_score,
        "case_status": case_status,
        "critical_flags": critical_flags,
        "warnings": warnings,
        "findings": findings,
        "needs_attention": needs_attention,
    }


def _apply_reviewer_corrections(extractions: dict, actions: list) -> dict:
    """
    Apply override corrections from reviewer actions back into extractions
    so the rules engine re-evaluates with corrected values.
    """
    import copy
    corrected = copy.deepcopy(extractions)

    for action in actions:
        if action.get("action") != "override":
            continue
        corrected_value = action.get("corrected_value")
        rule_id = action.get("finding_rule_id", "")

        # rule_id format: "doc_type.field_name" e.g. "application_form.nominee_relationship"
        if "." in rule_id:
            doc_type, field = rule_id.split(".", 1)
            if doc_type in corrected and isinstance(corrected[doc_type], dict):
                corrected[doc_type][field] = corrected_value

    return corrected


def _build_findings(nb_reqs: dict, critical_flags: list, warnings: list) -> list[Finding]:
    """Convert NB requirement misses and validation failures into findings."""
    findings: list[Finding] = []

    def _safe_id(label: str) -> str:
        import re
        return re.sub(r"[^a-z0-9_]", "_", label.lower().replace(" ", "_"))

    # From NB requirements — missing crucial fields are blocking
    for req in nb_reqs.get("crucial", []):
        if req["status"] == "missing":
            findings.append(Finding(
                rule_id=f"nb_crucial.{_safe_id(req['requirement'])}",
                severity="blocking",
                description=f"Missing: {req['requirement']}",
                note=req.get("note") or f"This field is required and was not found on the {req.get('source', 'document')}. Please request the client or FA to provide it.",
                source=req.get("source", ""),
                triggered_by=req.get("source", ""),
                status="open",
            ))
        elif req["status"] == "present" and req.get("note") and "required" in req["note"].lower():
            # Present but triggers an external document requirement
            findings.append(Finding(
                rule_id=f"nb_trigger.{_safe_id(req['requirement'])}",
                severity="attention",
                description=f"Follow-up required: {req['requirement']}",
                note=req["note"],
                source=req.get("source", ""),
                triggered_by=req.get("source", ""),
                status="open",
            ))

    # From NB requirements — missing minor fields are attention
    for req in nb_reqs.get("minor", []):
        if req["status"] == "missing":
            findings.append(Finding(
                rule_id=f"nb_minor.{_safe_id(req['requirement'])}",
                severity="attention",
                description=f"Missing: {req['requirement']}",
                note=req.get("note") or f"This field was not found on the {req.get('source', 'document')}.",
                source=req.get("source", ""),
                triggered_by=req.get("source", ""),
                status="open",
            ))
        elif req["status"] == "external_document_required":
            findings.append(Finding(
                rule_id=f"nb_external.{_safe_id(req['requirement'])}",
                severity="attention",
                description=f"External document required: {req['requirement']}",
                note=req.get("note", req["requirement"]),
                source=req.get("source", ""),
                triggered_by=req.get("source", ""),
                status="open",
            ))

    # From cross-document validation failures
    for v in critical_flags:
        vals = v.get("values", {})
        vals_text = "; ".join(f"{k}: {val}" for k, val in vals.items()) if vals else ""
        findings.append(Finding(
            rule_id=f"validation.{v['check']}",
            severity="blocking",
            description=v["message"],
            note=(
                f"Values compared — {vals_text}. "
                "Verify with the original documents and use Override if a correction is needed."
            ) if vals_text else "Verify with the original documents.",
            source="Cross-document check",
            triggered_by=v["check"],
            status="open",
        ))
    for w in warnings:
        vals = w.get("values", {})
        vals_text = "; ".join(f"{k}: {val}" for k, val in vals.items()) if vals else ""
        findings.append(Finding(
            rule_id=f"validation.{w['check']}",
            severity="advisory",
            description=w["message"],
            note=(
                f"Values compared — {vals_text}. "
                "Minor discrepancies may be acceptable; confirm or waive as appropriate."
            ) if vals_text else None,
            source="Cross-document check",
            triggered_by=w["check"],
            status="open",
        ))

    return findings


def _merge_finding_statuses(
    findings: list[Finding], reviewer_actions: list
) -> list[Finding]:
    """Carry over reviewed/waived statuses from previous reviewer actions."""
    action_map = {a["finding_rule_id"]: a["action"] for a in reviewer_actions}
    for finding in findings:
        action = action_map.get(finding["rule_id"])
        if action == "waive":
            finding["status"] = "waived"
        elif action in ("confirm", "override"):
            finding["status"] = "reviewed"
    return findings


# ── Conditional edge: route_after_rules ────────────────────────────────────────

def route_after_rules(state: CaseState) -> str:
    """Return the next node name based on whether human review is needed."""
    return "human_review" if state.get("needs_attention") else "finalize"


# ── Node 4: human_review ───────────────────────────────────────────────────────

def human_review(state: CaseState) -> dict:
    """
    Pause the graph and present open findings to the human reviewer.
    LangGraph's interrupt() serialises the pause point — the graph resumes
    when the /api/resume-case endpoint calls graph.invoke() with a Command.

    The interrupt payload is what the frontend receives as the "needs attention"
    response. The reviewer's response (list of ReviewerAction dicts) is passed
    back via Command(resume=...) and becomes the return value of interrupt().
    """
    from langgraph.types import interrupt

    open_findings = [f for f in (state.get("findings") or []) if f["status"] == "open"]

    reviewer_response = interrupt({
        "case_id": state["case_id"],
        "case_score": state.get("case_score"),
        "case_status": state.get("case_status"),
        "open_findings": open_findings,
        "extractions": state.get("extractions"),
    })

    # reviewer_response is the list of ReviewerAction dicts passed by the frontend
    actions = reviewer_response if isinstance(reviewer_response, list) else []

    return {"reviewer_actions": actions}


# ── Node 5: finalize ───────────────────────────────────────────────────────────

def finalize(state: CaseState) -> dict:
    """
    Terminal node. Re-evaluates case_status after any reviewer actions and
    marks remaining open findings as advisory (human has cleared or accepted them).
    Nothing is submitted — this produces the output the UI renders as the modal.
    """
    findings = state.get("findings") or []

    # Any finding still open after finalize is implicitly accepted
    for finding in findings:
        if finding["status"] == "open":
            finding["status"] = "reviewed"

    # Promote status if all blocking issues are resolved
    unresolved_blocking = [
        f for f in findings
        if f["severity"] == "blocking" and f["status"] not in ("reviewed", "waived")
    ]

    case_status = state.get("case_status", "Incomplete / Refer Back")
    if not unresolved_blocking and case_status == "Needs Attention":
        case_status = "Ready for Review"

    return {
        "findings": findings,
        "case_status": case_status,
    }
