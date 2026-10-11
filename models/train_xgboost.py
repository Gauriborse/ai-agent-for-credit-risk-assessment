"""
XGBoost Credit Risk Model Training Script
==========================================
Trains on the real individual-loan-credit-risk-dataset.csv
with all 13 features. Saves model + feature list to models/credit_risk_model.pkl
"""

import os
import pickle
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    classification_report, roc_auc_score,
    accuracy_score, confusion_matrix
)
import xgboost as xgb

# ── Paths ──────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_PATH  = os.path.join(BASE_DIR, 'dataset', 'individual-loan-credit-risk-dataset.csv')
MODEL_PATH = os.path.join(BASE_DIR, 'credit_risk_model.pkl')

# ── Feature columns ────────────────────────────────────────
FEATURES = [
    'Age',
    'MonthlyIncome',
    'EmploymentLength',
    'LoanAmount',
    'LoanTerm',
    'ExistingLoanAmount',
    'DebtToIncomeRatio',
    'CreditHistoryLength',
    'CreditUtilizationRatio',
    'NumberOfPreviousLoans',
    'NumberOfLatePayments',
    'NumberOf90DaysLate',
    'NumberOfDependents',
]
TARGET = 'Loan_Default'

def load_data():
    df = pd.read_csv(DATA_PATH)
    print(f"Dataset loaded: {df.shape[0]} rows, {df.shape[1]} columns")
    print(f"Default rate: {df[TARGET].mean():.1%}")
    return df

def preprocess(df):
    df = df.copy()
    # Fill missing values with median
    for col in FEATURES:
        if df[col].isnull().any():
            df[col] = df[col].fillna(df[col].median())
    X = df[FEATURES]
    y = df[TARGET]
    return X, y

def train():
    print("=" * 60)
    print("CREDIT RISK MODEL TRAINING — XGBoost")
    print("=" * 60)

    df = load_data()
    X, y = preprocess(df)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"\nTrain: {X_train.shape[0]} | Test: {X_test.shape[0]}")

    # ── XGBoost with class balancing ──────────────────────
    scale_pos = (y_train == 0).sum() / (y_train == 1).sum()
    print(f"Class imbalance ratio (scale_pos_weight): {scale_pos:.2f}")

    model = xgb.XGBClassifier(
        n_estimators       = 300,
        max_depth          = 6,
        learning_rate      = 0.05,
        subsample          = 0.8,
        colsample_bytree   = 0.8,
        scale_pos_weight   = scale_pos,
        use_label_encoder  = False,
        eval_metric        = 'logloss',
        random_state       = 42,
        n_jobs             = -1,
    )

    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=50,
    )

    # ── Evaluation ────────────────────────────────────────
    y_pred      = model.predict(X_test)
    y_pred_prob = model.predict_proba(X_test)[:, 1]

    print("\n--- Classification Report ---")
    print(classification_report(y_test, y_pred, target_names=['No Default', 'Default']))
    print(f"ROC-AUC : {roc_auc_score(y_test, y_pred_prob):.4f}")
    print(f"Accuracy: {accuracy_score(y_test, y_pred):.4f}")
    print(f"\nConfusion Matrix:\n{confusion_matrix(y_test, y_pred)}")

    # ── Feature importance ────────────────────────────────
    importances = pd.Series(
        model.feature_importances_, index=FEATURES
    ).sort_values(ascending=False)
    print("\n--- Feature Importances ---")
    for feat, imp in importances.items():
        print(f"  {feat:<35} {imp:.4f}")

    # ── Save model + metadata ─────────────────────────────
    artifact = {
        'model':    model,
        'features': FEATURES,
        'auc':      float(roc_auc_score(y_test, y_pred_prob)),
        'accuracy': float(accuracy_score(y_test, y_pred)),
    }
    os.makedirs(BASE_DIR, exist_ok=True)
    with open(MODEL_PATH, 'wb') as f:
        pickle.dump(artifact, f)

    print(f"\nModel saved → {MODEL_PATH}")
    print("=" * 60)
    return model

if __name__ == '__main__':
    train()
