"""CLI interface for Capital Raise Detector."""

import argparse
import json
from typing import Optional
from tabulate import tabulate
from models import FinancialMetrics
from analyzer import CapitalRaiseAnalyzer
from data import EXAMPLE_COMPANIES, EARNINGS_CALL_TRANSCRIPT, MARKET_NEWS


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Capital Raise Detector - Predict likelihood of equity raises"
    )
    parser.add_argument(
        "--ticker",
        type=str,
        help="Company ticker to analyze (or 'all' for example companies)",
        default="BURN",
    )
    parser.add_argument(
        "--use-examples",
        action="store_true",
        help="Run analysis on all example companies",
    )
    parser.add_argument(
        "--include-market-signals",
        action="store_true",
        help="Include LLM analysis of earnings calls/news (requires OPENAI_API_KEY)",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        help="Export results to JSON file",
    )
    parser.add_argument(
        "--alerts-only",
        action="store_true",
        help="Show only companies above threshold (score > 50)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o-mini",
        help="LLM model to use (gpt-4o-mini, gpt-4, etc.)",
    )

    args = parser.parse_args()

    # Initialize analyzer
    analyzer = CapitalRaiseAnalyzer(model_name=args.model)

    # Determine which companies to analyze
    if args.use_examples or args.ticker == "all":
        companies = EXAMPLE_COMPANIES
    else:
        # First check example companies
        matching = [c for c in EXAMPLE_COMPANIES if c.ticker == args.ticker]
        if matching:
            companies = matching
        else:
            # Fall back to fetching real data from SEC EDGAR
            try:
                from sec_fetcher import fetch_metrics
                print(f"Ticker '{args.ticker}' not in examples, fetching from SEC EDGAR...")
                metrics = fetch_metrics(args.ticker)
                companies = [metrics]
            except ValueError as e:
                print(f"Error: {e}")
                return
            except Exception as e:
                print(f"Error fetching data for {args.ticker}: {e}")
                return

    # Analyze companies
    predictions = []
    for company in companies:
        print(f"\nAnalyzing {company.ticker}...", end=" ", flush=True)

        # Include market signals if requested
        transcript = EARNINGS_CALL_TRANSCRIPT if args.include_market_signals else None
        news = MARKET_NEWS if args.include_market_signals else None

        prediction = analyzer.analyze(company, transcript, news)
        predictions.append(prediction)
        print("✓")

    # Filter to alerts if requested
    if args.alerts_only:
        predictions = analyzer.get_alerts(predictions)

    # Display results
    print("\n" + "=" * 80)
    print("CAPITAL RAISE DETECTOR - RESULTS")
    print("=" * 80)

    if not predictions:
        print("No companies above threshold.")
        return

    # Summary table
    summary_data = [
        [
            p.ticker,
            f"{p.likelihood_score:.1f}",
            p.risk_level.upper(),
            "⚠️ YES" if p.above_threshold else "✓ No",
            f"{p.confidence:.0f}%",
        ]
        for p in predictions
    ]

    print(
        "\nSUMMARY TABLE:"
    )
    print(
        tabulate(
            summary_data,
            headers=["Ticker", "Score", "Risk", "Alert", "Confidence"],
            tablefmt="grid",
        )
    )

    # Detailed results
    print("\n" + "=" * 80)
    print("DETAILED RESULTS")
    print("=" * 80)

    for prediction in predictions:
        print(prediction)
        print("-" * 80)

    # Export to JSON if requested
    if args.output_json:
        export_data = [
            {
                "ticker": p.ticker,
                "company_name": p.company_name,
                "likelihood_score": p.likelihood_score,
                "signal_scores": p.signal_scores.model_dump(),
                "above_threshold": p.above_threshold,
                "risk_level": p.risk_level,
                "key_drivers": p.key_drivers,
                "confidence": p.confidence,
            }
            for p in predictions
        ]

        with open(args.output_json, "w") as f:
            json.dump(export_data, f, indent=2, default=str)

        print(f"\nResults exported to {args.output_json}")

    # Summary stats
    print("\n" + "=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)
    alert_count = sum(1 for p in predictions if p.above_threshold)
    print(f"Total companies analyzed: {len(predictions)}")
    print(f"Companies above threshold (score > 50): {alert_count}")
    print(
        f"Average likelihood score: {sum(p.likelihood_score for p in predictions) / len(predictions):.1f}"
    )

    if alert_count > 0:
        avg_alert_score = sum(
            p.likelihood_score for p in predictions if p.above_threshold
        ) / alert_count
        print(f"Average score for alerts: {avg_alert_score:.1f}")


if __name__ == "__main__":
    main()
