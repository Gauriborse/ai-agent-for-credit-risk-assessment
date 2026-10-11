"""
Mock Credit Bureau Service
===========================
Simulates a credit bureau API response for demo/testing purposes.
All data returned is SIMULATED — not from any real credit bureau.
Results are clearly labelled as mock/simulated data.

If the external bureau API is not available (which is the default),
it falls back to deterministic mock data seeded on the user_id hash.
This ensures consistent results for the same applicant across sessions.
"""

import hashlib
import random
import httpx
from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class MockCreditBureauService:
    """
    Mock Credit Bureau — generates realistic but entirely simulated credit data.
    Clearly labelled as SIMULATED throughout.
    """

    def _seed_for_user(self, user_id: str) -> int:
        """Deterministic seed based on user_id so data is consistent per user."""
        return int(hashlib.md5(user_id.encode()).hexdigest(), 16) % (10**8)

    def _simulate_credit_data(self, user_id: str) -> dict:
        """
        Generate deterministic simulated credit data for a given user_id.
        Weighted towards realistic applicant profiles — people who apply for
        loans typically have moderate-to-good credit (not the full random range).

        Credit quality is distributed as:
          65% good (score 720–850, low utilization, clean payment history)
          28% fair (score 600–719, moderate utilization, few late payments)
           7% poor (score 400–599, high utilization, more late payments)
        """
        seed = self._seed_for_user(user_id)
        rng = random.Random(seed)

        # Use SHA-256 for bucket selection — gives more uniform distribution
        # than MD5, avoiding clustering of certain user IDs in the poor bucket
        sha_seed = int(hashlib.sha256(user_id.encode()).hexdigest(), 16) % 100
        if sha_seed < 65:
            score_bucket = 'good'
        elif sha_seed < 93:
            score_bucket = 'fair'
        else:
            score_bucket = 'poor'

        if score_bucket == 'good':
            credit_score          = rng.randint(720, 850)
            credit_utilization    = round(rng.uniform(0.05, 0.40), 2)
            late_payments         = rng.choices([0, 1, 2], weights=[70, 20, 10])[0]
            late_90_days          = rng.choices([0, 1],    weights=[95, 5])[0]
            outstanding_debt      = round(rng.uniform(0, 120_000), 2)
        elif score_bucket == 'fair':
            credit_score          = rng.randint(600, 719)
            credit_utilization    = round(rng.uniform(0.25, 0.60), 2)
            late_payments         = rng.choices([0, 1, 2, 3], weights=[45, 30, 17, 8])[0]
            late_90_days          = rng.choices([0, 1],       weights=[82, 18])[0]
            outstanding_debt      = round(rng.uniform(10_000, 250_000), 2)
        else:  # poor
            credit_score          = rng.randint(400, 599)
            credit_utilization    = round(rng.uniform(0.55, 0.90), 2)
            late_payments         = rng.randint(3, 8)
            late_90_days          = rng.choices([0, 1, 2], weights=[55, 30, 15])[0]
            outstanding_debt      = round(rng.uniform(80_000, 450_000), 2)

        credit_history_months = rng.randint(24, 240)
        total_accounts        = rng.randint(1, 8)
        delinquent_accounts   = rng.choices([0, 1, 2], weights=[78, 17, 5])[0]
        previous_loans        = rng.randint(0, 5)

        if credit_score >= 750:
            risk_category = "Low"
        elif credit_score >= 600:
            risk_category = "Medium"
        else:
            risk_category = "High"

        return {
            "success":               True,
            "data_source":           "SIMULATED",
            "disclaimer": (
                "This is SIMULATED credit data for demonstration purposes only. "
                "It does NOT represent actual bureau records, CIBIL scores, or real financial history. "
                "All values are algorithmically generated for testing."
            ),
            "bureau_name":           "MockCreditBureau (Simulated)",
            "user_id":               user_id,
            "credit_score":          credit_score,
            "credit_score_label":    "Illustrative Internal Score (300–900, NOT official CIBIL)",
            "credit_history_months": credit_history_months,
            "credit_history_years":  round(credit_history_months / 12, 1),
            "credit_utilization":    credit_utilization,
            "credit_utilization_pct": round(credit_utilization * 100, 1),
            "total_accounts":        total_accounts,
            "delinquent_accounts":   delinquent_accounts,
            "late_payments":         late_payments,
            "late_90_days":          late_90_days,
            "payment_history_score": max(0, 100 - (late_payments * 5) - (late_90_days * 10)),
            "outstanding_debt":      outstanding_debt,
            "previous_loans":        previous_loans,
            "risk_category":         risk_category,
            "debt_index":            round(min(credit_utilization + (delinquent_accounts * 0.1), 1.0), 3),
        }

    async def get_credit_data(self, user_id: str, full_name: str = "") -> dict:
        """
        Attempt to call external bureau API; fall back to mock simulation.
        Returns clearly-labelled simulated data in all cases for this demo.
        """
        # Try external API first (if configured)
        if settings.CREDIT_BUREAU_API_URL and settings.CREDIT_BUREAU_API_URL != "http://localhost:8001":
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        f"{settings.CREDIT_BUREAU_API_URL}/api/v1/credit-check",
                        json={"user_id": user_id, "full_name": full_name},
                        headers={"X-API-Key": getattr(settings, "CREDIT_BUREAU_API_KEY", "")},
                    )
                    if response.status_code == 200:
                        data = response.json()
                        data["data_source"] = "EXTERNAL_MOCK"
                        data["disclaimer"] = (
                            "⚠️ Data returned by mock external bureau API — "
                            "not real bureau records."
                        )
                        logger.info(f"External credit bureau data fetched for {user_id}")
                        return data
            except Exception as e:
                logger.warning(f"External bureau API unavailable: {e}. Using built-in mock.")

        # Default: built-in deterministic mock
        data = self._simulate_credit_data(user_id)
        logger.info(f"Simulated credit bureau data generated for {user_id} (score={data['credit_score']})")
        return data

    def get_credit_data_sync(self, user_id: str) -> dict:
        """Synchronous version for use inside non-async agent code."""
        return self._simulate_credit_data(user_id)


# Singleton
credit_bureau_service = MockCreditBureauService()
