"""Example financial data for testing."""

from models import FinancialMetrics
from datetime import datetime


# Example 1: Company with strong financials
STRONG_COMPANY = FinancialMetrics(
    ticker="STRONG",
    company_name="Strong Tech Inc",
    cash_and_equivalents=500_000_000,
    monthly_burn_rate=5_000_000,  # Positive cash generation
    current_assets=600_000_000,
    current_liabilities=200_000_000,
    quick_assets=550_000_000,
    accounts_payable=50_000_000,
    total_debt=100_000_000,
    debt_due_12mo=5_000_000,
    debt_due_6_18mo=10_000_000,
    revenue_trailing_12m=1_000_000_000,
    revenue_prior_year=900_000_000,
    operating_cash_flow_trailing_12m=150_000_000,
    gross_margin=0.75,
    prior_gross_margin=0.74,
    capex_annual=30_000_000,
    stock_price=150.0,
    stock_price_52w_high=160.0,
    insider_selling_activity="normal",
    auditor_going_concern=False,
    credit_rating="BBB+",
    credit_rating_outlook="stable",
    sector="Information Technology",
    market_cap=15_000_000_000,  # $15B market cap
)

# Example 2: Company with cash runway concerns
CASH_RUNWAY_RISK = FinancialMetrics(
    ticker="BURN",
    company_name="Burn Fast Corp",
    cash_and_equivalents=50_000_000,
    monthly_burn_rate=10_000_000,  # 5 months runway
    current_assets=80_000_000,
    current_liabilities=60_000_000,
    quick_assets=50_000_000,
    accounts_payable=40_000_000,
    total_debt=100_000_000,
    debt_due_12mo=20_000_000,
    debt_due_6_18mo=25_000_000,
    revenue_trailing_12m=200_000_000,
    revenue_prior_year=190_000_000,
    operating_cash_flow_trailing_12m=-40_000_000,
    gross_margin=0.55,
    prior_gross_margin=0.58,
    capex_annual=15_000_000,
    stock_price=45.0,
    stock_price_52w_high=120.0,
    insider_selling_activity="elevated",
    auditor_going_concern=False,
    credit_rating="B",
    credit_rating_outlook="negative",
    sector="Energy",
    market_cap=1_800_000_000,  # $1.8B market cap
)

# Example 3: Company with operational and liquidity stress
OPERATIONAL_STRESS = FinancialMetrics(
    ticker="STRESS",
    company_name="Struggling Industries",
    cash_and_equivalents=30_000_000,
    monthly_burn_rate=8_000_000,  # ~4 months runway
    current_assets=90_000_000,
    current_liabilities=110_000_000,  # Current ratio < 1.0
    quick_assets=40_000_000,
    accounts_payable=70_000_000,
    total_debt=250_000_000,
    debt_due_12mo=50_000_000,  # > cash level
    debt_due_6_18mo=40_000_000,
    revenue_trailing_12m=300_000_000,
    revenue_prior_year=360_000_000,  # -17% decline
    operating_cash_flow_trailing_12m=-30_000_000,
    gross_margin=0.40,
    prior_gross_margin=0.50,  # -10% margin compression
    capex_annual=25_000_000,
    stock_price=8.0,
    stock_price_52w_high=45.0,  # Down 82%
    insider_selling_activity="high",
    auditor_going_concern=True,  # Red flag!
    credit_rating="CCC",
    credit_rating_outlook="negative",
    sector="Consumer Discretionary",
    market_cap=2_500_000_000,  # $2.5B market cap
)

# Example 4: Growth-stage company needing capital
GROWTH_STAGE = FinancialMetrics(
    ticker="GROW",
    company_name="Growth Ventures LLC",
    cash_and_equivalents=80_000_000,
    monthly_burn_rate=15_000_000,  # ~5.3 months runway
    current_assets=120_000_000,
    current_liabilities=40_000_000,
    quick_assets=80_000_000,
    accounts_payable=20_000_000,
    total_debt=50_000_000,
    debt_due_12mo=10_000_000,
    debt_due_6_18mo=15_000_000,
    revenue_trailing_12m=150_000_000,
    revenue_prior_year=100_000_000,  # +50% growth
    operating_cash_flow_trailing_12m=-80_000_000,
    gross_margin=0.70,
    prior_gross_margin=0.68,
    capex_annual=40_000_000,  # Heavy investment for growth
    stock_price=85.0,
    stock_price_52w_high=95.0,
    insider_selling_activity="normal",
    auditor_going_concern=False,
    credit_rating="BB+",
    credit_rating_outlook="positive",
    sector="Information Technology",
    market_cap=8_500_000_000,  # $8.5B market cap
)

# Example 5: Stable mature company
MATURE_STABLE = FinancialMetrics(
    ticker="STABLE",
    company_name="Mature Corp Inc",
    cash_and_equivalents=200_000_000,
    monthly_burn_rate=-10_000_000,  # Generating cash
    current_assets=400_000_000,
    current_liabilities=150_000_000,
    quick_assets=350_000_000,
    accounts_payable=50_000_000,
    total_debt=200_000_000,
    debt_due_12mo=20_000_000,
    debt_due_6_18mo=30_000_000,
    revenue_trailing_12m=2_000_000_000,
    revenue_prior_year=1_950_000_000,  # Flat, stable
    operating_cash_flow_trailing_12m=200_000_000,
    gross_margin=0.65,
    prior_gross_margin=0.64,
    capex_annual=50_000_000,
    stock_price=125.0,
    stock_price_52w_high=130.0,
    insider_selling_activity="normal",
    auditor_going_concern=False,
    credit_rating="A-",
    credit_rating_outlook="stable",
    sector="Financials",
    market_cap=45_200_000_000,  # $45.2B market cap
)


EXAMPLE_COMPANIES = [
    STRONG_COMPANY,
    CASH_RUNWAY_RISK,
    OPERATIONAL_STRESS,
    GROWTH_STAGE,
    MATURE_STABLE,
]


# Example earnings call transcript (snippet)
EARNINGS_CALL_TRANSCRIPT = """
Thank you for joining us today. We're pleased to report Q3 results.

Revenue was $500M, up 8% year-over-year. However, as you'll see, we're facing
significant headwinds in our core market. We've begun exploring strategic options
to optimize our capital structure.

We're evaluating several financing alternatives, including a potential secondary
offering to fund our expansion into new verticals. Our CFO will speak more to
financing timelines, but we wanted to give you early visibility on this.

We're also in advanced discussions with several strategic partners about potential
partnerships or investments. More to come on this front.

On the positive side, our gross margins improved 150 basis points, and we're
on track for EBITDA profitability by Q4.

Operator, let's take questions.
"""


# Example market news
MARKET_NEWS = """
SAN FRANCISCO - Tech startup exploring IPO, eyes $2B valuation (Reuters)

SOURCES: Company considering secondary offering to fund expansion (Bloomberg)

CEO interview: "We have optionality on capital structure" (TC Crunch)

Insider selling: CFO and 2 board members sold 5M shares over past month (SEC filing)

Credit rating downgrade to BB+ outlook negative from Moody's
"""
