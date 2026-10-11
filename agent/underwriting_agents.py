"""
Modular AI Agent Workflow — Loan Underwriting
=============================================
Seven modular agents in a pipeline:

  1. DocumentAgent        — validate & parse payslip data
  2. CreditBureauAgent    — fetch mock credit bureau data
  3. CreditScoringAgent   — run XGBoost, compute internal score
  4. RiskAssessmentAgent  — classify risk, compute DTI
  5. FraudInvestigationAgent — anomaly detection + heuristic flags
  6. LoanDecisionAgent    — combine all signals → Approve/Review/Reject
  7. ExplanationAgent     — generate human-readable explanation + report

Each agent has a Think → Act → Observe → Decide loop.
All agents are deterministic Python (mock mode).
LLM explanations use OpenAI if USE_LOCAL_LLM=False.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from config import settings
from tools.risk_model import predict_risk, compute_score, detect_anomaly
from tools.explainability import explain_prediction
from tools.decision import decision_engine
from services.credit_bureau_service import credit_bureau_service
from utils.logger import get_logger

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────
#  Shared pipeline context
# ─────────────────────────────────────────────────────────
@dataclass
class UnderwritingContext:
    # ── Applicant inputs ──────────────────────────────────
    user_id:          str
    full_name:        str         = ""
    age:              int         = 35
    income:           float       = 0.0      # monthly
    employment_type:  str         = "salaried"
    employment_length: float      = 5.0      # years
    loan_amount:      float       = 300_000.0
    loan_tenure:      int         = 36        # months
    loan_purpose:     str         = "personal"
    existing_emi:     float       = 0.0
    currency:         str         = "USD"

    # ── Payslip / document ────────────────────────────────
    payslip_data:     Optional[dict] = None

    # ── Cross-document verification ───────────────────────
    cross_verify_data: Optional[dict] = None

    # ── Credit bureau ─────────────────────────────────────
    bureau_data:      Optional[dict] = None

    # ── Model outputs ─────────────────────────────────────
    risk_probability: float       = 0.0
    confidence:       float       = 0.0
    internal_score:   int         = 650
    dti:              float       = 0.0
    features_used:    Optional[dict] = None

    # ── Agent outputs ─────────────────────────────────────
    shap_features:    List[dict]  = field(default_factory=list)
    fraud_result:     Optional[dict] = None
    risk_category:    str         = "Unknown"
    decision:         str         = "Review"
    explanation:      str         = ""
    reasoning_steps:  List[str]   = field(default_factory=list)
    fraud_flags:      List[str]   = field(default_factory=list)
    validation_notes: List[str]   = field(default_factory=list)


# ─────────────────────────────────────────────────────────
#  Agent 1 — Document Agent
# ─────────────────────────────────────────────────────────
class DocumentAgent:
    """
    Validates and processes payslip / income document data.
    Also integrates cross-document verification flags if available.
    """

    @staticmethod
    def run(ctx: UnderwritingContext) -> UnderwritingContext:
        steps = ctx.reasoning_steps
        steps.append("AGENT 1 (Document): THINK — Checking payslip/document and cross-verification data.")

        # ── Cross-verify flags (from KYC + payslip cross-check) ──
        cross_verify = getattr(ctx, 'cross_verify_data', None)
        if cross_verify:
            cv_status = cross_verify.get("overall_status", "pending")
            cv_flags  = cross_verify.get("flags", [])
            steps.append(
                f"AGENT 1 (Document): OBSERVE — Cross-verify status: {cv_status}. "
                f"Flags: {cv_flags or 'none'}."
            )
            if cv_status == "mismatch":
                ctx.fraud_flags.extend(cv_flags)
                ctx.validation_notes.append(
                    f"Cross-document verification: {cross_verify.get('overall_message', '')}"
                )
                steps.append("AGENT 1 (Document): OBSERVE — Cross-verify mismatch flagged.")
            elif cv_status == "manual_review":
                ctx.validation_notes.append(
                    "Cross-document verification inconclusive — manual review recommended."
                )
            elif cv_status in ("unable_to_verify",):
                ctx.validation_notes.append(
                    "Cross-document OCR unavailable — identity consistency not confirmed."
                )

        if not ctx.payslip_data:
            steps.append("AGENT 1 (Document): OBSERVE — No payslip data provided. Proceeding with self-reported income.")
            ctx.validation_notes.append("No payslip document was processed before this analysis.")
            return ctx

        ps = ctx.payslip_data
        steps.append(f"AGENT 1 (Document): ACT — Reviewing payslip extraction result: {json.dumps({k:v for k,v in ps.items() if k not in ('raw_text',)}, default=str)[:300]}")

        if ps.get("fraud_flag"):
            ctx.fraud_flags.append(
                f"Payslip income mismatch: claimed {ctx.income:,.0f} vs "
                f"extracted {ps.get('extracted_income','unknown')}."
            )
            steps.append("AGENT 1 (Document): OBSERVE — Fraud flag: income mismatch in payslip.")
        elif ps.get("verified"):
            steps.append(f"AGENT 1 (Document): OBSERVE — Payslip verified. "
                         f"Extracted income: {ps.get('extracted_income','?')}, "
                         f"Employer: {ps.get('extracted_employer','unknown')}.")
        elif ps.get("extraction_success"):
            steps.append("AGENT 1 (Document): OBSERVE — Document parsed but income unconfirmed.")
            ctx.validation_notes.append("Payslip text extracted but income amount not confirmed — manual review advised.")
        else:
            steps.append("AGENT 1 (Document): OBSERVE — Document processing failed. Flagging for manual review.")
            ctx.validation_notes.append("Payslip document could not be processed — manual verification required.")

        return ctx


# ─────────────────────────────────────────────────────────
#  Agent 2 — Credit Bureau Agent
# ─────────────────────────────────────────────────────────
class CreditBureauAgent:
    """
    Calls mock credit bureau and populates bureau data.
    Always labels data as SIMULATED.
    """

    @staticmethod
    def run(ctx: UnderwritingContext) -> UnderwritingContext:
        steps = ctx.reasoning_steps
        steps.append("AGENT 2 (CreditBureau): THINK — Fetching simulated credit bureau data.")

        bureau = credit_bureau_service.get_credit_data_sync(ctx.user_id)
        ctx.bureau_data = bureau

        score  = bureau.get("credit_score", 650)
        hist   = bureau.get("credit_history_months", 60)
        util   = bureau.get("credit_utilization", 0.4)
        late   = bureau.get("late_payments", 1)
        late90 = bureau.get("late_90_days", 0)
        debt   = bureau.get("outstanding_debt", 0)

        steps.append(
            f"AGENT 2 (CreditBureau): ACT — [SIMULATED] Score={score}, "
            f"History={hist}mo, Utilization={util:.0%}, LatePayments={late}, "
            f"90DaysLate={late90}, OutstandingDebt={debt:,.0f}."
        )
        steps.append(
            "AGENT 2 (CreditBureau): OBSERVE — Bureau data loaded (labelled SIMULATED). "
            "Proceeding to scoring."
        )
        return ctx


# ─────────────────────────────────────────────────────────
#  Agent 3 — Credit Scoring Agent
# ─────────────────────────────────────────────────────────
class CreditScoringAgent:
    """
    Runs XGBoost model with all 13 features.
    Derives illustrative internal score (300-900).
    """

    @staticmethod
    def run(ctx: UnderwritingContext) -> UnderwritingContext:
        steps = ctx.reasoning_steps
        steps.append("AGENT 3 (CreditScoring): THINK — Preparing all 13 features for XGBoost inference.")

        # Pull bureau values
        bureau = ctx.bureau_data or {}
        credit_history = bureau.get("credit_history_months", 60) / 12  # months → years
        credit_util    = bureau.get("credit_utilization", 0.4) * 100    # 0-1 → 0-100
        late_payments  = bureau.get("late_payments", 1)
        late_90        = bureau.get("late_90_days", 0)
        prev_loans     = bureau.get("previous_loans", 1)

        # Compute DTI = (existing_emi + estimated_new_emi) / income
        estimated_new_emi = (ctx.loan_amount / max(ctx.loan_tenure, 1)) * 1.05  # rough EMI
        total_emi = ctx.existing_emi + estimated_new_emi
        dti = min(total_emi / max(ctx.income, 1), 1.0)
        ctx.dti = dti

        # Store feature dict for reference
        ctx.features_used = {
            "Age":                    ctx.age,
            "MonthlyIncome":          ctx.income,
            "EmploymentLength":       ctx.employment_length,
            "LoanAmount":             ctx.loan_amount,
            "LoanTerm":               ctx.loan_tenure,
            "ExistingLoanAmount":     ctx.existing_emi * 12,
            "DebtToIncomeRatio":      dti,
            "CreditHistoryLength":    credit_history,
            "CreditUtilizationRatio": credit_util,
            "NumberOfPreviousLoans":  prev_loans,
            "NumberOfLatePayments":   late_payments,
            "NumberOf90DaysLate":     late_90,
            "NumberOfDependents":     1,
        }

        steps.append(f"AGENT 3 (CreditScoring): ACT — Running XGBoost with features: DTI={dti:.2f}, "
                     f"Income={ctx.income:,.0f}, Utilization={credit_util:.1f}%, LatePayments={late_payments}.")

        prob, conf = predict_risk(
            income              = ctx.income,
            dti                 = dti,
            employment_length   = ctx.employment_length,
            age                 = ctx.age,
            loan_amount         = ctx.loan_amount,
            loan_term           = ctx.loan_tenure,
            existing_loan_amount= ctx.existing_emi * 12,
            credit_history_length = credit_history,
            credit_utilization  = credit_util,
            num_previous_loans  = prev_loans,
            num_late_payments   = late_payments,
            num_90days_late     = late_90,
            num_dependents      = 1,
        )

        ctx.risk_probability = prob
        ctx.confidence       = conf
        ctx.internal_score   = compute_score(prob)

        # SHAP explanations
        ctx.shap_features = explain_prediction(
            income              = ctx.income,
            credit_score        = ctx.internal_score,
            dti                 = dti,
            employment_length   = ctx.employment_length,
            age                 = ctx.age,
            loan_amount         = ctx.loan_amount,
            loan_term           = ctx.loan_tenure,
            existing_loan_amount= ctx.existing_emi * 12,
            credit_history_length = credit_history,
            credit_utilization  = credit_util,
            num_previous_loans  = prev_loans,
            num_late_payments   = late_payments,
            num_90days_late     = late_90,
            num_dependents      = 1,
        )

        steps.append(f"AGENT 3 (CreditScoring): OBSERVE — "
                     f"Default probability={prob:.3f}, Confidence={conf:.3f}, "
                     f"Internal score={ctx.internal_score} (illustrative, NOT CIBIL).")
        return ctx


# ─────────────────────────────────────────────────────────
#  Agent 4 — Risk Assessment Agent
# ─────────────────────────────────────────────────────────
class RiskAssessmentAgent:
    """
    Classifies risk as Low/Medium/High and explains contributing factors.
    """

    @staticmethod
    def run(ctx: UnderwritingContext) -> UnderwritingContext:
        steps = ctx.reasoning_steps
        steps.append("AGENT 4 (RiskAssessment): THINK — Classifying risk level and major factors.")

        p = ctx.risk_probability
        if p < 0.35:
            ctx.risk_category = "Low"
        elif p < 0.60:
            ctx.risk_category = "Medium"
        else:
            ctx.risk_category = "High"

        # Key risk factors
        factors = []
        if ctx.dti > 0.5:
            factors.append(f"high DTI ({ctx.dti:.0%})")
        if ctx.income < 20_000:
            factors.append("low monthly income")
        bureau = ctx.bureau_data or {}
        if bureau.get("late_90_days", 0) > 2:
            factors.append("multiple 90-day delinquencies")
        if bureau.get("credit_utilization", 0) > 0.8:
            factors.append("very high credit utilization")
        if ctx.employment_type in ("unemployed",):
            factors.append("no current employment")

        steps.append(
            f"AGENT 4 (RiskAssessment): OBSERVE — Risk category: {ctx.risk_category}. "
            f"Risk={p:.1%}. Key factors: {', '.join(factors) if factors else 'none flagged'}."
        )
        return ctx


# ─────────────────────────────────────────────────────────
#  Agent 5 — Fraud Investigation Agent
# ─────────────────────────────────────────────────────────
class FraudInvestigationAgent:
    """
    Uses IsolationForest anomaly detection + heuristic checks.
    Flags suspicious patterns for manual review.
    """

    @staticmethod
    def run(ctx: UnderwritingContext) -> UnderwritingContext:
        steps = ctx.reasoning_steps
        steps.append("AGENT 5 (FraudInvestigation): THINK — Running anomaly detection and heuristic fraud checks.")

        bureau = ctx.bureau_data or {}
        fraud_result = detect_anomaly(
            income              = ctx.income,
            dti                 = ctx.dti,
            employment_length   = ctx.employment_length,
            age                 = ctx.age,
            loan_amount         = ctx.loan_amount,
            loan_term           = ctx.loan_tenure,
            existing_loan_amount= ctx.existing_emi * 12,
            credit_history_length = bureau.get("credit_history_months", 60) / 12,
            credit_utilization  = bureau.get("credit_utilization", 0.4) * 100,
            num_previous_loans  = bureau.get("previous_loans", 1),
            num_late_payments   = bureau.get("late_payments", 1),
            num_90days_late     = bureau.get("late_90_days", 0),
        )

        ctx.fraud_result = fraud_result
        ctx.fraud_flags.extend(fraud_result.get("flags", []))

        steps.append(
            f"AGENT 5 (FraudInvestigation): ACT — IsolationForest: is_anomaly={fraud_result['is_anomaly']}, "
            f"score={fraud_result['anomaly_score']:.4f}."
        )
        if ctx.fraud_flags:
            steps.append(f"AGENT 5 (FraudInvestigation): OBSERVE — Fraud/anomaly flags: {ctx.fraud_flags}")
        else:
            steps.append("AGENT 5 (FraudInvestigation): OBSERVE — No fraud or anomaly signals detected.")

        return ctx


# ─────────────────────────────────────────────────────────
#  Agent 6 — Loan Decision Agent
# ─────────────────────────────────────────────────────────
class LoanDecisionAgent:
    """
    Combines all signals to produce final Approve/Review/Reject.
    Escalates to Review if fraud flags or low confidence.
    """

    @staticmethod
    def run(ctx: UnderwritingContext) -> UnderwritingContext:
        steps = ctx.reasoning_steps
        steps.append("AGENT 6 (LoanDecision): THINK — Combining model score, fraud flags, and risk category.")

        # Base decision from ML thresholds
        base_decision, base_reasoning = decision_engine(
            probability       = ctx.risk_probability,
            credit_score      = ctx.internal_score,
            dti               = ctx.dti,
            employment_length = int(ctx.employment_length),
        )

        # Override to Review if fraud flags exist
        if ctx.fraud_flags and base_decision == "Approve":
            base_decision = "Review"
            steps.append("AGENT 6 (LoanDecision): OBSERVE — Fraud flags present → escalating Approve → Review.")

        # Override to Review if payslip unverified and income not confirmed
        if ctx.payslip_data and ctx.payslip_data.get("fraud_flag") and base_decision == "Approve":
            base_decision = "Review"
            steps.append("AGENT 6 (LoanDecision): OBSERVE — Payslip fraud flag → escalating to Review.")

        # Override to Review if cross-document mismatch detected
        cross_verify = getattr(ctx, 'cross_verify_data', None)
        if cross_verify and cross_verify.get("flag_for_review") and base_decision == "Approve":
            base_decision = "Review"
            steps.append(
                f"AGENT 6 (LoanDecision): OBSERVE — Cross-document verification flagged "
                f"({cross_verify.get('overall_status', '?')}) → escalating Approve → Review."
            )

        # Override to Review if low confidence
        if ctx.confidence < 0.35 and base_decision != "Reject":
            base_decision = "Review"
            steps.append(f"AGENT 6 (LoanDecision): OBSERVE — Low model confidence ({ctx.confidence:.0%}) → escalating to Review.")

        ctx.decision = base_decision
        steps.append(
            f"AGENT 6 (LoanDecision): DECIDE — Final decision: {ctx.decision}. "
            f"Risk={ctx.risk_probability:.1%}, Score={ctx.internal_score}, "
            f"Category={ctx.risk_category}."
        )
        return ctx


# ─────────────────────────────────────────────────────────
#  Agent 7 — Explanation Agent
# ─────────────────────────────────────────────────────────
class ExplanationAgent:
    """
    Generates a clear, human-readable explanation of the decision.
    Uses OpenAI if USE_LOCAL_LLM=False, otherwise deterministic Python.
    """

    @staticmethod
    def _build_explanation(ctx: UnderwritingContext) -> str:
        d   = ctx.decision
        p   = ctx.risk_probability
        sc  = ctx.internal_score
        cat = ctx.risk_category
        bureau = ctx.bureau_data or {}

        # Key positive and negative factors
        positives = []
        negatives = []

        if ctx.income >= 50_000:
            positives.append("strong monthly income")
        elif ctx.income < 20_000:
            negatives.append("low monthly income")

        if ctx.employment_length >= 3:
            positives.append("stable employment history")
        elif ctx.employment_length < 1:
            negatives.append("very short employment history")

        if ctx.dti < 0.35:
            positives.append("manageable debt-to-income ratio")
        elif ctx.dti > 0.55:
            negatives.append("high debt burden")

        late = bureau.get("late_payments", 0)
        late90 = bureau.get("late_90_days", 0)
        if late90 == 0 and late <= 1:
            positives.append("clean payment history")
        elif late90 > 2:
            negatives.append("multiple 90-day delinquencies")
        elif late > 5:
            negatives.append("frequent late payments")

        util = bureau.get("credit_utilization", 0)
        if util < 0.4:
            positives.append("healthy credit utilization")
        elif util > 0.8:
            negatives.append("very high credit utilization")

        # Build explanation
        lines = []

        if d == "Approve":
            lines.append(
                f"Application approved. The applicant presents a {cat.lower()} credit risk "
                f"with an internal score of {sc} (illustrative scale, not an official CIBIL score) "
                f"and a default probability of {p:.1%}."
            )
        elif d == "Reject":
            lines.append(
                f"Application rejected. The applicant presents a {cat.lower()} credit risk "
                f"with an internal score of {sc} and a default probability of {p:.1%}, "
                f"which exceeds acceptable thresholds."
            )
        else:
            lines.append(
                f"Application flagged for manual review. The applicant has a {cat.lower()} "
                f"risk profile with an internal score of {sc} and default probability of {p:.1%}. "
                f"Borderline indicators require human verification."
            )

        if positives:
            pos_str = ", ".join(positives)
            lines.append(f"Positive factors: {pos_str}.")
        if negatives:
            neg_str = ", ".join(negatives)
            lines.append(f"Risk factors: {neg_str}.")
        if ctx.fraud_flags:
            lines.append(
                f"Note: {len(ctx.fraud_flags)} anomaly/fraud signal(s) were detected and "
                "have been included in this assessment."
            )

        bureau_disclaimer = bureau.get(
            "disclaimer",
            "Credit data is simulated for demonstration purposes only."
        )
        lines.append(f"[{bureau_disclaimer}]")

        return " ".join(lines)

    @staticmethod
    def _openai_explanation(ctx: UnderwritingContext) -> str:
        """Generate explanation using GPT if available."""
        try:
            from openai import OpenAI
            client = OpenAI(api_key=settings.OPENAI_API_KEY)

            bureau = ctx.bureau_data or {}
            prompt = f"""
You are an AI loan underwriting assistant. Summarize the following loan decision in 3-4 sentences,
suitable for the applicant. Be clear, respectful, and factual.

Decision: {ctx.decision}
Default Probability: {ctx.risk_probability:.1%}
Internal Score: {ctx.internal_score} (illustrative, NOT official CIBIL)
Risk Category: {ctx.risk_category}
Monthly Income: {ctx.income:,.0f}
Loan Amount: {ctx.loan_amount:,.0f}
DTI: {ctx.dti:.0%}
Employment Length: {ctx.employment_length} years
Fraud Flags: {ctx.fraud_flags or 'None'}
[All credit bureau data is simulated for demo purposes.]
"""
            resp = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.3,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logger.warning(f"OpenAI explanation failed: {e}. Using local explanation.")
            return ExplanationAgent._build_explanation(ctx)

    @staticmethod
    def run(ctx: UnderwritingContext) -> UnderwritingContext:
        steps = ctx.reasoning_steps
        steps.append("AGENT 7 (Explanation): THINK — Generating human-readable explanation.")

        if settings.USE_LOCAL_LLM:
            ctx.explanation = ExplanationAgent._build_explanation(ctx)
        else:
            ctx.explanation = ExplanationAgent._openai_explanation(ctx)

        steps.append(f"AGENT 7 (Explanation): DECIDE — Explanation generated ({len(ctx.explanation)} chars).")
        return ctx


# ─────────────────────────────────────────────────────────
#  Pipeline orchestrator
# ─────────────────────────────────────────────────────────
class UnderwritingPipeline:
    """
    Runs all 7 agents in sequence, sharing UnderwritingContext.
    """
    AGENTS = [
        DocumentAgent,
        CreditBureauAgent,
        CreditScoringAgent,
        RiskAssessmentAgent,
        FraudInvestigationAgent,
        LoanDecisionAgent,
        ExplanationAgent,
    ]

    @classmethod
    def run(cls, ctx: UnderwritingContext) -> UnderwritingContext:
        logger.info(f"UnderwritingPipeline starting for user: {ctx.user_id}")
        for Agent in cls.AGENTS:
            try:
                ctx = Agent.run(ctx)
            except Exception as e:
                logger.error(f"{Agent.__name__} failed: {e}", exc_info=True)
                ctx.reasoning_steps.append(f"{Agent.__name__}: ERROR — {e}")
                ctx.validation_notes.append(f"Agent error in {Agent.__name__}: {str(e)[:100]}")
        logger.info(f"Pipeline complete: decision={ctx.decision}, risk={ctx.risk_probability:.3f}")
        return ctx
