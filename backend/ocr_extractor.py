"""
Local OCR extraction for Philippine government-issued ID documents.
Tesseract runs entirely on-device — no document data leaves the machine.

Supported types:
  - BIR TIN Card           (Bureau of Internal Revenue)
  - LTO Driver's License   (Land Transportation Office)
  - PhlPost Postal ID      (both old and new card designs)
"""

import re
from io import BytesIO
from typing import Optional

import pytesseract
from PIL import Image, ImageEnhance, ImageFilter


# ── Image loading ──────────────────────────────────────────────────────────────

def _load_image(data: bytes, file_type: str) -> Image.Image:
    if file_type == "application/pdf":
        from pdf2image import convert_from_bytes
        pages = convert_from_bytes(data, first_page=1, last_page=1, dpi=300)
        if not pages:
            raise ValueError("PDF to image conversion failed")
        img = pages[0]
    else:
        img = Image.open(BytesIO(data))

    # Normalise to RGB first (handles RGBA webp, palette, etc.)
    if img.mode != "RGB":
        img = img.convert("RGB")

    # Re-encode as PNG and re-open. This forces PIL to fully decode
    # the source format (webp in particular) before Tesseract touches it.
    # Without this, pytesseract's internal temp-file conversion of webp
    # produces garbage output regardless of preprocessing.
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return Image.open(buf)


# ── Preprocessing ──────────────────────────────────────────────────────────────

import numpy as np


def _is_dark_background(img: Image.Image) -> bool:
    """Return True if the image has a predominantly dark background (e.g. new Postal ID)."""
    gray = img.convert("L")
    arr = np.array(gray)
    return float(arr.mean()) < 100


def _upscale(img: Image.Image, min_width: int = 1400) -> Image.Image:
    w, h = img.size
    if w < min_width:
        scale = min_width / w
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    return img


def _preprocess_standard(img: Image.Image) -> Image.Image:
    """Grayscale → upscale → contrast → sharpen. For light-background cards."""
    img = img.convert("L")
    img = _upscale(img)
    img = ImageEnhance.Contrast(img).enhance(2.5)
    img = ImageEnhance.Sharpness(img).enhance(2.0)
    img = img.filter(ImageFilter.SHARPEN)
    return img


def _preprocess_inverted(img: Image.Image) -> Image.Image:
    """Invert → upscale → contrast → sharpen. For dark-background cards (new Postal ID)."""
    from PIL import ImageOps
    img = img.convert("L")
    img = ImageOps.invert(img)
    img = _upscale(img, min_width=1600)
    img = ImageEnhance.Contrast(img).enhance(2.5)
    img = ImageEnhance.Sharpness(img).enhance(2.0)
    img = img.filter(ImageFilter.SHARPEN)
    return img


def _preprocess_binarize(img: Image.Image, invert: bool = False) -> Image.Image:
    """Hard-threshold binarize. For patterned backgrounds (LTO, old Postal)."""
    from PIL import ImageOps
    img = img.convert("L")
    if invert:
        img = ImageOps.invert(img)
    img = _upscale(img, min_width=1600)
    img = ImageEnhance.Contrast(img).enhance(3.0)
    img = img.point(lambda p: 255 if p > 145 else 0)
    return img


# ── OCR ────────────────────────────────────────────────────────────────────────

def _ocr(img: Image.Image, psm: int = 3) -> str:
    """Save preprocessed PIL image as PNG temp file and run Tesseract on it."""
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        img.save(tmp_path, format="PNG")
        return pytesseract.image_to_string(tmp_path, config=f"--psm {psm} --oem 3")
    finally:
        os.unlink(tmp_path)


def _ocr_raw_bytes(raw_bytes: bytes, ext: str, psm: int = 3) -> str:
    """
    Write original file bytes to a temp file with the correct extension and
    run Tesseract directly on it — bypasses PIL entirely so Tesseract uses
    its own native decoders (libwebp, libjpeg, etc.).
    """
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(raw_bytes)
        tmp_path = tmp.name
    try:
        return pytesseract.image_to_string(tmp_path, config=f"--psm {psm} --oem 3")
    finally:
        os.unlink(tmp_path)


def _score(text: str) -> int:
    """Score OCR output by length of meaningful alpha-numeric content."""
    return len(re.sub(r"[^A-Za-z0-9]", "", text))


def _best_ocr(raw_img: Image.Image, raw_bytes: bytes = b"", ext: str = ".png") -> str:
    """
    Try multiple strategies and return whichever produces the most readable text:
    1. Native Tesseract decode of original bytes (best for webp — uses libwebp directly)
    2. Preprocessed PIL pipelines (grayscale, inverted, binarized × PSM modes)
    """
    dark = _is_dark_background(raw_img)
    candidates = []

    # ── Strategy 1: let Tesseract use its own native decoder ──────────────────
    if raw_bytes:
        for psm in (3, 6):
            candidates.append(_ocr_raw_bytes(raw_bytes, ext, psm=psm))

    # ── Strategy 2: preprocessed PIL pipelines ────────────────────────────────
    if dark:
        for psm in (6, 3):
            candidates.append(_ocr(_preprocess_inverted(raw_img), psm=psm))
            candidates.append(_ocr(_preprocess_binarize(raw_img, invert=True), psm=psm))

    for psm in (3, 6):
        candidates.append(_ocr(_preprocess_standard(raw_img), psm=psm))
        candidates.append(_ocr(_preprocess_binarize(raw_img, invert=False), psm=psm))

    return max(candidates, key=_score)


# ── Date normalisation ─────────────────────────────────────────────────────────

_MONTH_MAP = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
}


def _expand_year(yy: int) -> int:
    return 1900 + yy if yy > 25 else 2000 + yy


def _parse_date(raw: str) -> Optional[str]:
    raw = raw.strip()

    # YYYY/MM/DD or YYYY-MM-DD  (LTO)
    m = re.match(r"(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})$", raw)
    if m:
        return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"

    # MM/DD/YYYY  (BIR — form label is always mm/dd/yyyy)
    # group(1)=month, group(2)=day, group(3)=year
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})$", raw)
    if m:
        month, day, year = int(m.group(1)), int(m.group(2)), m.group(3)
        if 1 <= month <= 12 and 1 <= day <= 31:
            return f"{year}-{str(month).zfill(2)}-{str(day).zfill(2)}"

    # DD MMM YY or DD MMM YYYY  (Postal)
    m = re.match(r"(\d{1,2})\s+([A-Za-z]{3})\s+(\d{2,4})$", raw)
    if m:
        day, mon, yr = int(m.group(1)), m.group(2).lower(), int(m.group(3))
        month = _MONTH_MAP.get(mon)
        if month and 1 <= day <= 31:
            yr = _expand_year(yr) if yr < 100 else yr
            return f"{yr}-{month}-{str(day).zfill(2)}"

    return None


# ── ID-type detection ──────────────────────────────────────────────────────────

def _detect_type(text: str) -> str:
    t = text.upper()
    if "BUREAU OF INTERNAL REVENUE" in t or ("BIR" in t and "TIN" in t):
        return "BIR_TIN"
    if "LAND TRANSPORTATION" in t or "DRIVER" in t or "LICENSE NO" in t:
        return "DRIVERS_LICENSE"
    if "POSTAL IDENTITY" in t or "PHLPOST" in t or "POSTAL CORPORATION" in t:
        return "POSTAL_ID"
    if re.search(r"\bTIN\b.*\d{3}-\d{3}", t):
        return "BIR_TIN"
    if re.search(r"LICENSE\s*NO", t):
        return "DRIVERS_LICENSE"
    return "UNKNOWN"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _extract_pincode(text: str) -> Optional[str]:
    """Philippine postal codes are exactly 4 digits."""
    m = re.search(r"\b(\d{4})\b", text)
    return m.group(1) if m else None


def _clean(s: str) -> str:
    """Strip leading OCR noise characters from a line."""
    return re.sub(r"^[^A-Za-z0-9]+", "", s).strip()


_INSTITUTION_KEYWORDS = {
    "REPUBLIC", "DEPARTMENT", "BUREAU", "REVENUE", "FINANCE",
    "TRANSPORTATION", "POSTAL", "PHLPOST", "PHILIPPINES",
    "CORPORATION", "NON-PROFESSIONAL", "PREMIUM",
}


def _is_institution_line(line: str) -> bool:
    return any(kw in line.upper() for kw in _INSTITUTION_KEYWORDS)


def _looks_like_name(line: str) -> bool:
    """
    True if a line looks like a Philippine name in ALL CAPS.
    Handles 'LAST,FIRST' and 'FIRST MIDDLE LAST' styles.
    Rejects lines that are mostly digits or noise.
    """
    cleaned = _clean(line).strip()
    if len(cleaned) < 4:
        return False
    # Must be ≥2 words composed of letters, spaces, commas, hyphens, dots
    if not re.match(r"^[A-Z][A-Z\s,\.\-]+$", cleaned):
        return False
    words = re.split(r"[\s,]+", cleaned)
    real_words = [w for w in words if len(w) >= 2]
    return len(real_words) >= 2


def _normalize_name(raw: str) -> str:
    """'LAST,FIRST MIDDLE' → 'FIRST MIDDLE LAST'."""
    cleaned = _clean(raw)
    m = re.match(r"^([A-Z][A-Z\s]+),\s*([A-Z][A-Z\s]+)$", cleaned)
    if m:
        return f"{m.group(2).strip()} {m.group(1).strip()}"
    return cleaned


# ── BIR TIN Card ───────────────────────────────────────────────────────────────

def _parse_bir(lines: list[str], full_text: str) -> dict:
    result = dict.fromkeys(
        ["id_type", "id_number", "full_name", "date_of_birth", "address", "pincode", "gender"]
    )
    result["id_type"] = "BIR TIN Card"

    # TIN number
    m = re.search(r"TIN\s*[:.]?\s*(\d{3}[-\s]\d{3}[-\s]\d{3}(?:[-\s]\d{3})?)", full_text, re.I)
    if m:
        result["id_number"] = re.sub(r"\s", "-", m.group(1))

    # Name: first non-institution line before the TIN line
    tin_idx = next(
        (i for i, l in enumerate(lines) if re.search(r"TIN\s*[:.]?\s*\d", l, re.I)), None
    )
    if tin_idx is not None:
        for i in range(tin_idx - 1, max(tin_idx - 6, -1), -1):
            candidate = lines[i].strip()
            if candidate and not _is_institution_line(candidate):
                result["full_name"] = candidate
                break

    # DOB
    m = re.search(r"DATE\s+OF\s+BIRTH\s*[:.]?\s*([\d/\-]+)", full_text, re.I)
    if m:
        result["date_of_birth"] = _parse_date(m.group(1))

    # Address: lines between TIN line and DOB line
    dob_idx = next(
        (i for i, l in enumerate(lines) if re.search(r"DATE\s+OF\s+BIRTH", l, re.I)), None
    )
    if tin_idx is not None and dob_idx is not None and dob_idx > tin_idx + 1:
        addr_lines = [
            _clean(lines[i])
            for i in range(tin_idx + 1, dob_idx)
            if lines[i].strip() and not re.search(r"TIN\s*[:.]", lines[i], re.I)
        ]
        addr_lines = [a for a in addr_lines if a]
        if addr_lines:
            result["address"] = ", ".join(addr_lines)
            result["pincode"] = _extract_pincode(result["address"])

    return result


# ── LTO Driver's License ───────────────────────────────────────────────────────

def _extract_lto_name(lines: list[str]) -> Optional[str]:
    """
    Extract name from LTO card.  The OCR line looks like:
      ". JUAN,PEDRO EES eee"   or   "JUAN,PEDRO"
    Strategy: scan every line for a LAST,FIRST token (all-caps, comma-separated).
    Extract just that token, ignoring surrounding noise.
    """
    # LTO name format is strictly LASTNAME,FIRSTNAME (no spaces in either token).
    # Match only single-word last and first names separated by a comma.
    for line in lines:
        m = re.search(r"\b([A-Z]{2,}),([A-Z]{2,})\b", line)
        if m:
            last, first = m.group(1), m.group(2)
            if not _is_institution_line(f"{last},{first}"):
                return f"{first} {last}"
    return None


def _parse_lto(lines: list[str], full_text: str) -> dict:
    result = dict.fromkeys(
        ["id_type", "id_number", "full_name", "date_of_birth", "address", "pincode", "gender"]
    )
    result["id_type"] = "Driver's License"

    # License number — LTO format: letter(s) + digits + dashes e.g. N03-12-123434
    # OCR often reads 0 as O, so allow letters mixed with digits in the first segment
    m = re.search(r"\b([A-Z][A-Z0-9]{1,2}-\d{2}-\d{4,})\b", full_text, re.I)
    if m:
        # Normalise: replace letter-O with zero in numeric positions
        raw_lic = m.group(1).upper()
        parts = raw_lic.split("-")
        # First segment: keep as-is (intentional alphanumeric prefix)
        result["id_number"] = "-".join(parts)

    # Name
    result["full_name"] = _extract_lto_name(lines)

    # Sex + DOB from the tabular data row: PHL  M  1987/10/04  77  1.55
    m = re.search(r"\bPHL\s+(M|F)\s+(\d{4}[/\-]\d{2}[/\-]\d{2})", full_text, re.I)
    if m:
        result["gender"] = "Male" if m.group(1).upper() == "M" else "Female"
        result["date_of_birth"] = _parse_date(m.group(2))
    else:
        m = re.search(r"\bSex\b[\s\S]{0,30}?\b(M|F)\b", full_text, re.I)
        if m:
            result["gender"] = "Male" if m.group(1).upper() == "M" else "Female"
        # First YYYY/MM/DD that isn't an expiry date
        for dm in re.finditer(r"(\d{4}/\d{2}/\d{2})", full_text):
            context = full_text[max(0, dm.start() - 50):dm.start()].upper()
            if "EXPIR" not in context and "ISSUE" not in context:
                result["date_of_birth"] = _parse_date(dm.group(1))
                break

    # Address: lines between "Address" label and the license-number line
    # The label line may have trailing OCR noise so use startswith match
    addr_start = next(
        (i for i, l in enumerate(lines) if re.match(r"^Address\b", l.strip(), re.I)), None
    )
    lic_idx = next(
        (i for i, l in enumerate(lines) if re.search(r"\b[A-Z][A-Z0-9]{1,2}-\d{2}-\d{4}", l)), None
    )
    if addr_start is not None:
        end = lic_idx if lic_idx else min(addr_start + 6, len(lines))
        addr_lines = [_clean(lines[i]) for i in range(addr_start + 1, end) if lines[i].strip()]
        # Strip trailing noise characters (non-alphanumeric, non-punctuation)
        addr_lines = [re.sub(r"[^A-Za-z0-9\s,./\-]+$", "", a).strip() for a in addr_lines]
        addr_lines = [a for a in addr_lines if len(a) > 3]
        if addr_lines:
            result["address"] = " ".join(addr_lines)
            result["pincode"] = _extract_pincode(result["address"])

    return result


# ── PhlPost Postal Identity Card ───────────────────────────────────────────────

_ADDR_KEYWORDS = re.compile(
    r"\b(st|blvd|ave|road|rd|brgy|barangay|city|municipality|village|street|gen|dr)\b", re.I
)


def _parse_postal(lines: list[str], full_text: str) -> dict:
    result = dict.fromkeys(
        ["id_type", "id_number", "full_name", "date_of_birth", "address", "pincode", "gender"]
    )
    result["id_type"] = "Postal ID"

    # ── PAN number ────────────────────────────────────────────────────────────
    # Label is "PRN" or "PAN" depending on card version; 12 digits follow
    m = re.search(r"\b(?:PAN|PRN)\s+([\d\s]{12,15})\b", full_text, re.I)
    if m:
        digits = re.sub(r"\s", "", m.group(1))
        if len(digits) >= 12:
            result["id_number"] = digits[:12]
    if not result["id_number"]:
        m = re.search(r"\b(\d{12})\b", full_text)
        if m:
            result["id_number"] = m.group(1)

    # ── Name ──────────────────────────────────────────────────────────────────
    # Find the first ALL-CAPS multi-word line that isn't an institution header
    name_line_idx = None
    for i, line in enumerate(lines):
        if not _is_institution_line(line) and _looks_like_name(line):
            result["full_name"] = _clean(line)
            name_line_idx = i
            break

    # ── DOB ───────────────────────────────────────────────────────────────────
    # Postal ID format: "DD MMM YY"
    # Tesseract frequently corrupts digits, so we also try a looser pattern
    # that accepts 1-2 non-space characters as the day token.
    dob_line_idx = None

    # Strict: proper digits before and after the month
    strict_dob = re.compile(
        r"(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{2,4})\b",
        re.I,
    )
    # Loose: any 1-2 non-space chars as day (handles OCR corruption like "BY Aug 48")
    loose_dob = re.compile(
        r"(\S{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{2,4})\b",
        re.I,
    )

    for pattern in (strict_dob, loose_dob):
        m = pattern.search(full_text)
        if m:
            day_raw, mon_raw, yr_raw = m.group(1), m.group(2), m.group(3)
            month = _MONTH_MAP.get(mon_raw.lower())
            if month:
                # Attempt to recover corrupted day: keep only digits, clamp 1-31
                day_digits = re.sub(r"\D", "", day_raw)
                day = int(day_digits) if day_digits and 1 <= int(day_digits) <= 31 else None
                yr = int(yr_raw)
                yr = _expand_year(yr) if yr < 100 else yr
                if day:
                    result["date_of_birth"] = f"{yr}-{month}-{str(day).zfill(2)}"
                else:
                    result["date_of_birth"] = f"{yr}-{month}-01"  # day unreadable
            dob_line_idx = next(
                (i for i, l in enumerate(lines) if pattern.search(l)), None
            )
            break

    # ── Address ───────────────────────────────────────────────────────────────
    # Anchor: lines between name line and the nationality/DOB line.
    # Use "Filipino" (nationality) as the end anchor — it appears on the same
    # line as DOB and is more reliably OCR'd than the corrupted date digits.
    nat_line_idx = next(
        (i for i, l in enumerate(lines) if re.search(r"\bFilipino\b", l, re.I)), None
    )
    # End is whichever anchor comes first
    addr_end = min(
        x for x in (dob_line_idx, nat_line_idx, len(lines)) if x is not None
    )

    if name_line_idx is not None and addr_end > name_line_idx + 1:
        raw_addr_lines = [
            _clean(lines[i])
            for i in range(name_line_idx + 1, addr_end)
            if lines[i].strip()
        ]
        # For each candidate line, use targeted regex to extract only the
        # meaningful address fragment, discarding surrounding OCR noise.
        _PATTERNS = [
            # "585 Gen. Tuazon Blvd." — house number + street
            re.compile(r"(\d+[A-Z]?\s+(?:Gen\.?\s+)?[\w\s\.]+(?:Blvd|Ave|St|Rd|Street|Road|Drive|Dr)\.?)", re.I),
            # "Brgy. Rivera" — stop at first short/noise word after the name
            re.compile(r"((?:Brgy|Barangay)\.?\s+[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]{2,})*)", re.I),
            # "1742 Pasay City" — 4-digit code + place name + City/Municipality
            re.compile(r"(\d{4}\s+[\w\s]+?(?:City|Municipality|Town))", re.I),
        ]
        cleaned_addr = []
        for line in raw_addr_lines:
            matched = False
            for pat in _PATTERNS:
                m = pat.search(line)
                if m:
                    cleaned_addr.append(m.group(1).strip())
                    matched = True
                    break
            if not matched and _ADDR_KEYWORDS.search(line):
                # Fallback: keep the line but strip obvious leading/trailing noise
                cleaned_addr.append(re.sub(r"^[^A-Z0-9]+", "", line).strip())
        if cleaned_addr:
            result["address"] = ", ".join(cleaned_addr)
            result["pincode"] = _extract_pincode(result["address"])

    if not result["pincode"]:
        result["pincode"] = _extract_pincode(full_text)

    return result


# ── Generic fallback ───────────────────────────────────────────────────────────

def _parse_fallback(lines: list[str], full_text: str) -> dict:
    result = dict.fromkeys(
        ["id_type", "id_number", "full_name", "date_of_birth", "address", "pincode", "gender"]
    )
    result["id_type"] = "Unknown"

    # Try to find a name
    for line in lines:
        if not _is_institution_line(line) and _looks_like_name(line):
            result["full_name"] = _clean(line)
            break

    # Any recognisable date
    for pattern in [
        r"\d{4}[/\-]\d{2}[/\-]\d{2}",
        r"\d{1,2}[/\-]\d{1,2}[/\-]\d{4}",
        r"\d{1,2}\s+[A-Za-z]{3}\s+\d{2,4}",
    ]:
        m = re.search(pattern, full_text)
        if m:
            parsed = _parse_date(m.group(0))
            if parsed:
                result["date_of_birth"] = parsed
                break

    # Gender
    if re.search(r"\bFEMALE\b", full_text, re.I):
        result["gender"] = "Female"
    elif re.search(r"\bMALE\b", full_text, re.I):
        result["gender"] = "Male"

    result["pincode"] = _extract_pincode(full_text)
    return result


# ── Public interface ───────────────────────────────────────────────────────────

_MIME_TO_EXT = {
    "image/webp": ".webp",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/tiff": ".tiff",
}


def extract_government_id(file_bytes: bytes, file_type: str) -> dict:
    """
    Extract structured fields from a Philippine government ID using Tesseract OCR.
    Processing is entirely local — no data is sent to any external service.

    Args:
        file_bytes: Raw file bytes (image or PDF)
        file_type:  MIME type ("image/jpeg", "image/png", "image/webp", "application/pdf")

    Returns:
        Dict with keys: id_type, id_number, full_name, date_of_birth,
                        address, pincode, gender
    """
    ext = _MIME_TO_EXT.get(file_type, ".png")
    raw_img = _load_image(file_bytes, file_type)

    # Pass both PIL image (for preprocessing) and original bytes (for native decode)
    raw_text = _best_ocr(raw_img, raw_bytes=file_bytes, ext=ext)

    lines = [l for l in raw_text.splitlines() if l.strip()]
    detected = _detect_type(raw_text)

    if detected == "BIR_TIN":
        return _parse_bir(lines, raw_text)
    if detected == "DRIVERS_LICENSE":
        return _parse_lto(lines, raw_text)
    if detected == "POSTAL_ID":
        return _parse_postal(lines, raw_text)

    return _parse_fallback(lines, raw_text)
