"""Fetch company financial metrics from SEC EDGAR and Yahoo Finance."""

import re
import requests
import time
from collections import Counter
from datetime import datetime, timedelta
from typing import Optional
from models import FinancialMetrics

# SEC EDGAR requires a User-Agent header with contact info
SEC_HEADERS = {
    "User-Agent": "CapitalRaiseDetector/1.0 (student@university.edu)",
    "Accept-Encoding": "gzip, deflate",
}

# Cache the ticker-to-CIK mapping so we only download it once
_TICKER_CIK_CACHE: Optional[dict] = None


def _get_ticker_cik_map() -> dict:
    """Download and cache the SEC ticker-to-CIK mapping (with exchange info)."""
    global _TICKER_CIK_CACHE
    if _TICKER_CIK_CACHE is not None:
        return _TICKER_CIK_CACHE

    url = "https://www.sec.gov/files/company_tickers_exchange.json"
    resp = requests.get(url, headers=SEC_HEADERS)
    resp.raise_for_status()
    data = resp.json()

    # Fields: [cik, name, ticker, exchange]
    fields = data.get("fields", [])
    rows = data.get("data", [])

    # Build ticker -> {cik, name, exchange} mapping
    mapping = {}
    for row in rows:
        cik = row[0]
        name = row[1]
        ticker = str(row[2]).upper()
        exchange = row[3] if len(row) > 3 else ""
        mapping[ticker] = {
            "cik": cik,
            "name": name,
            "exchange": exchange or "",
        }

    _TICKER_CIK_CACHE = mapping
    return mapping


def ticker_to_cik(ticker: str) -> tuple[int, str]:
    """
    Look up CIK number and company name from ticker symbol.

    Returns:
        (cik_number, company_name)

    Raises:
        ValueError if ticker not found
    """
    mapping = _get_ticker_cik_map()
    ticker = ticker.upper().strip()
    if ticker not in mapping:
        raise ValueError(
            f"Ticker '{ticker}' not found in SEC EDGAR. "
            f"Make sure it's a valid US public company ticker."
        )
    entry = mapping[ticker]
    return entry["cik"], entry["name"]


def fetch_company_facts(cik: int) -> dict:
    """
    Fetch all XBRL facts for a company from SEC EDGAR.

    Args:
        cik: SEC Central Index Key

    Returns:
        Raw JSON dict of all company facts
    """
    cik_padded = str(cik).zfill(10)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json"
    resp = requests.get(url, headers=SEC_HEADERS)
    resp.raise_for_status()
    return resp.json()


def _extract_latest_value(facts: dict, tag: str, prefer_10k: bool = False) -> Optional[float]:
    """
    Extract the most recent value for an XBRL tag from company facts.

    Args:
        facts: Raw company facts JSON
        tag: US-GAAP XBRL tag name
        prefer_10k: If True, prefer annual (10-K) filings over quarterly

    Returns:
        Most recent value, or None if not found
    """
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    tag_data = us_gaap.get(tag, {})
    units = tag_data.get("units", {})

    # Most financial values are in USD
    values = units.get("USD", [])
    if not values:
        # Some values might be in USD/shares or pure numbers
        values = units.get("USD/shares", [])
    if not values:
        values = units.get("pure", [])
    if not values:
        return None

    # Filter by form type if preferred
    if prefer_10k:
        annual = [v for v in values if v.get("form") in ("10-K", "10-K/A")]
        if annual:
            values = annual

    # Sort by end date descending to get most recent
    values_sorted = sorted(values, key=lambda v: v.get("end", ""), reverse=True)

    if values_sorted:
        return float(values_sorted[0]["val"])
    return None


def _extract_prior_year_value(facts: dict, tag: str) -> Optional[float]:
    """
    Extract the value from the prior year's annual filing.

    Returns the second most recent 10-K value.
    """
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    tag_data = us_gaap.get(tag, {})
    units = tag_data.get("units", {})

    values = units.get("USD", [])
    if not values:
        values = units.get("pure", [])
    if not values:
        return None

    # Get 10-K filings only
    annual = [v for v in values if v.get("form") in ("10-K", "10-K/A")]
    # Sort by end date descending
    annual_sorted = sorted(annual, key=lambda v: v.get("end", ""), reverse=True)

    # Return the second most recent (prior year)
    if len(annual_sorted) >= 2:
        return float(annual_sorted[1]["val"])
    return None


def fetch_stock_data(ticker: str) -> dict:
    """
    Fetch current stock price and 52-week high from Yahoo Finance.

    Returns:
        Dict with 'price' and 'fifty_two_week_high'
    """
    import yfinance as yf

    stock = yf.Ticker(ticker)
    info = stock.info

    return {
        "price": info.get("currentPrice") or info.get("regularMarketPrice", 0.0),
        "fifty_two_week_high": info.get("fiftyTwoWeekHigh", 0.0),
    }


# ── Credit-rating regex helpers ──────────────────────────────────────────────

# Matches a rating mentioned in context: "rated BBB+", "rating of A-", etc.
_RATING_CONTEXT_RE = re.compile(
    r'(?:rated?|rating(?:\s+of)?|assigned(?:\s+a)?\s+rating(?:\s+of)?)\s*'
    r'["\u2019\u201c\u201d]?\s*'
    r'(AAA|AA[+\-]?|A[+\-]?|BBB[+\-]?|BB[+\-]?|B[+\-]?|CCC[+\-]?|CC|C|D)'
    r'(?=[^A-Za-z])',
    re.IGNORECASE,
)

# Bare unambiguous S&P-style tokens (avoids single-letter false positives)
_RATING_BARE_RE = re.compile(
    r'\b(AAA|AA[+\-]|AA|A[+\-]|BBB[+\-]|BBB|BB[+\-]|BB|B[+\-]|CCC[+\-]|CCC|CC)\b'
)

# Outlook in context: "outlook is stable", "negative outlook", etc.
_OUTLOOK_RE = re.compile(
    r'(?:(?:credit\s+)?outlook(?:\s+is)?[^.]{0,30}?)(stable|negative|positive|developing)'
    r'|\b(stable|negative|positive)\s+(?:credit\s+)?outlook\b',
    re.IGNORECASE,
)


def _strip_html(text: str) -> str:
    """Remove HTML tags and decode common entities."""
    text = re.sub(r'<[^>]+>', ' ', text)
    return (
        text.replace('&amp;', '&')
            .replace('&lt;', '<')
            .replace('&gt;', '>')
            .replace('&nbsp;', ' ')
    )


def _parse_credit_info(text: str) -> tuple[Optional[str], Optional[str]]:
    """Extract (credit_rating, outlook) from raw text or HTML."""
    clean = _strip_html(text)

    # Contextual match is most reliable
    cr_match = _RATING_CONTEXT_RE.search(clean)
    if cr_match:
        credit_rating = cr_match.group(1).upper()
    else:
        bare_matches = _RATING_BARE_RE.findall(clean)
        credit_rating = Counter(bare_matches).most_common(1)[0][0].upper() if bare_matches else None

    credit_rating_outlook = None
    for m in _OUTLOOK_RE.finditer(clean):
        word = (m.group(1) or m.group(2) or "").lower()
        if word in ("stable", "negative", "positive", "developing"):
            credit_rating_outlook = word
            break

    return credit_rating, credit_rating_outlook


def _fetch_recent_10k_text(cik: int) -> Optional[str]:
    """
    Fetch the first 400 KB of the most recent 10-K filing text for a company.
    Returns raw HTML/text or None on failure.
    """
    cik_padded = str(cik).zfill(10)
    sub_url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
    try:
        resp = requests.get(sub_url, headers=SEC_HEADERS, timeout=15)
        resp.raise_for_status()
        sub_data = resp.json()
    except Exception:
        return None

    recent = sub_data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])

    for i, form in enumerate(forms):
        if form in ("10-K", "10-K/A"):
            acc_no = accessions[i].replace("-", "")
            doc_url = (
                f"https://www.sec.gov/Archives/edgar/data/{cik}"
                f"/{acc_no}/{primary_docs[i]}"
            )
            try:
                time.sleep(0.15)
                doc_resp = requests.get(doc_url, headers=SEC_HEADERS, timeout=30, stream=True)
                if doc_resp.status_code != 200:
                    return None
                chunks = []
                total = 0
                for chunk in doc_resp.iter_content(chunk_size=16_384):
                    chunks.append(chunk)
                    total += len(chunk)
                    if total >= 400_000:
                        break
                return b"".join(chunks).decode("utf-8", errors="ignore")
            except Exception:
                return None

    return None


def fetch_credit_rating(ticker: str, cik: int) -> tuple[Optional[str], Optional[str]]:
    """
    Fetch credit rating and outlook from SEC EDGAR.

    Strategy:
    1. Query EDGAR full-text search (EFTS) for credit-rating mentions in recent
       10-K filings. If highlighted snippets are returned, parse them directly.
    2. Fall back to fetching the first 400 KB of the most recent 10-K document.

    Returns:
        (credit_rating, credit_rating_outlook) — either value may be None if
        the company has no rated debt or the information is unavailable.
    """
    # ── Step 1: EDGAR EFTS full-text search ──────────────────────────────────
    two_years_ago = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")
    try:
        resp = requests.get(
            "https://efts.sec.gov/LATEST/search-index",
            params={
                "q": '"credit rating"',
                "forms": "10-K",
                "dateRange": "custom",
                "startdt": two_years_ago,
                "entity": ticker,
            },
            headers=SEC_HEADERS,
            timeout=15,
        )
        if resp.status_code == 200:
            hits = resp.json().get("hits", {}).get("hits", [])
            snippets: list[str] = []
            for hit in hits[:5]:
                for field_snippets in hit.get("highlight", {}).values():
                    if isinstance(field_snippets, list):
                        snippets.extend(field_snippets)
            if snippets:
                rating, outlook = _parse_credit_info(" ".join(snippets))
                if rating:
                    return rating, outlook
    except Exception:
        pass

    # ── Step 2: Fetch 10-K document directly ─────────────────────────────────
    text = _fetch_recent_10k_text(cik)
    if text:
        return _parse_credit_info(text)

    return None, None


def fetch_insider_activity(cik: int, lookback_days: int = 180) -> str:
    """
    Classify insider selling activity from SEC Form 4 filings.

    Fetches all Form 4s filed in the past `lookback_days` days and counts
    open-market sale transactions (transaction code 'S'). Classifies as:
      - "high"     : 5+ sale transactions
      - "elevated" : 2-4 sale transactions
      - "normal"   : 0-1 sale transactions

    Args:
        cik: SEC Central Index Key
        lookback_days: How far back to look for Form 4 filings

    Returns:
        "high" | "elevated" | "normal"
    """
    cik_padded = str(cik).zfill(10)
    since = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

    try:
        # Fetch submission history to find recent Form 4 filings
        sub_url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
        resp = requests.get(sub_url, headers=SEC_HEADERS, timeout=15)
        resp.raise_for_status()
        sub_data = resp.json()
    except Exception:
        return "normal"

    recent = sub_data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    filed_dates = recent.get("filingDate", [])
    primary_docs = recent.get("primaryDocument", [])

    # Collect Form 4 accession numbers filed within lookback window
    form4_filings = []
    for i, form in enumerate(forms):
        if form == "4" and filed_dates[i] >= since:
            form4_filings.append((accessions[i], primary_docs[i]))
        if len(form4_filings) >= 20:  # Cap at 20 to limit API calls
            break

    if not form4_filings:
        return "normal"

    sale_count = 0
    for acc_no, primary_doc in form4_filings:
        try:
            acc_clean = acc_no.replace("-", "")
            doc_url = (
                f"https://www.sec.gov/Archives/edgar/data/{cik}"
                f"/{acc_clean}/{primary_doc}"
            )
            time.sleep(0.12)
            doc_resp = requests.get(doc_url, headers=SEC_HEADERS, timeout=15)
            if doc_resp.status_code != 200:
                continue

            text = doc_resp.text

            # Form 4 XML: transactionCode 'S' = open-market sale
            # Also catch HTML-rendered Form 4s
            sales_in_filing = len(re.findall(
                r'<transactionCode>\s*S\s*</transactionCode>'
                r'|transactionCode[^>]*>\s*S\s*<',
                text,
                re.IGNORECASE,
            ))
            # Fallback: plain-text / HTML table rendering
            if sales_in_filing == 0:
                sales_in_filing = len(re.findall(
                    r'(?:^|\b)S(?:\s+|\t+)(?:\d|open\s+market)',
                    text,
                    re.IGNORECASE | re.MULTILINE,
                ))
            sale_count += min(sales_in_filing, 3)  # Cap contribution per filing
        except Exception:
            continue

    if sale_count >= 5:
        return "high"
    elif sale_count >= 2:
        return "elevated"
    else:
        return "normal"


# Going concern keyword patterns from auditing standards (AS 2415 / AU-C 570)
_GOING_CONCERN_PATTERNS = [
    r'substantial\s+doubt\s+about\s+(?:the\s+)?(?:company\'?s?\s+)?ability\s+to\s+continue',
    r'going[\s\-]concern',
    r'ability\s+to\s+continue\s+as\s+a\s+going\s+concern',
    r'raise[sd]?\s+substantial\s+doubt',
    r'conditions?\s+(?:and\s+events?\s+)?that\s+raise\s+substantial\s+doubt',
    r'recoverability\s+of\s+(?:the\s+)?assets?\s+(?:is|are|may\s+be)\s+uncertain',
]

_GOING_CONCERN_RE = re.compile(
    "|".join(_GOING_CONCERN_PATTERNS),
    re.IGNORECASE,
)


def fetch_going_concern(cik: int) -> bool:
    """
    Detect auditor going concern warnings from the most recent 10-K filing.

    Searches the first 400 KB of the 10-K for language consistent with a
    going concern qualification per AS 2415 / AU-C 570 auditing standards.

    Args:
        cik: SEC Central Index Key

    Returns:
        True if a going concern warning is detected, False otherwise
    """
    text = _fetch_recent_10k_text(cik)
    if not text:
        return False
    clean = _strip_html(text)
    return bool(_GOING_CONCERN_RE.search(clean))


def fetch_metrics(ticker: str) -> FinancialMetrics:
    """
    Fetch all financial metrics for a company from SEC EDGAR and Yahoo Finance.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")

    Returns:
        Populated FinancialMetrics object
    """
    print(f"Looking up {ticker}...")
    cik, company_name = ticker_to_cik(ticker)
    print(f"  Found: {company_name} (CIK: {cik})")

    print(f"  Fetching SEC filings...")
    facts = fetch_company_facts(cik)
    time.sleep(0.15)  # Respect rate limits

    # Extract financial data from XBRL tags
    # Try multiple tag variants since companies use different ones
    cash = (
        _extract_latest_value(facts, "CashAndCashEquivalentsAtCarryingValue")
        or _extract_latest_value(facts, "CashCashEquivalentsAndShortTermInvestments")
        or _extract_latest_value(facts, "Cash")
        or 0.0
    )

    current_assets = _extract_latest_value(facts, "AssetsCurrent") or 0.0
    current_liabilities = _extract_latest_value(facts, "LiabilitiesCurrent") or 0.0

    inventory = _extract_latest_value(facts, "InventoryNet") or 0.0
    quick_assets = current_assets - inventory

    accounts_payable = _extract_latest_value(facts, "AccountsPayableCurrent") or 0.0

    # Debt
    long_term_debt = _extract_latest_value(facts, "LongTermDebt") or 0.0
    short_term_debt = (
        _extract_latest_value(facts, "ShortTermBorrowings")
        or _extract_latest_value(facts, "DebtCurrent")
        or 0.0
    )
    total_debt = long_term_debt + short_term_debt

    debt_due_12mo = (
        _extract_latest_value(facts, "LongTermDebtCurrent")
        or _extract_latest_value(facts, "CurrentPortionOfLongTermDebt")
        or short_term_debt
    )

    # Approximate debt_due_6_18mo — try XBRL tag first, fall back to estimation
    debt_due_6_18mo = (
        _extract_latest_value(facts, "LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo")
        or (max(0.0, total_debt - long_term_debt - debt_due_12mo) if total_debt > 0 else 0.0)
    )

    # Revenue
    revenue = (
        _extract_latest_value(facts, "Revenues")
        or _extract_latest_value(facts, "RevenueFromContractWithCustomerExcludingAssessedTax")
        or _extract_latest_value(facts, "SalesRevenueNet")
        or 0.0
    )

    revenue_prior = (
        _extract_prior_year_value(facts, "Revenues")
        or _extract_prior_year_value(facts, "RevenueFromContractWithCustomerExcludingAssessedTax")
        or _extract_prior_year_value(facts, "SalesRevenueNet")
        or revenue  # Fallback to current if no prior data
    )

    # Operating cash flow
    ocf = (
        _extract_latest_value(facts, "NetCashProvidedByUsedInOperatingActivities")
        or 0.0
    )

    # Gross profit and margin
    gross_profit = _extract_latest_value(facts, "GrossProfit") or 0.0
    gross_margin = (gross_profit / revenue) if revenue > 0 else 0.0

    prior_gross_profit = _extract_prior_year_value(facts, "GrossProfit") or 0.0
    prior_gross_margin = (prior_gross_profit / revenue_prior) if revenue_prior > 0 else gross_margin

    # Capex
    capex = (
        _extract_latest_value(facts, "PaymentsToAcquirePropertyPlantAndEquipment")
        or 0.0
    )

    # Monthly burn rate (derived from OCF)
    monthly_burn_rate = max(0.0, -ocf / 12) if ocf < 0 else 0.0

    # Credit rating from SEC EDGAR filings
    print(f"  Fetching credit rating...")
    try:
        credit_rating, credit_rating_outlook = fetch_credit_rating(ticker, cik)
    except Exception:
        credit_rating, credit_rating_outlook = None, None

    # Insider selling activity from Form 4 filings
    print(f"  Fetching insider activity (Form 4)...")
    try:
        insider_selling_activity = fetch_insider_activity(cik)
    except Exception:
        insider_selling_activity = "normal"

    # Going concern warning from 10-K auditor's report
    print(f"  Checking for going concern warnings...")
    try:
        auditor_going_concern = fetch_going_concern(cik)
    except Exception:
        auditor_going_concern = False

    # Stock data from Yahoo Finance
    print(f"  Fetching stock data...")
    try:
        stock_data = fetch_stock_data(ticker)
        stock_price = stock_data["price"]
        stock_price_52w_high = stock_data["fifty_two_week_high"]
    except Exception as e:
        print(f"  Warning: Could not fetch stock data: {e}")
        stock_price = 0.0
        stock_price_52w_high = 0.0

    # Ensure no zeros that would cause division errors in scorer
    if current_liabilities == 0:
        current_liabilities = 1.0
    if revenue_prior == 0:
        revenue_prior = 1.0

    metrics = FinancialMetrics(
        ticker=ticker.upper(),
        company_name=company_name,
        cash_and_equivalents=cash,
        monthly_burn_rate=monthly_burn_rate,
        current_assets=current_assets,
        current_liabilities=current_liabilities,
        quick_assets=quick_assets,
        accounts_payable=accounts_payable,
        total_debt=total_debt,
        debt_due_12mo=debt_due_12mo,
        debt_due_6_18mo=debt_due_6_18mo,
        revenue_trailing_12m=revenue,
        revenue_prior_year=revenue_prior,
        operating_cash_flow_trailing_12m=ocf,
        gross_margin=gross_margin,
        prior_gross_margin=prior_gross_margin,
        capex_annual=capex,
        stock_price=stock_price,
        stock_price_52w_high=stock_price_52w_high,
        insider_selling_activity=insider_selling_activity,
        auditor_going_concern=auditor_going_concern,
        credit_rating=credit_rating,
        credit_rating_outlook=credit_rating_outlook,
    )

    print(f"  Done! Metrics loaded for {company_name}")
    return metrics
