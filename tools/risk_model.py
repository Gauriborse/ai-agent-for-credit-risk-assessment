"""
Credit Risk Model — XGBoost + Anomaly Detection
================================================
Loads trained XGBoost model and IsolationForest anomaly detector.
Provides:
  predict_risk()    — default probability + confidence
  compute_score()   — illustrative 300-900 internal score (NOT CIBIL)
  detect_anomaly()  — fraud/anomaly flag via IsolationForest
  get_feature_names() — ordered feature list
"""

import pickle
import pandas as pd
import numpy as np
import os
from typing import Tuple, List

# ── Model paths ────────────────────────────────────────────
_BASE_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MODEL_PATH    = os.path.join(_BASE_DIR, "models", "credit_risk_model.pkl")
_ANOMALY_PATH  = os.path.join(_BASE_DIR, "models", "anomaly_model.pkl")

# ── Global caches ──────────────────────────────────────────
_artifact        = None
_anomaly_artifact = None


def get_model():
    """Load XGBoost artifact once, cache globally."""
    global _artifact
    if _artifact is None:
        if not os.path.exists(_MODEL_PATH):
            raise FileNotFoundError(
                f"Model not found at {_MODEL_PATH}. "
                "Run: python models/train_models.py"
            )
        with open(_MODEL_PATH, "rb") as f:
            _artifact = pickle.load(f)
    return _artifact


def get_anomaly_model():
    """Load IsolationForest artifact once, cache globally."""
    global _anomaly_artifact
    if _anomaly_artifact is None:
        if not os.path.exists(_ANOMALY_PATH):
            return None
        with open(_ANOMALY_PATH, "rb") as f:
            _anomaly_artifact = pickle.load(f)
    return _anomaly_artifact


def get_feature_names() -> List[str]:
    return get_model()["features"]


def _build_row(
    income: float,
    # optional: from credit bureau or defaults
    credit_history_length: float = 10.0,
    credit_utilization:    float = 40.0,
    num_late_payments:     int   = 1,
    num_90days_late:       int   = 0,
    # optional: from loan form
    age:                   int   = 35,
    employment_length:     float = 5.0,
    loan_amount:           float = 300_000,
    loan_term:             int   = 36,
    existing_loan_amount:  float = 0,
    num_previous_loans:    int   = 1,
    num_dependents:        int   = 1,
    # legacy DTI scalar — kept for backward compat
    dti:                   float = 0.3,
    **_,  # absorb unknown kwargs silently
) -> dict:
    """Build feature dict in the exact order the model was trained on."""
    # dti provided as 0-1 scale, model trained on 0-70 scale
    dti_scaled = dti * 70.0

    return {
        "Age":                    age,
        "MonthlyIncome":          income,
        "EmploymentLength":       employment_length,
        "LoanAmount":             loan_amount,
        "LoanTerm":               loan_term,
        "ExistingLoanAmount":     existing_loan_amount,
        "DebtToIncomeRatio":      dti_scaled,
        "CreditHistoryLength":    credit_history_length,
        "CreditUtilizationRatio": credit_utilization,
        "NumberOfPreviousLoans":  num_previous_loans,
        "NumberOfLatePayments":   num_late_payments,
        "NumberOf90DaysLate":     num_90days_late,
        "NumberOfDependents":     num_dependents,
    }


def predict_risk(
    income:                float,
    # Legacy positional params (kept for backward compat with old callers)
    credit_score:          int   = 650,
    dti:                   float = 0.3,
    employment_length:     int   = 5,
    # Extended params
    age:                   int   = 35,
    loan_amount:           float = 300_000,
    loan_term:             int   = 36,
    existing_loan_amount:  float = 0,
    credit_history_length: float = 10.0,
    credit_utilization:    float = 40.0,
    num_previous_loans:    int   = 1,
    num_late_payments:     int   = 1,
    num_90days_late:       int   = 0,
    num_dependents:        int   = 1,
) -> Tuple[float, float]:
    """
    Predict default probability using XGBoost.
    Returns (risk_probability, confidence_score) both in [0,1].
    """
    artifact = get_model()
    model    = artifact["model"]
    features = artifact["features"]

    row = _build_row(
        income=income, dti=dti, employment_length=employment_length,
        age=age, loan_amount=loan_amount, loan_term=loan_term,
        existing_loan_amount=existing_loan_amount,
        credit_history_length=credit_history_length,
        credit_utilization=credit_utilization,
        num_previous_loans=num_previous_loans,
        num_late_payments=num_late_payments,
        num_90days_late=num_90days_late,
        num_dependents=num_dependents,
    )

    df   = pd.DataFrame([row])[features]
    prob = float(model.predict_proba(df)[0][1])
    conf = float(min(abs(prob - 0.5) * 2, 1.0))
    return prob, conf


def compute_score(risk_probability: float) -> int:
    """
    Convert default probability to an illustrative internal score (300-900).
    NOT an official CIBIL score. For demonstration purposes only.
    """
    score = int(900 - risk_probability * 600)
    return max(300, min(900, score))


def detect_anomaly(
    income: float,
    dti:    float = 0.3,
    employment_length: float = 5.0,
    age:    int   = 35,
    loan_amount:   float = 300_000,
    loan_term:     int   = 36,
    existing_loan_amount: float = 0,
    credit_history_length: float = 10.0,
    credit_utilization:   float = 40.0,
    num_previous_loans:   int   = 1,
    num_late_payments:    int   = 1,
    num_90days_late:      int   = 0,
    num_dependents:       int   = 1,
) -> dict:
    """
    Detect anomalies using IsolationForest.
    Returns { is_anomaly: bool, anomaly_score: float, flags: [str] }
    """
    artifact = get_anomaly_model()
    if artifact is None:
        return {"is_anomaly": False, "anomaly_score": 0.0, "flags": []}

    model  = artifact["model"]
    scaler = artifact["scaler"]
    features = artifact["features"]

    row = _build_row(
        income=income, dti=dti, employment_length=employment_length,
        age=age, loan_amount=loan_amount, loan_term=loan_term,
        existing_loan_amount=existing_loan_amount,
        credit_history_length=credit_history_length,
        credit_utilization=credit_utilization,
        num_previous_loans=num_previous_loans,
        num_late_payments=num_late_payments,
        num_90days_late=num_90days_late,
        num_dependents=num_dependents,
    )

    df     = pd.DataFrame([row])[features]
    X_sc   = scaler.transform(df)
    pred   = model.predict(X_sc)[0]          # 1=normal, -1=anomaly
    score  = float(model.score_samples(X_sc)[0])  # more negative = more anomalous

    is_anom = (pred == -1)
    flags   = []

    # Additional heuristic flags
    dti_scaled = dti * 70.0
    if dti_scaled > 60:
        flags.append("Extremely high debt-to-income ratio (>60%)")
    if num_90days_late > 3:
        flags.append("Excessive 90-day late payments")
    if income < 5000 and loan_amount > 500_000:
        flags.append("Very high loan amount relative to low income")
    if credit_utilization > 90:
        flags.append("Near-maxed credit utilization")
    if num_late_payments > 10:
        flags.append("History of frequent late payments")
    if is_anom:
        flags.append("Statistical anomaly detected by IsolationForest")

    return {
        "is_anomaly":    is_anom,
        "anomaly_score": round(score, 4),
        "flags":         flags,
    }
