"""
Credit Risk AI Agent
=====================
Think → Act → Observe → Decide loop.

Tools:
  1. tool_validate_inputs        — sanity-check all 13 input fields
  2. tool_predict_default_risk   — XGBoost risk probability
  3. tool_explain_features       — SHAP feature attribution
  4. tool_assess_fraud_signals   — flag suspicious input combinations
  5. tool_make_decision          — final Approve / Review / Reject

Mock mode  (USE_LOCAL_LLM=True)  — deterministic Python reasoning.
OpenAI mode (USE_LOCAL_LLM=False) — LangChain + GPT-3.5.
"""

import json
from dataclasses import dataclass, field
from typing import List, Optional

from config import settings
from tools.risk_model import predict_risk
from tools.explainability import explain_prediction
from tools.decision import decision_engine
from utils.logger import get_logger

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────
#  Input / Output dataclasses
# ─────────────────────────────────────────────────────────
@dataclass
class CreditRiskInput:
    user_id:               str
    # Core (always present)
    income:                float          # monthly income
    credit_score:          int            # 300-900 (used for validation display only)
    dti:                   float          # 0-1
    employment_length:     int            # years
    # Extended
    age:                   int   = 35
    loan_amount:           float = 300000
    loan_term:             int   = 36
    existing_loan_amount:  float = 0
    credit_history_length: float = 10.0
    credit_utilization:    float = 40.0
    num_previous_loans:    int   = 1
    num_late_payments:     int   = 1
    num_90days_late:       int   = 0
    num_dependents:        int   = 1


@dataclass
class CreditRiskResult:
    status:           str            # "completed" | "error"
    risk_score:       float
    confidence:       float
    decision:         str            # Approve | Review | Reject
    explanation:      str
    important_features: List[dict]
    reasoning_steps:  List[str]      = field(default_factory=list)
    fraud_flags:      List[str]      = field(default_factory=list)
    validation_notes: List[str]      = field(default_factory=list)


# ─────────────────────────────────────────────────────────
#  TOOL 1 — Input Validation
# ─────────────────────────────────────────────────────────
def tool_validate_inputs(inp: CreditRiskInput) -> dict:
    """
    Validate and flag any suspicious or out-of-range input values.
    Returns: { valid: bool, issues: [str], warnings: [str] }
    """
    issues   = []
    warnings = []

    if inp.income < 5000:
        issues.append("Monthly income below minimum threshold ($5,000).")
    if inp.income > 1_000_000:
        warnings.append("Unusually high income — may need verification.")

    if not (18 <= inp.age <= 75):
        issues.append(f"Age {inp.age} is outside valid range (18-75).")

    if not (0 <= inp.dti <= 1):
        issues.append(f"DTI {inp.dti} must be between 0 and 1.")
    elif inp.dti > 0.65:
        warnings.append("DTI above 65% — very high debt burden.")

    if inp.employment_length < 0:
        issues.append("Employment length cannot be negative.")

    if inp.loan_amount <= 0:
        issues.append("Loan amount must be positive.")

    if inp.loan_term not in [12, 24, 36, 48, 60, 72, 84]:
        warnings.append(f"Unusual loan term: {inp.loan_term} months.")

    if inp.num_90days_late > 5:
        warnings.append("High number of 90-day late payments — severe credit risk signal.")

    if inp.credit_utilization > 90:
        warnings.append("Credit utilization above 90% — near credit limit.")

    return {
        "valid":    len(issues) == 0,
        "issues":   issues,
        "warnings": warnings,
    }


# ─────────────────────────────────────────────────────────
#  TOOL 2 — Predict Default Risk
# ─────────────────────────────────────────────────────────
def tool_predict_default_risk(inp: CreditRiskInput) -> dict:
    """Run XGBoost model — returns risk_probability and confidence."""
    try:
        prob, conf = predict_risk(
            income                = inp.income,
            credit_score          = inp.credit_score,
            dti                   = inp.dti,
            employment_length     = inp.employment_length,
            age                   = inp.age,
            loan_amount           = inp.loan_amount,
            loan_term             = inp.loan_term,
            existing_loan_amount  = inp.existing_loan_amount,
            credit_history_length = inp.credit_history_length,
            credit_utilization    = inp.credit_utilization,
            num_previous_loans    = inp.num_previous_loans,
            num_late_payments     = inp.num_late_payments,
            num_90days_late       = inp.num_90days_late,
            num_dependents        = inp.num_dependents,
        )
        return {"risk_probability": prob, "confidence": conf}
    except Exception as e:
        logger.error(f"tool_predict_default_risk error: {e}")
        return {"risk_probability": 0.5, "confidence": 0.65, "error": str(e)}


# ─────────────────────────────────────────────────────────
#  TOOL 3 — SHAP Feature Explanation
# ─────────────────────────────────────────────────────────
def tool_explain_features(inp: CreditRiskInput) -> dict:
    """Run SHAP — returns ranked feature attributions."""
    try:
        features = explain_prediction(
            income                = inp.income,
            credit_score          = inp.credit_score,
            dti                   = inp.dti,
            employment_length     = inp.employment_length,
            age                   = inp.age,
            loan_amount           = inp.loan_amount,
            loan_term             = inp.loan_term,
            existing_loan_amount  = inp.existing_loan_amount,
            credit_history_length = inp.credit_history_length,
            credit_utilization    = inp.credit_utilization,
            num_previous_loans    = inp.num_previous_loans,
            num_late_payments     = inp.num_late_payments,
            num_90days_late       = inp.num_90days_late,
            num_dependents        = inp.num_dependents,
        )
        return {"features": features, "top_driver": features[0]['feature'] if features else "unknown"}
    except Exception as e:
        logger.error(f"tool_explain_features error: {e}")
        return {"features": [], "top_driver": "unknown", "error": str(e)}


# ─────────────────────────────────────────────────────────
#  TOOL 4 — Fraud Signal Assessment
# ─────────────────────────────────────────────────────────
def tool_assess_fraud_signals(inp: CreditRiskInput) -> dict:
    """
    Rule-based fraud detection on the financial profile.
    Flags suspicious combinations that warrant manual review.
    """
    flags = []

    # Income vs loan amount ratio
    annual_income = inp.income * 12
    loan_to_income = inp.loan_amount / annual_income if annual_income > 0 else 99
    if loan_to_income > 10:
        flags.append(f"Loan-to-income ratio is {loan_to_income:.1f}x — excessively high.")

    # New employee requesting huge loan
    if inp.employment_length < 1 and inp.loan_amount > 500000:
        flags.append("New employee (<1 yr) requesting large loan (>500k) — suspicious.")

    # High DTI + high credit utilization
    if inp.dti > 0.6 and inp.credit_utilization > 80:
        flags.append("Both DTI >60% and credit utilization >80% — severe over-leverage.")

    # Many late payments with short credit history
    if inp.num_late_payments > 5 and inp.credit_history_length < 3:
        flags.append("5+ late payments in <3 years credit history — pattern mismatch.")

    # 90-day lates alongside claimed stable income
    if inp.num_90days_late >= 3 and inp.income > 100000:
        flags.append("3+ 90-day lates despite high income — inconsistency flagged.")

    return {
        "fraud_flag_count": len(flags),
        "flags":            flags,
        "risk_elevated":    len(flags) > 0,
    }


# ─────────────────────────────────────────────────────────
#  TOOL 5 — Make Decision
# ─────────────────────────────────────────────────────────
def tool_make_decision(
    risk_probability: float,
    credit_score:     int,
    dti:              float,
    employment_length: int,
    fraud_flags:      int = 0,
) -> dict:
    """
    Combine model output + fraud signals → final Approve / Review / Reject.
    If fraud flags present, force Review regardless of model score.
    """
    # Force Review if fraud flags found
    if fraud_flags > 0:
        return {
            "decision": "Review",
            "reasoning": (
                f"Fraud signals detected ({fraud_flags} flag(s)). "
                "Manual verification required before final decision."
            )
        }

    decision, reasoning = decision_engine(
        risk_probability, credit_score, dti, employment_length
    )
    return {"decision": decision, "reasoning": reasoning}


# ─────────────────────────────────────────────────────────
#  MOCK AGENT  (Think → Act → Observe → Decide)
# ─────────────────────────────────────────────────────────
def mock_credit_risk_agent(inp: CreditRiskInput) -> CreditRiskResult:
    steps       = []
    fraud_flags = []
    val_notes   = []

    # ── STEP 1: Validate inputs ──────────────────────────
    steps.append("THINK: Validate all 13 input fields before running the model.")
    steps.append("ACT  : Running tool_validate_inputs.")
    val = tool_validate_inputs(inp)

    if not val['valid']:
        for iss in val['issues']:
            steps.append(f"OBSERVE: Validation error — {iss}")
            val_notes.append(iss)
        steps.append("DECIDE: Hard validation failed. Cannot process application.")
        return CreditRiskResult(
            status="error",
            risk_score=0, confidence=0,
            decision="Reject",
            explanation="Application rejected: " + "; ".join(val['issues']),
            important_features=[],
            reasoning_steps=steps,
            validation_notes=val_notes,
        )

    for w in val['warnings']:
        steps.append(f"OBSERVE: Warning — {w}")
        val_notes.append(w)

    steps.append("OBSERVE: Input validation passed.")

    # ── STEP 2: Predict risk ─────────────────────────────
    steps.append("THINK: Run XGBoost model to get default probability.")
    steps.append("ACT  : Running tool_predict_default_risk.")
    pred = tool_predict_default_risk(inp)
    risk_prob  = pred['risk_probability']
    confidence = pred['confidence']
    steps.append(
        f"OBSERVE: Risk probability = {risk_prob:.1%}, Confidence = {confidence:.1%}"
    )

    # ── STEP 3: SHAP explanation ─────────────────────────
    steps.append("THINK: Use SHAP to find which features drove this score.")
    steps.append("ACT  : Running tool_explain_features.")
    exp        = tool_explain_features(inp)
    features   = exp['features']
    top_driver = exp['top_driver']
    steps.append(f"OBSERVE: Top risk driver = {top_driver}")

    # ── STEP 4: Fraud detection ──────────────────────────
    steps.append("THINK: Check for suspicious input combinations.")
    steps.append("ACT  : Running tool_assess_fraud_signals.")
    fraud = tool_assess_fraud_signals(inp)
    for f in fraud['flags']:
        steps.append(f"OBSERVE: Fraud signal — {f}")
        fraud_flags.append(f)

    if fraud['risk_elevated']:
        steps.append("THINK: Fraud signals found. Will force Review regardless of model score.")

    # ── STEP 5: Final decision ───────────────────────────
    steps.append("THINK: Combine model score, fraud signals → final decision.")
    steps.append("ACT  : Running tool_make_decision.")
    dec = tool_make_decision(
        risk_probability  = risk_prob,
        credit_score      = inp.credit_score,
        dti               = inp.dti,
        employment_length = inp.employment_length,
        fraud_flags       = len(fraud['flags']),
    )
    decision  = dec['decision']
    reasoning = dec['reasoning']

    # Enrich reasoning with top SHAP driver
    full_explanation = (
        f"{reasoning} "
        f"Primary risk driver: {top_driver.replace('_', ' ')}. "
        f"Agent confidence: {confidence:.0%}."
    )
    if fraud_flags:
        full_explanation += f" Fraud signals detected: {'; '.join(fraud_flags)}"

    steps.append(
        f"DECIDE: {decision} (risk={risk_prob:.1%}, "
        f"fraud_flags={len(fraud_flags)}, top_driver={top_driver})"
    )

    return CreditRiskResult(
        status           = "completed",
        risk_score       = risk_prob,
        confidence       = confidence,
        decision         = decision,
        explanation      = full_explanation,
        important_features = features,
        reasoning_steps  = steps,
        fraud_flags      = fraud_flags,
        validation_notes = val_notes,
    )


# ─────────────────────────────────────────────────────────
#  OPENAI AGENT  (LangChain)
# ─────────────────────────────────────────────────────────
def openai_credit_risk_agent(inp: CreditRiskInput) -> CreditRiskResult:
    from langchain_openai import ChatOpenAI
    from langchain.agents import initialize_agent, AgentType
    from langchain.tools import tool as lc_tool

    @lc_tool
    def lc_validate_inputs(dummy: str = "") -> str:
        """Validate all 13 input fields for range and consistency."""
        return json.dumps(tool_validate_inputs(inp))

    @lc_tool
    def lc_predict_risk(dummy: str = "") -> str:
        """Run XGBoost model to predict default probability."""
        return json.dumps(tool_predict_default_risk(inp))

    @lc_tool
    def lc_explain_features(dummy: str = "") -> str:
        """Run SHAP to get feature attribution for the prediction."""
        return json.dumps(tool_explain_features(inp))

    @lc_tool
    def lc_fraud_signals(dummy: str = "") -> str:
        """Check for fraud signals in the applicant's financial profile."""
        return json.dumps(tool_assess_fraud_signals(inp))

    @lc_tool
    def lc_make_decision(risk_prob: float, fraud_flags: int) -> str:
        """Make the final Approve/Review/Reject decision."""
        return json.dumps(tool_make_decision(
            risk_probability=risk_prob,
            credit_score=inp.credit_score,
            dti=inp.dti,
            employment_length=inp.employment_length,
            fraud_flags=fraud_flags,
        ))

    tools = [lc_validate_inputs, lc_predict_risk, lc_explain_features,
             lc_fraud_signals, lc_make_decision]
    llm   = ChatOpenAI(model="gpt-3.5-turbo", temperature=0,
                       openai_api_key=settings.OPENAI_API_KEY)
    agent = initialize_agent(
        tools, llm,
        agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
        verbose=True
    )

    prompt = f"""
You are a Credit Risk AI Agent evaluating a loan application.
Applicant profile: income={inp.income}, dti={inp.dti}, employment={inp.employment_length}yrs,
age={inp.age}, loan={inp.loan_amount}, late_payments={inp.num_late_payments},
90days_late={inp.num_90days_late}, credit_util={inp.credit_utilization}%.

Run tools in order:
1. lc_validate_inputs  — check all fields
2. lc_predict_risk     — get XGBoost probability
3. lc_explain_features — get SHAP attribution
4. lc_fraud_signals    — check for red flags
5. lc_make_decision    — final verdict

Final answer MUST be valid JSON only:
{{
  "risk_score": 0.00, "confidence": 0.00,
  "decision": "Approve|Review|Reject",
  "explanation": "...", "reasoning_steps": ["..."],
  "important_features": [{{"feature":"...", "impact":"..."}}],
  "fraud_flags": []
}}
"""
    try:
        res   = agent.run(prompt)
        clean = res.strip().removeprefix("```json").removesuffix("```").strip()
        data  = json.loads(clean)
        return CreditRiskResult(
            status             = "completed",
            risk_score         = data.get("risk_score", 0.5),
            confidence         = data.get("confidence", 0.7),
            decision           = data.get("decision", "Review"),
            explanation        = data.get("explanation", ""),
            important_features = data.get("important_features", []),
            reasoning_steps    = data.get("reasoning_steps", []),
            fraud_flags        = data.get("fraud_flags", []),
        )
    except Exception as e:
        logger.error(f"OpenAI credit risk agent failed: {e}")
        return mock_credit_risk_agent(inp)   # graceful fallback


# ─────────────────────────────────────────────────────────
#  PUBLIC ENTRY POINT
# ─────────────────────────────────────────────────────────
class CreditRiskAgent:
    @staticmethod
    def evaluate(inp: CreditRiskInput) -> CreditRiskResult:
        if settings.USE_LOCAL_LLM:
            return mock_credit_risk_agent(inp)
        else:
            return openai_credit_risk_agent(inp)
