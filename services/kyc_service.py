"""
KYC (Know Your Customer) Document Verification Service
=======================================================
Handles ID document upload, OCR extraction, and cross-document verification.

OCR strategy (auto-detected at runtime, no code changes needed):
  Text extraction  — Tesseract via pytesseract (install binary from
                     https://github.com/UB-Mannheim/tesseract/wiki)
                     Falls back to PyPDF2 for PDF embedded text.
  Photo detection  — OpenCV Haar cascades (bundled, zero install)
  Face matching    — OpenCV LBPH face recogniser (bundled, zero install)
                     Falls back to DeepFace if installed.

Cross-verification logic lives here (name match, ID number match, photo check).
Payslip name check lives in payslip_service.py.
Final aggregation lives in agent/kyc_agent.py.

Status values used throughout:
  "verified"          — extracted data matches entered data
  "mismatch"          — data clearly does not match → flag for manual review
  "unable_to_verify"  — OCR failed / document unreadable
  "manual_review"     — borderline; human must decide
  "pending"           — check has not run yet
"""

import re
import io
import os
import unicodedata
from dataclasses import dataclass, field
from typing import Optional
from PIL import Image, ImageFilter, ImageEnhance
from datetime import datetime
from pathlib import Path

from utils.logger import get_logger
from config import settings

logger = get_logger(__name__)

# ─────────────────────────────────────────────────────────
#  Tesseract binary — auto-locate on Windows if not in PATH
# ─────────────────────────────────────────────────────────
_TESSERACT_SEARCH_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Tesseract-OCR", "tesseract.exe"),
    os.path.join(os.environ.get("USERPROFILE", ""), "AppData", "Local", "Programs", "Tesseract-OCR", "tesseract.exe"),
]

def _configure_tesseract() -> bool:
    """
    Auto-locate the Tesseract binary and configure pytesseract.
    Returns True if Tesseract is available and responding.
    """
    try:
        import pytesseract
        # First try the PATH-configured binary
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        pass

    # Search common Windows install paths
    try:
        import pytesseract
        for path in _TESSERACT_SEARCH_PATHS:
            if os.path.isfile(path):
                pytesseract.pytesseract.tesseract_cmd = path
                try:
                    pytesseract.get_tesseract_version()
                    logger.info(f"Tesseract found at: {path}")
                    return True
                except Exception:
                    continue
    except ImportError:
        pass

    return False

# Run once at module load
_TESSERACT_AVAILABLE = _configure_tesseract()
if _TESSERACT_AVAILABLE:
    logger.info("Tesseract OCR: available — text extraction enabled.")
else:
    logger.warning(
        "Tesseract binary not found. Text extraction will be unavailable. "
        "Install from https://github.com/UB-Mannheim/tesseract/wiki"
    )

# ─────────────────────────────────────────────────────────
#  OpenCV — Haar cascade paths (bundled with opencv-python)
# ─────────────────────────────────────────────────────────
def _get_cascade(filename: str):
    """Load an OpenCV Haar cascade. Returns None if OpenCV unavailable."""
    try:
        import cv2
        path = os.path.join(cv2.data.haarcascades, filename)
        cascade = cv2.CascadeClassifier(path)
        if cascade.empty():
            logger.warning(f"Cascade file empty or not found: {path}")
            return None
        return cascade
    except Exception as e:
        logger.warning(f"Could not load cascade {filename}: {e}")
        return None


# ─────────────────────────────────────────────────────────
#  Result dataclass for a single field check
# ─────────────────────────────────────────────────────────

@dataclass
class FieldCheck:
    """Result for a single cross-document field comparison."""
    status: str           # verified | mismatch | unable_to_verify | manual_review | pending
    message: str  = ""
    confidence: float = 0.0
    ocr_mode: str = "none"   # live | demo | none


# ─────────────────────────────────────────────────────────
#  Name normalization helpers
# ─────────────────────────────────────────────────────────

def _normalize_name(name: str) -> str:
    """
    Normalize a name for comparison:
    - Lowercase, strip, collapse spaces
    - Remove Unicode accents
    - Remove punctuation (.,  -  ')
    - Remove ALL spaces for no-space comparison (PAN card OCR often removes spaces)
    """
    if not name:
        return ""
    n = unicodedata.normalize("NFKD", name)
    n = "".join(c for c in n if not unicodedata.combining(c))
    n = n.lower().strip()
    n = re.sub(r"[.\-',]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n


def _normalize_name_nospace(name: str) -> str:
    """Remove all spaces — for comparing GAURISANJAYBORSE vs GAURI SANJAY BORSE."""
    return re.sub(r"\s+", "", _normalize_name(name))


def _name_similarity(a: str, b: str) -> float:
    """
    0–1 similarity score between two normalized names.
    Uses token overlap + initial matching so "R Kumar" ~ "Rahul Kumar".
    """
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0

    ta = set(a.split())
    tb = set(b.split())

    jaccard = len(ta & tb) / len(ta | tb) if (ta | tb) else 0.0

    if a in b or b in a:
        return max(jaccard, 0.85)

    init_a = {t[0] for t in ta if t}
    init_b = {t[0] for t in tb if t}
    initial_score = len(init_a & init_b) / max(len(init_a | init_b), 1) * 0.8

    return max(jaccard, initial_score)


# ─────────────────────────────────────────────────────────
#  Name comparison
# ─────────────────────────────────────────────────────────

def compare_names(
    entered: str,
    extracted: str,
    threshold_match: float = 0.75,
    threshold_manual: float = 0.50,
    source: str = "document",
) -> FieldCheck:
    """
    Compare entered name vs OCR-extracted name.

    - score >= threshold_match  → verified
    - score >= threshold_manual → manual_review
    - score <  threshold_manual → mismatch  (flag application)
    - extracted empty           → unable_to_verify
    """
    if not extracted:
        return FieldCheck(
            status="unable_to_verify",
            message=f"Name could not be read from the {source}. Will be flagged for manual review.",
            confidence=0.0,
        )

    score = _name_similarity(_normalize_name(entered), _normalize_name(extracted))

    # Also check without spaces — PAN cards often have no spaces between name words
    # e.g. "GAURISANJAYBORSE" should match "GAURI SANJAY BORSE"
    if score < threshold_match:
        nospace_score = _name_similarity(
            _normalize_name_nospace(entered),
            _normalize_name_nospace(extracted),
        )
        score = max(score, nospace_score)

    if score >= threshold_match:
        return FieldCheck(
            status="verified",
            message=f"Name on {source} matches the registered name.",
            confidence=score,
        )
    elif score >= threshold_manual:
        return FieldCheck(
            status="manual_review",
            message=(
                f"Name on {source} partially matches the registered name. "
                "Minor differences may be due to OCR, initials, or formatting. "
                "Flagged for manual review."
            ),
            confidence=score,
        )
    else:
        return FieldCheck(
            status="mismatch",
            message=(
                f"Name on {source} does not match the registered applicant name. "
                "Please ensure you have uploaded the correct document, or contact support."
            ),
            confidence=score,
        )


# ─────────────────────────────────────────────────────────
#  ID number comparison
# ─────────────────────────────────────────────────────────

def compare_id_numbers(entered: str, extracted: str, id_type: str) -> FieldCheck:
    """
    Compare entered ID number vs OCR-extracted ID number.
    Never returns the actual numbers — status + message only.

    Exact match   → verified
    ≥85% chars    → manual_review  (likely OCR error)
    <85%          → mismatch
    empty extract → unable_to_verify
    """
    if not extracted:
        return FieldCheck(
            status="unable_to_verify",
            message="ID number could not be extracted from the document. Manual review required.",
            confidence=0.0,
        )

    clean_e = re.sub(r"\s", "", entered).upper()
    clean_x = re.sub(r"\s", "", extracted).upper()

    if clean_e == clean_x:
        return FieldCheck(
            status="verified",
            message=f"ID number on the document matches the entered {id_type.upper()} number.",
            confidence=1.0,
        )

    common = sum(1 for a, b in zip(clean_e, clean_x) if a == b)
    score  = common / max(len(clean_e), len(clean_x), 1)

    if score >= 0.85:
        return FieldCheck(
            status="manual_review",
            message=(
                f"{id_type.upper()} number extracted from the document partially matches "
                "but has minor differences — likely an OCR reading error. Flagged for manual review."
            ),
            confidence=score,
        )

    return FieldCheck(
        status="mismatch",
        message="ID number does not match the uploaded document.",
        confidence=score,
    )


# ─────────────────────────────────────────────────────────
#  Photo presence detection — OpenCV Haar cascade
# ─────────────────────────────────────────────────────────

def detect_photo_in_document(file_path: str) -> FieldCheck:
    """
    Detect whether the uploaded ID document contains a face photograph.

    Strategy:
      1. OpenCV Haar cascade frontal face detector (bundled, zero install).
         Crops the ID into regions and scans each for a face.
      2. Falls back to pixel variance heuristic (PIL) if OpenCV fails.

    Does NOT authenticate the photo — only confirms a face region exists.
    """
    if file_path.lower().endswith(".pdf"):
        return FieldCheck(
            status="unable_to_verify",
            message="Photo detection not applicable for PDF documents.",
            confidence=0.0,
        )

    # ── Attempt 1: OpenCV Haar cascade ──────────────────
    try:
        import cv2
        import numpy as np

        cascade = _get_cascade("haarcascade_frontalface_default.xml")
        if cascade is not None:
            img_bgr = cv2.imread(file_path)
            if img_bgr is not None:
                h, w = img_bgr.shape[:2]
                if min(h, w) >= 80:
                    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
                    # Enhance contrast for better detection on ID cards
                    gray = cv2.equalizeHist(gray)

                    faces = cascade.detectMultiScale(
                        gray,
                        scaleFactor  = 1.05,
                        minNeighbors = 3,
                        minSize      = (30, 30),
                        flags        = cv2.CASCADE_SCALE_IMAGE,
                    )

                    if len(faces) > 0:
                        # Pick the largest detected face (most likely the photo)
                        areas = [(fw * fh, fx, fy, fw, fh) for (fx, fy, fw, fh) in faces]
                        areas.sort(reverse=True)
                        _, fx, fy, fw, fh = areas[0]
                        face_area_ratio = (fw * fh) / (w * h)
                        # ID card photo typically 5–25% of card area
                        conf = min(0.90, 0.55 + face_area_ratio * 2)
                        logger.info(
                            f"OpenCV face detection: {len(faces)} face(s) found, "
                            f"largest area ratio={face_area_ratio:.2f}"
                        )
                        return FieldCheck(
                            status="verified",
                            message=(
                                f"Face photograph detected in the ID document "
                                f"({len(faces)} face region(s) found via OpenCV). "
                                "Note: presence confirmed, not authenticated."
                            ),
                            confidence=round(conf, 3),
                            ocr_mode="live",
                        )
                    else:
                        # No face found — try profile cascade as backup
                        profile_cascade = _get_cascade("haarcascade_profileface.xml")
                        if profile_cascade is not None:
                            faces_p = profile_cascade.detectMultiScale(
                                gray, scaleFactor=1.05, minNeighbors=3, minSize=(30, 30)
                            )
                            if len(faces_p) > 0:
                                return FieldCheck(
                                    status="verified",
                                    message=(
                                        "Profile face detected in ID document (OpenCV). "
                                        "Note: presence confirmed, not authenticated."
                                    ),
                                    confidence=0.65,
                                    ocr_mode="live",
                                )

                        # No face in either cascade — could be PAN card (no photo) or low quality
                        return FieldCheck(
                            status="unable_to_verify",
                            message=(
                                "No face photograph detected in the document image (OpenCV). "
                                "This may be a low-resolution scan, a document type without a photo "
                                "(e.g. some PAN cards), or the face region may be too small. "
                                "Manual review recommended."
                            ),
                            confidence=0.2,
                            ocr_mode="live",
                        )

    except Exception as e:
        logger.warning(f"OpenCV photo detection failed: {e}")

    # ── Fallback: PIL pixel variance heuristic ───────────
    try:
        import numpy as np
        img = Image.open(file_path).convert("RGB")
        arr = np.array(img)
        h, w = arr.shape[:2]
        if min(h, w) < 100:
            return FieldCheck(
                status="unable_to_verify",
                message="Document image resolution too low for photo detection.",
                confidence=0.0,
            )
        gh, gw = h // 3, w // 3
        cells = [
            float(np.mean(arr[r * gh:(r + 1) * gh, c * gw:(c + 1) * gw]))
            for r in range(3) for c in range(3)
        ]
        variance = float(np.std(cells))
        if variance > 15.0:
            return FieldCheck(
                status="verified",
                message=(
                    "A photograph region was detected in the ID document (variance heuristic). "
                    "Note: this confirms an image region exists, not that it is authenticated."
                ),
                confidence=min(variance / 40.0, 0.65),
            )
        return FieldCheck(
            status="unable_to_verify",
            message="No clear photograph region detected in the document image.",
            confidence=0.2,
        )
    except Exception as e:
        logger.warning(f"PIL photo fallback failed: {e}")
        return FieldCheck(
            status="unable_to_verify",
            message="Photo detection could not be completed. Manual review required.",
            confidence=0.0,
        )


# ─────────────────────────────────────────────────────────
#  Selfie vs ID photo — OpenCV LBPH face comparison
# ─────────────────────────────────────────────────────────

def _crop_largest_face(gray_img, cascade) -> Optional["np.ndarray"]:
    """
    Detect faces and return the largest cropped face region, or None.
    Uses strict minNeighbors=5 to avoid false positives on text/patterns.
    """
    try:
        import numpy as np
        equalized = cv2_equalise(gray_img)
        # minNeighbors=5 — strict, avoids false positives on PAN card text or backgrounds
        faces = cascade.detectMultiScale(
            equalized, scaleFactor=1.05, minNeighbors=5, minSize=(60, 60)
        )
        if len(faces) == 0:
            # Try slightly more lenient if strict finds nothing
            faces = cascade.detectMultiScale(
                equalized, scaleFactor=1.03, minNeighbors=4, minSize=(50, 50)
            )
        if len(faces) == 0:
            return None
        areas = sorted([(fw * fh, fx, fy, fw, fh) for (fx, fy, fw, fh) in faces], reverse=True)
        _, fx, fy, fw, fh = areas[0]
        return gray_img[fy:fy + fh, fx:fx + fw]
    except Exception:
        return None


def cv2_equalise(gray):
    """Histogram-equalise a grayscale OpenCV image."""
    try:
        import cv2
        return cv2.equalizeHist(gray)
    except Exception:
        return gray


def _img_sharpness(gray_img) -> float:
    """Laplacian variance — higher = sharper."""
    try:
        import cv2
        return float(cv2.Laplacian(gray_img, cv2.CV_64F).var())
    except Exception:
        return 0.0


def _lbph_similarity(face_a, face_b) -> float:
    """
    Compare two face crops using OpenCV LBPHFaceRecognizer.
    Train on face_a, predict face_b — lower confidence = better match.
    Returns a 0–1 similarity score (1 = same person, 0 = different).
    Falls back to histogram correlation if LBPH recognizer is unavailable.
    """
    try:
        import cv2
        import numpy as np

        size = (100, 100)
        fa = cv2.resize(face_a, size)
        fb = cv2.resize(face_b, size)

        # Try LBPHFaceRecognizer first (more accurate for real faces)
        try:
            recognizer = cv2.face.LBPHFaceRecognizer_create()
            recognizer.train([fa], np.array([0]))
            label, confidence = recognizer.predict(fb)
            # LBPH confidence: 0 = perfect match, ~100 = different person
            # Map to 0–1 similarity: lower confidence = higher similarity
            similarity = max(0.0, 1.0 - (confidence / 100.0))
            logger.info(f"LBPH recognizer confidence: {confidence:.1f} => similarity: {similarity:.3f}")
            return similarity
        except (AttributeError, cv2.error):
            # cv2.face not available, fall back to histogram
            pass

        # Fallback: histogram correlation
        hist_a = cv2.calcHist([fa], [0], None, [256], [0, 256])
        hist_b = cv2.calcHist([fb], [0], None, [256], [0, 256])
        cv2.normalize(hist_a, hist_a)
        cv2.normalize(hist_b, hist_b)
        score = cv2.compareHist(hist_a, hist_b, cv2.HISTCMP_CORREL)
        return max(0.0, float(score))

    except Exception as e:
        logger.warning(f"Face similarity failed: {e}")
        return 0.0


def check_selfie_vs_id_photo(id_image_path: str, selfie_path: str) -> FieldCheck:
    """
    Compare the photograph on the ID document with the applicant's selfie.

    Strategy (in priority order):
      1. DeepFace VGG-Face (if installed) — accurate deep embedding comparison.
      2. OpenCV face presence check only — confirms both images contain a face,
         but does NOT claim a match/mismatch (LBPH single-sample is unreliable).

    LBPH with one training sample consistently produces confidence > 100 (unknown),
    making it useless for verification. We are honest about this limitation rather
    than returning a false mismatch.
    """
    if not id_image_path or not selfie_path:
        return FieldCheck(
            status="unable_to_verify",
            message="Selfie or ID document path not provided. Face comparison could not be performed.",
            confidence=0.0,
        )

    # ── Attempt 1: DeepFace (accurate, optional) ─────────
    try:
        from deepface import DeepFace

        def _run(enforce: bool):
            return DeepFace.verify(
                img1_path         = id_image_path,
                img2_path         = selfie_path,
                model_name        = "VGG-Face",
                enforce_detection = enforce,
                detector_backend  = "opencv",
            )
        try:
            res      = _run(enforce=True)
            matched  = bool(res.get("verified", False))
            distance = round(float(res.get("distance", 1.0)), 3)
            conf     = round(max(0.0, 1.0 - distance / 0.6), 3)
            return FieldCheck(
                status="verified" if matched else "mismatch",
                message=(
                    f"Selfie matches the photograph on the ID document (DeepFace, distance={distance})."
                    if matched else
                    f"Selfie does not match the photograph on the ID document (DeepFace, distance={distance}). "
                    "Please upload a clear selfie of the same person as on the ID."
                ),
                confidence=conf if matched else 0.0,
                ocr_mode="live",
            )
        except Exception as e1:
            if not any(k in str(e1).lower() for k in ["face", "detect", "no face", "cannot"]):
                raise
            # Lenient attempt
            res      = _run(enforce=False)
            distance = round(float(res.get("distance", 1.0)), 3)
            matched  = distance < 0.35
            conf     = round(max(0.0, 1.0 - distance / 0.6), 3)
            return FieldCheck(
                status="verified" if matched else "mismatch",
                message=(
                    f"Selfie {'matches' if matched else 'does not match'} the ID photograph "
                    f"(DeepFace lenient, distance={distance})."
                ),
                confidence=conf if matched else 0.0,
                ocr_mode="live",
            )

    except ImportError:
        pass  # DeepFace not installed — fall through
    except Exception as e:
        logger.warning(f"DeepFace face match failed: {e}")

    # ── Attempt 2: OpenCV — presence only, no match claim ─
    # LBPH with a single training sample always returns high uncertainty (confidence > 100).
    # We only confirm that BOTH images contain a visible face.
    # We do NOT claim match or mismatch — that requires a proper embedding model.
    try:
        import cv2

        cascade = _get_cascade("haarcascade_frontalface_default.xml")
        if cascade is not None:
            img_id     = cv2.imread(id_image_path)
            img_selfie = cv2.imread(selfie_path)

            if img_id is not None and img_selfie is not None:
                g_id  = cv2.cvtColor(img_id,     cv2.COLOR_BGR2GRAY)
                g_sel = cv2.cvtColor(img_selfie, cv2.COLOR_BGR2GRAY)

                face_id  = _crop_largest_face(g_id,  cascade)
                face_sel = _crop_largest_face(g_sel, cascade)

                selfie_sharpness = _img_sharpness(g_sel)
                if selfie_sharpness < 30.0:
                    return FieldCheck(
                        status="unable_to_verify",
                        message=(
                            f"Selfie is too blurry for face verification "
                            f"(sharpness={selfie_sharpness:.0f}). "
                            "Please upload a clear, well-lit selfie."
                        ),
                        confidence=0.0,
                        ocr_mode="live",
                    )

                if face_id is None:
                    return FieldCheck(
                        status="unable_to_verify",
                        message=(
                            "No face detected in the ID document. "
                            "Please ensure your ID card contains a clear photograph."
                        ),
                        confidence=0.0,
                        ocr_mode="live",
                    )
                if face_sel is None:
                    return FieldCheck(
                        status="unable_to_verify",
                        message=(
                            "No face detected in the selfie. "
                            "Please upload a clear frontal selfie."
                        ),
                        confidence=0.0,
                        ocr_mode="live",
                    )

                # Both faces detected — but we cannot reliably compare them
                # without a proper embedding model. Mark for manual review.
                return FieldCheck(
                    status="manual_review",
                    message=(
                        "A face was detected in both the ID card and the selfie. "
                        "Automated face matching requires DeepFace (not installed). "
                        "A staff member will visually verify the photographs during manual review."
                    ),
                    confidence=0.5,
                    ocr_mode="live",
                )

    except Exception as e:
        logger.warning(f"OpenCV face presence check failed: {e}")

    return FieldCheck(
        status="unable_to_verify",
        message=(
            "Face verification could not be completed automatically. "
            "Your documents will be reviewed manually."
        ),
        confidence=0.0,
    )


# ─────────────────────────────────────────────────────────
#  OCR helpers — Tesseract + OpenCV preprocessing
# ─────────────────────────────────────────────────────────

def _ocr_available() -> bool:
    """Return True if Tesseract binary is available (checked at module load)."""
    return _TESSERACT_AVAILABLE


def _preprocess_for_ocr(path: str) -> "Image":
    """
    OpenCV-based preprocessing pipeline to improve Tesseract accuracy:
      1. Load with OpenCV (handles more formats than PIL)
      2. Convert to grayscale
      3. Resize to a minimum width of 1200px (Tesseract works better on larger images)
      4. Adaptive threshold to binarise text cleanly
      5. Denoise with median blur
      6. Return as PIL Image for pytesseract
    """
    try:
        import cv2
        import numpy as np

        img = cv2.imread(path)
        if img is None:
            # Fallback: PIL load
            pil_img = Image.open(path).convert("RGB")
            img = np.array(pil_img)[:, :, ::-1]  # RGB → BGR

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Upscale if too small — Tesseract needs at least ~300 DPI equivalent
        h, w = gray.shape
        if w < 1200:
            scale = 1200 / w
            gray = cv2.resize(gray, None, fx=scale, fy=scale,
                              interpolation=cv2.INTER_CUBIC)

        # Denoise before threshold
        gray = cv2.medianBlur(gray, 3)

        # Adaptive threshold — handles uneven lighting on ID cards
        binary = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=31,
            C=10,
        )

        # Slight sharpening pass
        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
        sharpened = cv2.filter2D(binary, -1, kernel)

        return Image.fromarray(sharpened)

    except Exception as e:
        logger.warning(f"OpenCV preprocessing failed, falling back to plain PIL: {e}")
        try:
            return Image.open(path).convert("L")
        except Exception:
            return None


def _extract_text_image(path: str) -> str:
    """Extract text from an ID card image using OpenCV preprocessing + Tesseract."""
    try:
        import pytesseract

        preprocessed = _preprocess_for_ocr(path)
        if preprocessed is None:
            return ""

        # PSM 6 = assume uniform block of text (good for ID cards)
        # OEM 3 = default engine (LSTM + legacy)
        config = "--psm 6 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789/: .-"
        text = pytesseract.image_to_string(preprocessed, config=config)

        # Also try PSM 4 (assume single column) and pick the longer result
        try:
            config2 = "--psm 4 --oem 3"
            text2 = pytesseract.image_to_string(preprocessed, config=config2)
            if len(text2.strip()) > len(text.strip()):
                text = text2
        except Exception:
            pass

        logger.info(f"Tesseract extracted {len(text.strip())} chars from {path}")
        return text

    except Exception as e:
        logger.warning(f"Tesseract image OCR failed: {e}")
        return ""


def _extract_text_pdf(path: str) -> str:
    """Extract embedded text from a PDF using PyPDF2."""
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(path)
        text = "\n".join(p.extract_text() or "" for p in reader.pages)
        logger.info(f"PyPDF2 extracted {len(text.strip())} chars from PDF")
        return text
    except Exception as e:
        logger.warning(f"PDF text extraction failed: {e}")
        return ""


def extract_document_text(file_path: str) -> tuple[str, str]:
    """
    Extract text from an image or PDF KYC document.

    For images: OpenCV preprocessing → Tesseract OCR.
    For PDFs:   PyPDF2 embedded text extraction (no OCR needed for digital PDFs).

    Returns (text, mode):
      mode = 'live'  — text successfully extracted
      mode = 'demo'  — Tesseract not available (install binary)
      mode = 'error' — extraction failed or returned empty
    """
    is_pdf = file_path.lower().endswith(".pdf")

    if is_pdf:
        # PDFs with embedded text work without Tesseract
        text = _extract_text_pdf(file_path)
        if text.strip():
            return text, "live"
        # Scanned PDF — would need OCR; flag as demo if Tesseract absent
        if not _TESSERACT_AVAILABLE:
            return "", "demo"
        return "", "error"

    # Image file
    if not _TESSERACT_AVAILABLE:
        return "", "demo"

    text = _extract_text_image(file_path)
    return (text, "live") if text.strip() else ("", "error")


# ─────────────────────────────────────────────────────────
#  Per-ID-type field extractors
# ─────────────────────────────────────────────────────────

def _clean_ocr_text(text: str) -> str:
    """Collapse extra spaces and normalise common OCR noise in a single line."""
    return re.sub(r"\s+", " ", text.strip())


def _extract_aadhaar_fields(text: str) -> dict:
    """
    Extract name and Aadhaar UID from OCR text.
    Handles OCR noise: spaces inserted between digits, mixed case labels.
    """
    name, uid = "", ""

    # Name: look for explicit label first, then capitalised word sequence
    for p in [
        r"(?:name|नाम)\s*[:\-]?\s*([A-Za-z][A-Za-z ]{2,48})",
        r"(?:^|\n)([A-Z][a-z]+(?: [A-Z][a-z]+)+)",
    ]:
        m = re.search(p, text, re.IGNORECASE | re.MULTILINE)
        if m:
            name = _clean_ocr_text(m.group(1))
            break

    # Aadhaar: 12 digits, possibly with spaces every 4 (e.g. "1234 5678 9012")
    for p in [
        r"\b(\d{4}\s?\d{4}\s?\d{4})\b",   # formatted
        r"\b(\d{12})\b",                    # raw
    ]:
        m = re.search(p, text)
        if m:
            uid = re.sub(r"\s", "", m.group(1))
            break

    return {"name": name, "id_number": uid}


def _fix_pan_ocr(raw: str) -> str:
    """
    Fix common OCR misreads in a PAN number string.
    PAN format: 5 letters + 4 digits + 1 letter  (e.g. ABCDE1234F)
    OCR commonly:
      - inserts spaces between chars  → remove all spaces first
      - reads O as 0 in digit positions (positions 5–8)
      - reads 0 as O in letter positions (0–4, 9)
      - reads D as 0 or vice versa
    """
    # Remove spaces
    s = re.sub(r"\s+", "", raw).upper()
    if len(s) != 10:
        return s  # can't fix if length is wrong

    result = list(s)
    # Positions 0–4 must be letters
    letter_fixes = {'0': 'O', '1': 'I', '8': 'B', '5': 'S', '6': 'G'}
    for i in range(5):
        result[i] = letter_fixes.get(result[i], result[i])

    # Positions 5–8 must be digits
    digit_fixes = {'O': '0', 'I': '1', 'B': '8', 'S': '5', 'G': '6', 'D': '0', 'Q': '0'}
    for i in range(5, 9):
        result[i] = digit_fixes.get(result[i], result[i])

    # Position 9 must be a letter
    result[9] = letter_fixes.get(result[9], result[9])
    return "".join(result)


def _extract_pan_fields(text: str) -> dict:
    """
    Extract name and PAN number from OCR text.
    Handles real PAN card OCR output including:
      - No spaces between words (GAURISANJAYBORSE)
      - Noise before the actual name line
      - Mixed labels (amaName, Name, name:)
      - PAN number with OCR noise (spaces, 0/O confusion)
    """
    name, pan = "", ""
    upper = text.upper()

    # ── Name extraction ──────────────────────────────────
    # Strategy: look for a line that is ALL-CAPS alphabetic chars, at least 6 chars,
    # preceded by a name-related label OR just standalone on a line.
    # PAN cards often have name without spaces: GAURISANJAYBORSE

    # 1. Try label-based: look for "Name" keyword then next non-empty line
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    found_name_label = False
    for i, line in enumerate(lines):
        # Detect name label line (often garbled: "amaName", "Name", "name:")
        if re.search(r'(?:name|ame\s*N)', line, re.IGNORECASE) and len(line) < 30:
            found_name_label = True
            # Look at the next 1-2 lines for the actual name
            for j in range(i + 1, min(i + 3, len(lines))):
                candidate = lines[j].strip()
                # Clean OCR noise chars
                cleaned = re.sub(r'[^A-Za-z\s]', '', candidate).strip()
                cleaned = re.sub(r'\s+', ' ', cleaned).strip()
                # A valid name is 4+ alpha chars, mostly letters
                if len(cleaned) >= 4 and len(re.sub(r'[^A-Za-z]', '', cleaned)) / max(len(cleaned), 1) > 0.7:
                    # Skip obvious non-name words
                    skip = {'INCOME', 'TAX', 'DEPARTMENT', 'GOVT', 'INDIA', 'PERMANENT',
                            'ACCOUNT', 'NUMBER', 'CARD', 'FATHERS', 'FATHER', 'DATE',
                            'BIRTH', 'SIGNATURE', 'GOVERNMENT', 'SERIAL'}
                    words = cleaned.upper().split()
                    if not any(w in skip for w in words if len(w) > 3):
                        name = cleaned.upper()
                        break
            if name:
                break

    # 2. If no name found, look for a line with a colon prefix followed by all-caps: e.g. ":GAURISANJAYBORSE"
    if not name:
        for line in lines:
            m = re.match(r'^[:\s]*([A-Z]{4,}(?:\s[A-Z]{2,})*)$', line.strip())
            if m:
                candidate = m.group(1).strip()
                skip = {'INCOMETAXDEPARTMENT', 'PERMANENTACCOUNTNUMBER', 'GOVERNMENTOFINDIA',
                        'INDIA', 'SIGNATURE', 'FATHERSNAME', 'DATEOFBIRTH'}
                if candidate not in skip and len(candidate) >= 4:
                    name = candidate
                    break

    # 3. Fallback: find ":GAURISANJAYBORSE"-style line (colon then all caps, no spaces)
    if not name:
        for line in lines:
            m = re.match(r'^[:\s]*([A-Z]{6,40})$', line.strip().upper())
            if m:
                candidate = m.group(1)
                skip_words = {'INCOMETAXDEPARTMENT', 'PERMANENTACCOUNTNUMBER', 'GOVERNMENTOFINDIA',
                              'FATHERSNAME', 'DATEOFBIRTH', 'SIGNATURE'}
                if candidate not in skip_words:
                    name = candidate
                    break

    # ── PAN number extraction ────────────────────────────
    # Strict match first
    m = re.search(r'\b([A-Z0-9]\s?[A-Z0-9]\s?[A-Z0-9]\s?[A-Z0-9]\s?[A-Z0-9]\s?'
                  r'[0-9]\s?[0-9]\s?[0-9]\s?[0-9]\s?[A-Z0-9])\b', upper)
    if m:
        candidate = _fix_pan_ocr(re.sub(r'\s', '', m.group(1)))
        if re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]$', candidate):
            pan = candidate

    # Fallback: any 10-char alphanumeric block
    if not pan:
        for token in re.findall(r'[A-Z0-9][\sA-Z0-9]{8,12}[A-Z0-9]', upper):
            candidate = _fix_pan_ocr(re.sub(r'\s', '', token))
            if re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]$', candidate):
                pan = candidate
                break

    return {"name": name, "id_number": pan}


def _extract_dl_fields(text: str) -> dict:
    """
    Extract name and DL number from OCR text.
    Handles common OCR noise in alphanumeric licence numbers.
    """
    name, dl = "", ""

    for p in [
        r"(?:name|Name|s/o|d/o|w/o)\s*[:\-]?\s*([A-Za-z][A-Za-z ]{2,48})",
        r"(?:holder|Holder)\s*[:\-]?\s*([A-Za-z][A-Za-z ]{2,48})",
    ]:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            name = _clean_ocr_text(m.group(1))
            break

    # DL: state code (2 letters) + digits/alphanum, remove spaces
    upper = re.sub(r"\s+", "", text.upper())
    m = re.search(r"([A-Z]{2}\d{2,}[A-Z0-9]{4,})", upper)
    if m and 9 <= len(m.group(1)) <= 20:
        dl = m.group(1)

    return {"name": name, "id_number": dl}


def extract_id_fields(text: str, id_type: str) -> dict:
    """Dispatch to correct extractor. Returns dict with 'name' and 'id_number'."""
    if id_type == "aadhaar":
        return _extract_aadhaar_fields(text)
    elif id_type == "pan":
        return _extract_pan_fields(text)
    elif id_type == "dl":
        return _extract_dl_fields(text)
    return {"name": "", "id_number": ""}


# ─────────────────────────────────────────────────────────
#  KYCService — file save + legacy document verify
# ─────────────────────────────────────────────────────────

class KYCService:
    def __init__(self):
        self.upload_dir = Path(settings.UPLOAD_DIR)
        self.upload_dir.mkdir(exist_ok=True)

        self._tesseract_available = _ocr_available()
        if self._tesseract_available:
            logger.info("Tesseract OCR available.")
        else:
            logger.warning("Tesseract not found — KYC will use mock verification.")

    async def save_document(self, file_content: bytes, user_id: str, filename: str) -> str:
        try:
            safe_user_id = user_id.replace('@', '_at_').replace('.', '_')
            user_dir     = self.upload_dir / safe_user_id
            user_dir.mkdir(exist_ok=True)
            ts           = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_filename = f"id_document_{ts}{Path(filename).suffix}"
            file_path    = user_dir / new_filename
            with open(file_path, 'wb') as f:
                f.write(file_content)
            logger.info(f"Saved KYC document for user {user_id}: {new_filename}")
            return str(file_path)
        except Exception as e:
            logger.error(f"Error saving document: {e}")
            raise Exception(f"Failed to save document: {str(e)}")

    async def extract_text_from_image(self, image_path: str) -> str:
        if not self._tesseract_available:
            return ""
        return _extract_text_image(image_path)

    def extract_name_from_text(self, text: str) -> str:
        for pattern in [
            r'Name[:\s]+([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'FULL NAME[:\s]+([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'Name:\s*([^\n]+)',
        ]:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return re.sub(r'\s+', ' ', m.group(1).strip())
        return ""

    def extract_dob_from_text(self, text: str) -> str:
        for pattern in [
            r'DOB[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'Date of Birth[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
        ]:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return m.group(1)
        return ""

    async def verify_document(
        self,
        image_path: str,
        expected_name: str = None,
        expected_dob:  str = None,
    ) -> dict:
        try:
            text = await self.extract_text_from_image(image_path)

            if not self._tesseract_available or not text.strip():
                logger.info("KYC mock verification used (Tesseract unavailable or empty OCR)")
                return {
                    "status":         "verified",
                    "extracted_name": expected_name or "N/A",
                    "extracted_dob":  expected_dob  or "N/A",
                    "name_match":     True,
                    "dob_match":      True,
                    "confidence":     0.75,
                    "mock":           True,
                }

            extracted_name = self.extract_name_from_text(text)
            extracted_dob  = self.extract_dob_from_text(text)
            name_match     = self._fuzzy_match(expected_name, extracted_name) if expected_name and extracted_name else False
            dob_match      = self._fuzzy_match(expected_dob,  extracted_dob)  if expected_dob  and extracted_dob  else False
            status         = "verified" if (name_match or dob_match) else "needs_review"
            confidence     = 0.85       if (name_match or dob_match) else 0.4

            return {
                "status":         status,
                "extracted_name": extracted_name,
                "extracted_dob":  extracted_dob,
                "name_match":     name_match,
                "dob_match":      dob_match,
                "confidence":     confidence,
                "mock":           False,
            }
        except Exception as e:
            logger.error(f"Error verifying document: {e}")
            return {"status": "error", "error": str(e), "confidence": 0.0}

    def _fuzzy_match(self, str1: str, str2: str, threshold: float = 0.7) -> bool:
        str1 = str1.lower().strip()
        str2 = str2.lower().strip()
        if str1 == str2:
            return True
        if str1 in str2 or str2 in str1:
            return True
        common_chars = sum(1 for c in str1 if c in str2)
        similarity   = common_chars / max(len(str1), len(str2))
        return similarity >= threshold


kyc_service = KYCService()
