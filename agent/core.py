"""
Agent Core — routes loan applications through the appropriate pipeline.

New path:  UnderwritingPipeline (7 modular agents)
Legacy path: CreditRiskAgent (4-feature XGBoost, kept for backward compat)
"""

from config import settings
from tools.user_data import fetch_user_data
from tools.risk_model import predict_risk
from tools.explainability import explain_prediction
from tools.decision import decision_engine
from agent.credit_risk_agent import CreditRiskAgent, CreditRiskInput
from agent.underwriting_agents import UnderwritingPipeline, UnderwritingContext
from api.schemas import LoanApplicationRequest, AgentDecisionResponse, FeatureImpact
from utils.logger import get_logger

logger = get_logger(__name__)


def _context_from_request(
    app: LoanApplicationRequest,
    cross_verify_data: dict = None,
) -> UnderwritingContext:
    """Build UnderwritingContext from a LoanApplicationRequest."""
    return UnderwritingContext(
        user_id         = app.user_id,
        full_name       = getattr(app, "full_name", None) or app.user_id,
        age             = getattr(app, "age", None) or 35,
        income          = app.income,
        employment_type = getattr(app, "employment_type", None) or "salaried",
        employment_length = float(getattr(app, "employment_length", None) or 5),
        loan_amount     = float(getattr(app, "loan_amount", None) or 300_000),
        loan_tenure     = int(getattr(app, "loan_tenure", None) or 36),
        loan_purpose    = getattr(app, "loan_purpose", None) or "personal",
        existing_emi    = float(getattr(app, "existing_emi", None) or 0.0),
        currency        = getattr(app, "currency", None) or "USD",
        payslip_data    = getattr(app, "payslip_verification", None),
        cross_verify_data = cross_verify_data,
    )


def _response_from_context(ctx: UnderwritingContext) -> AgentDecisionResponse:
    """Convert UnderwritingContext back to AgentDecisionResponse."""
    features = [
        FeatureImpact(feature=f["feature"], impact=f["impact"])
        for f in (ctx.shap_features or [])
    ]
    return AgentDecisionResponse(
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


def new_pipeline_agent(
    app: LoanApplicationRequest,
    cross_verify_data: dict = None,
) -> AgentDecisionResponse:
    """
    Full 7-agent underwriting pipeline.
    Fetches credit bureau data, runs all ML models, generates explanation.
    cross_verify_data: dict from kyc_records (cross-document verification result).
    """
    ctx = _context_from_request(app, cross_verify_data=cross_verify_data)
    ctx = UnderwritingPipeline.run(ctx)
    return _response_from_context(ctx)


def mock_llm_agent(
    app: LoanApplicationRequest,
    cross_verify_data: dict = None,
) -> AgentDecisionResponse:
    """
    Legacy mock agent — now delegates to new pipeline.
    Kept for backward compat.
    """
    return new_pipeline_agent(app, cross_verify_data=cross_verify_data)


def openai_llm_agent(
    app: LoanApplicationRequest,
    cross_verify_data: dict = None,
) -> AgentDecisionResponse:
    """
    OpenAI-backed agent — uses new pipeline (ExplanationAgent uses GPT).
    """
    return new_pipeline_agent(app, cross_verify_data=cross_verify_data)


class LoanAgent:
    @staticmethod
    def process_application(
        app: LoanApplicationRequest,
        cross_verify_data: dict = None,
    ) -> AgentDecisionResponse:
        """Route to the new 7-agent pipeline."""
        try:
            return new_pipeline_agent(app, cross_verify_data=cross_verify_data)
        except Exception as e:
            logger.error(f"LoanAgent pipeline failed: {e}", exc_info=True)
            raise RuntimeError(f"Agent Pipeline Error: {e}")
