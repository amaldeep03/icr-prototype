# ICR Intelligent Onboarding Prototype
## A Plain-Language Technical Guide for Insurance Operations Managers

---

# 1. Executive Summary

The ICR Intelligent Onboarding prototype is a software tool that automates the reading and cross-checking of insurance application documents submitted by new policyholders. It extracts key data fields from an application form, a government ID, and a policy illustration, compares the data across all three documents to surface mismatches, and produces a single case score that tells an underwriter or operations manager whether a case is ready to proceed, needs correction, or must be referred back to the customer.

---

# 2. System Overview

## The Problem It Solves

In a traditional insurance onboarding process, a processor must manually open each document in a case — the completed application form, the customer's government-issued ID, and the sales illustration — and visually verify that the name, date of birth, address, sum assured, and other key fields are consistent across all documents. This is time-consuming, error-prone, and creates a bottleneck before underwriting can begin.

A mismatch — for example, a date of birth written differently on the form versus the ID — may not be caught until late in the process, causing re-work, delays, and potential compliance issues.

## What the System Does

The ICR system replaces that manual check with an automated pipeline:

1. The user uploads up to three documents through a web interface.
2. The system reads each document and extracts structured data fields.
3. It compares matching fields across documents and flags any discrepancies.
4. It calculates a single case score and assigns a traffic-light status.
5. The result — all extracted values, every comparison outcome, and the final score — is displayed on screen for the underwriter to review in minutes rather than hours.

## Who Uses It

The primary user is an insurance operations manager, case processor, or underwriter at a Philippine life insurance company (specifically calibrated for Allianz PNB Life Insurance products). The system is a decision-support tool: it does not approve or reject cases, it surfaces information so the human reviewer can make a faster, better-informed decision.

---

# 3. Document Types Accepted

The system accepts three document types. All three can be submitted as PDF, JPG, PNG, or WebP files.

| Document Type | What It Is | Fields Extracted | Extraction Tool |
|---|---|---|---|
| **Application Form** | The Allianz PNB Life Simplified Issuance Offer (SIO) form completed by the customer | Full name, date of birth, gender, civil status, address, postcode, phone, email, nominee name, nominee relationship, sum assured, plan name, payment frequency | GPT-4o Vision (OpenAI — data sent to OpenAI API) |
| **Government ID** | A Philippine government-issued photo ID: BIR TIN Card, LTO Driver's License, or PhlPost Postal Identity Card (old or new design) | ID type, ID number, full name, date of birth, address, postcode, gender | Tesseract OCR (fully local — data never leaves the machine) |
| **Policy Illustration** | The Allianz Sales Illustration document prepared by the agent | Plan name, policy term, premium payment term, sum assured, annual premium, applicant name, applicant date of birth, maturity benefit, death benefit | pdfplumber text extraction + GPT-4o Mini (OpenAI — text only, cheaper than vision) |

**Important note on the government ID:** Because government IDs contain highly sensitive identity data, a deliberate design decision was made to process them entirely on the local machine using Tesseract OCR. No government ID image or text is ever transmitted to an external server or third-party API.

---

# 4. How Extraction Works

## Three Different Tools for Three Different Jobs

### GPT-4o Vision (Application Form only)

GPT-4o is a multimodal AI model from OpenAI that can "read" an image of a document the same way a person would — understanding layout, handwriting, printed text, checkboxes, and tables in context.

**How it works, step by step:**

1. If the document is a PDF, the system converts the first page into a high-resolution PNG image (at 200 DPI).
2. The image is encoded in Base64 format and sent to the OpenAI API along with a detailed prompt that specifies exactly which fields to extract and what format to return them in.
3. The model returns a structured JSON response — a clean list of field names and their extracted values.
4. A date-normalisation step is applied: because the application form labels the date of birth as month/day/year (mm/dd/yyyy), but AI models sometimes read it as day/month/year, the system detects and corrects any swapped month and day values.

**Why this approach for the application form:** The SIO form contains handwriting, ticked checkboxes, and a fixed printed layout. GPT-4o vision handles these reliably. The form is one page, so a single-image call captures everything.

---

### pdfplumber + GPT-4o Mini (Policy Illustration)

Policy illustrations are multi-page PDFs (typically 3–10 pages) with key information scattered across different sections: the applicant name and plan on page 1, premium schedules in a table on page 3 or 4, and benefit summaries elsewhere. Sending a single page image to a vision model misses most of the data.

The system uses a two-step pipeline:

**Step 1 — Text and table extraction (pdfplumber)**

pdfplumber reads all pages of the PDF and extracts clean text without converting to an image. Tables (premium schedules, benefit tables) are extracted separately and rendered as pipe-separated rows so the model can read them in structured form, rather than having values collapse into unreadable flattened text.

The full document text — all pages, all tables — is assembled into a single structured string with clear page markers.

**Step 2 — Single LLM call (GPT-4o Mini)**

The full extracted text is sent to GPT-4o Mini with a comprehensive prompt asking for all nine fields at once. Because the input is plain text rather than an image, the cheaper Mini model is sufficient and handles the task accurately. A single call covers the entire document regardless of how many pages it has.

A date-normalisation step is applied to the output for the same mm/dd/yyyy vs dd/mm/yyyy reason as the application form.

**Why this approach is better than full-document vision:**

| | Previous approach (vision, page 1 only) | Current approach (pdfplumber + text) |
|---|---|---|
| Pages covered | 1 | All pages |
| Tables | Flattened or missed | Preserved as structured rows |
| Model cost | GPT-4o (higher cost) | GPT-4o Mini (≈10× cheaper) |
| OCR hallucination risk | Present (image → text) | Eliminated (native text extraction) |
| Works across product types | Inconsistent | Consistent — semantic content drives extraction |

**Debug tool:** The `/api/test-illustration-extraction` endpoint returns the raw extracted text page by page, including all tables as the LLM will receive them, before any extraction call runs. Use this to verify that pdfplumber is capturing the right content before spending API tokens.

---

### Tesseract OCR (Government ID Only)

Tesseract is an open-source text recognition engine that runs entirely on the local computer with no internet connection.

**How it works, step by step:**

1. The uploaded ID image is loaded and converted to a standard format. WebP images, which can cause issues with some processing tools, are re-encoded as PNG before being passed to Tesseract.
2. The system detects whether the ID has a light or dark background. The newer PhlPost Postal ID has a dark background and requires the image colours to be inverted before text can be read.
3. Multiple image preprocessing strategies are tested in parallel:
   - **Standard:** grayscale, increase contrast, sharpen
   - **Inverted:** flip light/dark for dark-background cards
   - **Binarised:** convert all pixels to pure black or white to eliminate background patterns
4. Each variant is run through Tesseract using two different page-layout modes (full-page scan and uniform block), producing up to eight candidate outputs.
5. The output with the most readable alphanumeric content is selected as the best result.
6. The system identifies the ID type by scanning for keywords: "BUREAU OF INTERNAL REVENUE" → BIR TIN Card; "LAND TRANSPORTATION" → Driver's License; "PHLPOST" → Postal ID.
7. ID-type-specific parsing rules extract the structured fields:

| ID Type | Name Extraction | DOB Extraction | ID Number Extraction |
|---|---|---|---|
| BIR TIN Card | Lines immediately above the TIN number line | "DATE OF BIRTH: MM/DD/YYYY" label | "TIN: XXX-XXX-XXX-XXX" pattern |
| LTO Driver's License | "LASTNAME,FIRSTNAME" token (single-word, no spaces) | Data row containing nationality code "PHL" and gender | Pattern matching license format (e.g., N03-12-123434) |
| PhlPost Postal ID | First ALL-CAPS multi-word line that is not a header | "DD MMM YY" date format with fallback for OCR-corrupted digits | 12-digit number following "PAN" or "PRN" label |

---

# 5. Cross-Document Validation

Once data has been extracted from all uploaded documents, the system runs seven comparison checks. Each check takes one field from one document and compares it to the equivalent field in another document.

## The Seven Validation Checks

| # | Check | Documents | Field | Method | Threshold | Severity |
|---|---|---|---|---|---|---|
| 1 | Name: Form vs ID | Application Form ↔ Government ID | full_name | Fuzzy (token sort) | Score ≥ 85 | **Critical** |
| 2 | Name: Form vs Policy | Application Form ↔ Policy Illustration | full_name / applicant_name | Fuzzy (token sort) | Score ≥ 85 | **Critical** |
| 3 | DOB: Form vs ID | Application Form ↔ Government ID | date_of_birth | Exact match | Identical | **Critical** |
| 4 | DOB: Form vs Policy | Application Form ↔ Policy Illustration | date_of_birth / applicant_dob | Exact match | Identical | **Critical** |
| 5 | Postcode: Form vs ID | Application Form ↔ Government ID | pincode | Exact match | Identical | Warning |
| 6 | Sum Assured: Form vs Policy | Application Form ↔ Policy Illustration | sum_assured | Numeric ±1% | Difference ≤ 1% | Warning |
| 7 | Plan Name: Form vs Policy | Application Form ↔ Policy Illustration | plan_name | Fuzzy (token sort) | Score ≥ 80 | Warning |

## How Each Method Works

### Exact Match
Values are compared character-for-character after trimming spaces and converting to lowercase. Any difference is a failure.

- PASS: `"1989-01-16"` vs `"1989-01-16"`
- FAIL: `"1989-01-16"` vs `"1989-16-01"` (day and month transposed)

### Fuzzy Match — Token Sort Ratio
Punctuation is removed, text is lowercased, words are sorted alphabetically, then compared. This makes word order irrelevant — the format of names on ID cards (first-name-first) vs forms (last-name-first, with comma) is handled automatically.

Score ranges from 0 to 100. A score at or above the threshold is a pass.

- PASS: `"LORENCO, MARIA CRISTINA"` vs `"MARIA CRISTINA LORENCO"` → score 100
- PASS: `"EAZY HEALTH SILVER"` vs `"Allianz eAZy Health Silver"` → score 82 (above 80 threshold)
- FAIL: `"DELA CRUZ, JUAN"` vs `"SANTOS, PEDRO"` → score ~10

### Numeric Tolerance (±1%)
Both values are stripped of currency symbols, commas, and spaces, then compared as numbers. A difference of 1% or less is a pass.

- PASS: `"300,000"` vs `"300000"` → 0% difference
- FAIL: `"300000"` vs `"500000"` → 40% difference

## The Three Possible Statuses

| Status | What It Means | Display |
|---|---|---|
| **Pass** | The two values agree within the threshold | ✅ Green |
| **Fail** | The two values disagree beyond the threshold | ❌ Red |
| **Unverified** | At least one value was not extracted (field missing from document) | 🔍 Grey |

The message shown to the reviewer will always name the specific field(s) that are missing, for example:
> *"Could not compare — missing: policy_illustration › applicant_dob"*

---

# 6. Mismatch Flagging

## Critical Flags

Raised when any of the four **critical** checks results in **Fail** or **Unverified**.

**The four critical checks:** Name (form vs ID), Name (form vs policy), DOB (form vs ID), DOB (form vs policy).

**Why these are critical:** Name and date of birth are the primary identifiers confirming all documents belong to the same person. Any failure suggests a data entry error, a document mix-up, or a potential fraud indicator. Cases with unresolved critical flags should not proceed to underwriting without manual investigation.

**What the reviewer should do:**
- Compare the displayed values side by side.
- Determine whether the difference is a formatting issue (e.g., comma in name), a data entry error, or a genuine inconsistency.
- Contact the agent or customer for a corrected form or replacement document if needed.

## Warnings

Raised when any of the three **warning** checks results in **Fail** or **Unverified**.

**The three warning checks:** Postcode (form vs ID), Sum Assured (form vs policy), Plan Name (form vs policy).

**Why these are warnings:** A postcode mismatch may mean a recent address change. A sum assured discrepancy may mean the illustration was updated after the form was signed. Plan name differences are often formatting variations.

**What the reviewer should do:** Use judgement. If the sum assured differs significantly, verify which figure is correct before issuing the policy.

---

# 7. Completeness Scoring

## Required Fields Per Document

| Document | Required Fields | Total |
|---|---|---|
| Application Form | full_name, date_of_birth, gender, civil_status, address, phone, email, nominee_name, nominee_relationship, sum_assured, plan_name, payment_frequency | 12 |
| Government ID | id_type, id_number, full_name, date_of_birth | 4 |
| Policy Illustration | plan_name, sum_assured, annual_premium, applicant_name, death_benefit | 5 |

## Calculation

> **Document Score = (Fields Present ÷ Total Required Fields) × 100**

Example: Policy illustration has 5 required fields. If `annual_premium` is missing:
> 4 ÷ 5 × 100 = **80%**

---

# 8. Case Score Calculation

## Step 1 — Weighted Completeness Baseline

| Document | Weight |
|---|---|
| Application Form | 50% |
| Government ID | 30% |
| Policy Illustration | 20% |

> **Baseline = (Form Score × 0.50) + (ID Score × 0.30) + (Policy Score × 0.20)**

## Step 2 — Validation Penalties

| Validation Result | Penalty |
|---|---|
| Critical check — **Fail** | −15 points |
| Critical check — **Unverified** | −7 points |
| Warning check — **Fail** | −5 points |
| Warning check — **Unverified** | 0 points |

> **Case Score = max(0, min(100, Baseline − Total Penalties))**

## Step 3 — Status Thresholds

| Score | Status |
|---|---|
| 85 – 100 | ✅ Ready for Review |
| 60 – 84 | ⚠️ Needs Attention |
| 0 – 59 | ❌ Incomplete / Refer Back |

**Worked Examples:**

*All documents complete, all checks pass:*
Baseline = 100 · Penalties = 0 · **Score = 100 — Ready for Review**

*Policy illustration missing one field (score 80%), one critical check unverified:*
Baseline = (100 × 0.50) + (100 × 0.30) + (80 × 0.20) = 96
Penalties = 7 · **Score = 89 — Ready for Review**

*Two critical failures, government ID incomplete (score 50%):*
Baseline = (100 × 0.50) + (50 × 0.30) + (100 × 0.20) = 85
Penalties = 15 + 15 + 5 = 35 · **Score = 50 — Incomplete / Refer Back**

---

# 9. Sample Case Walkthrough — LORENCO, MARIA CRISTINA

This is the built-in demo case (accessible via "Load Mock Data" in the interface).

**Policy:** Allianz eAZy Health Silver
**Application date:** July 17, 2025

## Extraction Results

**Application Form**

| Field | Value |
|---|---|
| Full Name | LORENCO, MARIA CRISTINA |
| Date of Birth | 1989-01-16 |
| Gender | Female |
| Civil Status | Single |
| Address | 517 GEN. TUAZON BLVD, BRGY. RIVERA, PASAY CITY |
| Postcode | 1717 |
| Phone | 09345678901 |
| Email | lorenco.mc@123.com |
| Nominee | LORENCO, JAMESON (Brother) |
| Sum Assured | 300,000 |
| Plan Name | EAZY HEALTH SILVER |
| Payment Frequency | Annual |

Completeness: **100%** (all 12 required fields present)

**Government ID — PhlPost Postal Identity Card**

The card has a dark background. The system applies inverted preprocessing, identifies it as a Postal ID from the "PHLPOST" keyword, and extracts:

| Field | Value |
|---|---|
| ID Type | Postal ID |
| ID Number | 100041034067 |
| Full Name | MARIA CRISTINA LORENCO |
| Date of Birth | 1989-01-16 |
| Address | 517 GEN. TUAZON BLVD, BRGY. RIVERA, 1717 PASAY CITY |
| Postcode | 1717 |

Completeness: **100%** (all 4 required fields present)

Note: The name on the ID uses first-name-first order while the form uses last-name-first. This is expected and handled by the token sort fuzzy matching.

**Policy Illustration — Allianz eAZy Health Silver**

| Field | Value |
|---|---|
| Plan Name | Allianz eAZy Health Silver |
| Sum Assured | 300,000 |
| Annual Premium (Year 1–5) | 15,600 |
| Applicant Name | Lorenco, Maria Cristina |
| Applicant DOB | **null** — illustration shows age 37, not exact DOB |
| Death Benefit | 300,000 |

Completeness: **80%** — `applicant_dob` is absent because this product's illustration shows age, not date of birth.

## Validation Results

| Check | Status | Form Value | ID / Policy Value | Score |
|---|---|---|---|---|
| Name: Form vs ID | ✅ Pass | LORENCO, MARIA CRISTINA | MARIA CRISTINA LORENCO | 88 |
| Name: Form vs Policy | ✅ Pass | LORENCO, MARIA CRISTINA | Lorenco, Maria Cristina | 100 |
| DOB: Form vs ID | ✅ Pass | 1989-01-16 | 1989-01-16 | 100 |
| DOB: Form vs Policy | 🔍 Unverified | 1989-01-16 | (null) | — |
| Postcode: Form vs ID | ✅ Pass | 1717 | 1717 | 100 |
| Sum Assured: Form vs Policy | ✅ Pass | 300000 | 300000 | 100 |
| Plan Name: Form vs Policy | ✅ Pass | EAZY HEALTH SILVER | Allianz eAZy Health Silver | 82 |

## Score Calculation

Baseline = (100 × 0.50) + (100 × 0.30) + (80 × 0.20) = **96**
Penalties = 7 (one critical unverified)
**Case Score = 89 — Ready for Review**

## What the Reviewer Sees

**1 Critical Flag:**
> DOB: Form vs Policy — Unverified. Could not compare — missing: policy_illustration › applicant_dob

**0 Warnings**

**Recommended action:** This flag is structural — the eAZy Health Silver illustration always shows age rather than DOB. The reviewer should confirm that the age on the illustration (37) is consistent with the DOB on the form (January 16, 1989). At July 2025 the applicant is 36 turning 37, which is consistent. The reviewer can note this and proceed to underwriting.

---

# 10. Limitations and Known Behaviours

## OCR Accuracy for Government IDs

- **Low-resolution images:** The system applies multiple preprocessing strategies but cannot recover genuinely blurry or pixelated text.
- **Corrupted date digits:** Tesseract frequently misreads individual digits on IDs with decorative backgrounds. The system includes fallback logic to produce partial dates, but the extracted value may still be wrong.
- **Unknown ID types:** If the system cannot identify the ID type, it falls back to a generic parser with lower accuracy.
- **Debug tool:** The `/api/test-id-ocr` endpoint returns the raw OCR text and all preprocessing candidates before any parsing, useful for diagnosing extraction failures.

## GPT-4o Extraction Limitations (Application Form)

- **Single page only:** The application form pipeline converts and sends only the first page. If any field is on page 2 or later it will not be captured (the SIO form fits on one page, so this is not expected to be an issue in practice).
- **Handwritten fields:** Heavily cursive or illegible handwriting may cause incorrect extraction without any error signal.
- **Date format edge cases:** A correction step handles the common mm/dd/yyyy vs dd/mm/yyyy confusion, but unusual formats may not be corrected.

## Policy Illustration Extraction Limitations

- **Text-based PDFs only:** The pdfplumber pipeline extracts digital text. Scanned illustration PDFs (images embedded in a PDF) will produce empty or near-empty text. In that case, the fallback vision path using the uploaded image will be used for non-PDF uploads. If a scanned PDF is submitted, extraction will return mostly null values.
- **Table formatting:** Some PDFs embed premium tables as graphics rather than text cells. pdfplumber cannot read graphic tables. The debug endpoint (`/api/test-illustration-extraction`) will show empty `tables` arrays for affected pages, making this easy to diagnose.
- **Non-standard layouts:** The prompt is calibrated for Allianz PNB Life illustration formats. Other insurers may use different section names or field arrangements that require prompt adjustments.

## Validation Design Constraints

- Only seven validation checks are currently implemented. Other fields (gender, nominee information, premium amount) are not cross-checked.
- The fuzzy name match can pass even with a meaningful difference if names share many tokens. The raw values are always shown so the reviewer can make their own judgement.
- **The DOB unverified flag on Allianz eAZy Health illustrations is structural and expected.** Every case using this product will produce this flag. Teams should establish a standard operating procedure for how to treat it.

## Score Calibration

- The weights (50% / 30% / 20%) and penalty values (−15 / −7 / −5) are configurable in the source code.
- They should be reviewed and calibrated against historical case data before production deployment.
- A case with two critical failures (name and DOB both mismatched) will lose at least 30 points from the baseline and will almost always fall into "Needs Attention" or "Incomplete / Refer Back."

## Data Privacy

- **Government ID data never leaves the local server.** All extraction is performed on-device by Tesseract.
- **Application form and policy illustration images are sent to the OpenAI API.** Teams should confirm this is consistent with data handling policies and customer consent notices before production deployment.
- **No data is persisted.** The system processes each submission in memory and returns results immediately without storing them in a database.
