from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from api.schemas import LoanApplicationRequest, AgentDecisionResponse, LoggedDecision, DownloadReportRequest
from agent.core import LoanAgent
from agent.memory import save_decision, get_similar_decisions
from utils.db import create_or_update_user, update_user_stats, get_user_profile
from utils.report_generator import generate_loan_report_pdf
from utils.logger import get_logger
from services.credit_bureau_service import credit_bureau_service
from services.kyc_service import kyc_service
from database import get_loan_applications

logger = get_logger(__name__)
router = APIRouter()

@router.get("/health")
async def health_check():
    return {"status": "ok", "message": "Autonomous Credit Underwriting Agent is running."}

@router.get("/user/{user_id}")
async def get_user(user_id: str):
    """Get user profile and statistics"""
    try:
        user = await get_user_profile(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        # Convert ObjectId to string for JSON serialization
        if "_id" in user:
            user["_id"] = str(user["_id"])
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user: {e}")
        raise HTTPException(status_code=500, detail="Error fetching user profile")

@router.post("/analyze-loan", response_model=AgentDecisionResponse)
async def analyze_loan(application: LoanApplicationRequest, background_tasks: BackgroundTasks):
    try:
        logger.info(f"Processing loan application for user: {application.user_id}")
        
        # Ensure user exists in database
        await create_or_update_user(application.user_id)
        
        # Log similar decisions for contextual visibility (use internal_score if credit_score missing)
        score_for_lookup = application.credit_score or 650
        similar_past = await get_similar_decisions(score_for_lookup)
        if similar_past:
            logger.info(f"Found {len(similar_past)} similar past decisions: {similar_past}")
        
        # Fast processing via the agent
        # Fetch cross-verify data from DB before running the pipeline
        # so LoanDecisionAgent can use it to escalate decisions
        cross_verify_data = None
        try:
            from utils.db import get_db as _get_db
            _db = _get_db()
            if _db is not None:
                _kyc_rec = await _db["kyc_records"].find_one({"user_id": application.user_id})
                if _kyc_rec and _kyc_rec.get("cross_verify_status"):
                    cross_verify_data = {
                        "overall_status": _kyc_rec.get("cross_verify_status"),
                        "overall_message": "",
                        "flag_for_review": _kyc_rec.get("flag_for_review", False),
                        "flags": _kyc_rec.get("cross_verify_flags", []),
                        "checks": _kyc_rec.get("cross_verify_checks", {}),
                    }
        except Exception:
            pass

        try:
            decision: AgentDecisionResponse = LoanAgent.process_application(
                application, cross_verify_data=cross_verify_data
            )
        except RuntimeError as agent_err:
            logger.error(f"Agent internally failed: {agent_err}")
            raise HTTPException(status_code=500, detail=str(agent_err))
            
        logger.info(f"Agent decision for {application.user_id}: {decision.decision} with confidence: {decision.confidence:.2f}")
        
        # Prepare the log data
        logged_data = LoggedDecision(
            user_id=application.user_id,
            application_data=application.model_dump(),
            risk_score=decision.risk_score,
            confidence=decision.confidence,
            decision=decision.decision,
            explanation=decision.explanation,
            important_features=decision.important_features
        )

        # Attach KYC status from DB (best-effort)
        try:
            from utils.db import get_db
            db = get_db()
            if db is not None:
                kyc_rec = await db["kyc_records"].find_one({"user_id": application.user_id})
                if kyc_rec:
                    logged_data.application_data["kyc_status"]           = kyc_rec.get("kyc_status", "pending")
                    logged_data.application_data["kyc_id_type"]          = kyc_rec.get("id_type")
                    logged_data.application_data["cross_verify_status"]  = kyc_rec.get("cross_verify_status")
                    logged_data.application_data["cross_verify_flags"]   = kyc_rec.get("cross_verify_flags", [])
        except Exception:
            pass

        # Save synchronously so admin sees it immediately
        await save_decision(logged_data)
        background_tasks.add_task(update_user_stats, application.user_id, decision.decision)
        
        return decision
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unhandled error processing loan application: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error during loan analysis.")

@router.post("/download-report")
async def download_report(report_data: DownloadReportRequest):
    """
    Generate and download a PDF report of the loan decision
    """
    try:
        logger.info(f"Generating PDF report for user: {report_data.user_id}")
        
        # Separate application data and decision data
        application_data = {
            "user_id": report_data.user_id,
            "income": report_data.income,
            "credit_score": report_data.credit_score,
            "dti": report_data.dti,
            "employment_length": report_data.employment_length,
            "currency": report_data.currency
        }
        
        decision_data = {
            "risk_score": report_data.risk_score,
            "confidence": report_data.confidence,
            "decision": report_data.decision,
            "explanation": report_data.explanation,
            "important_features": [f.dict() for f in report_data.important_features]
        }
        
        # Generate PDF
        pdf_buffer = generate_loan_report_pdf(
            application_data=application_data,
            decision_data=decision_data
        )
        
        # Return as streaming response
        filename = f"Loan_Decision_{report_data.user_id}_{report_data.decision}.pdf"
        
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except Exception as e:
        logger.error(f"Error generating PDF report: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF report: {str(e)}")


# ============================================
# PLAID INTEGRATION ENDPOINTS
# ============================================

@router.post("/plaid/create-link-token")
async def create_plaid_link_token(user_id: str, user_name: str = None):
    """
    Create Plaid Link token for frontend initialization
    """
    try:
        result = await plaid_service.create_link_token(user_id, user_name)
        return result
    except Exception as e:
        logger.error(f"Error creating Plaid link token: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/plaid/exchange-token")
async def exchange_plaid_token(public_token: str):
    """
    Exchange Plaid public token for access token
    """
    try:
        result = await plaid_service.exchange_public_token(public_token)
        return result
    except Exception as e:
        logger.error(f"Error exchanging Plaid token: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/plaid/get-balances")
async def get_plaid_balances(access_token: str):
    """
    Get account balances from Plaid
    """
    try:
        result = await plaid_service.get_account_balances(access_token)
        return result
    except Exception as e:
        logger.error(f"Error getting Plaid balances: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/plaid/get-income")
async def get_plaid_income(access_token: str):
    """
    Get income data from Plaid
    """
    try:
        result = await plaid_service.get_income_data(access_token)
        return result
    except Exception as e:
        logger.error(f"Error getting Plaid income: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# CREDIT BUREAU INTEGRATION ENDPOINTS
# ============================================

@router.post("/credit-bureau/check")
async def check_credit_bureau(user_id: str, full_name: str = ""):
    """
    Get credit data from credit bureau API
    """
    try:
        result = await credit_bureau_service.get_credit_data(user_id, full_name)
        return result
    except Exception as e:
        logger.error(f"Error checking credit bureau: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# KYC / DOCUMENT VERIFICATION ENDPOINTS
# ============================================

@router.post("/kyc/upload-document")
async def upload_kyc_document(
    user_id: str = Form(...),
    expected_name: str = Form(None),
    expected_dob: str = Form(None),
    file: UploadFile = File(...)
):
    """
    Upload and verify ID document
    """
    try:
        # Validate file type
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="Only image files are allowed")
        
        # Read file content
        content = await file.read()
        
        # Check file size (5MB limit)
        if len(content) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File size exceeds 5MB limit")
        
        # Save document
        file_path = await kyc_service.save_document(content, user_id, file.filename)
        
        # Verify document
        verification_result = await kyc_service.verify_document(
            file_path,
            expected_name,
            expected_dob
        )
        
        return {
            "success": True,
            "file_path": file_path,
            "verification": verification_result
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading KYC document: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# ENHANCED LOAN ANALYSIS WITH INTEGRATIONS
# ============================================

@router.post("/analyze-loan-enhanced", response_model=AgentDecisionResponse)
async def analyze_loan_enhanced(
    application: LoanApplicationRequest,
    background_tasks: BackgroundTasks,
    use_credit_bureau: bool = True,
    plaid_access_token: str = None
):
    """
    Enhanced loan analysis with credit bureau and Plaid integration
    """
    try:
        logger.info(f"Processing enhanced loan application for user: {application.user_id}")
        
        # Ensure user exists in database
        await create_or_update_user(application.user_id)
        
        # Step 1: Get credit data from credit bureau
        credit_data = None
        if use_credit_bureau:
            credit_data = await credit_bureau_service.get_credit_data(application.user_id)
            logger.info(f"Credit bureau data: Score={credit_data['credit_score']}, DTI={credit_data['debt_index']}")
            
            # Override application data with bureau data
            application.credit_score = credit_data['credit_score']
            application.dti = credit_data['debt_index']
        
        # Step 2: Get Plaid data if access token provided
        plaid_data = None
        if plaid_access_token:
            try:
                balance_data = await plaid_service.get_account_balances(plaid_access_token)
                income_data = await plaid_service.get_income_data(plaid_access_token)
                
                plaid_data = {
                    "total_balance": balance_data['total_balance'],
                    "annual_income": income_data['annual_income']
                }
                
                # Override income with Plaid data
                if income_data['verified']:
                    application.income = income_data['annual_income']
                
                logger.info(f"Plaid data: Balance=${balance_data['total_balance']}, Income=${income_data['annual_income']}")
            except Exception as e:
                logger.warning(f"Could not fetch Plaid data: {e}")
        
        # Step 3: Run AI agent analysis
        try:
            decision: AgentDecisionResponse = LoanAgent.process_application(application)
        except RuntimeError as agent_err:
            logger.error(f"Agent internally failed: {agent_err}")
            raise HTTPException(status_code=500, detail=str(agent_err))
        
        logger.info(f"Agent decision for {application.user_id}: {decision.decision} with confidence: {decision.confidence:.2f}")
        
        # Step 4: Save decision with enhanced data
        logged_data = LoggedDecision(
            user_id=application.user_id,
            application_data={
                **application.model_dump(),
                "credit_bureau_data": credit_data,
                "plaid_data": plaid_data
            },
            risk_score=decision.risk_score,
            confidence=decision.confidence,
            decision=decision.decision,
            explanation=decision.explanation,
            important_features=decision.important_features
        )
        
        # Save synchronously so admin sees it immediately
        await save_decision(logged_data)
        background_tasks.add_task(update_user_stats, application.user_id, decision.decision)
        
        return decision
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unhandled error in enhanced loan analysis: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error during enhanced loan analysis.")


# ============================================
# ADMIN ENDPOINTS
# ============================================

@router.get("/admin/applications")
async def admin_get_applications(limit: int = 200):
    """
    Return all loan applications for the admin dashboard.
    Pulls from the 'decisions' collection (saved by agent/memory.py)
    as well as the 'loans' collection.
    """
    try:
        from utils.db import get_db
        db = get_db()
        if db is None:
            raise HTTPException(status_code=503, detail="Database not connected.")

        # Fetch from decisions collection (agent memory)
        cursor = db["decisions"].find({}).sort("timestamp", -1).limit(limit)
        docs = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            docs.append(doc)

        # If decisions collection is empty, fall back to loans collection
        if not docs:
            loans = await get_loan_applications(limit=limit)
            for loan in loans:
                # Normalise field names to match what the frontend expects
                docs.append({
                    "_id":            loan.get("id", ""),
                    "user_id":        loan.get("applicant_id", loan.get("user_id", "—")),
                    "decision":       loan.get("decision", {}).get("authorization", loan.get("status", "—")).capitalize(),
                    "risk_score":     loan.get("ai_analysis", {}).get("risk_probability", 0),
                    "confidence":     loan.get("ai_analysis", {}).get("confidence_score", 0),
                    "explanation":    loan.get("decision", {}).get("reasoning", ""),
                    "timestamp":      str(loan.get("created_at", "")),
                    "application_data": {
                        "income":             loan.get("income"),
                        "credit_score":       loan.get("credit_score_input"),
                        "dti":                loan.get("dti_input"),
                        "employment_length":  loan.get("employment_length"),
                        "currency":           loan.get("currency", "USD"),
                    },
                })

        return docs

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin applications fetch error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/admin/applications/{app_id}/decision")
async def admin_override_decision(app_id: str, payload: dict):
    """
    Admin overrides the decision for a Review application.
    payload: { "decision": "Approve" | "Reject", "admin_note": "..." }
    """
    try:
        from utils.db import get_db
        from bson import ObjectId
        from datetime import datetime

        db = get_db()
        if db is None:
            raise HTTPException(status_code=503, detail="Database not connected.")

        new_decision = payload.get("decision")
        if new_decision not in ("Approve", "Reject"):
            raise HTTPException(status_code=400, detail="Decision must be Approve or Reject.")

        result = await db["decisions"].update_one(
            {"_id": ObjectId(app_id)},
            {"$set": {
                "decision":        new_decision,
                "admin_override":  True,
                "admin_note":      payload.get("admin_note", ""),
                "reviewed_at":     datetime.utcnow().isoformat(),
            }}
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Application not found.")

        logger.info(f"Admin overrode decision for {app_id} → {new_decision}")
        return {"success": True, "new_decision": new_decision}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin override error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/kyc/cross-verify")
async def cross_verify_documents(
    user_id:         str        = Form(...),
    registered_name: str        = Form(...),
    id_type:         str        = Form(...),
    id_number:       str        = Form(...),
    id_document:     UploadFile = File(...),
    payslip_data_json: str      = Form(default="{}"),
    selfie:          UploadFile = File(default=None),
):
    """
    Cross-verify the applicant's registered details against their
    KYC document and payslip data already extracted by /verify-income.

    - Extracts name + ID number from the KYC document via OCR
    - Normalises names (lowercase, collapse spaces) before comparison
    - Compares entered ID number vs extracted ID number
    - Detects photo presence in ID document (heuristic)
    - If selfie provided: compares selfie with ID photo via DeepFace
      (or marks as "Unable to Verify" if DeepFace not installed)
    - Cross-checks payslip employee name vs registered name
    - Returns structured CrossVerifyResult (never exposes full ID numbers)

    Final logic:
      Name match + ID match + required photo pass + payslip name match → Verification Passed
      Any confirmed mismatch → Verification Failed + Manual Review Required
      Missing / unreadable info → Unable to Verify
    """
    import json as _json
    import tempfile, os
    from agent.kyc_agent import _mask_id, run_cross_verification
    from pathlib import Path
    from datetime import datetime
    from config import settings as _settings

    allowed_id_types = {"aadhaar", "pan", "dl"}
    clean_id_type = id_type.lower().strip()
    if clean_id_type not in allowed_id_types:
        raise HTTPException(status_code=400, detail=f"Invalid id_type '{id_type}'.")

    # Validate KYC document file type
    ct = id_document.content_type or ""
    fn = (id_document.filename or "").lower()
    if not ct.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail=(
                "ID document must be a JPG or PNG image, not a PDF. "
                "PDFs cannot be scanned for ID number verification. "
                "Please upload a clear photo of your ID card."
            )
        )

    id_bytes = await id_document.read()
    if len(id_bytes) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Document exceeds 5 MB limit.")

    # Parse optional payslip data JSON
    try:
        payslip_data = _json.loads(payslip_data_json) if payslip_data_json.strip() else {}
    except Exception:
        payslip_data = {}

    # Write KYC document to temp file
    suffix = ".pdf" if ("pdf" in ct or fn.endswith(".pdf")) else ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(id_bytes)
        tmp_path = f.name

    # Write selfie to temp file (optional)
    tmp_selfie = ""
    if selfie is not None:
        selfie_ct = selfie.content_type or ""
        if selfie_ct.startswith("image/"):
            selfie_bytes = await selfie.read()
            if len(selfie_bytes) <= 5 * 1024 * 1024:
                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as sf:
                    sf.write(selfie_bytes)
                    tmp_selfie = sf.name

    try:
        result = run_cross_verification(
            registered_name   = registered_name,
            id_type           = clean_id_type,
            id_number_entered = id_number,
            id_image_path     = tmp_path,
            payslip_data      = payslip_data or None,
            selfie_path       = tmp_selfie,
        )

        # Persist cross-verify result to DB (best-effort)
        try:
            from utils.db import get_db
            db = get_db()
            if db is not None:
                await db["kyc_records"].update_one(
                    {"user_id": user_id},
                    {"$set": {
                        "cross_verify_status":  result.overall_status,
                        "cross_verify_flags":   result.flags,
                        "cross_verify_mock":    result.mock_mode,
                        "cross_verify_checks":  result.checks,
                        "cross_verify_updated": datetime.utcnow().isoformat(),
                        "flag_for_review":      result.flag_for_review,
                    }},
                    upsert=True,
                )
        except Exception as db_err:
            logger.warning(f"CrossVerify DB persist skipped: {db_err}")

        masked_id = _mask_id(id_number.replace(" ", "").upper())
        logger.info(
            f"CrossVerify for user=*** id_type={clean_id_type} id={masked_id} "
            f"status={result.overall_status} flags={len(result.flags)}"
        )

        return {
            "success":         True,
            "overall_status":  result.overall_status,
            "overall_message": result.overall_message,
            "flag_for_review": result.flag_for_review,
            "flags":           result.flags,
            "mock_mode":       result.mock_mode,
            "checks":          result.checks,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cross-verify error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        for p in (tmp_path, tmp_selfie):
            if p:
                try:
                    os.unlink(p)
                except Exception:
                    pass


@router.post("/kyc/extract-fields")
async def extract_id_fields_from_image(
    id_type:     str        = Form(...),
    id_document: UploadFile = File(...),
):
    """
    Quick OCR scan of an uploaded ID card image.
    Returns extracted name and (masked) ID number immediately so the
    frontend can auto-fill the Name field.
    Only accepts JPG/PNG — no PDFs.
    """
    import tempfile, os
    from services.kyc_service import (
        extract_document_text, extract_id_fields as _extract_id_fields,
        _TESSERACT_AVAILABLE,
    )
    from agent.kyc_agent import _mask_id

    ct = id_document.content_type or ""
    if not ct.startswith("image/"):
        raise HTTPException(status_code=400, detail="ID card must be a JPG or PNG image.")

    id_bytes = await id_document.read()
    if len(id_bytes) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File exceeds 5 MB.")

    clean_id_type = id_type.lower().strip()
    if clean_id_type not in {"aadhaar", "pan", "dl", "college"}:
        raise HTTPException(status_code=400, detail=f"Invalid id_type '{id_type}'.")

    if not _TESSERACT_AVAILABLE:
        return {"success": False, "reason": "OCR not available", "name": "", "id_number_masked": ""}

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        f.write(id_bytes)
        tmp = f.name

    try:
        text, mode = extract_document_text(tmp)
        if not text.strip():
            return {"success": False, "reason": "Could not read text from image", "name": "", "id_number_masked": ""}

        fields = _extract_id_fields(text, clean_id_type)
        name      = fields.get("name", "").strip()
        id_number = fields.get("id_number", "").strip()
        masked    = _mask_id(id_number) if id_number else ""

        return {
            "success":          bool(name or id_number),
            "name":             name,
            "id_number_masked": masked,
            "id_number_found":  bool(id_number),
        }
    finally:
        try: os.unlink(tmp)
        except Exception: pass


@router.get("/kyc/status/{user_id}")
async def get_kyc_status(user_id: str):
    """
    Return the latest KYC verification status for a user,
    including cross-document verification results.
    Used by admin dashboard and applicant dashboard.
    """
    try:
        from utils.db import get_db
        db = get_db()
        if db is None:
            return {"kyc_status": "pending", "id_type": None, "confidence": 0.0}

        record = await db["kyc_records"].find_one({"user_id": user_id})
        if not record:
            return {"kyc_status": "pending", "id_type": None, "confidence": 0.0}

        return {
            "kyc_status":            record.get("kyc_status", "pending"),
            "id_type":               record.get("id_type"),
            "dl_state":              record.get("dl_state"),
            "confidence":            record.get("confidence", 0.0),
            "updated_at":            record.get("updated_at"),
            "cross_verify_status":   record.get("cross_verify_status"),
            "cross_verify_flags":    record.get("cross_verify_flags", []),
            "cross_verify_checks":   record.get("cross_verify_checks", {}),
            "cross_verify_mock":     record.get("cross_verify_mock", True),
            "flag_for_review":       record.get("flag_for_review", False),
        }
    except Exception as e:
        logger.error(f"KYC status fetch error: {e}")
        return {"kyc_status": "pending", "id_type": None, "confidence": 0.0}


@router.get("/my-applications")
async def my_applications(user_id: str):
    """
    Returns all past applications for a given user_id,
    including any admin override decisions.
    """
    try:
        from utils.db import get_db
        db = get_db()
        if db is None:
            raise HTTPException(status_code=503, detail="Database not connected.")

        cursor = db["decisions"].find({"user_id": user_id}).sort("timestamp", -1)
        docs = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            docs.append(doc)
        return docs

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"my-applications error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# COLLEGE KYC AI AGENT ENDPOINT
# ============================================

@router.post("/kyc/verify-college-id")
async def verify_college_id(
    user_id:      str        = Form(...),
    full_name:    str        = Form(...),
    dob:          str        = Form(...),
    college_id:   str        = Form(...),
    id_type:      str        = Form(default="college"),
    dl_state:     str        = Form(default=""),
    id_card:      UploadFile = File(...),
    selfie:       UploadFile = File(...),
):
    """
    KYC AI Agent endpoint.
    Accepts Aadhaar, PAN, Driving Licence, or college IDs.
    Delegates all verification logic to agent/kyc_agent.py KYCAgent.

    Security:
    - ID numbers are never logged in full — only masked values appear in logs.
    - format_valid status is distinct from verified; format checks alone are
      not sufficient for official identity verification.
    """
    import tempfile, os
    from agent.kyc_agent import KYCAgent
    from datetime import datetime
    from pathlib import Path
    from config import settings as _settings

    # Validate id_type
    allowed_id_types = {"aadhaar", "pan", "dl", "college"}
    clean_id_type = id_type.lower().strip()
    if clean_id_type not in allowed_id_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid id_type '{id_type}'. Must be one of: {sorted(allowed_id_types)}"
        )

    # Validate file types — ID card must be an IMAGE (JPG/PNG) for OCR to work.
    # PDFs cannot be reliably scanned for ID numbers (no embedded text in most PAN/Aadhaar PDFs).
    # Selfie must always be an image.
    id_ct = id_card.content_type or ""
    id_fn = (id_card.filename or "").lower()
    if not id_ct.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail=(
                "ID card must be uploaded as a JPG or PNG image, not a PDF. "
                "PDFs cannot be scanned for ID number verification. "
                "Please take a clear photo of your ID card and upload that instead."
            )
        )

    selfie_ct = selfie.content_type or ""
    if not selfie_ct.startswith("image/"):
        raise HTTPException(status_code=400, detail="Selfie must be a JPG or PNG image.")

    id_bytes     = await id_card.read()
    selfie_bytes = await selfie.read()

    # Enforce size limits (5 MB)
    for label, data in [("ID card", id_bytes), ("Selfie", selfie_bytes)]:
        if len(data) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail=f"{label} exceeds 5 MB size limit.")

    # Write to temp files — use .pdf extension when needed so PIL/OCR handle it
    id_suffix     = ".pdf" if (id_card.content_type == "application/pdf") else ".jpg"
    self_suffix   = ".jpg"

    with tempfile.NamedTemporaryFile(suffix=id_suffix,   delete=False) as f:
        f.write(id_bytes);     id_path = f.name
    with tempfile.NamedTemporaryFile(suffix=self_suffix, delete=False) as f:
        f.write(selfie_bytes); selfie_path = f.name

    try:
        result = KYCAgent.verify(
            user_id       = user_id,
            full_name     = full_name,
            dob           = dob,
            id_number     = college_id,   # college_id param is the raw ID number
            id_type       = clean_id_type,
            id_image_path = id_path,
            selfie_path   = selfie_path,
        )

        # Persist uploaded files under a per-user directory
        safe_uid = user_id.replace('@', '_at_').replace('.', '_')
        save_dir = Path(_settings.UPLOAD_DIR) / safe_uid
        save_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        id_ext   = ".pdf" if id_suffix == ".pdf" else ".jpg"
        with open(save_dir / f"{clean_id_type}_id_{ts}{id_ext}", "wb") as f:
            f.write(id_bytes)
        with open(save_dir / f"selfie_{ts}.jpg", "wb") as f:
            f.write(selfie_bytes)

        # Persist KYC status to DB (non-blocking best-effort)
        try:
            from utils.db import get_db
            db = get_db()
            if db is not None:
                await db["kyc_records"].update_one(
                    {"user_id": user_id},
                    {"$set": {
                        "user_id":      user_id,
                        "id_type":      clean_id_type,
                        "dl_state":     dl_state or None,
                        "kyc_status":   result.status,
                        "confidence":   result.confidence,
                        "updated_at":   datetime.utcnow().isoformat(),
                    }},
                    upsert=True,
                )
        except Exception as db_err:
            logger.warning(f"KYC DB persist skipped: {db_err}")

        # Never expose full id number in response — only masked summary
        from agent.kyc_agent import _mask_id
        masked_id = _mask_id(college_id.replace(" ", "").upper())

        logger.info(
            f"KYC result for user_id=*** id_type={clean_id_type} "
            f"id={masked_id} status={result.status} conf={result.confidence:.0%}"
        )

        return {
            "success":         True,
            "status":          result.status,
            "id_type":         clean_id_type,
            "confidence":      result.confidence,
            "verdict":         result.verdict,
            "reasoning_steps": result.reasoning_steps,
            "checks":          result.checks,
            "summary":         {k: v.get("passed", False) for k, v in result.checks.items()},
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"KYC endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        for p in [id_path, selfie_path]:
            try:
                os.unlink(p)
            except Exception:
                pass
