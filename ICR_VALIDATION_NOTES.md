# ICR Prototype — Validation Implementation Notes

> **Scope:** Life GAE (Guaranteed Acceptance Endorsement) form only.
> **Source of truth for business rules:** `New Business Document Type.xlsx` (Allianz PNB Life NB guidelines).

---

## 1. How the System Works

### Document Inputs
Three documents are submitted:
| Document | How Extracted |
|---|---|
| Application Form (GAE, 7 pages) | 2-pass GPT-4o vision: pages 1–2 (identity/plan/Q14/payout), pages 3–4 (signatures) |
| Government ID | Tesseract OCR (runs locally — no data sent to OpenAI) |
| Sales Illustration | pdfplumber text extraction + GPT-4o-mini for field parsing |

### Pipeline
```
Upload → classify product type → extract all 3 docs (parallel)
       → evaluate NB requirements (nb_requirements.py)
       → run cross-document validations (validator.py)
       → LangGraph: run_rules → [human_review if needed] → finalize
       → return structured result to UI
```

### UI (2-page)
**Upload page** → user uploads PDFs → clicks "Run Evaluation"
**Review page** (3 tabs):
- **Key Checks** — the 8 business questions + NB Requirements Checklist
- **Validations** — cross-document data match table (Form vs. ID / SI)
- **Human Review** — open findings requiring human decision

---

## 2. The 8 Key Business Checks (Key Checks tab)

These are derived from the NB guidelines and displayed as cards in the UI.

| # | Check | Source | How |
|---|---|---|---|
| 1 | Age & Gender (Substandard SI) | Application Form + Sales Illustration | Age computed from DOB. Substandard flag read from SI extraction |
| 2 | Question #14 (PEP check) | Application Form | Reads `question_14_answer`. "Yes" triggers AID Form requirement |
| 3 | Payout option + Fund direction | Application Form + Sales Illustration | Reads `payout_option` and `fund_direction`. Auto transfer + Dividend Paying Fund → bank proof required |
| 4 | US Person / FATCA | Application Form | Reads `is_us_person`, `nationality`, `place_of_birth`. "Yes" → ACIF + W-9 required |
| 5 | Height & Weight | Application Form | Always **N/A for GAE** (Guaranteed Acceptance = no medical underwriting) |
| 6 | Email + Contact Number | Application Form | Reads `email` and `phone` fields |
| 7 | Signatures (Insured, AO, FA) | Application Form (pages 3–4) | Reads `insured_signature_present`, `payor_signature_present`, `fa_signature_present` via vision |
| 8 | Beneficiary / Relationship | Application Form | Reads `nominee_name` and `nominee_relationship` from Section B |

---

## 3. NB Requirements Checklist (full list)

Located below the 8 cards. Shows ALL items from `nb_requirements.py` gated by product type.

### Crucial Requirements (block case processing if missing)
| Requirement | How Checked |
|---|---|
| Application number | Reads `application_number` from form. Missing → likely wrong form version |
| Insured age (DOB) | From form DOB or SI insured age |
| Insured gender | From form or SI |
| Substandard SI flag | From SI `is_substandard` field |
| Question #14 answer | From form. "Yes" → triggers AID Form note |
| Payout option | From form `payout_option` |
| US Person / FATCA | From form. "Yes" → ACIF required |
| Email address | From form |
| Mobile / contact number | From form |
| Preferred mailing address | From form (Present or Work checkbox) |
| Source of funds | From form Section A (AML requirement) |
| Estimated annual income | From form Section A (AML + suitability) |
| High-risk client check | Always flagged for manual review (cannot be automated — see Section 4) |
| Fund direction | From form + SI (UL products only) |
| Place of signing | From form signature page |
| Date of signing | From form signature page |
| Payor / Applicant Owner signature | Vision detection on pages 3–4 |
| Financial Advisor signature | Vision detection on page 4 |
| Insured signature | Vision detection on page 3 (not required if insured is a minor) |
| Designated beneficiary name | From form Section B |
| Beneficiary relationship | From form Section B |

### Minor Requirements (shown in collapsible section)
| Requirement | How Checked |
|---|---|
| Height / Weight / Health declaration | Always N/A for GAE |
| Occupation title | From form |
| Occupation main duties | From form |
| Employer / business name | From form |
| Employer / business address | From form |
| Payment method | From form. Direct Debit → ADA Form required |
| Valid government ID | From ID extraction (type + number) |
| Payment slip | Always flagged as external document required |
| FNA (Financial Needs Analysis) | External document flag (not required for GAE) |
| IRPQ (Investor Risk Profile Questionnaire) | External document flag (required for UL_GAE) |

---

## 4. Cross-Document Validations (Validations tab)

All checks compare values across documents. Outcome is always **Notify FSS** (not rejection) per the Excel guidelines — a mismatch means FSS must verify with the FA before proceeding.

| Check | Documents Compared | Method | Pass Threshold |
|---|---|---|---|
| Name — Form vs. ID | Application Form ↔ Government ID | Fuzzy token sort | ≥ 85 |
| Name — Form vs. Sales Illustration | Application Form ↔ SI | Fuzzy token sort | ≥ 85 |
| Date of Birth — Form vs. ID | Application Form ↔ Government ID | Exact string match | — |
| Date of Birth — Form vs. SI | Application Form ↔ SI | Exact string match | — |
| Postal Code — Form vs. ID | Application Form ↔ Government ID | Exact string match | — |
| Sum Assured — Form vs. SI | Application Form ↔ SI | Numeric within 1% | 1% tolerance |
| Plan Name — Form vs. SI | Application Form ↔ SI | Fuzzy token sort | ≥ 80 |
| Fund Direction — Form vs. SI | Application Form ↔ SI | Fuzzy token sort | ≥ 80 |

**Fuzzy matching** uses `rapidfuzz.fuzz.token_sort_ratio` after stripping punctuation and lowercasing. This handles common variations like "JUAN, PEDRO DE LA CRUZ" vs "PEDRO JUAN DE LA CRUZ".

**Unverified** status is returned when either field is null (data could not be extracted from one or both documents). This is not a failure — it means the check could not be performed.

---

## 5. What Was Implemented from the Excel

The Excel file (`New Business Document Type.xlsx`, Validation sheet) lists checks under "PI/PO Information" and other categories with a "Remarks" column indicating either "application will be rejected" or "manual notification to FSS to verify."

### Implemented checks (and where)

| Excel Check | Implemented | Where |
|---|---|---|
| Name matches Government ID | ✅ | Validations tab — `name_match_form_vs_id` |
| Date of birth matches Government ID | ✅ | Validations tab — `dob_match_form_vs_id` |
| Address / postal code matches Government ID | ✅ | Validations tab — `pincode_match_form_vs_id` |
| US Person / US indicia (FATCA) | ✅ | Key Checks card #4 + NB Checklist |
| Mobile number present | ✅ | NB Checklist — crucial item |
| Email address present | ✅ | NB Checklist — crucial item |
| Preferred mailing address ticked | ✅ | NB Checklist — crucial item |
| Occupation title present | ✅ | NB Checklist — minor item |
| Occupation duties present | ✅ | NB Checklist — minor item |
| Employer name present | ✅ | NB Checklist — minor item |
| Employer address present | ✅ | NB Checklist — minor item |
| Source of funds declared | ✅ | NB Checklist — crucial item |
| High-risk client check (PI, PO, beneficiaries) | ✅ (manual flag) | NB Checklist — always flagged for reviewer |
| Name matches Sales Illustration | ✅ | Validations tab — `name_match_form_vs_policy` |
| Date of birth matches Sales Illustration | ✅ | Validations tab — `dob_match_form_vs_policy` |
| Sum Assured matches Sales Illustration | ✅ | Validations tab — `sum_assured_match_form_vs_policy` |
| Plan Name matches Sales Illustration | ✅ | Validations tab — `plan_name_match` |
| Fund Direction matches Sales Illustration | ✅ | Validations tab — `fund_direction_match` |
| Question #14 (PEP check) | ✅ | Key Checks card #2 + NB Checklist |
| Payout option declared | ✅ | Key Checks card #3 + NB Checklist |
| Signatures (Insured, AO, FA) | ✅ | Key Checks card #7 + NB Checklist |
| Beneficiary name + relationship | ✅ | Key Checks card #8 + NB Checklist |
| Application number present | ✅ | NB Checklist — crucial item |
| Substandard SI flag | ✅ | Key Checks card #1 |

---

## 6. What Was NOT Implemented — and Why

### 6a. Wrong form version → Rejection

**Excel says:** If the wrong version of the application form is used, the case is rejected.

**Why not automated:** There is no reliable machine-readable version number on the form. Detecting "wrong version" would require maintaining a reference of every current valid form version and comparing visual structure — this is too fragile and error-prone for automation. The `application_number` check partially covers this (missing number can indicate wrong form), but an explicit version check is not implemented.

### 6b. High-risk client classification (PI, PO, beneficiaries)

**Excel says:** If the Proposed Insured, Applicant Owner, or any beneficiary is a High-Risk Client (PEP, relative of PEP, or close associate), an AID Form and source of funds proof are required.

**Why only flagged, not automated:** Classifying someone as a PEP (Politically Exposed Person) or high-risk requires access to a PEP/sanctions watchlist database. The prototype has no external AML/PEP lookup service. The check is surfaced as a mandatory manual review item in the NB Checklist so the reviewer knows they must verify it — but the system cannot make the determination automatically.

### 6c. Remittance Agent / Money Changer / NGO — additional documents

**Excel says:** If the Applicant Owner is a Remittance Agent, Money Changer, or NGO, additional business registration documents and an AMLC Certificate are required.

**Why not automated:** This requires knowing the nature of the AO's business at a categorical level (e.g., "is this person operating an MSB?"). The occupation/employer fields extracted from the form are free-text and not reliable enough to make this classification programmatically without a high false-positive rate.

### 6d. Payment slip verification

**Excel says:** Payment slip must be verified — amount matches SI, merchant name is correct, application number on slip matches the form.

**Why not automated:** The payment slip is not one of the three submitted documents. It is a separate physical receipt. Even if submitted, matching a payment slip amount to a Sales Illustration premium requires knowing which premium figure to compare (annual, monthly, etc.), which varies by payment frequency. Flagged as "external document required" in the Minor Requirements checklist.

### 6e. ADA Enrollment Form (Auto-Debit Arrangement)

**Excel says:** If payment method is Auto-Debit, the ADA Enrollment Form must be submitted.

**Why only flagged:** The ADA form is a separate document (bank form) not included in the standard submission set. The system detects when Auto-Debit is selected and notes that the ADA form is required, but it cannot verify the form's presence because it was not submitted. Surfaced as a note in the Minor Requirements — Payment Method row.

### 6f. ACIF, W-9, W-8BEN (FATCA external documents)

**Excel says:** US indicia → ACIF required. Confirmed US person → W-9. Denied but indicia present → W-8BEN + non-US passport.

**Why only flagged:** These are external documents (bank/IRS forms) that are not part of the standard submission. The system correctly detects the trigger condition (US person = yes or US indicia present) and surfaces the requirement in the NB Checklist, but cannot verify the documents because they were not submitted.

### 6g. FNA and IRPQ documents

**Excel says:** Financial Needs Analysis required for life products. IRPQ required for Unit-Linked.

**Why only flagged:** These are separate forms completed during the sales process, typically submitted alongside the main application but not as a PDF in this system. They are flagged as `external_document_required` in the Minor Requirements so the reviewer knows to check for them in the physical file.

### 6h. AID Form (Additional Intermediary Declaration)

**Excel says:** Required when Question #14 is "Yes" or when the client is classified as high-risk.

**Why only flagged:** The AID form is a separate document. The trigger condition (Q14 = Yes) is detected and shown as a note in the NB Checklist, but the AID form itself is not submitted in this workflow.

---

## 7. Severity Policy

Per the Excel validation sheet, **no cross-document data mismatch triggers automatic rejection** in the current NB workflow. All data mismatches require a "manual notification to FSS to verify with the FA." The one action that triggers rejection (wrong form version) cannot be reliably automated (see 6a above).

This is why every failing check in both the Validations tab and the NB Requirements Checklist shows a **"Notify FSS"** button rather than a "Rejected" label. The FSS button generates a pre-filled email draft that the reviewer can edit and send to `fss@allianzpnblife.ph`.

---

## 8. Limitations and Known Gaps

| Limitation | Impact |
|---|---|
| Vision extraction accuracy | GPT-4o reads handwritten forms well but can misread poor handwriting. Scores < 85 on fuzzy match should be manually verified. |
| Tesseract OCR on low-res ID scans | If the ID scan is blurry or poorly lit, field extraction may fail. The system returns `unverified` for affected checks rather than a false pass/fail. |
| Fund direction on GAE form | The GAE application form has no fund direction field. `fund_direction` from the form is always null; the cross-doc check will always show "unverified." This is correct behavior — fund direction is confirmed from the SI only. |
| Single beneficiary | Only the first beneficiary (nominee_name + nominee_relationship) is extracted from Section B. Multiple beneficiaries and their percentage splits are not fully modelled. |
| Pincode extraction | Postal code is often written in a small box and may not be extracted cleanly from either the form or the ID. "Unverified" pincode is common and not a cause for concern unless both documents are clearly readable. |
