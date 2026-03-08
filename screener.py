"""Bulk market screener using SEC EDGAR XBRL Frames API."""

import requests
import time
from datetime import datetime
from typing import List, Optional
from models import FinancialMetrics
from scorer import CapitalRaiseScorer
from sec_fetcher import _get_ticker_cik_map, SEC_HEADERS

# SIC code to GICS sector mapping (2-digit division)
# GICS Sectors: Energy, Materials, Industrials, Consumer Discretionary, Consumer Staples,
# Health Care, Financials, Information Technology, Communication Services, Utilities, Real Estate
_SIC_TO_SECTOR = {
    # 01-09: Agriculture, forestry, fishing
    "01": "Materials", "02": "Materials", "07": "Materials", "08": "Materials", "09": "Materials",
    # 10-14: Mining
    "10": "Energy", "11": "Energy", "12": "Energy", "13": "Energy", "14": "Energy",
    # 15-17: Construction
    "15": "Industrials", "16": "Industrials", "17": "Industrials",
    # 20-39: Manufacturing
    "20": "Materials", "21": "Materials", "22": "Materials", "23": "Materials", "24": "Materials",
    "25": "Materials", "26": "Materials", "27": "Materials", "28": "Materials", "29": "Energy",
    "30": "Materials", "31": "Materials", "32": "Materials", "33": "Materials", "34": "Industrials",
    "35": "Information Technology",  # Industrial machinery, computers, electronics
    "36": "Information Technology",  # Electronic/electrical equipment
    "37": "Industrials",  # Transportation equipment
    "38": "Industrials",  # Instruments
    "39": "Industrials",  # Misc manufacturing
    # 40-49: Transportation, utilities, waste
    "40": "Industrials", "41": "Industrials", "42": "Industrials", "43": "Industrials",
    "44": "Utilities", "45": "Industrials", "46": "Industrials", "47": "Industrials", "48": "Utilities", "49": "Utilities",
    # 50-59: Wholesale & retail trade
    "50": "Consumer Discretionary", "51": "Consumer Discretionary", "52": "Consumer Discretionary", "53": "Consumer Discretionary", "54": "Consumer Discretionary",
    "55": "Consumer Discretionary", "56": "Consumer Discretionary", "57": "Consumer Discretionary", "58": "Consumer Discretionary", "59": "Consumer Discretionary",
    # 60-69: Finance, insurance, real estate
    "60": "Financials", "61": "Financials", "62": "Financials", "63": "Financials", "64": "Financials", "65": "Financials",
    "66": "Financials", "67": "Real Estate", "68": "Real Estate", "69": "Financials",
    # 70-89: Services
    "70": "Information Technology",  # Business/computer services
    "71": "Consumer Discretionary",  # Hotels, entertainment, recreation
    "72": "Consumer Discretionary",  # Personal services
    "73": "Information Technology",  # Business/computer services
    "74": "Information Technology",  # Data processing, software
    "75": "Industrials", "76": "Consumer Discretionary", "77": "Consumer Discretionary", "78": "Consumer Discretionary", "79": "Consumer Discretionary",
    "80": "Health Care", "81": "Health Care", "82": "Health Care", "83": "Health Care",
    "84": "Consumer Staples", "85": "Information Technology", "86": "Financials", "87": "Information Technology", "88": "Information Technology", "89": "Information Technology",
    # 90-99: Government
    "91": "Consumer Staples", "92": "Consumer Staples", "93": "Consumer Staples", "94": "Consumer Staples",
    "95": "Consumer Staples", "96": "Consumer Staples", "97": "Consumer Staples", "98": "Consumer Staples", "99": "Consumer Staples",
}

_SECTOR_CACHE = {}
_SIC_CACHE = {}


def _fetch_sic_for_cik(cik: int) -> Optional[str]:
    """
    Fetch SIC code from SEC EDGAR CIK lookup page.

    Args:
        cik: Central Index Key number

    Returns:
        SIC code (4 digits), or None if not available
    """
    if cik in _SIC_CACHE:
        return _SIC_CACHE[cik]

    try:
        import re
        # Fetch the company's EDGAR CIK page which shows SIC code
        cik_str = str(cik).zfill(10)
        url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik_str}&type=&dateb=&owner=exclude&count=40"

        resp = requests.get(url, headers=SEC_HEADERS, timeout=5)

        if resp.status_code == 200:
            # Look for "SIC=" in the HTML
            match = re.search(r'SIC=(\d{4})', resp.text)
            if match:
                sic = match.group(1)
                _SIC_CACHE[cik] = sic
                return sic
    except Exception:
        pass

    _SIC_CACHE[cik] = None
    return None


def _get_sector_from_sic(sic_code: Optional[str]) -> str:
    """Map SIC code to sector."""
    if not sic_code:
        return "Unknown"

    # Get first 2 digits
    code_prefix = sic_code[:2] if len(sic_code) >= 2 else sic_code
    return _SIC_TO_SECTOR.get(code_prefix, "Unknown")


def _fetch_sector_for_ticker(ticker: str, sic_code: Optional[str] = None) -> str:
    """
    Fetch sector using SIC code from SEC data or yfinance as fallback.

    Args:
        ticker: Stock ticker symbol
        sic_code: Optional SIC code from SEC EDGAR

    Returns:
        Sector name, or "Unknown" if unavailable
    """
    ticker_upper = ticker.upper()

    # Check cache first
    if ticker_upper in _SECTOR_CACHE:
        return _SECTOR_CACHE[ticker_upper]

    # Try SIC code mapping first (from SEC)
    if sic_code:
        sector = _get_sector_from_sic(sic_code)
        if sector != "Unknown":
            _SECTOR_CACHE[ticker_upper] = sector
            return sector

    # Try yfinance as fallback
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker_upper)
        sector = stock.info.get("sector", "Unknown")
        result = sector if sector and sector != "None" else "Unknown"
        _SECTOR_CACHE[ticker_upper] = result
        time.sleep(0.05)
        return result
    except Exception:
        pass

    # Final fallback
    _SECTOR_CACHE[ticker_upper] = "Unknown"
    return "Unknown"

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


def fetch_frame(
    tag: str,
    year: int,
    quarter: Optional[int] = None,
    instant: bool = False,
    taxonomy: str = "us-gaap",
) -> dict:
    """
    Fetch one XBRL metric for ALL companies from the Frames API.

    Args:
        tag: XBRL tag name
        year: Calendar year (e.g., 2024)
        quarter: Quarter number (1-4), or None for annual
        instant: If True, fetch instantaneous (balance sheet) data
        taxonomy: XBRL taxonomy namespace (default: "us-gaap"; use "dei" for
                  Document and Entity Information tags like EntityPublicFloat)

    Returns:
        Dict mapping CIK -> value
    """
    if quarter:
        period = f"CY{year}Q{quarter}I" if instant else f"CY{year}Q{quarter}"
    else:
        period = f"CY{year}" if not instant else f"CY{year}I"

    url = f"https://data.sec.gov/api/xbrl/frames/{taxonomy}/{tag}/USD/{period}.json"
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

    def _fetch(tag, yr, qtr, instant, taxonomy="us-gaap"):
        step[0] += 1
        result = fetch_frame(tag, yr, qtr, instant=instant, taxonomy=taxonomy)
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

    # EntityPublicFloat (DEI tag) — aggregate market value of shares held by
    # non-affiliates, reported on the 10-K cover page. Used as an EDGAR-native
    # market cap proxy so we don't rely on yfinance for size filtering.
    print(f"  Fetching public float data (Q1-Q4)...")
    pf_frames = [_fetch("EntityPublicFloat", year, q, True, taxonomy="dei") for q in quarters]
    frames["public_float"] = _merge_frames(*pf_frames)

    # Try to get the exact amount of long-term debt maturing in year 2 (i.e. the year after next)
    # from the company's SEC filing. If not available, fall back to estimating it from total debt.
    debt_6_18mo_frames = []
    for q in quarters:
        debt_6_18mo_frames.append(_fetch("LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo", year, q, True))
    frames["debt_due_6_18mo_xbrl"] = _merge_frames(*debt_6_18mo_frames)

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
    exchanges: Optional[List[str]] = None,
    min_market_cap: float = 1_000_000_000,
) -> list:
    """
    Screen US public companies for capital raise risk.

    Args:
        year: Calendar year to analyze (default: most recent full year).
              Data is fetched across all 4 quarters for maximum coverage.
        exchanges: Filter to these exchanges (e.g., ["NYSE", "Nasdaq"]).
                   Default: NYSE and Nasdaq only.
        min_market_cap: Minimum market cap in USD (default: $1B).
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

    # SPAC name patterns — SPACs almost always contain these phrases
    _SPAC_PATTERNS = (
        "acquisition corp",
        "acquisition co",
        "blank check",
        "special purpose acquisition",
    )

    cik_to_ticker = {}
    for ticker, info in ticker_map.items():
        if exchange_filter:
            company_exchange = info.get("exchange", "").lower()
            if company_exchange not in exchange_filter:
                continue
        name_lower = info["name"].lower()
        if any(p in name_lower for p in _SPAC_PATTERNS):
            continue
        cik = info["cik"]
        # Don't fetch SIC codes yet - only fetch for high-risk companies later
        cik_to_ticker[cik] = {"ticker": ticker, "name": info["name"], "cik": cik}

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
            debt_due_6_18mo_xbrl = frames.get("debt_due_6_18mo_xbrl", {}).get(cik, None)
            revenue = frames.get("revenue", {}).get(cik, 0.0)

            # Size pre-filter using EDGAR data only — no external API calls.
            # Primary: EntityPublicFloat (public float from 10-K cover page).
            # Fallback: revenue proxy when float data is unavailable.
            public_float = frames.get("public_float", {}).get(cik, 0.0)
            if public_float > 0:
                if public_float < min_market_cap:
                    continue  # EDGAR directly confirms company is too small
            else:
                # No float data filed — use stricter revenue floor as proxy
                if revenue < min_market_cap * 0.10:
                    continue
            ocf = frames.get("ocf", {}).get(cik, 0.0)
            gross_profit = frames.get("gross_profit", {}).get(cik, 0.0)
            capex = frames.get("capex", {}).get(cik, 0.0)

            revenue_prior = prior_frames.get("revenue_prior", {}).get(cik, revenue) or revenue or 1.0
            gross_profit_prior = prior_frames.get("gross_profit_prior", {}).get(cik, 0.0)

            total_debt = long_term_debt + debt_current
            monthly_burn = max(0.0, -ocf / 12) if ocf < 0 else 0.0
            gross_margin = (gross_profit / revenue) if revenue > 0 else 0.0
            prior_gross_margin = (gross_profit_prior / revenue_prior) if revenue_prior > 0 else gross_margin

            # Use public_float as market cap (EDGAR native, no external API calls)
            market_cap = public_float or (revenue * 1.5 if revenue > 0 else 0.0)  # fallback estimate

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
                # Try to get the exact amount of long-term debt maturing in year 2 (i.e. the year after next)
                # from the company's SEC filing. If not available, fall back to estimating it from total debt.
                debt_due_6_18mo=debt_due_6_18mo_xbrl or max(0.0, total_debt - long_term_debt - debt_current),
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
                sector="Unknown",  # Will be populated for high-risk results
                market_cap=market_cap,
            )

            prediction = scorer.score(metrics)
            if prediction.above_threshold:
                # Fetch sector for high-risk results (fetch SIC on-demand to speed up screening)
                sic = _fetch_sic_for_cik(company_info["cik"])
                sector = _fetch_sector_for_ticker(company_info["ticker"], sic)
                if sector != "Unknown":
                    print(f"    {company_info['ticker']}: {sector}")
                prediction.sector = sector
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

    print(f"\nDone! Screened {len(ciks_with_data)} companies.")
    print(f"  High-risk companies found: {len(results)}")
    if errors > 0:
        print(f"  Skipped {errors} companies due to data issues")

    return results


def format_results_table(results: List) -> str:
    """
    Format screening results as a table with sector and market cap columns.

    Args:
        results: List of (ticker, company_name, CapitalRaisePrediction) tuples

    Returns:
        Formatted table string
    """
    if not results:
        return "No high-risk companies found."

    # Header
    header = f"{'Ticker':<8} {'Company':<35} {'Sector':<20} {'Market Cap':<15} {'Score':<8} {'Risk':<10}"
    lines = [header, "-" * 96]

    for ticker, company_name, prediction in results:
        market_cap_str = (
            f"${prediction.market_cap/1e9:.1f}B"
            if prediction.market_cap > 0
            else "Unknown"
        )
        lines.append(
            f"{ticker:<8} {company_name:<35} {prediction.sector:<20} {market_cap_str:<15} "
            f"{prediction.likelihood_score:<8.1f} {prediction.risk_level.upper():<10}"
        )

    return "\n".join(lines)
