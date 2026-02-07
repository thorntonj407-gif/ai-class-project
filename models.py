"""Data models for Capital Raise Detector using Pydantic."""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class FinancialMetrics(BaseModel):
    """Financial metrics for a company."""
    ticker: str
    company_name: str

    # Cash and liquidity
    cash_and_equivalents: float = Field(..., description="Cash & equivalents in USD")
    monthly_burn_rate: float = Field(..., description="Monthly operating cash outflow")
    current_assets: float = Field(..., description="Total current assets")
    current_liabilities: float = Field(..., description="Total current liabilities")
    quick_assets: float = Field(..., description="Current assets - inventory")
    accounts_payable: float = Field(..., description="Accounts payable")

    # Debt and maturities
    total_debt: float = Field(..., description="Total outstanding debt")
    debt_due_12mo: float = Field(..., description="Debt maturing in next 12 months")
    debt_due_6_18mo: float = Field(..., description="Debt maturing in 6-18 months")

    # Operating performance
    revenue_trailing_12m: float = Field(..., description="Revenue (trailing 12 months)")
    revenue_prior_year: float = Field(..., description="Revenue (prior year)")
    operating_cash_flow_trailing_12m: float = Field(..., description="OCF (trailing 12 months)")
    gross_margin: float = Field(..., description="Gross margin (%)")
    prior_gross_margin: float = Field(..., description="Prior gross margin (%)")
    capex_annual: float = Field(..., description="Annual capital expenditures")

    # Market and behavioral
    stock_price: float = Field(..., description="Current stock price")
    stock_price_52w_high: float = Field(..., description="52-week high stock price")
    insider_selling_activity: str = Field(default="normal", description="normal/elevated/high")
    auditor_going_concern: bool = Field(default=False, description="Any going concern warnings")
    credit_rating: Optional[str] = Field(default=None, description="Credit rating (e.g., BBB, BB)")
    credit_rating_outlook: Optional[str] = Field(default=None, description="Outlook: stable/negative/positive")

    # Metadata
    last_updated: datetime = Field(default_factory=datetime.now)


class SignalScores(BaseModel):
    """Breakdown of scores for each signal."""
    cash_runway_score: float = Field(..., description="0-40 points")
    liquidity_stress_score: float = Field(..., description="0-20 points")
    debt_maturity_score: float = Field(..., description="0-15 points")
    operational_red_flags_score: float = Field(..., description="0-15 points")
    market_behavioral_score: float = Field(..., description="0-10 points")


class CapitalRaisePrediction(BaseModel):
    """Final capital raise prediction for a company."""
    ticker: str
    company_name: str
    likelihood_score: float = Field(..., description="Total score 0-100")
    signal_scores: SignalScores

    # Alert status
    above_threshold: bool = Field(..., description="Score > threshold (50)")
    risk_level: str = Field(..., description="low/medium/high/critical")

    # Key drivers
    key_drivers: list[str] = Field(default_factory=list, description="Top risk factors")

    # Confidence
    confidence: float = Field(..., description="Confidence in prediction (0-100)")

    # Timestamp
    timestamp: datetime = Field(default_factory=datetime.now)

    def __str__(self) -> str:
        """Pretty print the prediction."""
        return f"""
Capital Raise Detector Report
{'='*50}
Company: {self.company_name} ({self.ticker})
Likelihood Score: {self.likelihood_score:.1f}/100
Risk Level: {self.risk_level.upper()}
Status: {"⚠️  ABOVE THRESHOLD" if self.above_threshold else "✓ Below threshold"}
Confidence: {self.confidence:.1f}%

Signal Breakdown:
  • Cash Runway: {self.signal_scores.cash_runway_score:.1f}/40
  • Liquidity Stress: {self.signal_scores.liquidity_stress_score:.1f}/20
  • Debt Maturity: {self.signal_scores.debt_maturity_score:.1f}/15
  • Operational Red Flags: {self.signal_scores.operational_red_flags_score:.1f}/15
  • Market & Behavioral: {self.signal_scores.market_behavioral_score:.1f}/10

Key Drivers:
{chr(10).join(f"  - {driver}" for driver in self.key_drivers)}
"""
