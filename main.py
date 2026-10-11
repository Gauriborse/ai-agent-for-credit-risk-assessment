"""
FastAPI Application Entry Point
================================
AI-Powered Loan Underwriting & Credit Risk Assessment Engine.
"""

import os
from fastapi import FastAPI, BackgroundTasks, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, Any

from api.routes import router
from api.schemas import LoanApplicationRequest, AgentDecisionResponse, FeatureImpact
from services.credit_bureau_service import credit_bureau_service
from services.payslip_service import verify_income_against_document
from agent.underwriting_agents import UnderwritingPipeline, UnderwritingContext
from database import insert_loan_application
from utils.db import connect_to_db, close_db_connection
from utils.logger import get_logger
from config import settings
import uvicorn

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up AI Loan Underwriting Engine…")
    await connect_to_db()
    yield
    logger.info("Shutting down…")
    await close_db_connection()


app = FastAPI(
    title="AI Loan Underwriting & Credit Risk API",
    description=(
        "Multi-agent AI system for loan underwriting. "
        "All credit bureau data is SIMULATED for demonstration purposes."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


# ═══════════════════════════════════════════════════════════
#  PAYSLIP / INCOME VERIFICATION ENDPOINT
#  Accepts PDF, JPG, PNG
# ═══════════════════════════════════════════════════════════
@app.post("/verify-income")
async def verify_income(
    claimed_income:  str  = Form(...),
    document:        UploadFile = File(...),
    registered_name: str  = Form(default=""),   # optional — for payslip name cross-check
):
    """
    Verify income from uploaded payslip document.
    Accepts: PDF, JPG, JPEG, PNG.
    Extracts income, employer, salary period, and employee name via OCR/PDF parsing.
    Optionally compares employee name against registered_name for cross-document verification.
    Returns structured verification result with fraud flag and name_check result.
    """
    try:
        logger.info(f"Income verification request — claimed: {claimed_income}")

        # Validate claimed income
        try:
            income_val = float(claimed_income.replace(",", "").replace("$", "").replace("₹", "").strip())
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid income value provided.")

        # Validate file type
        ct  = (document.content_type or "").lower()
        fn  = (document.filename or "").lower()
        allowed_types = ["pdf", "jpg", "jpeg", "png", "image/jpeg", "image/png", "application/pdf"]
        if not any(a in ct or fn.endswith(a.replace("image/", ".").replace("application/", "."))
                   for a in allowed_types):
            raise HTTPException(
                status_code=400,
                detail="Only PDF, JPG, and PNG files are supported for payslip verification."
            )

        file_bytes = await document.read()

        # Size check (10 MB)
        if len(file_bytes) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File size exceeds 10 MB limit.")

        # Run verification
        result = verify_income_against_document(
            claimed_income = income_val,
            file_bytes     = file_bytes,
            content_type   = document.content_type,
            filename       = document.filename,
        )

        logger.info(
            f"Income verification result: verified={result['verified']}, "
            f"fraud_flag={result['fraud_flag']}, "
            f"extracted={result.get('extracted_income')}"
        )

        # ── Payslip name cross-check (optional) ────────────────────────────
        name_check = None
        if registered_name.strip():
            from services.payslip_service import check_payslip_name
            employee_name = result.get("employee_name") or ""
            nc = check_payslip_name(
                registered_name=registered_name.strip(),
                payslip_employee_name=employee_name or None,
            )
            name_check = {
                "status":     nc["status"],
                "message":    nc["message"],
                "confidence": round(nc["confidence"], 3),
            }
            if nc["status"] == "mismatch":
                logger.warning(
                    f"Payslip name mismatch for registered_name=*** — "
                    f"employee_name extracted=*** status=mismatch"
                )

        return {
            "status":            "success",
            "fraud_flag":        result["fraud_flag"],
            "verified":          result["verified"],
            "message":           result["message"],
            "name_check":        name_check,          # None if no registered_name given
            "verification_data": {
                "verified":           result["verified"],
                "claimed_income":     income_val,
                "extracted_income":   result.get("extracted_income"),
                "extracted_employer": result.get("extracted_employer"),
                "salary_period":      result.get("salary_period"),
                "employee_name":      result.get("employee_name"),
                "income_match_pct":   result.get("income_match_pct"),
                "payslip_filename":   document.filename,
                "notes":              result.get("notes", []),
                "name_check":         name_check,
                "verification_timestamp": datetime.utcnow().isoformat(),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unhandled error in income verification: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal error during income verification: {str(e)}"
        )


# ═══════════════════════════════════════════════════════════
#  COMPLETE LOAN ANALYSIS ENDPOINT
#  Runs full 7-agent pipeline
# ═══════════════════════════════════════════════════════════
@app.post("/analyze-loan-complete", response_model=AgentDecisionResponse)
async def analyze_loan_complete(
    application: LoanApplicationRequest,
    background_tasks: BackgroundTasks,
):
    """
    Full 7-agent underwriting pipeline:
    1. Document Agent       — validates payslip data
    2. Credit Bureau Agent  — fetches SIMULATED credit bureau data
    3. Credit Scoring Agent — XGBoost default probability + SHAP
    4. Risk Assessment Agent — Low/Medium/High classification
    5. Fraud Investigation Agent — anomaly detection
    6. Loan Decision Agent  — Approve / Review / Reject
    7. Explanation Agent    — generates human-readable reasoning
    """
    try:
        logger.info(f"Full pipeline analysis for: {application.user_id}")

        from utils.db import create_or_update_user
        await create_or_update_user(application.user_id)

        ctx = UnderwritingContext(
            user_id          = application.user_id,
            full_name        = getattr(application, "full_name", None) or application.user_id,
            age              = getattr(application, "age", None) or 35,
            income           = application.income,
            employment_type  = getattr(application, "employment_type", None) or "salaried",
            employment_length= float(getattr(application, "employment_length", None) or 5),
            loan_amount      = float(getattr(application, "loan_amount", None) or 300_000),
            loan_tenure      = int(getattr(application, "loan_tenure", None) or 36),
            loan_purpose     = getattr(application, "loan_purpose", None) or "personal",
            existing_emi     = float(getattr(application, "existing_emi", None) or 0.0),
            currency         = getattr(application, "currency", None) or "USD",
            payslip_data     = getattr(application, "payslip_verification", None),
        )

        # Attach cross-verify data from DB if available (best-effort)
        try:
            from utils.db import get_db
            _db = get_db()
            if _db is not None:
                kyc_rec = await _db["kyc_records"].find_one({"user_id": application.user_id})
                if kyc_rec and kyc_rec.get("cross_verify_status"):
                    ctx.cross_verify_data = {
                        "overall_status": kyc_rec.get("cross_verify_status"),
                        "flags":          kyc_rec.get("cross_verify_flags", []),
                        "flag_for_review": kyc_rec.get("flag_for_review", False),
                    }
        except Exception:
            pass

        ctx = UnderwritingPipeline.run(ctx)

        features = [
            FeatureImpact(feature=f["feature"], impact=f["impact"])
            for f in (ctx.shap_features or [])
        ]

        response = AgentDecisionResponse(
            risk_score         = ctx.risk_probability,
            confidence         = ctx.confidence,
            decision           = ctx.decision,
            explanation        = ctx.explanation,
            important_features = features,
            credit_bureau_data = ctx.bureau_data,
            internal_score     = ctx.internal_score,
            fraud_flags        = ctx.fraud_flags or [],
            risk_category      = ctx.risk_category,
            payslip_data       = ctx.payslip_data,
        )

        # Persist in background
        from agent.memory import save_decision
        from api.schemas import LoggedDecision
        from utils.db import update_user_stats

        # Attach KYC status from DB (best-effort)
        kyc_status_for_log  = "pending"
        kyc_id_type_for_log = None
        try:
            from utils.db import get_db
            _db = get_db()
            if _db is not None:
                kyc_rec = await _db["kyc_records"].find_one({"user_id": application.user_id})
                if kyc_rec:
                    kyc_status_for_log  = kyc_rec.get("kyc_status", "pending")
                    kyc_id_type_for_log = kyc_rec.get("id_type")
        except Exception:
            pass

        logged = LoggedDecision(
            user_id            = application.user_id,
            application_data   = {
                **application.model_dump(),
                "full_name":     ctx.full_name,
                "age":           ctx.age,
                "loan_amount":   ctx.loan_amount,
                "loan_tenure":   ctx.loan_tenure,
                "loan_purpose":  ctx.loan_purpose,
                "existing_emi":  ctx.existing_emi,
                "dti":           ctx.dti,
                "risk_category": ctx.risk_category,
                "kyc_status":    kyc_status_for_log,
                "kyc_id_type":   kyc_id_type_for_log,
                "cross_verify_status": kyc_rec.get("cross_verify_status") if kyc_rec else None,
                "cross_verify_flags":  kyc_rec.get("cross_verify_flags", []) if kyc_rec else [],
            },
            risk_score         = ctx.risk_probability,
            confidence         = ctx.confidence,
            decision           = ctx.decision,
            explanation        = ctx.explanation,
            important_features = features,
            credit_bureau_data = ctx.bureau_data,
            internal_score     = ctx.internal_score,
            fraud_flags        = ctx.fraud_flags or [],
            risk_category      = ctx.risk_category,
        )
        # Save synchronously so admin dashboard sees it immediately
        await save_decision(logged)
        background_tasks.add_task(update_user_stats, application.user_id, ctx.decision)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"analyze_loan_complete failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)}")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
