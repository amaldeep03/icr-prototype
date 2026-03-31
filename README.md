# ICR Intelligent Onboarding — Prototype

A working prototype of an Intelligent Case Review (ICR) system for insurance onboarding.
Uploads up to 3 documents, extracts structured data, runs cross-document validation, scores case completeness, and flags exceptions.

---

## Architecture

```
icr-prototype/
├── backend/          # Python FastAPI
│   ├── main.py       # API endpoints
│   ├── extractor.py  # GPT-4o vision extraction (application form, policy illustration)
│   ├── ocr_extractor.py  # Tesseract OCR extraction (government ID — fully local)
│   ├── validator.py  # Cross-document validation engine
│   ├── scorer.py     # Completeness scoring
│   └── requirements.txt
├── frontend/         # React + Vite + Tailwind
│   └── src/
│       ├── App.jsx
│       └── components/
│           ├── DocumentUploader.jsx
│           ├── ExtractionPanel.jsx
│           ├── ValidationPanel.jsx
│           └── CaseScoreCard.jsx
└── sample_docs/      # Place test documents here
```

### Document handling

| Document | Extraction method | Data leaves device? |
|----------|------------------|---------------------|
| Application Form | GPT-4o vision (OpenAI API) | Yes |
| Government ID | Tesseract OCR (local) | **No** |
| Policy Illustration | GPT-4o vision (OpenAI API) | Yes |

Supported government ID types: BIR TIN Card, LTO Driver's License, PhlPost Postal Identity Card (old & new design).
Supported file formats: PDF, JPG, PNG, WebP.

---

## Prerequisites

| Requirement | Version | Install |
|-------------|---------|---------|
| Python | 3.11+ | [python.org](https://python.org) |
| Node.js | 18+ | [nodejs.org](https://nodejs.org) |
| Tesseract OCR | 5.x | `brew install tesseract` |
| Poppler (PDF support) | any | `brew install poppler` |
| OpenAI API key | — | [platform.openai.com](https://platform.openai.com) |

Verify Tesseract has WebP support:
```bash
tesseract --version
# Should list: libwebp x.x.x
```

---

## Setup

### 1. Clone the repo

```bash
git clone <repo-url>
cd icr-prototype
```

### 2. Backend

```bash
cd backend

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env and add your OpenAI API key:
#   OPENAI_API_KEY=sk-...
```

### 3. Frontend

```bash
cd frontend
npm install
```

---

## Running

Open two terminals.

**Terminal 1 — Backend**
```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload --port 8000
```

**Terminal 2 — Frontend**
```bash
cd frontend
npm run dev
```

Open **http://localhost:5173** in your browser.

---

## API

Base URL: `http://localhost:8000`

Interactive docs: **http://localhost:8000/docs**

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/evaluate-case` | Upload up to 3 documents, returns full extraction + validation + score |
| `GET` | `/api/mock-evaluation` | Returns a hardcoded realistic response (no API key needed) |
| `POST` | `/api/test-id-ocr` | Debug endpoint — returns raw OCR text + structured extraction for a government ID |

### `POST /api/evaluate-case`

Accepts `multipart/form-data` with any combination of:

| Field | Type | Required |
|-------|------|----------|
| `application_form` | File (PDF/JPG/PNG/WebP) | Minimum: form + ID |
| `government_id` | File (PDF/JPG/PNG/WebP) | Minimum: form + ID |
| `policy_illustration` | File (PDF/JPG/PNG/WebP) | Optional |

### Response shape

```json
{
  "case_id": "uuid",
  "extractions": {
    "application_form": { ... },
    "government_id": { ... },
    "policy_illustration": { ... }
  },
  "validations": [
    {
      "check": "name_match_form_vs_id",
      "status": "pass | fail | unverified",
      "values": { "Application Form": "...", "Government Id": "..." },
      "score": 100,
      "severity": "critical | warning",
      "message": "..."
    }
  ],
  "completeness": {
    "application_form": { "score": 90, "missing": ["pincode"] },
    "government_id": { "score": 100, "missing": [] },
    "policy_illustration": { "score": 80, "missing": ["applicant_dob"] }
  },
  "case_score": 84,
  "case_status": "Ready for Review | Needs Attention | Incomplete / Refer Back",
  "critical_flags": [ ... ],
  "warnings": [ ... ]
}
```

### Validation checks

| Check | Method | Severity |
|-------|--------|----------|
| Name: form vs ID | Fuzzy (token sort, ≥85) | Critical |
| Name: form vs policy | Fuzzy (token sort, ≥85) | Critical |
| DOB: form vs ID | Exact | Critical |
| DOB: form vs policy | Exact | Critical |
| Pincode: form vs ID | Exact | Warning |
| Sum assured: form vs policy | Numeric (±1%) | Warning |
| Plan name: form vs policy | Fuzzy (≥80) | Warning |

### Case score thresholds

| Score | Status |
|-------|--------|
| 85–100 | Ready for Review |
| 60–84 | Needs Attention |
| < 60 | Incomplete / Refer Back |

Penalties: Critical fail −15 pts · Critical unverified −7 pts · Warning fail −5 pts

---

## Demo (no documents needed)

Click **Load Mock Data** in the UI — this calls `GET /api/mock-evaluation` and populates the entire interface with a realistic Allianz PNB Life case (LORENCO, MARIA CRISTINA · eAZy Health Silver).

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key for GPT-4o vision extraction |

Government ID extraction uses local Tesseract only — no API key required for that path.
