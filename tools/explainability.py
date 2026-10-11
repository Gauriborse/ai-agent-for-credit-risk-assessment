"""
SHAP Explainability — XGBoost 13-feature model
"""

import shap
import pandas as pd
from tools.risk_model import get_model, get_feature_names

_explainer = None

def get_explainer():
    global _explainer
    if _explainer is None:
        artifact = get_model()
        _explainer = shap.TreeExplainer(artifact['model'])
    return _explainer


def explain_prediction(
    income: float,
    credit_score: int,
    dti: float,
    employment_length: int,
    age: int                    = 35,
    loan_amount: float          = 300000,
    loan_term: int              = 36,
    existing_loan_amount: float = 0,
    credit_history_length: float= 10.0,
    credit_utilization: float   = 40.0,
    num_previous_loans: int     = 1,
    num_late_payments: int      = 1,
    num_90days_late: int        = 0,
    num_dependents: int         = 1,
) -> list:
    """
    Use SHAP TreeExplainer to rank feature contributions.
    Returns list of {feature, impact} dicts sorted by importance.
    """
    explainer = get_explainer()
    features  = get_feature_names()

    dti_scaled = dti * 70.0

    row = {
        'Age':                    age,
        'MonthlyIncome':          income,
        'EmploymentLength':       employment_length,
        'LoanAmount':             loan_amount,
        'LoanTerm':               loan_term,
        'ExistingLoanAmount':     existing_loan_amount,
        'DebtToIncomeRatio':      dti_scaled,
        'CreditHistoryLength':    credit_history_length,
        'CreditUtilizationRatio': credit_utilization,
        'NumberOfPreviousLoans':  num_previous_loans,
        'NumberOfLatePayments':   num_late_payments,
        'NumberOf90DaysLate':     num_90days_late,
        'NumberOfDependents':     num_dependents,
    }

    df = pd.DataFrame([row])[features]

    shap_values = explainer.shap_values(df)

    if isinstance(shap_values, list):
        vals = shap_values[1][0]
    elif len(shap_values.shape) == 3:
        vals = shap_values[0, :, 1]
    else:
        vals = shap_values[0]

    explanation = []
    for i, feature in enumerate(features):
        contribution = float(vals[i])
        if contribution < -0.15:
            impact = "High positive impact reducing risk"
        elif contribution < -0.05:
            impact = "Moderate positive impact reducing risk"
        elif contribution < 0.05:
            impact = "Low impact"
        elif contribution < 0.15:
            impact = "Moderate negative impact increasing risk"
        else:
            impact = "High negative impact increasing risk"

        explanation.append({
            "feature":      feature,
            "raw_contrib":  contribution,
            "impact":       impact
        })

    explanation.sort(key=lambda x: abs(x["raw_contrib"]), reverse=True)
    return [{"feature": e["feature"], "impact": e["impact"]} for e in explanation]
