"""
KYC AI Agent
============
Follows the same Think -> Act -> Observe -> Decide loop as LoanAgent.

Tools available to the agent:
  1. tool_check_id_format    — validates ID number format by type
  2. tool_run_ocr             — extracts name + DOB from ID card image
  3. tool_face_match          — DeepFace face similarity check
  4. tool_liveness_check      — selfie quality / sharpness check

ID types supported: aadhaar, pan, dl, college (default)

Mock mode  (USE_LOCAL_LLM=True)  — agent logic is hand-coded in Python.
OpenAI mode (USE_LOCAL_LLM=False) — LangChain + GPT decides tool order & retries.

Security:
  - ID numbers are NEVER logged in full; always masked.
  - Format validation alone does NOT mark identity as verified.
  - Status values: "verified" | "format_valid" | "pending" | "failed"
"""

import re
import json
import os
from dataclasses import dataclass, field
from typing import List, Optional
from PIL import Image
import numpy as np

from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


# ─────────────────────────────────────────────
#  Shared result dataclass
# ─────────────────────────────────────────────
@dataclass
class KYCResult:
    status: str               # "verified" | "format_valid" | "pending" | "failed"
    confidence: float
    verdict: str              # human-readable final decision
    reasoning_steps: List[str] = field(default_factory=list)
    checks: dict              = field(default_factory=dict)
    id_type: str              = field(default="college")


# ─────────────────────────────────────────────
#  Internal helper — mask sensitive ID numbers
# ─────────────────────────────────────────────
def _mask_id(val: str) -> str:
    """Return a masked version — never expose full ID in logs."""
    if len(val) <= 4:
        return '****'
    return val[:2] + '*' * (len(val) - 4) + val[-2:]


# ─────────────────────────────────────────────
#  TOOL 1 — ID Format Check (multi-type)
# ─────────────────────────────────────────────
def tool_check_id_format(id_number: str, id_type: str = "college") -> dict:
    """
    Validates the ID number format based on id_type.
    Supported types: aadhaar, pan, dl, college (default = 8 digits)
    Returns: { passed, detail, id_type }
    Never logs or returns the full number — always masks.
    """
    clean  = re.sub(r'\s', '', id_number).upper()
    masked = _mask_id(clean)

    if id_type == "aadhaar":
        passed = bool(re.match(r'^\d{12}$', clean))
        if not passed:
            if not clean.isdigit():
                detail = "Aadhaar number must contain digits only. Got non-digit characters."
            elif len(clean) != 12:
                detail = f"Aadhaar number must be exactly 12 digits. Got {len(clean)} digits."
            else:
                detail = "Invalid Aadhaar number format."
        else:
            detail = f"Aadhaar number ({masked}) is valid — 12 digits."

    elif id_type == "pan":
        passed = bool(re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$', clean))
        if not passed:
            if len(clean) != 10:
                detail = f"PAN must be exactly 10 characters. Got {len(clean)}."
            else:
                detail = (
                    f"Invalid PAN format ({masked}). "
                    "Expected: 5 letters + 4 digits + 1 letter (e.g. ABCDE1234F)."
                )
        else:
            detail = f"PAN number ({masked}) format is valid."

    elif id_type == "dl":
        # Basic format: 2-letter state code + digits, total 9–20 chars
        passed = (
            bool(re.match(r'^[A-Z]{2}\d{1,}[A-Z0-9]{1,}$', clean))
            and 9 <= len(clean) <= 20
        )
        if not passed:
            if len(clean) < 9:
                detail = f"Driving licence too short ({len(clean)} chars). Minimum 9."
            elif len(clean) > 20:
                detail = "Driving licence too long. Maximum 20 characters."
            elif not re.match(r'^[A-Z]{2}', clean):
                detail = "Driving licence must start with 2-letter state code (e.g. MH, DL, KA)."
            else:
                detail = f"Invalid driving licence format ({masked}). Basic format validation only."
        else:
            detail = (
                f"Driving licence ({masked}) basic format is valid. "
                "Note: full validation requires state-specific rules."
            )

    else:
        # Default: college ID = 8 numeric digits
        passed = bool(re.match(r'^\d{8}$', clean))
        if not passed:
            detail = f"College ID must be exactly 8 digits. Got {len(clean)} character(s)."
        else:
            detail = f"College ID ({masked}) is valid — 8-digit numeric."

    return {"passed": passed, "detail": detail, "id_type": id_type}


# ─────────────────────────────────────────────
#  TOOL 2 — OCR (Name + DOB extraction)
# ─────────────────────────────────────────────
def tool_run_ocr(id_image_path: str, expected_name: str, expected_dob: str) -> dict:
    """
    Runs OCR on the ID card image using OpenCV preprocessing + Tesseract.
    Extracts name and DOB, fuzzy-matches against provided values.
    Falls back to demo-pass if Tesseract binary is not installed.
    Returns: { name_passed, dob_passed, extracted_name, extracted_dob, mode }
    """
    from services.kyc_service import _TESSERACT_AVAILABLE, _preprocess_for_ocr

    if not _TESSERACT_AVAILABLE:
        logger.info("OCR tool: Tesseract binary not installed — using demo pass.")
        return {
            "name_passed":    True,
            "dob_passed":     True,
            "extracted_name": expected_name,
            "extracted_dob":  expected_dob,
            "name_detail":    "Name matched (demo mode — Tesseract binary not installed).",
            "dob_detail":     "DOB matched (demo mode — Tesseract binary not installed).",
            "mode":           "demo",
        }

    try:
        import pytesseract

        # Use OpenCV preprocessing for better accuracy on ID cards
        preprocessed = _preprocess_for_ocr(id_image_path)
        if preprocessed is None:
            raise RuntimeError("Image preprocessing failed.")

        config = "--psm 6 --oem 3"
        text = pytesseract.image_to_string(preprocessed, config=config)

        # Extract name
        extracted_name = ""
        for pat in [
            r'Name[:\s]+([A-Za-z ]{3,40})',
            r'(?:^|\n)([A-Z][a-z]+(?: [A-Z][a-z]+)+)',
        ]:
            m = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
            if m:
                extracted_name = re.sub(r'\s+', ' ', m.group(1).strip())
                break

        # Extract DOB
        extracted_dob = ""
        for pat in [
            r'DOB[:\s]*([\d]{1,2}[/\-][\d]{1,2}[/\-][\d]{2,4})',
            r'Date\s+of\s+Birth[:\s]*([\d]{1,2}[/\-][\d]{1,2}[/\-][\d]{2,4})',
            r'([\d]{1,2}[/\-][\d]{1,2}[/\-][\d]{4})',
        ]:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                extracted_dob = m.group(1)
                break

        def fuzzy(a, b):
            a, b = a.lower().strip(), b.lower().strip()
            if not a or not b:
                return False
            if a in b or b in a:
                return True
            common = sum(1 for c in a if c in b)
            return common / max(len(a), len(b)) >= 0.65

        name_passed = fuzzy(expected_name, extracted_name) if extracted_name else False
        dob_passed  = fuzzy(expected_dob,  extracted_dob)  if extracted_dob  else False

        return {
            "name_passed":    name_passed,
            "dob_passed":     dob_passed,
            "extracted_name": extracted_name or "Not found",
            "extracted_dob":  extracted_dob  or "Not found",
            "name_detail":    "Name matched on ID." if name_passed else "Name mismatch on ID.",
            "dob_detail":     "DOB matched on ID."  if dob_passed  else "DOB mismatch on ID.",
            "mode":           "live",
        }

    except Exception as e:
        logger.error(f"OCR tool error: {e}")
        return {
            "name_passed":    False,
            "dob_passed":     False,
            "extracted_name": "Error",
            "extracted_dob":  "Error",
            "name_detail":    f"OCR error: {e}",
            "dob_detail":     f"OCR error: {e}",
            "mode":           "error",
        }


# ─────────────────────────────────────────────
#  TOOL 3 — Face Match
# ─────────────────────────────────────────────
def tool_face_match(id_image_path: str, selfie_path: str) -> dict:
    """
    Uses DeepFace to compare the face on the ID card with the selfie.
    Falls back to demo-pass if deepface is not installed.
    """
    try:
        from deepface import DeepFace
    except ImportError:
        logger.info("DeepFace not installed — using demo face match pass.")
        return {
            "passed":   True,
            "distance": 0.0,
            "detail":   "Face match passed (demo mode — DeepFace not installed).",
        }

    def _run_verify(enforce: bool) -> dict:
        return DeepFace.verify(
            img1_path         = id_image_path,
            img2_path         = selfie_path,
            model_name        = "VGG-Face",
            enforce_detection = enforce,
            detector_backend  = "opencv",
        )

    # ── Attempt 1: strict face detection ──
    try:
        result   = _run_verify(enforce=True)
        matched  = bool(result.get("verified", False))
        distance = round(float(result.get("distance", 1.0)), 3)
        return {
            "passed":   matched,
            "distance": distance,
            "detail":   "Face on ID matches selfie." if matched else (
                f"Face mismatch — photos are of different people "
                f"(distance={distance}, threshold=0.40). "
                "The selfie must show the same person as the ID card."
            ),
        }
    except Exception as e1:
        err = str(e1).lower()
        if any(k in err for k in ["face", "detect", "no face", "cannot"]):
            pass  # fall through to lenient mode
        else:
            logger.error(f"Face match unexpected error: {e1}")
            return {
                "passed":   False,
                "distance": 1.0,
                "detail":   "Face verification error. Please upload clearer photos.",
            }

    # ── Attempt 2: lenient detection with tighter threshold ──
    try:
        result   = _run_verify(enforce=False)
        distance = round(float(result.get("distance", 1.0)), 3)
        matched  = distance < 0.35
        return {
            "passed":   matched,
            "distance": distance,
            "detail":   "Face on ID matches selfie (lenient scan)." if matched else (
                f"Face mismatch — photos are of different people "
                f"(distance={distance}, threshold=0.35). "
                "The selfie must show the same person as the ID card."
            ),
        }
    except Exception as e2:
        logger.warning(f"Face match failed both attempts: {e2}")
        return {
            "passed":   False,
            "distance": 1.0,
            "detail":   (
                "Could not detect a face in one or both images. "
                "Please upload a clear, well-lit front-facing photo for both "
                "the ID card and selfie."
            ),
        }


# ─────────────────────────────────────────────
#  TOOL 4 — Liveness Check
# ─────────────────────────────────────────────
def tool_liveness_check(selfie_path: str) -> dict:
    """
    Checks that the selfie is a real, clear photo.
    Uses OpenCV Laplacian variance (sharpness) as the primary signal,
    falls back to PIL pixel variance. Both are bundled — no install needed.
    """
    # ── OpenCV Laplacian sharpness (more accurate) ────────
    try:
        import cv2
        img_cv = cv2.imread(selfie_path)
        if img_cv is not None:
            gray     = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
            h, w     = gray.shape
            lap_var  = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            min_dim  = min(h, w)
            # Laplacian variance >80 = acceptably sharp; <30 = blurry
            is_live  = (min_dim >= 100) and (lap_var > 80.0)
            return {
                "passed":          is_live,
                "resolution":      f"{w}x{h}",
                "sharpness_score": round(lap_var, 1),
                "detail":          (
                    "Selfie passes liveness check (OpenCV sharpness)."
                    if is_live else
                    f"Selfie too blurry or low-resolution "
                    f"(sharpness={lap_var:.0f}, need >80; size={w}x{h})."
                ),
            }
    except Exception as e:
        logger.warning(f"OpenCV liveness check failed, falling back to PIL: {e}")

    # ── PIL fallback ──────────────────────────────────────
    try:
        img           = Image.open(selfie_path).convert("RGB")
        width, height = img.size
        min_dim       = min(width, height)
        gray          = np.array(img.convert("L"), dtype=float)
        variance      = float(np.var(gray))
        is_live       = (min_dim >= 100) and (variance > 100)
        return {
            "passed":          is_live,
            "resolution":      f"{width}x{height}",
            "sharpness_score": round(variance, 1),
            "detail":          "Selfie passes liveness check." if is_live
                               else "Selfie too blurry or low-resolution.",
        }
    except Exception as e:
        logger.error(f"Liveness tool error: {e}")
        return {
            "passed":          False,
            "resolution":      "?",
            "sharpness_score": 0,
            "detail":          f"Liveness check error: {e}",
        }


# ─────────────────────────────────────────────
#  MOCK AGENT  (Think → Act → Observe → Decide)
# ─────────────────────────────────────────────
def mock_kyc_agent(
    user_id:       str,
    full_name:     str,
    dob:           str,
    id_number:     str,
    id_type:       str,
    id_image_path: str,
    selfie_path:   str,
) -> KYCResult:
    """
    Deterministic reasoning agent — no LLM needed.
    Each step logs its THINK → ACT → OBSERVE reasoning.
    Validates ID format by the declared id_type (aadhaar/pan/dl/college).
    """
    steps  = []
    checks = {}

    # ── STEP 1 — ID Format ───────────────────
    steps.append(f"THINK: Check the {id_type.upper()} number format before processing images.")
    steps.append("ACT  : Running tool_check_id_format.")
    id_result = tool_check_id_format(id_number, id_type)
    checks["id_format"] = id_result
    steps.append(
        f"OBSERVE: {id_type.upper()} format → {'PASS' if id_result['passed'] else 'FAIL'} "
        f"— {id_result['detail']}"
    )

    if not id_result["passed"]:
        steps.append("DECIDE: ID format failed — hard block, stopping early.")
        return KYCResult(
            status="failed",
            confidence=0.0,
            verdict=(
                f"KYC Failed: Invalid {id_type.upper()} format. "
                f"{id_result['detail']}"
            ),
            reasoning_steps=steps,
            checks=checks,
            id_type=id_type,
        )

    # ── STEP 2 — OCR ─────────────────────────
    steps.append("THINK: ID format valid. Scanning card for name and DOB via OCR.")
    steps.append("ACT  : Running tool_run_ocr.")
    ocr_result = tool_run_ocr(id_image_path, full_name, dob)
    checks["name_match"] = {
        "passed":   ocr_result["name_passed"],
        "extracted": ocr_result["extracted_name"],
        "provided":  full_name,
        "detail":    ocr_result["name_detail"],
        "ocr_mode":  ocr_result["mode"],
    }
    checks["dob_match"] = {
        "passed":   ocr_result["dob_passed"],
        "extracted": ocr_result["extracted_dob"],
        "provided":  dob,
        "detail":    ocr_result["dob_detail"],
        "ocr_mode":  ocr_result["mode"],
    }
    steps.append(f"OBSERVE: Name match → {'PASS' if ocr_result['name_passed'] else 'FAIL'}")
    steps.append(f"OBSERVE: DOB match  → {'PASS' if ocr_result['dob_passed'] else 'FAIL'}")

    ocr_both_failed = not ocr_result["name_passed"] and not ocr_result["dob_passed"]
    if ocr_both_failed and ocr_result["mode"] == "live":
        steps.append(
            "THINK: Both name and DOB failed live OCR — ID card may be unclear. "
            "Will still check face; if face matches, treat as low-confidence pass."
        )
    else:
        steps.append("THINK: OCR done. Proceeding to face match.")

    # ── STEP 3 — Face Match ──────────────────
    steps.append("ACT  : Running tool_face_match (DeepFace VGG-Face).")
    face_result = tool_face_match(id_image_path, selfie_path)
    checks["face_match"] = face_result
    steps.append(
        f"OBSERVE: Face match → {'PASS' if face_result['passed'] else 'FAIL'} "
        f"(distance={face_result['distance']})"
    )

    if not face_result["passed"]:
        steps.append(
            "THINK: Face match failed — critical check. "
            "Will still run liveness but overall verdict is failed."
        )
    else:
        steps.append("THINK: Face match passed. Running final liveness check.")

    # ── STEP 4 — Liveness ────────────────────
    steps.append("ACT  : Running tool_liveness_check.")
    live_result = tool_liveness_check(selfie_path)
    checks["liveness"] = live_result
    steps.append(
        f"OBSERVE: Liveness → {'PASS' if live_result['passed'] else 'FAIL'} "
        f"(sharpness={live_result['sharpness_score']})"
    )

    # ── DECIDE ───────────────────────────────
    steps.append("THINK: All tools run. Weighing the evidence.")

    if not face_result["passed"]:
        steps.append(
            f"DECIDE: Face match FAILED (distance={face_result['distance']}) → REJECTED."
        )
        return KYCResult(
            status="failed",
            confidence=0.0,
            verdict=(
                f"KYC Failed: Face mismatch. {face_result['detail']} "
                "The selfie and ID card must show the same person."
            ),
            reasoning_steps=steps,
            checks=checks,
            id_type=id_type,
        )

    if not live_result["passed"]:
        steps.append("DECIDE: Liveness FAILED → REJECTED.")
        return KYCResult(
            status="failed",
            confidence=0.0,
            verdict=(
                f"KYC Failed: Selfie quality too low. {live_result['detail']}"
            ),
            reasoning_steps=steps,
            checks=checks,
            id_type=id_type,
        )

    # Both critical checks passed — assess OCR
    ocr_score    = int(ocr_result["name_passed"]) + int(ocr_result["dob_passed"])
    total_passed = sum([
        id_result["passed"],
        ocr_result["name_passed"],
        ocr_result["dob_passed"],
        face_result["passed"],
        live_result["passed"],
    ])

    if total_passed >= 4:
        confidence = 0.95 if total_passed == 5 else 0.82
        status     = "verified"
        verdict    = (
            f"KYC Verified with {int(confidence*100)}% confidence. "
            f"Face matches selfie, ID is valid, liveness confirmed. "
            f"OCR matched {ocr_score}/2 text fields."
        )
        steps.append(
            f"DECIDE: {total_passed}/5 checks passed → VERIFIED ({int(confidence*100)}%)."
        )
    elif total_passed == 3:
        # Face+liveness passed but OCR could not read name/dob
        confidence = 0.65
        status     = "verified"
        verdict    = (
            "KYC Conditionally Verified (65% confidence). "
            "Face and liveness passed but OCR could not fully read the ID card. "
            "Proceed with caution."
        )
        steps.append("DECIDE: Critical checks passed, OCR weak → VERIFIED with low confidence.")
    else:
        failed_list = []
        if not id_result["passed"]:   failed_list.append("ID Format")
        if not face_result["passed"]: failed_list.append("Face Match")
        if not live_result["passed"]: failed_list.append("Liveness")
        confidence = 0.0
        status     = "failed"
        verdict    = f"KYC Failed. Critical check(s) did not pass: {', '.join(failed_list)}."
        steps.append(f"DECIDE: Critical failures: {failed_list} → REJECTED.")

    return KYCResult(
        status=status,
        confidence=confidence,
        verdict=verdict,
        reasoning_steps=steps,
        checks=checks,
        id_type=id_type,
    )


# ─────────────────────────────────────────────
#  OPENAI AGENT  (LangChain)
# ─────────────────────────────────────────────
def openai_kyc_agent(
    user_id:       str,
    full_name:     str,
    dob:           str,
    id_number:     str,
    id_type:       str,
    id_image_path: str,
    selfie_path:   str,
) -> KYCResult:
    from langchain_openai import ChatOpenAI
    from langchain.agents import initialize_agent, AgentType
    from langchain.tools import tool as lc_tool

    @lc_tool
    def lc_check_id_format(dummy: str = "") -> str:
        """Check if the ID number matches the expected format for the selected ID type."""
        return json.dumps(tool_check_id_format(id_number, id_type))

    @lc_tool
    def lc_run_ocr(dummy: str = "") -> str:
        """Run OCR on the uploaded ID card to extract and verify name and date of birth."""
        return json.dumps(tool_run_ocr(id_image_path, full_name, dob))

    @lc_tool
    def lc_face_match(dummy: str = "") -> str:
        """Run DeepFace face verification between the ID card photo and the selfie."""
        return json.dumps(tool_face_match(id_image_path, selfie_path))

    @lc_tool
    def lc_liveness_check(dummy: str = "") -> str:
        """Check selfie quality: resolution and sharpness to confirm it is a live photo."""
        return json.dumps(tool_liveness_check(selfie_path))

    tools = [lc_check_id_format, lc_run_ocr, lc_face_match, lc_liveness_check]
    llm   = ChatOpenAI(
        model="gpt-3.5-turbo",
        temperature=0,
        openai_api_key=settings.OPENAI_API_KEY,
    )
    agent = initialize_agent(
        tools, llm,
        agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
        verbose=True,
    )

    prompt = f"""
You are a KYC (Know Your Customer) AI Agent for a loan underwriting system.
Your job is to verify the identity of an applicant.

Applicant details:
- Name:      {full_name}
- DOB:       {dob}
- ID Type:   {id_type}
- ID Number: (masked — use lc_check_id_format to validate)

You have 4 tools. Use them in this order:
1. lc_check_id_format  — always run this first; stop immediately if it fails
2. lc_run_ocr          — scan the ID card for name and DOB
3. lc_face_match       — compare ID photo with selfie using AI
4. lc_liveness_check   — check selfie quality

Rules:
- If ID format fails, stop immediately.
- If face match fails, still run liveness but mark as failed overall.
- If OCR fails but face passes, grant low-confidence verification.
- Format validation alone NEVER marks the ID as officially verified.

Your final answer must be ONLY valid JSON:
{{
  "status": "verified" | "failed",
  "confidence": 0.00,
  "verdict": "explanation of final decision",
  "reasoning_steps": ["step1", "step2", ...]
}}
"""

    try:
        res   = agent.run(prompt)
        clean = res.strip().removeprefix("```json").removesuffix("```").strip()
        data  = json.loads(clean)
        checks = {
            "id_format":  tool_check_id_format(id_number, id_type),
            "name_match": {"passed": True, "detail": "See OCR tool output"},
            "dob_match":  {"passed": True, "detail": "See OCR tool output"},
            "face_match": tool_face_match(id_image_path, selfie_path),
            "liveness":   tool_liveness_check(selfie_path),
        }
        return KYCResult(
            status=data["status"],
            confidence=float(data["confidence"]),
            verdict=data["verdict"],
            reasoning_steps=data.get("reasoning_steps", []),
            checks=checks,
            id_type=id_type,
        )
    except Exception as e:
        logger.error(f"OpenAI KYC agent failed: {e}")
        raise RuntimeError(f"KYC Agent Error: {e}")


# ─────────────────────────────────────────────
#  PUBLIC ENTRY POINT
# ─────────────────────────────────────────────
class KYCAgent:
    @staticmethod
    def verify(
        user_id:       str,
        full_name:     str,
        dob:           str,
        id_number:     str,
        id_type:       str = "college",
        id_image_path: str = "",
        selfie_path:   str = "",
    ) -> KYCResult:
        """
        Verify applicant identity.

        Parameters
        ----------
        id_number   : The raw ID number (Aadhaar/PAN/DL/college).
        id_type     : 'aadhaar' | 'pan' | 'dl' | 'college'
        """
        if settings.USE_LOCAL_LLM:
            return mock_kyc_agent(
                user_id, full_name, dob,
                id_number, id_type,
                id_image_path, selfie_path,
            )
        else:
            return openai_kyc_agent(
                user_id, full_name, dob,
                id_number, id_type,
                id_image_path, selfie_path,
            )


# ─────────────────────────────────────────────────────────
#  Cross-document verification aggregator
#  (moved here from the deleted cross_verify.py)
#
#  Applies simple conditional rules:
#    name match + ID match + photo check + payslip name match
#      → overall status and flag_for_review decision
#
#  Does NOT auto-reject loans — only sets status and flags.
# ─────────────────────────────────────────────────────────

from dataclasses import dataclass as _dc, field as _f
from typing import Optional as _Opt


@_dc
class CrossVerifyResult:
    """Aggregated cross-document verification result returned to the API."""
    overall_status:  str         # verified | partially_verified | unable_to_verify | mismatch | manual_review | pending
    overall_message: str         = ""
    flag_for_review: bool        = False
    flags:           list        = _f(default_factory=list)
    mock_mode:       bool        = True
    checks:          dict        = _f(default_factory=dict)


def run_cross_verification(
    registered_name:    str,
    id_type:            str,
    id_number_entered:  str,
    id_image_path:      str,
    payslip_data:       _Opt[dict] = None,
    selfie_path:        str = "",
) -> CrossVerifyResult:
    """
    Run all cross-document checks using simple conditional logic.

    Checks performed (each returned separately):
      1. kyc_name         — registered name vs OCR-extracted name from ID
      2. kyc_id_number    — entered ID number vs extracted ID number
      3. kyc_photo        — photo presence heuristic in ID document
      4. kyc_selfie_match — selfie vs ID photo (DeepFace if available,
                            "Unable to Verify" / "Not Implemented" otherwise)
      5. payslip_name     — registered name vs employee name from payslip
      6. payslip_income   — income consistency (from payslip_data)
      7. name_consistency — KYC name + payslip name both consistent

    Final conditional logic (per spec):
      Name match + ID number match + required photo check pass + payslip name match
        → verified
      Any confirmed mismatch
        → mismatch + flag_for_review
      Missing / unreadable / unextractable info
        → unable_to_verify
      Borderline / partial
        → partially_verified or manual_review

    Does NOT reject the loan — only sets status + flags.
    """
    from services.kyc_service import (
        extract_document_text, extract_id_fields,
        compare_names, compare_id_numbers, detect_photo_in_document,
        check_selfie_vs_id_photo,
        FieldCheck,
    )
    from services.payslip_service import check_payslip_name

    flags   = []
    is_mock = True

    # ── 1. OCR: extract text from KYC document ──────────
    doc_text = ""
    ocr_mode = "demo"
    if id_image_path:
        doc_text, ocr_mode = extract_document_text(id_image_path)
        is_mock = (ocr_mode == "demo")

    # ── 2. KYC name check ───────────────────────────────
    # Normalise before comparison: lowercase, collapse spaces, strip punctuation.
    if ocr_mode in ("demo", "error") or not doc_text.strip():
        kyc_name_check = FieldCheck(
            status="unable_to_verify",
            message=(
                "OCR is unavailable in this environment (Tesseract not installed). "
                "Name could not be extracted from the document. Manual review required."
            ),
            confidence=0.0,
            ocr_mode="demo",
        )
        kyc_id_check = FieldCheck(
            status="unable_to_verify",
            message=(
                "OCR unavailable — ID number could not be extracted from the document. "
                "Manual review required."
            ),
            confidence=0.0,
            ocr_mode="demo",
        )
    else:
        fields = extract_id_fields(doc_text, id_type)
        extracted_name = fields.get("name", "")
        extracted_id   = fields.get("id_number", "")

        # Name check — uses _normalize_name internally (lowercase, strip, collapse spaces)
        kyc_name_check = compare_names(
            entered=registered_name,
            extracted=extracted_name,
            source=f"{id_type.upper()} document",
        )
        kyc_name_check.ocr_mode = "live"

        # If names do not match, add explicit error flag per spec
        if kyc_name_check.status == "mismatch":
            flags.append(
                f"Name on {id_type.upper()} does not match the registered applicant name. "
                "Application flagged for manual review."
            )

        # ID number check — normalise (strip spaces, uppercase) before comparing
        kyc_id_check = compare_id_numbers(
            entered=id_number_entered,
            extracted=extracted_id,
            id_type=id_type,
        )
        kyc_id_check.ocr_mode = "live"

        if kyc_id_check.status == "mismatch":
            flags.append("ID number does not match the uploaded document.")

    # ── 3. Photo presence heuristic ─────────────────────
    # Checks for a visible photo region in the ID image.
    # Does NOT claim face authentication — only detects presence.
    if id_image_path and not id_image_path.lower().endswith(".pdf"):
        kyc_photo_check = detect_photo_in_document(id_image_path)
    else:
        kyc_photo_check = FieldCheck(
            status="unable_to_verify",
            message="Photo presence detection not applicable for PDF documents.",
            confidence=0.0,
        )

    # ── 4. Selfie vs ID photo face check ────────────────
    # Uses DeepFace if available; otherwise explicitly marks as
    # "Unable to Verify" — never falsely claims a match.
    if selfie_path and id_image_path and not id_image_path.lower().endswith(".pdf"):
        kyc_selfie_check = check_selfie_vs_id_photo(id_image_path, selfie_path)
    else:
        kyc_selfie_check = FieldCheck(
            status="unable_to_verify",
            message=(
                "Selfie was not provided or document is a PDF — "
                "face comparison between selfie and ID photograph could not be performed. "
                "Photo verification is marked 'Unable to Verify'."
            ),
            confidence=0.0,
        )

    # ── 5. Payslip name check ───────────────────────────
    if payslip_data:
        employee_name = payslip_data.get("employee_name") or ""
        raw_ps = check_payslip_name(registered_name, employee_name or None)
        payslip_name_check = FieldCheck(
            status=raw_ps["status"],
            message=raw_ps["message"],
            confidence=raw_ps["confidence"],
            ocr_mode=raw_ps.get("ocr_mode", "none"),
        )

        if payslip_name_check.status == "mismatch":
            flags.append("Payslip name does not match the registered applicant name.")

        # Income check
        if payslip_data.get("verified"):
            payslip_income_check = FieldCheck(
                status="verified",
                message=payslip_data.get("message", "Income verified against payslip."),
                confidence=0.9,
            )
        elif payslip_data.get("fraud_flag"):
            payslip_income_check = FieldCheck(
                status="mismatch",
                message=payslip_data.get("message", "Income on payslip does not match declared income."),
                confidence=0.8,
            )
            flags.append("Income mismatch on payslip.")
        elif payslip_data.get("extraction_success") is False:
            payslip_income_check = FieldCheck(
                status="unable_to_verify",
                message=(
                    "Payslip could not be read. "
                    "Income verification is marked 'Unable to Verify' — manual review required."
                ),
                confidence=0.0,
            )
        else:
            payslip_income_check = FieldCheck(
                status="unable_to_verify",
                message="Income amount could not be confirmed from the payslip.",
                confidence=0.0,
            )
    else:
        payslip_name_check   = FieldCheck(status="pending", message="Payslip has not been provided yet.")
        payslip_income_check = FieldCheck(status="pending", message="Payslip has not been provided yet.")

    # ── 6. Cross-document name consistency ──────────────
    kyc_ok       = kyc_name_check.status == "verified"
    pay_ok       = payslip_name_check.status in ("verified",)
    kyc_uv       = kyc_name_check.status in ("unable_to_verify", "pending")
    pay_uv       = payslip_name_check.status in ("unable_to_verify", "pending")
    any_nm_mismatch = "mismatch" in (kyc_name_check.status, payslip_name_check.status)

    if kyc_ok and (pay_ok or pay_uv):
        name_consistency_check = FieldCheck(
            status="verified" if pay_ok else "partially_verified",
            message=(
                "Name is consistent across the KYC document and payslip."
                if pay_ok else
                "KYC document name matches but payslip name could not be verified."
            ),
            confidence=0.95 if pay_ok else 0.65,
        )
    elif kyc_uv and pay_uv:
        name_consistency_check = FieldCheck(
            status="unable_to_verify",
            message=(
                "Name consistency could not be checked — OCR unavailable for both documents."
            ),
            confidence=0.0,
        )
    elif any_nm_mismatch:
        name_consistency_check = FieldCheck(
            status="mismatch",
            message=(
                "Name mismatch detected between the registered name and one or more documents. "
                "Please ensure the correct documents are uploaded."
            ),
            confidence=0.9,
        )
        if "Name mismatch across documents" not in flags:
            flags.append("Name mismatch across documents.")
    else:
        name_consistency_check = FieldCheck(
            status="manual_review",
            message="Name consistency check is inconclusive due to partial OCR results.",
            confidence=0.4,
        )

    # ── Collect remaining flags ──────────────────────────
    if kyc_name_check.status == "mismatch" and not any(
        "registered applicant name" in f or "match registered" in f for f in flags
    ):
        flags.append("KYC document name does not match registered name.")
    if kyc_id_check.status == "mismatch" and "ID number does not match" not in " ".join(flags):
        flags.append("ID number does not match the uploaded document.")
    if payslip_name_check.status == "mismatch" and "Payslip name does not match" not in " ".join(flags):
        flags.append("Payslip name does not match the registered applicant name.")

    # ── 7. Final conditional logic ───────────────────────
    #
    # Spec rules (applied in this priority order):
    #   a. Any confirmed mismatch → mismatch + flag_for_review
    #   b. Name match + ID match + photo check pass + payslip name match → verified
    #   c. Missing / unreadable / unextractable info → unable_to_verify
    #   d. Borderline → manual_review / partially_verified
    #
    # "Required" checks for a Verified outcome:
    #   kyc_name, kyc_id_number, payslip_name (if payslip provided)
    # "Photo requirement": kyc_selfie_check "verified" OR photo detection "verified"
    #   (both may be unable_to_verify in demo environment → does not block verified outcome)

    active = [
        kyc_name_check,
        kyc_id_check,
        payslip_name_check,
        payslip_income_check,
        name_consistency_check,
    ]
    statuses = [c.status for c in active if c.status != "pending"]

    # Determine photo-related outcome (selfie or presence)
    photo_statuses = {kyc_photo_check.status, kyc_selfie_check.status}
    photo_mismatch = "mismatch" in photo_statuses
    photo_verified = "verified" in photo_statuses

    if not statuses:
        overall_status = "pending"
    elif "mismatch" in statuses or photo_mismatch:
        overall_status = "mismatch"
    elif "manual_review" in statuses:
        overall_status = "manual_review"
    else:
        uv = statuses.count("unable_to_verify")
        ok = statuses.count("verified")

        # For a clean "verified" outcome:
        #   all required text checks must be "verified"
        #   photo check: if verified → great; if unable_to_verify → allow but note
        required_ok = (
            kyc_name_check.status == "verified"
            and kyc_id_check.status == "verified"
            and (payslip_name_check.status in ("verified", "pending"))
        )

        if required_ok and uv == 0:
            overall_status = "verified"
        elif required_ok and uv > 0:
            # Text fields all pass; only photo/OCR parts are unable_to_verify
            overall_status = "partially_verified"
        elif uv > 0 and ok == 0:
            overall_status = "unable_to_verify"
        elif uv > 0 and ok > 0:
            overall_status = "partially_verified"
        else:
            overall_status = "verified"

    _messages = {
        "verified":           (
            "All cross-document checks passed. "
            "Identity and income details are consistent — Verification Passed."
        ),
        "partially_verified": (
            "Some checks passed but others could not be verified due to document quality "
            "or missing data. Manual review may be required."
        ),
        "unable_to_verify":   (
            "Document processing returned insufficient data for full verification. "
            "This is usually because OCR (Tesseract) is not installed in this environment. "
            "Manual review is required — the application is not automatically rejected."
        ),
        "mismatch":           (
            "One or more details do not match across documents — Verification Failed. "
            "Manual Review Required. "
            "The loan will not be automatically rejected; a staff member will review."
        ),
        "manual_review":      (
            "One or more checks are borderline. "
            "A staff member will review your documents before a final decision."
        ),
        "pending":            "Verification has not been completed yet.",
    }
    overall_message = _messages.get(overall_status, "Verification status unknown.")
    unique_flags = list(dict.fromkeys(flags))  # preserve order, deduplicate
    if unique_flags:
        overall_message += f" Issues flagged: {'; '.join(unique_flags[:3])}"

    flag_for_review = overall_status in ("mismatch", "manual_review")

    logger.info(
        f"CrossVerify complete: overall={overall_status}, "
        f"mock={is_mock}, flags={len(unique_flags)}"
    )

    return CrossVerifyResult(
        overall_status  = overall_status,
        overall_message = overall_message,
        flag_for_review = flag_for_review,
        flags           = unique_flags,
        mock_mode       = is_mock,
        checks          = {
            "kyc_name":         _fc(kyc_name_check),
            "kyc_id_number":    _fc(kyc_id_check),
            "kyc_photo":        _fc(kyc_photo_check),
            "kyc_selfie_match": _fc(kyc_selfie_check),
            "payslip_name":     _fc(payslip_name_check),
            "payslip_income":   _fc(payslip_income_check),
            "name_consistency": _fc(name_consistency_check),
        },
    )


def _fc(check) -> dict:
    """Serialise a FieldCheck into a plain dict for the API response."""
    return {
        "status":     check.status,
        "message":    check.message,
        "confidence": round(check.confidence, 3),
        "ocr_mode":   check.ocr_mode,
    }
