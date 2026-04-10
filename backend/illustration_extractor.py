"""
Chunked extraction pipeline for insurance Sales Illustration PDFs.

Strategy: pdfplumber text + table extraction → single LLM call over full document text.

Why NOT zone-based chunking for this document type:
- Keywords like "insured", "age", "name" appear in every section (boilerplate, disclaimers,
  health forms), so keyword classifiers misfire on every chunk.
- Section headers vary wildly across product types and insurers.
- The document is small (~3–10 pages); sending full text to gpt-4o-mini is <0.01 USD and
  gives the model full context to resolve ambiguous or spread-out fields.

Why pdfplumber over GPT-4o vision:
- Text extraction preserves exact values (numbers, dates) without OCR hallucination.
- Table cells (premium schedules, benefit tables) are extracted via extract_tables()
  and rendered as pipe-separated rows so the LLM sees them in structured form.
- No image encoding overhead; cheaper model (mini) is sufficient.
"""

from io import BytesIO
import pdfplumber

from extractor import _get_client, _parse_json, _normalize_dates


# ── Document text extraction ───────────────────────────────────────────────────

def _page_to_text(page, page_num: int) -> str:
    """
    Extract text and tables from a single pdfplumber page.
    Tables are rendered as pipe-separated rows so the LLM sees
    the structure instead of flattened or missing cells.
    """
    parts: list[str] = [f"=== PAGE {page_num} ==="]

    # --- Tables (premium schedules, benefit tables) ---
    tables = page.extract_tables()
    table_bboxes: list[tuple] = []
    for table_obj in page.find_tables():
        table_bboxes.append(table_obj.bbox)

    for table in tables:
        if not table:
            continue
        rows = []
        for row in table:
            if row and any(cell for cell in row if cell):
                rows.append(" | ".join(str(cell or "").strip() for cell in row))
        if rows:
            parts.append("[TABLE]")
            parts.extend(rows)
            parts.append("[/TABLE]")

    # --- Remaining narrative text ---
    text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
    if text.strip():
        parts.append(text)

    return "\n".join(parts)


def extract_full_text(file_bytes: bytes) -> str:
    """Return the complete document text (all pages, tables preserved)."""
    page_texts: list[str] = []
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            page_texts.append(_page_to_text(page, i))
    return "\n\n".join(page_texts)


# ── LLM extraction prompt ─────────────────────────────────────────────────────

_PROMPT = """You are extracting data from an Allianz PNB Life Insurance Sales Illustration
(also called a Benefit Illustration or Product Illustration). This is a Philippine insurance document.

The document text below was extracted by pdfplumber. Tables appear between [TABLE] / [/TABLE] markers
as pipe-separated rows. Page breaks are marked with === PAGE N ===.

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
  "death_benefit": "",
  "fund_direction": null
}

Field extraction rules:
- plan_name: The insurance product / plan name shown as the document title or near the top
  (e.g. "Allianz eAZy Health Silver", "Allianz Fundamental Cover").
- policy_term: Policy / coverage duration in years if stated; "Renewable" for annually-renewable
  health plans; null if not stated.
- premium_payment_term: Payment mode or term (e.g. "Annual", "5 Pay", "10 Pay").
- sum_assured: Face amount / sum assured — numeric string only (no PHP, commas, spaces).
  For health plans this is often the coverage limit / maximum benefit, not a death benefit.
- annual_premium: Total annual premium for the first policy year. Look in premium tables or
  a PREMIUM SUMMARY section. Return as numeric string only (no PHP, commas, spaces).
- applicant_name: Full name of the proposed insured / client.
- applicant_dob: Exact date of birth in YYYY-MM-DD. Return null if only age is shown — do
  NOT guess the birth year from the age.
- insured_age: Age of the insured as shown in the illustration (e.g. "37"). Return as numeric
  string. Null if not shown.
- insured_gender: Gender of the insured as shown in the illustration — "Male" or "Female".
  Null if not stated.
- is_substandard: true if the illustration is marked as "Substandard" or shows a rating/extra
  premium due to health/occupational loading; false if explicitly standard; null if not stated.
- maturity_benefit: Maturity or endowment payout if explicitly stated; null for term/health plans.
- death_benefit: Death benefit amount — numeric string only. For term plans this is the
  "Term Benefit" or "Life Benefit". For health plans it may not exist.
- fund_direction: Fund direction or declared fund allocation shown in the illustration
  (e.g. "Dividend Paying Fund", "Peso Equity Fund", "Peso Bond Fund", "Balanced Fund").
  Only present on Unit-Linked / VUL / ULAM product illustrations. Return null for health
  or traditional plans that do not have fund selection.

If a field is not found in the document, return null for that key.
No explanation, no markdown, no code fences — return only the JSON object."""


# ── Public interface ───────────────────────────────────────────────────────────

def extract_policy_illustration(file_bytes: bytes) -> dict:
    """
    Extract structured fields from a policy illustration PDF.
    Uses full-document text (all pages + tables) with a single gpt-4o-mini call.
    """
    full_text = extract_full_text(file_bytes)

    response = _get_client().chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=512,
        messages=[
            {
                "role": "system",
                "content": "You extract structured data from insurance documents. Return only valid JSON.",
            },
            {
                "role": "user",
                "content": f"{_PROMPT}\n\n---\n{full_text}",
            },
        ],
    )

    try:
        result = _parse_json(response.choices[0].message.content)
    except Exception:
        result = {
            "plan_name": None, "policy_term": None, "premium_payment_term": None,
            "sum_assured": None, "annual_premium": None, "applicant_name": None,
            "applicant_dob": None, "insured_age": None, "insured_gender": None,
            "is_substandard": None, "maturity_benefit": None, "death_benefit": None,
            "fund_direction": None,
        }

    return _normalize_dates(result, "policy_illustration")


def get_extraction_debug(file_bytes: bytes) -> dict:
    """
    Return the raw extracted text (pages + tables) without calling the LLM.
    Use this to verify that pdfplumber is picking up all sections and tables
    before spending API tokens on the extraction call.
    """
    page_data: list[dict] = []
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables()
            text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
            rendered_tables = []
            for table in tables:
                if table:
                    rows = [
                        " | ".join(str(cell or "").strip() for cell in row)
                        for row in table if row and any(cell for cell in row if cell)
                    ]
                    rendered_tables.append(rows)

            page_data.append({
                "page": i,
                "table_count": len(tables),
                "tables": rendered_tables,
                "text_length": len(text),
                "text_preview": text[:600] + ("…" if len(text) > 600 else ""),
            })

    full_text = extract_full_text(file_bytes)
    return {
        "pages": page_data,
        "full_text_length": len(full_text),
        "full_text": full_text,
    }
