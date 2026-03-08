"""Streamlit GUI for Capital Raise Detector."""

import streamlit as st
import pandas as pd
from datetime import datetime

from analyzer import CapitalRaiseAnalyzer
from screener import screen_all_companies
from sec_fetcher import fetch_metrics
from data import EXAMPLE_COMPANIES
from models import CapitalRaisePrediction


# Page configuration
st.set_page_config(
    page_title="Capital Raise Detector",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for better styling
st.markdown(
    """
    <style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 8px;
        margin: 10px 0;
    }
    .high-risk {
        background-color: #ffebee;
        border-left: 4px solid #d32f2f;
    }
    .medium-risk {
        background-color: #fff3e0;
        border-left: 4px solid #f57c00;
    }
    .low-risk {
        background-color: #e8f5e9;
        border-left: 4px solid #388e3c;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# Initialize session state
if "analyzer" not in st.session_state:
    st.session_state.analyzer = CapitalRaiseAnalyzer()

if "ticker_result" not in st.session_state:
    st.session_state.ticker_result = None

if "screening_results" not in st.session_state:
    st.session_state.screening_results = None


@st.cache_data
def get_example_companies():
    """Load example companies from data module."""
    return EXAMPLE_COMPANIES


def get_risk_color(risk_level: str) -> str:
    """Return color based on risk level."""
    colors = {
        "critical": "#d32f2f",  # Red
        "high": "#f57c00",      # Orange
        "medium": "#fbc02d",    # Yellow
        "low": "#388e3c",       # Green
    }
    return colors.get(risk_level.lower(), "#9e9e9e")


def display_prediction_card(prediction: CapitalRaisePrediction):
    """Display a prediction result as a styled card."""
    # Create columns for layout
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Likelihood Score",
            f"{prediction.likelihood_score:.1f}/100",
            delta=None,
        )

    with col2:
        st.metric(
            "Risk Level",
            prediction.risk_level.upper(),
            delta=None,
        )

    with col3:
        st.metric(
            "Confidence",
            f"{prediction.confidence:.0f}%",
            delta=None,
        )

    with col4:
        status = "⚠️ ALERT" if prediction.above_threshold else "✓ Safe"
        st.metric(
            "Alert Status",
            status,
            delta=None,
        )

    st.divider()

    # Company details
    col1, col2, col3 = st.columns(3)
    with col1:
        st.write(f"**Company:** {prediction.company_name}")
    with col2:
        st.write(f"**Sector:** {prediction.sector}")
    with col3:
        market_cap_str = f"${prediction.market_cap/1e9:.1f}B" if prediction.market_cap > 0 else "Unknown"
        st.write(f"**Market Cap:** {market_cap_str}")

    st.divider()

    # Signal breakdown
    st.subheader("Signal Breakdown")
    signal_data = {
        "Signal": [
            "Cash Runway",
            "Liquidity Stress",
            "Debt Maturity",
            "Operational Red Flags",
            "Market & Behavioral",
        ],
        "Score": [
            f"{prediction.signal_scores.cash_runway_score:.1f}/40",
            f"{prediction.signal_scores.liquidity_stress_score:.1f}/20",
            f"{prediction.signal_scores.debt_maturity_score:.1f}/15",
            f"{prediction.signal_scores.operational_red_flags_score:.1f}/15",
            f"{prediction.signal_scores.market_behavioral_score:.1f}/10",
        ],
    }
    signal_df = pd.DataFrame(signal_data)
    st.dataframe(signal_df, use_container_width=True, hide_index=True)

    # Key drivers
    if prediction.key_drivers:
        st.subheader("Key Risk Drivers")
        for driver in prediction.key_drivers:
            st.write(f"• {driver}")

    st.divider()


def analyze_by_ticker_tab():
    """Analyze a single company by ticker."""
    st.header("📈 Analyze by Ticker")

    col1, col2 = st.columns([3, 1])

    with col1:
        ticker_input = st.text_input(
            "Enter Stock Ticker",
            placeholder="e.g., AAPL, MSFT, TSLA",
            help="Enter a valid stock ticker symbol",
        ).upper()

    with col2:
        analyze_button = st.button("🔍 Analyze", use_container_width=True)

    if analyze_button and ticker_input:
        with st.spinner(f"Analyzing {ticker_input}..."):
            try:
                # Try to fetch real data from SEC
                metrics = fetch_metrics(ticker_input)
                prediction = st.session_state.analyzer.analyze(metrics)
                st.session_state.ticker_result = prediction

                st.success(f"✅ Analysis complete for {ticker_input}")

            except ValueError as e:
                st.error(f"❌ Error: {str(e)}")
                st.info("Tip: Try using example companies (STRONG, BURN, STRESS, GROW, STABLE)")
            except Exception as e:
                st.error(f"❌ Unexpected error: {str(e)}")
                st.info("Try using example companies instead.")

    # Display result if available
    if st.session_state.ticker_result:
        st.divider()
        display_prediction_card(st.session_state.ticker_result)

        # Clear button
        if st.button("Clear Result"):
            st.session_state.ticker_result = None
            st.rerun()


def screen_all_companies_tab():
    """Screen all US public companies."""
    st.header("🔍 Screen All US Public Companies")

    # Filtering options
    st.subheader("Screening Parameters")

    col1, col2, col3 = st.columns(3)

    with col1:
        year = st.number_input(
            "Year",
            min_value=2020,
            max_value=datetime.now().year,
            value=datetime.now().year - 1,
            help="Calendar year to analyze",
        )

    with col2:
        min_market_cap = st.selectbox(
            "Minimum Market Cap",
            [100_000_000, 500_000_000, 1_000_000_000, 5_000_000_000],
            format_func=lambda x: f"${x/1e9:.1f}B" if x >= 1_000_000_000 else f"${x/1e6:.0f}M",
            index=2,
            help="Filter out smaller companies",
        )

    with col3:
        exchanges = st.multiselect(
            "Exchanges",
            ["NYSE", "Nasdaq"],
            default=["NYSE", "Nasdaq"],
            help="Filter by stock exchange",
        )

    st.divider()

    # Screen button
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        screen_button = st.button(
            "🚀 Start Screening",
            use_container_width=True,
            help="This will take 1-2 minutes to complete",
        )

    with col2:
        if st.button("🗑️ Clear Results", use_container_width=True):
            st.session_state.screening_results = None
            st.rerun()

    with col3:
        st.info("⏱️ Estimated time: 1-2 minutes for full screening")

    if screen_button:
        # Progress tracking
        progress_bar = st.progress(0, text="Starting screening...")
        status_text = st.empty()

        try:
            status_text.text("📡 Fetching financial data from SEC EDGAR...")
            progress_bar.progress(10)

            status_text.text("📊 Scoring companies...")
            progress_bar.progress(40)

            # Run screening
            results = screen_all_companies(
                year=int(year),
                exchanges=exchanges if exchanges else None,
                min_market_cap=min_market_cap,
            )

            progress_bar.progress(90, text="Formatting results...")
            st.session_state.screening_results = results

            progress_bar.progress(100, text="Complete!")
            st.success(f"✅ Screening complete! Found {len(results)} high-risk companies.")

        except Exception as e:
            st.error(f"❌ Screening failed: {str(e)}")
            st.info("Try adjusting the screening parameters.")

    # Display screening results
    if st.session_state.screening_results:
        st.divider()
        st.subheader(
            f"Results: {len(st.session_state.screening_results)} High-Risk Companies"
        )

        if st.session_state.screening_results:
            # Summary statistics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                avg_score = sum(
                    r[2].likelihood_score for r in st.session_state.screening_results
                ) / len(st.session_state.screening_results)
                st.metric("Avg Score", f"{avg_score:.1f}")

            with col2:
                critical_count = sum(
                    1 for r in st.session_state.screening_results
                    if r[2].risk_level == "critical"
                )
                st.metric("Critical Risk", critical_count)

            with col3:
                high_count = sum(
                    1 for r in st.session_state.screening_results
                    if r[2].risk_level == "high"
                )
                st.metric("High Risk", high_count)

            with col4:
                market_cap_total = sum(
                    r[2].market_cap for r in st.session_state.screening_results
                )
                st.metric(
                    "Total Market Cap",
                    f"${market_cap_total/1e12:.1f}T",
                )

            st.divider()

            # Results table
            results_data = []
            for ticker, company_name, prediction in st.session_state.screening_results:
                market_cap_str = (
                    f"${prediction.market_cap/1e9:.1f}B"
                    if prediction.market_cap > 0
                    else "Unknown"
                )
                results_data.append({
                    "Ticker": ticker,
                    "Company": company_name,
                    "Sector": prediction.sector,
                    "Market Cap": market_cap_str,
                    "Score": f"{prediction.likelihood_score:.1f}",
                    "Risk Level": prediction.risk_level.upper(),
                    "Confidence": f"{prediction.confidence:.0f}%",
                })

            results_df = pd.DataFrame(results_data)
            st.dataframe(
                results_df,
                use_container_width=True,
                hide_index=True,
            )

            # Export option
            csv = results_df.to_csv(index=False)
            st.download_button(
                label="📥 Download as CSV",
                data=csv,
                file_name=f"capital_raise_screening_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
            )

            st.divider()

            # Detailed results
            if st.checkbox("Show Detailed Results", value=False):
                st.subheader("Detailed Analysis")
                for ticker, company_name, prediction in st.session_state.screening_results:
                    with st.expander(
                        f"{ticker} - {company_name} (Score: {prediction.likelihood_score:.1f})"
                    ):
                        display_prediction_card(prediction)


def main():
    """Main application."""
    # Header
    st.title("📊 Capital Raise Detector")
    st.markdown(
        "Identify companies most likely to pursue equity raises based on financial stress signals."
    )

    # Sidebar
    with st.sidebar:
        st.header("About")
        st.markdown(
            """
            This tool analyzes financial data to identify companies that may pursue capital raises.

            **Scoring Factors:**
            - Cash runway and burn rate
            - Liquidity stress indicators
            - Debt maturity schedules
            - Operational red flags
            - Market & behavioral signals

            **Data Source:** SEC EDGAR (10-K and 10-Q filings)
            """
        )
        st.divider()

        st.header("Model Settings")
        model_name = st.selectbox(
            "LLM Model",
            ["gpt-4o-mini", "gpt-4", "gpt-3.5-turbo"],
            help="Model for analyzing market signals (if API key provided)",
        )

        # Update analyzer if model changed
        if model_name != st.session_state.analyzer.llm.model if st.session_state.analyzer.llm else None:
            st.session_state.analyzer = CapitalRaiseAnalyzer(model_name=model_name)

    # Main tabs
    tab1, tab2 = st.tabs(["Analyze by Ticker", "Screen All Companies"])

    with tab1:
        analyze_by_ticker_tab()

    with tab2:
        screen_all_companies_tab()


if __name__ == "__main__":
    main()
