"""
API Schemas — Pydantic models for request/response validation.
Updated to support user-friendly applicant form fields.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Any
from datetime import datetime


# ─────────────────────────────────────────────────────────
#  NEW: User-Friendly Loan Application
#  Applicants fill in plain fields; credit bureau data is
#  fetched automatically by the backend.
# ─────────────────────────────────────────────────────────
class LoanApplicationRequest(BaseModel):
    # Identity / contact
    user_id:        str   = Field(..., description="Applicant user ID / email")
    full_name:      Optional[str] = Field(default=None, description="Applicant full name")
    age:            Optional[int] = Field(default=None, ge=18, le=80, description="Applicant age")
    contact:        Optional[str] = Field(default=None, description="Phone or email contact")

    # Income
    income:         float = Field(..., gt=0, description="Monthly income of the applicant")
    employment_type: Optional[str] = Field(
        default="salaried",
        description="Employment type: salaried, self-employed, business, student, unemployed"
    )

    # Loan details
    loan_amount:    Optional[float] = Field(default=None, gt=0, description="Requested loan amount")
    loan_tenure:    Optional[int]   = Field(default=None, ge=1, le=360, description="Loan tenure in months")
    loan_purpose:   Optional[str]   = Field(default=None, description="Purpose of the loan")

    # Existing obligations
    existing_emi:   Optional[float] = Field(default=0.0, ge=0, description="Existing monthly EMI obligations")

    # Deprecated / legacy fields kept for backward compat — backend fetches these via bureau
    credit_score:      Optional[int]   = Field(default=None, ge=300, le=900)
    dti:               Optional[float] = Field(default=None, ge=0, le=1)
    employment_length: Optional[int]   = Field(default=None, ge=0)
    currency:          Optional[str]   = Field(default="USD")

    # Payslip verification result (populated by /verify-income endpoint)
    payslip_verification: Optional[dict] = Field(default=None)


class UserProfile(BaseModel):
    user_id:             str
    name:                str
    email:               str
    phone:               Optional[str] = None
    created_at:          datetime = Field(default_factory=datetime.utcnow)
    total_applications:  int = 0
    approved_count:      int = 0
    rejected_count:      int = 0
    review_count:        int = 0


class FeatureImpact(BaseModel):
    feature: str
    impact:  str


class AgentDecisionResponse(BaseModel):
    risk_score:          float       = Field(..., description="Probability of default (0-1)")
    confidence:          float       = Field(..., description="Agent confidence score (0-1)")
    decision:            str         = Field(..., description="Approve, Reject, or Review")
    explanation:         str         = Field(..., description="Natural language reasoning")
    important_features:  List[FeatureImpact] = Field(..., description="Key SHAP features")
    # Extended fields returned to frontend
    credit_bureau_data:  Optional[dict] = Field(default=None)
    internal_score:      Optional[int]  = Field(default=None, description="Illustrative 300-900 score")
    fraud_flags:         Optional[List[str]] = Field(default=None)
    risk_category:       Optional[str]  = Field(default=None)
    payslip_data:        Optional[dict] = Field(default=None)


class DownloadReportRequest(BaseModel):
    user_id:             str
    income:              float
    credit_score:        Optional[int]   = None
    dti:                 Optional[float] = None
    employment_length:   Optional[int]   = None
    loan_amount:         Optional[float] = None
    loan_tenure:         Optional[int]   = None
    loan_purpose:        Optional[str]   = None
    full_name:           Optional[str]   = None
    age:                 Optional[int]   = None
    currency:            Optional[str]   = "USD"
    risk_score:          float
    confidence:          float
    decision:            str
    explanation:         str
    important_features:  List[FeatureImpact]
    internal_score:      Optional[int]   = None
    risk_category:       Optional[str]   = None
    credit_bureau_data:  Optional[dict]  = None


class LoggedDecision(AgentDecisionResponse):
    user_id:             str
    application_data:    dict
    timestamp:           datetime = Field(default_factory=datetime.utcnow)
    admin_override:      bool = False
    admin_note:          Optional[str] = None


# ─────────────────────────────────────────────────────────
#  Payslip upload response schema
# ─────────────────────────────────────────────────────────
class PayslipVerificationResponse(BaseModel):
    verified:            bool
    fraud_flag:          bool
    extraction_success:  bool
    claimed_income:      float
    extracted_income:    Optional[float] = None
    extracted_employer:  Optional[str]   = None
    salary_period:       Optional[str]   = None
    employee_name:       Optional[str]   = None
    income_match_pct:    Optional[float] = None
    message:             str
    notes:               List[str]       = []
    filename:            str
