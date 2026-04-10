"""
Evaluates NB (New Business) requirements against the extracted document data.

Validation is gated by form category (derived from product_type):

  health        EAZY_HEALTH, IHP
                Requires: height/weight/health declaration, Section E dependents
                Does NOT require: Question #14, fund direction, payout option, FNA/IRPQ

  life_non_gae  UL_NON_GAE, TRAD_NON_GAE
                Requires: full underwriting (height/weight), Question #14, payout option
                UL also requires: fund direction, IRPQ
                Both require: FNA

  life_gae      UL_GAE, TRAD_GAE
                Guaranteed acceptance — does NOT require height/weight/health declaration
                Still requires: Question #14, payout option
                UL_GAE also requires: fund direction, IRPQ

  unknown       Run maximum checks, flag everything for review
"""

from datetime import date, datetime
from typing import Any

from form_type import (
    form_category,
    requires_medical_uw,
    requires_question_14,
    requires_fund_direction,
    requires_payout_option,
    requires_fna,
    requires_irpq,
)


def _get(extractions: dict, doc: str, field: str) -> Any:
    return (extractions.get(doc) or {}).get(field)


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return True
    return str(value).strip() != ""


def _resolve_age(extractions: dict) -> int | None:
    dob_str = _get(extractions, "application_form", "date_of_birth")
    if dob_str:
        try:
            dob = datetime.strptime(str(dob_str), "%Y-%m-%d").date()
            today = date.today()
            return (
                today.year - dob.year
                - ((today.month, today.day) < (dob.month, dob.day))
            )
        except ValueError:
            pass

    age_val = _get(extractions, "policy_illustration", "insured_age")
    if age_val is not None:
        try:
            return int(str(age_val).strip())
        except (ValueError, TypeError):
            pass

    return None


def _req(label: str, source: str, present: bool, note: str | None = None) -> dict:
    r = {
        "requirement": label,
        "source": source,
        "status": "present" if present else "missing",
    }
    if note:
        r["note"] = note
    return r


def _not_applicable(label: str, source: str, reason: str) -> dict:
    return {
        "requirement": label,
        "source": source,
        "status": "not_required",
        "note": reason,
    }


def evaluate_nb_requirements(extractions: dict, product_type: str = "UNKNOWN") -> dict:
    """
    Return a structured NB requirements report gated by the identified product/form type.

    Result shape:
    {
        "insured_age": int | None,
        "is_legal_age": bool | None,
        "product_type": str,
        "form_category": str,
        "crucial": [ { requirement, source, status, note? }, ... ],
        "minor":   [ { requirement, source, status, note? }, ... ],
    }
    """
    age = _resolve_age(extractions)
    is_legal_age: bool | None = None if age is None else age >= 18
    cat = form_category(product_type)

    crucial: list[dict] = []
    minor: list[dict] = []

    # ── C1: Application number ────────────────────────────────────────────────
    app_number = _get(extractions, "application_form", "application_number")
    crucial.append({
        "requirement": "Application number present",
        "source": "Application Form",
        "status": "present" if _present(app_number) else "missing",
        "note": (
            f"Application No: {app_number}" if _present(app_number)
            else "Application number not found — verify the correct form version is used. "
                 "Incorrect form will result in rejection."
        ),
    })

    # ── C2: Age and gender ────────────────────────────────────────────────────
    age_present = (
        _present(_get(extractions, "application_form", "date_of_birth"))
        or _present(_get(extractions, "policy_illustration", "insured_age"))
    )
    crucial.append(_req(
        "Insured age (Date of Birth)",
        "Application Form / Sales Illustration",
        age_present,
        "Affects premium calculation. Check for Substandard SI rating."
        + (f" Resolved age: {age}." if age is not None else ""),
    ))

    gender_present = (
        _present(_get(extractions, "application_form", "gender"))
        or _present(_get(extractions, "policy_illustration", "insured_gender"))
    )
    crucial.append(_req(
        "Insured gender",
        "Application Form / Sales Illustration",
        gender_present,
        "Required for premium calculation.",
    ))

    is_substandard = _get(extractions, "policy_illustration", "is_substandard")
    if is_substandard is True:
        crucial.append({
            "requirement": "Substandard SI flag",
            "source": "Sales Illustration",
            "status": "present",
            "note": "Illustration is marked Substandard — additional underwriting requirements apply. "
                    "Notify underwriting team.",
        })

    # ── C3: Medical underwriting fields (health + life_non_gae only) ──────────
    if requires_medical_uw(product_type):
        crucial.append(_req(
            "Height",
            "Application Form — Section E",
            _present(_get(extractions, "application_form", "height_cm")),
            "Required for underwriting assessment. Found in the health declaration section.",
        ))
        crucial.append(_req(
            "Weight",
            "Application Form — Section E",
            _present(_get(extractions, "application_form", "weight_kg")),
            "Required for underwriting assessment. Found in the health declaration section.",
        ))
        health_answered = _get(extractions, "application_form", "health_declaration_answered")
        crucial.append({
            "requirement": "Health declaration answered",
            "source": "Application Form — Section E",
            "status": "present" if health_answered is True else "missing",
            "note": (
                "All questions in the Non-Medical Questions / health declaration section must be answered. "
                "A 'Yes' answer requires the applicant to provide full details."
            ),
        })
    else:
        # GAE: medical underwriting not required
        minor.append(_not_applicable(
            "Height / Weight / Health declaration",
            "Application Form",
            f"Not required for {product_type} (Guaranteed Acceptance — no medical underwriting).",
        ))

    # ── C4: Question #14 — AID form trigger (life products only) ─────────────
    if requires_question_14(product_type):
        q14 = _get(extractions, "application_form", "question_14_answer")
        q14_note = (
            "A 'Yes' answer triggers the requirement for an "
            "Additional Intermediary Declaration (AID) Form + proof of Applicant Owner's source of funds "
            "(these are separate documents not in the current submission)."
            + (f" Answer recorded: {q14}." if _present(q14) else "")
        )
        if _present(q14) and str(q14).strip().lower() == "yes":
            crucial.append({
                "requirement": "Question #14 — AID Form required",
                "source": "Application Form",
                "status": "present",
                "note": "Client answered Yes — AID Form + source of funds proof must be collected. "
                        "These are not in the submitted document set.",
            })
        else:
            crucial.append(_req(
                "Question #14 answer",
                "Application Form",
                _present(q14),
                q14_note,
            ))
    else:
        minor.append(_not_applicable(
            "Question #14",
            "Application Form",
            f"Not applicable for {product_type} (health insurance — AID trigger does not apply).",
        ))

    # ── C5: Payout option (life products only) ────────────────────────────────
    if requires_payout_option(product_type):
        payout = _get(extractions, "application_form", "payout_option")
        crucial.append(_req(
            "Payout option",
            "Application Form",
            _present(payout),
            (
                "If 'Automatic transfer to my account' is selected AND the fund direction is "
                "Dividend Paying Fund, proof of bank account ownership is required (external document)."
                + (f" Selected: {payout}." if _present(payout) else "")
            ),
        ))
    else:
        minor.append(_not_applicable(
            "Payout option",
            "Application Form",
            f"Not applicable for {product_type} (health reimbursement product — no cash payout option).",
        ))

    # ── C6: US person / FATCA ─────────────────────────────────────────────────
    is_us = _get(extractions, "application_form", "is_us_person")
    pob = _get(extractions, "application_form", "place_of_birth")
    nat = _get(extractions, "application_form", "nationality")
    us_fields_present = _present(pob) or _present(nat) or is_us is not None

    if is_us is True:
        us_note = (
            "US indicia detected — Addendum to Client Information Form (ACIF) is required. "
            "This is an external document not in the current submission. "
            "If the client confirms US person status, a W-9 Form is also needed. "
            "If they deny, W-8BEN (individual) or W-8BEN-E (entity) + non-US passport are needed."
        )
    elif is_us is False:
        us_note = "No US indicia detected. ACIF / W-9 not required."
    else:
        us_note = (
            "Could not determine US person status — place of birth, nationality, and US person checkbox "
            "fields were not all found. Reviewer must verify manually against the original form."
        )

    crucial.append({
        "requirement": "US person / FATCA check",
        "source": "Application Form",
        "status": "present" if us_fields_present else "missing",
        "note": us_note,
        "values": {"place_of_birth": pob, "nationality": nat, "is_us_person": is_us},
    })

    # ── C7: Contact details ───────────────────────────────────────────────────
    crucial.append(_req(
        "Email address",
        "Application Form",
        _present(_get(extractions, "application_form", "email")),
        "Mandatory — required for e-Policy delivery, OTP, and notifications. "
        "If missing, FSS must contact the FA to provide.",
    ))
    crucial.append(_req(
        "Mobile / contact number",
        "Application Form",
        _present(_get(extractions, "application_form", "phone")),
        "Mandatory — required for SMS notifications and OTP. "
        "If missing, FSS must contact the FA to provide.",
    ))

    # ── C8: Preferred mailing address ─────────────────────────────────────────
    preferred_mail = _get(extractions, "application_form", "preferred_mailing_address")
    crucial.append(_req(
        "Preferred mailing address",
        "Application Form",
        _present(preferred_mail),
        "Client must tick whether correspondence should go to Present Address or Work Address. "
        "If missing, FSS must notify the FA."
        + (f" Selected: {preferred_mail}." if _present(preferred_mail) else ""),
    ))

    # ── C9–C10: Occupation and employer ──────────────────────────────────────
    occ_title = _get(extractions, "application_form", "occupation_title")
    occ_duties = _get(extractions, "application_form", "occupation_duties")
    employer_name = _get(extractions, "application_form", "employer_name")
    employer_addr = _get(extractions, "application_form", "employer_address")

    minor.append({
        "requirement": "Occupation title",
        "source": "Application Form",
        "status": "present" if _present(occ_title) else "missing",
        "note": (
            f"Occupation: {occ_title}." if _present(occ_title)
            else "If employed, occupation title is required. FSS to notify FA if missing."
        ),
    })
    minor.append({
        "requirement": "Occupation main duties",
        "source": "Application Form",
        "status": "present" if _present(occ_duties) else "missing",
        "note": (
            f"Duties: {occ_duties}." if _present(occ_duties)
            else "If employed, nature of work / main duties is required."
        ),
    })
    minor.append({
        "requirement": "Employer / business name",
        "source": "Application Form",
        "status": "present" if _present(employer_name) else "missing",
        "note": (
            f"Employer: {employer_name}." if _present(employer_name)
            else "If employed, employer or business name is required."
        ),
    })
    minor.append({
        "requirement": "Employer / business address",
        "source": "Application Form",
        "status": "present" if _present(employer_addr) else "missing",
        "note": (
            f"Address: {employer_addr}." if _present(employer_addr)
            else "If employed, employer or business address is required."
        ),
    })

    # ── C11: Source of funds + annual income ──────────────────────────────────
    sof = _get(extractions, "application_form", "source_of_funds")
    income = _get(extractions, "application_form", "estimated_annual_income")
    crucial.append(_req(
        "Source of funds",
        "Application Form",
        _present(sof),
        "Required for AML compliance. "
        "If missing, FSS must notify the FA to provide."
        + (f" Declared: {sof}." if _present(sof) else ""),
    ))
    crucial.append(_req(
        "Estimated annual income",
        "Application Form",
        _present(income),
        "Required for AML compliance and suitability assessment. "
        "If missing, FSS must notify the FA to provide."
        + (f" Declared: {income}." if _present(income) else ""),
    ))

    # ── C12: High-risk client screening ───────────────────────────────────────
    crucial.append({
        "requirement": "High-risk client check (PI, PO, Beneficiaries)",
        "source": "Application Form",
        "status": "present",   # always a manual review item
        "note": (
            "Reviewer must verify that the Proposed Insured, Applicant Owner, and all beneficiaries "
            "are not classified as High-Risk clients (PEPs, their relatives, or close associates). "
            "If any are High-Risk: AID Form + proof of source of funds are required. "
            "For Remittance Agents, Money Changers, NGOs: additional business registration and "
            "AMLC Certificate are also needed."
        ),
    })

    # ── C13: Fund direction (UL products only) ────────────────────────────────
    if requires_fund_direction(product_type):
        fund_dir_form = _get(extractions, "application_form", "fund_direction")
        fund_dir_si = _get(extractions, "policy_illustration", "fund_direction")
        fund_present = _present(fund_dir_form) or _present(fund_dir_si)
        crucial.append({
            "requirement": "Fund direction declared",
            "source": "Application Form / Sales Illustration",
            "status": "present" if fund_present else "missing",
            "note": (
                f"Fund direction: {fund_dir_form or fund_dir_si}. "
                "Ensure this matches the fund direction on the Sales Illustration."
                if fund_present else
                "Fund direction is required for Unit-Linked products. "
                "Not found on the application form or Sales Illustration — request from FA."
            ),
        })
    else:
        minor.append(_not_applicable(
            "Fund direction",
            "Application Form",
            f"Not applicable for {product_type}.",
        ))

    # ── C14: Place and date of signing ────────────────────────────────────────
    signing_place = _get(extractions, "application_form", "signing_place")
    signing_date = _get(extractions, "application_form", "signing_date")
    crucial.append(_req(
        "Place of signing",
        "Application Form — Signature page",
        _present(signing_place),
        "Must be indicated on the signature page. "
        "If missing, FSS must notify the FA."
        + (f" Location recorded: {signing_place}." if _present(signing_place) else ""),
    ))
    crucial.append(_req(
        "Date of signing",
        "Application Form — Signature page",
        _present(signing_date),
        "Must be indicated on the signature page. "
        "If missing, FSS must notify the FA."
        + (f" Date recorded: {signing_date}." if _present(signing_date) else ""),
    ))

    # ── C15: Signatures ───────────────────────────────────────────────────────
    payor_sig = _get(extractions, "application_form", "payor_signature_present")
    crucial.append({
        "requirement": "Payor / Applicant Owner signature",
        "source": "Application Form — Signature page",
        "status": "present" if payor_sig is True else "missing",
        "note": (
            "Applicant Owner signature present."
            if payor_sig is True else
            "Applicant Owner signature is missing from the signature page. "
            "The application cannot proceed without it."
        ),
    })

    fa_sig = _get(extractions, "application_form", "fa_signature_present")
    crucial.append({
        "requirement": "Financial Advisor signature",
        "source": "Application Form — Signature page",
        "status": "present" if fa_sig is True else "missing",
        "note": (
            "FA signature present."
            if fa_sig is True else
            "FA signature is missing. All applications require the FA to sign."
        ),
    })

    insured_sig = _get(extractions, "application_form", "insured_signature_present")
    if is_legal_age is True:
        sig_status = "present" if insured_sig is True else "missing"
        sig_note = (
            f"Insured is of legal age ({age}) — signature is required. "
            + ("Signature present." if insured_sig is True
               else "Signature missing from the Proposed Insured block on the signature page.")
        )
    elif is_legal_age is False:
        sig_status = "not_required"
        sig_note = (
            f"Insured is a minor (age {age}) — insured signature is not required. "
            "The Applicant Owner must sign on behalf of the minor. "
            "Authorization to Insure Child document may also be required if the AO is not a parent."
        )
    else:
        sig_status = "present" if insured_sig is True else "missing"
        sig_note = (
            "Insured age could not be determined — verify whether the insured is of legal age. "
            "If 18+, the insured's signature is mandatory."
        )

    crucial.append({
        "requirement": "Insured (Proposed Insured) signature",
        "source": "Application Form — Signature page",
        "status": sig_status,
        "note": sig_note,
    })

    # ── C16: Beneficiary info ─────────────────────────────────────────────────
    crucial.append(_req(
        "Designated beneficiary name",
        "Application Form",
        _present(_get(extractions, "application_form", "nominee_name")),
        "Beneficiary name is required. "
        "If the beneficiary is not an immediate family member, insurable interest must be justified "
        "on page 2 of the Agent's Confidential Report (ACR).",
    ))
    crucial.append(_req(
        "Beneficiary relationship to insured",
        "Application Form",
        _present(_get(extractions, "application_form", "nominee_relationship")),
        "Relationship is required for underwriting assessment. "
        "Non-immediate family members trigger insurable interest verification.",
    ))

    # ── Minor: Payment method ─────────────────────────────────────────────────
    payment_method = _get(extractions, "application_form", "payment_method")
    is_direct_debit = isinstance(payment_method, str) and "debit" in payment_method.lower()
    minor.append({
        "requirement": "Payment method",
        "source": "Application Form",
        "status": "present" if _present(payment_method) else "missing",
        "note": (
            "Direct Debit selected — Auto-Debit Arrangement (ADA) Enrollment Form is required. "
            "This is an external document not in the current submission."
            if is_direct_debit else
            (f"Payment method: {payment_method}." if _present(payment_method)
             else "Payment method not found on the form.")
        ),
    })

    # ── Minor: Valid government ID ────────────────────────────────────────────
    id_type = _get(extractions, "government_id", "id_type")
    id_number = _get(extractions, "government_id", "id_number")
    minor.append(_req(
        "Valid government ID",
        "Government ID",
        _present(id_type) and _present(id_number),
        "A photocopy of a valid ID with 3 specimen signatures is required. "
        "The FA must validate the copy against the original. "
        + (f"Detected: {id_type}." if _present(id_type) else "ID type not detected — check submitted copy."),
    ))

    # ── Minor: Payment slip ───────────────────────────────────────────────────
    minor.append({
        "requirement": "Payment slip",
        "source": "Not submitted",
        "status": "external_document_required",
        "note": (
            "Payment slip is required but was not included in the submitted documents. "
            "Verify: premium amount matches the Sales Illustration, payment is made to the correct "
            "merchant name, and the application number on the slip matches the form. "
            "Monthly mode requires 2 months' worth of premium."
        ),
    })

    # ── Minor: External docs by product type ─────────────────────────────────
    if requires_fna(product_type):
        minor.append({
            "requirement": "Financial Needs Analysis (FNA)",
            "source": "Not submitted",
            "status": "external_document_required",
            "note": f"FNA is required for {product_type} products. Not included in the current submission.",
        })

    if requires_irpq(product_type):
        minor.append({
            "requirement": "Investor Risk Profile Questionnaire (IRPQ)",
            "source": "Not submitted",
            "status": "external_document_required",
            "note": f"IRPQ is required for Unit-Linked products ({product_type}). Not included in the current submission.",
        })

    return {
        "insured_age": age,
        "is_legal_age": is_legal_age,
        "product_type": product_type,
        "form_category": cat,
        "crucial": crucial,
        "minor": minor,
    }
