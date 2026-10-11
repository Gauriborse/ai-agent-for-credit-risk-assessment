"""
Payslip / Income Document Processing Service
=============================================
Handles PDF, JPG, PNG uploads.
Extracts: income amount, employer name, salary period, employee name.
Uses PyPDF2 for PDFs and pytesseract (if available) for images.
Returns structured extraction result with confidence and validation flags.

Also contains check_payslip_name() for cross-document name verification.
"""

import re
import io
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ── Helper: normalize number strings ──────────────────────
def _normalize_number(text: str) -> Optional[float]:
    """Convert strings like '1,20,000', '$50,000', '50000.00' → float."""
    clean = re.sub(r"[₹$,\s]", "", text.strip())
    try:
        return float(clean)
    except ValueError:
        return None


# ── PDF text extraction ────────────────────────────────────
def extract_text_from_pdf(file_bytes: bytes) -> str:
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(file_bytes))
        text = ""
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
        return text
    except Exception as e:
        logger.warning(f"PyPDF2 extraction failed: {e}")
        return ""


# ── Image text extraction ──────────────────────────────────
def extract_text_from_image(file_bytes: bytes) -> str:
    try:
        import pytesseract
        from PIL import Image
        img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
        text = pytesseract.image_to_string(img)
        return text
    except ImportError:
        logger.warning("pytesseract not installed — image OCR unavailable.")
        return ""
    except Exception as e:
        logger.warning(f"Image OCR failed: {e}")
        return ""


# ── Core extraction logic ──────────────────────────────────
def parse_payslip_text(text: str) -> dict:
    """
    Parse extracted text and return structured payslip fields.
    Returns dict with extracted fields and confidence flags.
    """
    result = {
        "extracted_income":   None,
        "extracted_employer": None,
        "salary_period":      None,
        "employee_name":      None,
        "raw_text_length":    len(text),
        "parsing_notes":      [],
    }

    if not text.strip():
        result["parsing_notes"].append("No text could be extracted from the document.")
        return result

    # ── Income / Gross Salary ─────────────────────────────
    income_patterns = [
        r"(?:gross\s+(?:salary|pay|earnings?|income))[^\d]*?([\d,]+(?:\.\d{1,2})?)",
        r"(?:net\s+(?:salary|pay|take[- ]?home))[^\d]*?([\d,]+(?:\.\d{1,2})?)",
        r"(?:monthly\s+(?:salary|income|ctc))[^\d]*?([\d,]+(?:\.\d{1,2})?)",
        r"(?:total\s+earnings?)[^\d]*?([\d,]+(?:\.\d{1,2})?)",
        r"(?:basic\s+(?:salary|pay))[^\d]*?([\d,]+(?:\.\d{1,2})?)",
        r"(?:salary)[^\d]*?([\d,]+(?:\.\d{1,2})?)",
        # Bare large number after currency symbol
        r"[₹\$]\s*([\d,]+(?:\.\d{1,2})?)",
    ]
    for pat in income_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = _normalize_number(m.group(1))
            if val and val > 1000:  # sanity check
                result["extracted_income"] = val
                break
    if not result["extracted_income"]:
        result["parsing_notes"].append("Could not extract income amount from document.")

    # ── Employer Name ─────────────────────────────────────
    employer_patterns = [
        r"(?:employer|company|organisation|organization|firm)\s*[:\-]\s*([A-Za-z][A-Za-z0-9 &.,'-]{2,60})",
        r"(?:issued\s+by|from)\s*[:\-]?\s*([A-Za-z][A-Za-z0-9 &.,'-]{2,60})",
    ]
    for pat in employer_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            name = m.group(1).strip()
            if len(name) >= 3:
                result["extracted_employer"] = name
                break
    if not result["extracted_employer"]:
        result["parsing_notes"].append("Employer name not detected.")

    # ── Salary Period ─────────────────────────────────────
    period_patterns = [
        r"(?:pay\s*period|pay\s*date|salary\s*(?:for|month|period))[^\w]*([\w]+\s+\d{4}|\d{2}[\/\-]\d{4}|\d{4})",
        r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
        r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
        r"[\s\-,]*(\d{4})",
        r"(\d{2})[\/\-](\d{4})",
    ]
    for pat in period_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            result["salary_period"] = m.group(0).strip()[:30]
            break
    if not result["salary_period"]:
        result["parsing_notes"].append("Salary period not detected.")

    # ── Employee Name ─────────────────────────────────────
    name_patterns = [
        r"(?:employee\s+name|name\s+of\s+employee|dear)\s*[:\-]?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})",
        r"(?:^|\n)([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})(?:\s+\d|\s+ID)",
    ]
    for pat in name_patterns:
        m = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
        if m:
            name = m.group(1).strip()
            if 3 <= len(name) <= 60:
                result["employee_name"] = name
                break

    return result


# ── Income verification ────────────────────────────────────
def verify_income_against_document(
    claimed_income: float,
    file_bytes: bytes,
    content_type: str,
    filename: str,
) -> dict:
    """
    Extract income from uploaded document and compare with claimed income.
    Returns structured verification result with detailed notes.

    content_type: MIME type (application/pdf, image/jpeg, image/png, etc.)
    """
    result = {
        "verified": False,
        "fraud_flag": False,
        "extraction_success": False,
        "claimed_income": claimed_income,
        "extracted_income": None,
        "extracted_employer": None,
        "salary_period": None,
        "employee_name": None,
        "income_match_pct": None,
        "message": "",
        "notes": [],
        "filename": filename,
    }

    # ── Extract text ──────────────────────────────────────
    ct = (content_type or "").lower()
    fn = (filename or "").lower()

    if "pdf" in ct or fn.endswith(".pdf"):
        raw_text = extract_text_from_pdf(file_bytes)
        result["notes"].append(f"Document type: PDF ({len(file_bytes)//1024} KB)")
    elif any(x in ct for x in ["jpeg", "jpg", "png", "image"]) or \
         any(fn.endswith(x) for x in [".jpg", ".jpeg", ".png"]):
        raw_text = extract_text_from_image(file_bytes)
        result["notes"].append(f"Document type: Image ({len(file_bytes)//1024} KB)")
    else:
        result["notes"].append(f"Unsupported file type: {content_type or filename}")
        result["message"] = "Unsupported file type. Please upload PDF, JPG, or PNG."
        return result

    if not raw_text.strip():
        result["notes"].append("Text extraction returned empty result.")
        result["message"] = (
            "Could not read text from the uploaded document. "
            "Please ensure the file is clear and not password-protected."
        )
        return result

    # ── Parse extracted text ──────────────────────────────
    parsed = parse_payslip_text(raw_text)
    result["extraction_success"] = True
    result["extracted_income"] = parsed["extracted_income"]
    result["extracted_employer"] = parsed["extracted_employer"]
    result["salary_period"] = parsed["salary_period"]
    result["employee_name"] = parsed["employee_name"]
    result["notes"].extend(parsed["parsing_notes"])

    # ── Compare incomes ───────────────────────────────────
    extracted = parsed["extracted_income"]
    if extracted is None:
        # Cannot verify — don't flag fraud but note the gap
        result["message"] = (
            "Income amount could not be extracted from the document. "
            "The document will be reviewed manually. Your application can continue."
        )
        result["verified"] = False
        result["fraud_flag"] = False
        return result

    # Allow ±20% tolerance (monthly vs annual, rounding, tax deductions)
    lower = claimed_income * 0.70
    upper = claimed_income * 1.30
    match_pct = round(abs(claimed_income - extracted) / max(claimed_income, 1) * 100, 1)
    result["income_match_pct"] = match_pct

    if lower <= extracted <= upper:
        result["verified"] = True
        result["fraud_flag"] = False
        result["message"] = (
            f"Income verification passed. "
            f"Document shows {extracted:,.0f} vs claimed {claimed_income:,.0f} "
            f"(within {match_pct:.1f}% tolerance)."
        )
    else:
        result["verified"] = False
        result["fraud_flag"] = True
        result["message"] = (
            f"Income mismatch detected. "
            f"Document shows {extracted:,.0f} but you claimed {claimed_income:,.0f} "
            f"(difference: {match_pct:.1f}%). "
            "Please upload the correct payslip or contact support."
        )

    return result


# ─────────────────────────────────────────────────────────
#  Payslip name check (cross-document verification)
# ─────────────────────────────────────────────────────────

def check_payslip_name(
    registered_name: str,
    payslip_employee_name: Optional[str],
) -> dict:
    """
    Compare the registered applicant name with the employee name extracted
    from the payslip.

    Uses the same normalization logic as kyc_service.compare_names (inlined
    here to avoid a circular import).

    Returns a FieldCheck-compatible dict:
      { status, message, confidence }

    Status values:
      verified        — names match
      mismatch        — clear mismatch → flag for manual review
      manual_review   — partial match; human should confirm
      unable_to_verify— employee name not extracted from payslip
    """
    import unicodedata

    if not payslip_employee_name:
        return {
            "status":     "unable_to_verify",
            "message":    (
                "Employee name could not be extracted from the payslip. "
                "This will not block your application but may be reviewed manually."
            ),
            "confidence": 0.0,
            "ocr_mode":   "none",
        }

    def _norm(name):
        n = unicodedata.normalize("NFKD", name)
        n = "".join(c for c in n if not unicodedata.combining(c))
        n = n.lower().strip()
        n = re.sub(r"[.\-',]", " ", n)
        return re.sub(r"\s+", " ", n).strip()

    def _similarity(a, b):
        if not a or not b:
            return 0.0
        if a == b:
            return 1.0
        ta, tb = set(a.split()), set(b.split())
        jaccard = len(ta & tb) / len(ta | tb) if (ta | tb) else 0.0
        if a in b or b in a:
            return max(jaccard, 0.85)
        init_a = {t[0] for t in ta if t}
        init_b = {t[0] for t in tb if t}
        return max(jaccard, len(init_a & init_b) / max(len(init_a | init_b), 1) * 0.8)

    score = _similarity(_norm(registered_name), _norm(payslip_employee_name))

    if score >= 0.72:
        return {
            "status":     "verified",
            "message":    "Payslip employee name matches the registered applicant name.",
            "confidence": score,
            "ocr_mode":   "live",
        }
    elif score >= 0.50:
        return {
            "status":     "manual_review",
            "message":    (
                "Payslip name partially matches the registered name. "
                "Minor differences may be due to initials or formatting. "
                "Flagged for manual review."
            ),
            "confidence": score,
            "ocr_mode":   "live",
        }
    else:
        return {
            "status":     "mismatch",
            "message":    "Payslip name does not match the registered applicant name.",
            "confidence": score,
            "ocr_mode":   "live",
        }
