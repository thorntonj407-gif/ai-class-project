"""Bulk market screener using SEC EDGAR XBRL Frames API."""

import requests
import time
from datetime import datetime
from typing import Optional
from models import FinancialMetrics
from scorer import CapitalRaiseScorer
from sec_fetcher import _get_ticker_cik_map, SEC_HEADERS

# XBRL tags to fetch for screening
FRAME_TAGS = {
    "cash": "CashAndCashEquivalentsAtCarryingValue",
    "current_assets": "AssetsCurrent",
    "current_liabilities": "LiabilitiesCurrent",
    "inventory": "InventoryNet",
    "accounts_payable": "AccountsPayableCurrent",
    "long_term_debt": "LongTermDebt",
    "debt_current": "LongTermDebtCurrent",
    "revenue": "Revenues",
    "ocf": "NetCashProvidedByUsedInOperatingActivities",
    "gross_profit": "GrossProfit",
    "capex": "PaymentsToAcquirePropertyPlantAndEquipment",
}


def fetch_frame(tag: str, year: int, quarter: Optional[int] = None, instant: bool = False) -> dict:
    """
    Fetch one XBRL metric for ALL companies from the Frames API.

    Args:
        tag: US-GAAP XBRL tag
        year: Calendar year (e.g., 2024)
        quarter: Quarter number (1-4), or None for annual
        instant: If True, fetch instantaneous (balance sheet) data

    Returns:
        Dict mapping CIK -> value
    """
    if quarter:
        period = f"CY{year}Q{quarter}I" if instant else f"CY{year}Q{quarter}"
    else:
        period = f"CY{year}" if not instant else f"CY{year}I"

    url = f"https://data.sec.gov/api/xbrl/frames/us-gaap/{tag}/USD/{period}.json"
    resp = requests.get(url, headers=SEC_HEADERS)

    if resp.status_code != 200:
        return {}

    data = resp.json()
    result = {}
    for entry in data.get("data", []):
        cik = entry.get("cik")
        val = entry.get("val")
        if cik and val is not None:
            result[cik] = float(val)

    return result


def _merge_frames(*frame_dicts: dict) -> dict:
    """Merge multiple frame dicts, keeping the first non-zero value per CIK."""
    merged = {}
    for fd in frame_dicts:
        for cik, val in fd.items():
            if cik not in merged or merged[cik] == 0:
                merged[cik] = val
    return merged


def _fetch_all_frames(year: int) -> dict:
    """
    Fetch all needed XBRL frames across ALL quarters for maximum coverage.
    Companies with non-calendar fiscal years report in different quarters,
    so we merge Q1-Q4 to catch as many as possible.

    Returns:
        Dict of {tag_name: {cik: value}}
    """
    frames = {}
    step = [0]
    quarters = [1, 2, 3, 4]

    def _fetch(tag, yr, qtr, instant):
        step[0] += 1
        result = fetch_frame(tag, yr, qtr, instant=instant)
        time.sleep(0.12)
        return result

    # Balance sheet items (instantaneous) — merge all 4 quarters
    print(f"  Fetching balance sheet data (Q1-Q4)...")
    cash_frames = []
    ca_frames = []
    cl_frames = []
    inv_frames = []
    ap_frames = []
    ltd_frames = []
    dc_frames = []
    for q in quarters:
        cash_frames.append(_fetch("CashAndCashEquivalentsAtCarryingValue", year, q, True))
        cash_frames.append(_fetch("CashCashEquivalentsAndShortTermInvestments", year, q, True))
        ca_frames.append(_fetch("AssetsCurrent", year, q, True))
        cl_frames.append(_fetch("LiabilitiesCurrent", year, q, True))
        inv_frames.append(_fetch("InventoryNet", year, q, True))
        ap_frames.append(_fetch("AccountsPayableCurrent", year, q, True))
        ltd_frames.append(_fetch("LongTermDebt", year, q, True))
        dc_frames.append(_fetch("LongTermDebtCurrent", year, q, True))
        print(f"    Q{q} balance sheet done ({step[0]} calls)")

    frames["cash"] = _merge_frames(*cash_frames)
    frames["current_assets"] = _merge_frames(*ca_frames)
    frames["current_liabilities"] = _merge_frames(*cl_frames)
    frames["inventory"] = _merge_frames(*inv_frames)
    frames["accounts_payable"] = _merge_frames(*ap_frames)
    frames["long_term_debt"] = _merge_frames(*ltd_frames)
    frames["debt_current"] = _merge_frames(*dc_frames)

    # Revenue — merge both tags across all quarters
    print(f"  Fetching revenue data (Q1-Q4)...")
    rev_frames = []
    for q in quarters:
        rev_frames.append(_fetch("Revenues", year, q, False))
        rev_frames.append(_fetch("RevenueFromContractWithCustomerExcludingAssessedTax", year, q, False))
    frames["revenue"] = _merge_frames(*rev_frames)

    # OCF — try all quarters plus annual
    print(f"  Fetching cash flow data...")
    ocf_frames = [_fetch("NetCashProvidedByUsedInOperatingActivities", year, q, False) for q in quarters]
    ocf_frames.append(_fetch("NetCashProvidedByUsedInOperatingActivities", year, None, False))
    frames["ocf"] = _merge_frames(*ocf_frames)

    # Gross profit and capex — merge across quarters
    print(f"  Fetching profitability data...")
    gp_frames = [_fetch("GrossProfit", year, q, False) for q in quarters]
    frames["gross_profit"] = _merge_frames(*gp_frames)

    capex_frames = [_fetch("PaymentsToAcquirePropertyPlantAndEquipment", year, q, False) for q in quarters]
    frames["capex"] = _merge_frames(*capex_frames)

    print(f"  Total API calls: {step[0]}")
    return frames


def _fetch_prior_year_frames(year: int) -> dict:
    """Fetch prior year revenue and gross profit across all quarters."""
    prior_year = year - 1
    frames = {}
    quarters = [1, 2, 3, 4]

    print(f"  Fetching prior year revenue (Q1-Q4)...")
    rev_frames = []
    for q in quarters:
        rev_frames.append(fetch_frame("Revenues", prior_year, q, instant=False))
        rev_frames.append(fetch_frame("RevenueFromContractWithCustomerExcludingAssessedTax", prior_year, q, instant=False))
        time.sleep(0.12)
    frames["revenue_prior"] = _merge_frames(*rev_frames)

    print(f"  Fetching prior year gross profit (Q1-Q4)...")
    gp_frames = []
    for q in quarters:
        gp_frames.append(fetch_frame("GrossProfit", prior_year, q, instant=False))
        time.sleep(0.12)
    frames["gross_profit_prior"] = _merge_frames(*gp_frames)

    return frames


def screen_all_companies(
    year: Optional[int] = None,
    exchanges: Optional[list[str]] = None,
    min_market_cap: float = 0,
) -> list:
    """
    Screen US public companies for capital raise risk.

    Args:
        year: Calendar year to analyze (default: most recent full year).
              Data is fetched across all 4 quarters for maximum coverage.
        exchanges: Filter to these exchanges (e.g., ["NYSE", "Nasdaq"]).
                   Default: NYSE and Nasdaq only.
        min_market_cap: Minimum market cap in USD (default: 0, no filter).
                        Applied after scoring to minimize API calls.

    Returns:
        List of (ticker, company_name, CapitalRaisePrediction) tuples,
        sorted by likelihood score descending, filtered to high-risk only
    """
    if exchanges is None:
        exchanges = ["NYSE", "Nasdaq"]

    now = datetime.now()
    if year is None:
        year = now.year - 1

    exchange_label = "/".join(exchanges) if exchanges else "all exchanges"
    print(f"Screening {exchange_label} companies (CY{year} Q1-Q4)...")
    if min_market_cap > 0:
        print(f"  Minimum market cap: ${min_market_cap/1e6:.0f}M")
    print(f"Step 1: Fetching financial data from SEC EDGAR...")

    # Fetch all frames across all 4 quarters
    frames = _fetch_all_frames(year)

    # Fetch prior year for comparison
    prior_frames = _fetch_prior_year_frames(year)

    # Build ticker-CIK mapping filtered by exchange
    print(f"Step 2: Building company list...")
    ticker_map = _get_ticker_cik_map()
    # Normalize exchange filter to lowercase for comparison
    exchange_filter = [e.lower() for e in exchanges] if exchanges else []

    cik_to_ticker = {}
    for ticker, info in ticker_map.items():
        if exchange_filter:
            company_exchange = info.get("exchange", "").lower()
            if company_exchange not in exchange_filter:
                continue
        cik_to_ticker[info["cik"]] = {"ticker": ticker, "name": info["name"]}

    print(f"  {len(cik_to_ticker)} companies on {exchange_label}")

    # Find CIKs on the right exchange with at least cash OR revenue data
    ciks_with_any_data = (set(frames.get("cash", {}).keys()) | set(frames.get("revenue", {}).keys())) & set(cik_to_ticker.keys())
    # Prefer companies that have cash data (needed for cash runway scoring)
    ciks_with_data = ciks_with_any_data
    print(f"  {len(ciks_with_data)} with financial data")

    # Score each company
    print(f"Step 3: Scoring companies...")
    scorer = CapitalRaiseScorer()
    results = []
    errors = 0

    for cik in ciks_with_data:
        company_info = cik_to_ticker.get(cik)
        if not company_info:
            continue

        try:
            cash = frames.get("cash", {}).get(cik, 0.0)
            current_assets = frames.get("current_assets", {}).get(cik, 0.0)
            current_liabilities = frames.get("current_liabilities", {}).get(cik, 0.0) or 1.0
            inventory = frames.get("inventory", {}).get(cik, 0.0)
            accounts_payable = frames.get("accounts_payable", {}).get(cik, 0.0)
            long_term_debt = frames.get("long_term_debt", {}).get(cik, 0.0)
            debt_current = frames.get("debt_current", {}).get(cik, 0.0)
            revenue = frames.get("revenue", {}).get(cik, 0.0)
            ocf = frames.get("ocf", {}).get(cik, 0.0)
            gross_profit = frames.get("gross_profit", {}).get(cik, 0.0)
            capex = frames.get("capex", {}).get(cik, 0.0)

            revenue_prior = prior_frames.get("revenue_prior", {}).get(cik, revenue) or revenue or 1.0
            gross_profit_prior = prior_frames.get("gross_profit_prior", {}).get(cik, 0.0)

            total_debt = long_term_debt + debt_current
            monthly_burn = max(0.0, -ocf / 12) if ocf < 0 else 0.0
            gross_margin = (gross_profit / revenue) if revenue > 0 else 0.0
            prior_gross_margin = (gross_profit_prior / revenue_prior) if revenue_prior > 0 else gross_margin

            metrics = FinancialMetrics(
                ticker=company_info["ticker"],
                company_name=company_info["name"],
                cash_and_equivalents=cash,
                monthly_burn_rate=monthly_burn,
                current_assets=current_assets,
                current_liabilities=current_liabilities,
                quick_assets=current_assets - inventory,
                accounts_payable=accounts_payable,
                total_debt=total_debt,
                debt_due_12mo=debt_current,
                debt_due_6_18mo=max(0.0, total_debt - long_term_debt - debt_current),
                revenue_trailing_12m=revenue,
                revenue_prior_year=revenue_prior,
                operating_cash_flow_trailing_12m=ocf,
                gross_margin=gross_margin,
                prior_gross_margin=prior_gross_margin,
                capex_annual=capex,
                stock_price=0.0,  # Skip stock data for bulk screening
                stock_price_52w_high=0.0,
                insider_selling_activity="normal",
                auditor_going_concern=False,
                credit_rating=None,
                credit_rating_outlook=None,
            )

            prediction = scorer.score(metrics)
            if prediction.above_threshold:
                results.append((
                    company_info["ticker"],
                    company_info["name"],
                    prediction,
                ))

        except Exception:
            errors += 1
            continue

    # Sort by score descending
    results.sort(key=lambda x: x[2].likelihood_score, reverse=True)

    # Apply market cap filter using yfinance (only on high-risk results)
    if min_market_cap > 0 and results:
        print(f"Step 4: Filtering by market cap (checking {len(results)} companies)...")
        import yfinance as yf

        filtered = []
        for ticker, name, pred in results:
            try:
                info = yf.Ticker(ticker).info
                mcap = info.get("marketCap", 0) or 0
                if mcap >= min_market_cap:
                    filtered.append((ticker, name, pred))
            except Exception:
                continue
            time.sleep(0.05)

        print(f"  {len(filtered)} companies above ${min_market_cap/1e6:.0f}M market cap")
        results = filtered

    print(f"\nDone! Screened {len(ciks_with_data)} companies.")
    print(f"  High-risk companies found: {len(results)}")
    if errors > 0:
        print(f"  Skipped {errors} companies due to data issues")

    return results
