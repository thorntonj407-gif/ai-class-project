# Capital Raise Detector

Predict the likelihood of public companies performing primary equity raises (IPOs, secondary offerings, private fundraises) based on 5 key financial signals.

## Overview

The detector analyzes companies and assigns a **likelihood score (0-100)** that indicates how likely they are to pursue capital raise activity within the next 12 months.

### Scoring Model

Total Score = Sum of 5 Signals (max 100):

| Signal | Max Points | Description |
|--------|-----------|-------------|
| **Cash Runway** | 25 | Months of cash remaining at burn rate |
| **Liquidity Stress** | 10 | Current ratio, quick ratio, working capital |
| **Debt Maturity** | 25 | Near-term debt obligations & covenant risk |
| **Operational Red Flags** | 20 | Revenue trends, margins, operating cash flow |
| **Market & Behavioral** | 20 | Stock price, insider activity |

### Threshold

- **Score > 50**: Company flagged for monitoring (above threshold)
- **Score ≤ 50**: Below concern threshold

### Risk Levels

| Risk Level | Score Range | Interpretation |
|-----------|------------|-----------------|
| **Critical** | 75-100 | Immediate capital raise very likely |
| **High** | 60-74 | Strong likelihood in next 12 months |
| **Medium** | 40-59 | Moderate risk, monitor closely |
| **Low** | 0-39 | No immediate capital raise pressure |

## Signals Explained

### 1. Cash Runway (0-40 points)

**Measures**: How many months of cash the company has at current burn rate

**Calculation**: Cash & equivalents ÷ Monthly operating cash outflow

### 1. Cash Runway (0-25 points)
- < 6 months runway: 25 points
- 6-12 months: 15 points
- 12-18 months: 5 points
- > 18 months: 0 points

**Why it matters**: Companies with limited cash runway are forced to raise capital to survive.

### 2. Liquidity Stress (0-10 points)

**Measures**: Ability to meet short-term obligations

**Components**:
- **Current Ratio** (Current Assets ÷ Current Liabilities)
  - < 0.8: 10 points
  - 0.8-1.0: 7 points
  - 1.0-1.2: 3 points

- **Quick Ratio** (Quick Assets ÷ Current Liabilities)
  - < 0.5: 5 points
  - 0.5-0.75: 2 points

- **Working Capital** (Current Assets - Current Liabilities)
  - Negative: 5 points
  - < 25% of current liabilities: 2 points

**Why it matters**: Weak liquidity forces immediate capital needs.

### 3. Debt Maturity Profile (0-25 points)

**Measures**: Debt obligations due in 6-18 months

**Components**:
- **Near-term debt ratio** (Debt due in 12mo ÷ Cash)
  - > 50%: 10 points
  - 25-50%: 6 points
  - 10-25%: 2 points

- **Medium-term debt** (Debt due in 6-18mo > 30% of cash): 3 points

- **Credit rating outlook**
  - Negative: 3 points
  - Stable: 0 points
  - Positive: -1 points

**Why it matters**: Large debt maturities create refinancing pressure.

### 4. Operational Red Flags (0-20 points)

**Measures**: Business health and cash generation

**Components**:
- **Revenue trend** (YoY % change)
  - Decline > 10%: 10 points
  - Decline 5-10%: 5 points

- **Gross margin compression** (Margin decline YoY)
  - > 2%: 5 points
  - 1-2%: 2 points

- **Operating cash flow** (Trailing 12 months)
  - Negative: 10 points

- **Capex burden** (Capex > Free cash flow): 3 points

- **Going concern warning**: 10 points (critical red flag)

**Why it matters**: Deteriorating operations reduce internal cash generation and increase capital needs.

### 5. Market & Behavioral Signals (0-20 points)

**Measures**: Market perception and insider confidence

**Components**:
- **Stock price decline** (vs 52-week high)
  - Down > 30%: 5 points
  - Down 20-30%: 3 points
  - Down 10-20%: 1 point

- **Insider selling activity**
  - High: 5 points
  - Elevated: 3 points
  - Normal: 0 points

**Why it matters**: Weak stock price and insider selling reduce equity raise optionality and signal insider concern.

## Installation

### Prerequisites

- Python 3.10+
- OpenAI API key (for market signal analysis)

### Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment
export OPENAI_API_KEY="your-api-key-here"
```

## Usage

### Command Line

```bash
# Analyze a single example company
python main.py --ticker BURN

# Analyze all example companies
python main.py --use-examples

# Include LLM analysis of market signals (requires API key)
python main.py --ticker BURN --include-market-signals

# Show only companies above threshold
python main.py --use-examples --alerts-only

# Export results to JSON
python main.py --use-examples --output-json results.json

# Use a different LLM model
python main.py --ticker BURN --model gpt-4
```

### Python API

```python
from analyzer import CapitalRaiseAnalyzer
from models import FinancialMetrics

# Initialize analyzer
analyzer = CapitalRaiseAnalyzer(model_name="gpt-4o-mini")

# Create financial metrics
metrics = FinancialMetrics(
    ticker="DEMO",
    company_name="Demo Corp",
    cash_and_equivalents=100_000_000,
    monthly_burn_rate=5_000_000,
    # ... other fields
)

# Analyze
prediction = analyzer.analyze(metrics)
print(prediction.likelihood_score)
```

### Jupyter Notebook

```bash
jupyter notebook capital_raise_detector.ipynb
```

The notebook provides interactive analysis with visualization and custom company analysis.

## Example Companies

The system includes 5 example companies with different risk profiles:

1. **STRONG** - Healthy company with strong financials
2. **BURN** - Low cash runway, concerning burn rate
3. **STRESS** - Operational stress, liquidity issues, going concern warnings
4. **GROW** - High growth but negative FCF, needs capital
5. **STABLE** - Mature company with stable operations

## Advanced Usage

### Including Market Signals

Enhance scoring with LLM analysis of earnings calls and news:

```python
analyzer = CapitalRaiseAnalyzer()

prediction = analyzer.analyze(
    metrics,
    earnings_call_transcript="Q3 earnings call text...",
    market_news="Recent news about company..."
)
```

The LLM analyzes text for:
- Explicit capital raise mentions
- Strategic option language
- Financing discussions
- M&A activity
- Going concern warnings

### Batch Analysis

```python
from data import EXAMPLE_COMPANIES

predictions = analyzer.batch_analyze(EXAMPLE_COMPANIES)
alerts = analyzer.get_alerts(predictions)  # Above threshold only
```

## Data Sources

When connecting to real data, integrate with:

- **Financials**: SEC EDGAR (10-K, 10-Q), Bloomberg, FactSet
- **Debt schedules**: 10-K footnotes, bond databases (Bloomberg, Refinitiv)
- **Credit ratings**: Moody's, S&P, Fitch APIs
- **Earnings calls**: Seeking Alpha, company IR sites
- **Insider activity**: SEC Form 4 filings
- **Stock prices**: Yahoo Finance, Alpha Vantage, IEX Cloud

## Scoring Examples

### Example 1: BURN (Score: 67.0 - HIGH RISK)
```
Cash Runway: 25.0/25     (5.0 months runway)
Liquidity Stress: 0.0/10  (Current ratio 1.33, adequate)
Debt Maturity: 15.0/25   (Near-term debt obligations, negative outlook)
Operational: 11.0/20     (Negative OCF, capex exceeds FCF)
Market: 16.0/20          (Stock down 62%, elevated insider selling)
─────────────────────────
Total: 67.0/100 ⚠️  ABOVE THRESHOLD
```

### Example 2: STRONG (Score: 0.0 - LOW RISK)
```
Cash Runway: 0.0/25      (Strong cash generation)
Liquidity Stress: 0.0/10 (Excellent ratios)
Debt Maturity: 0.0/25    (Manageable debt schedule)
Operational: 0.0/20      (Strong revenue and margins)
Market: 0.0/20           (Stock near 52w high, normal insider activity)
─────────────────────────
Total: 0.0/100 ✓ Below threshold
```

## Implementation Approach

1. **Screen**: Filter universe by cash runway < 18 months
2. **Score**: Apply multi-factor risk model (5 signals)
3. **Validate**: Check recent 10-Q/10-K for covenant violations
4. **Monitor**: Track earnings calls for capital-related language
5. **Alert**: Flag when score crosses threshold or signals emerge

## Technical Details

### Architecture

- **models.py**: Pydantic data models for type safety
- **scorer.py**: Core 5-signal scoring logic (deterministic)
- **analyzer.py**: Orchestrates scoring + LLM market signal analysis
- **data.py**: Example financial data and transcripts
- **main.py**: CLI interface
- **capital_raise_detector.ipynb**: Interactive Jupyter notebook

### Dependencies

- `langchain`: LLM orchestration
- `langchain-openai`: OpenAI API integration
- `pydantic`: Data validation
- `pandas`: Data manipulation
- `jupyter`: Interactive notebooks
- `tabulate`: Terminal tables

## Future Enhancements

- [ ] Real API integration (SEC EDGAR, Bloomberg, etc.)
- [ ] Time-series analysis (score trends over quarters)
- [ ] Sector/peer comparison
- [ ] Confidence intervals based on data quality
- [ ] Alerts on score threshold crossings
- [ ] Integration with trading signals
- [ ] Web dashboard for portfolio monitoring
- [ ] Webhook notifications for major changes

## Disclaimer

This tool is for educational and analytical purposes. It should not be used as the sole basis for investment or business decisions. Always conduct thorough due diligence and consult with financial professionals.

## License

Educational use for BUSN30135 course.
