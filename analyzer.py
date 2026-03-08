"""Main analyzer that orchestrates scoring and AI-powered signal analysis."""

import os
import re
from typing import Optional
from models import FinancialMetrics, CapitalRaisePrediction
from scorer import CapitalRaiseScorer


class CapitalRaiseAnalyzer:
    """Orchestrates financial scoring and AI-powered market signal analysis."""

    def __init__(self, model_name: str = "gpt-4o-mini", temperature: float = 0.3):
        """
        Initialize analyzer with LLM.

        Args:
            model_name: OpenAI model to use (gpt-4, gpt-4o-mini, etc.)
            temperature: LLM temperature for reproducibility
        """
        self.scorer = CapitalRaiseScorer()
        self.llm = None
        if os.environ.get("OPENAI_API_KEY"):
            from langchain_openai import ChatOpenAI
            self.llm = ChatOpenAI(
                model=model_name,
                temperature=temperature,
            )

    def analyze(
        self,
        metrics: FinancialMetrics,
        earnings_call_transcript: Optional[str] = None,
        market_news: Optional[str] = None,
    ) -> CapitalRaisePrediction:
        """
        Analyze company for capital raise likelihood.

        Args:
            metrics: Financial metrics for the company
            earnings_call_transcript: Optional earnings call transcript to analyze
            market_news: Optional recent news/market signals

        Returns:
            CapitalRaisePrediction with scores and analysis
        """
        # Get base financial score
        prediction = self.scorer.score(metrics)

        # Enhance with market signal analysis if provided
        if earnings_call_transcript or market_news:
            enhanced_drivers = self._analyze_market_signals(
                metrics, earnings_call_transcript, market_news
            )
            # Add market-derived signals to key drivers
            prediction.key_drivers.extend(enhanced_drivers)
            prediction.key_drivers = prediction.key_drivers[:5]  # Keep top 5

        return prediction

    def _analyze_market_signals(
        self,
        metrics: FinancialMetrics,
        transcript: Optional[str] = None,
        news: Optional[str] = None,
    ) -> list[str]:
        """
        Use LLM to analyze earnings calls and news for capital raise signals.

        Prompts the LLM for structured JSON output — a list of up to 3 concise
        signal strings — so each signal can be cleanly parsed and displayed
        without truncation or mangling.

        Looks for:
        - Management language ("exploring strategic options", "financing")
        - Strategic shifts and financing discussions
        - Acquisition/divestiture activity
        - Going concern language or funding urgency
        """
        combined_text = ""
        if transcript:
            combined_text += f"EARNINGS CALL:\n{transcript}\n\n"
        if news:
            combined_text += f"RECENT NEWS:\n{news}\n\n"

        if not combined_text or self.llm is None:
            return []

        import json
        from langchain_core.prompts import PromptTemplate

        prompt_template = PromptTemplate(
            input_variables=["company_name", "text"],
            template="""Analyze the following text for {company_name} and identify signals \
suggesting the company may be considering a capital raise \
(secondary offering, private fundraise, debt refinancing, etc.).

Look for:
- Explicit mentions of financing, capital raise, equity raise, or strategic options
- Management commentary on funding needs or cash runway
- Mergers, acquisitions, or divestitures requiring capital
- Going concern language or urgency around liquidity

Text to analyze:
{text}

Respond ONLY with a JSON array of up to 3 short signal strings (each under 120 characters).
If no signals are found, respond with an empty array [].
Do not include any explanation, preamble, or markdown — just the raw JSON array.

Example of valid output:
["CFO mentioned exploring financing alternatives on the Q3 call", \
"News reports secondary offering being discussed with underwriters"]""",
        )

        chain = prompt_template | self.llm
        try:
            response = chain.invoke(
                {
                    "company_name": metrics.company_name,
                    "text": combined_text[:3000],
                }
            )

            # Strip markdown code fences if the LLM adds them anyway
            raw = response.content.strip()
            if raw.startswith("```"):
                raw = re.sub(r"^```[a-z]*\n?", "", raw)
                raw = re.sub(r"\n?```$", "", raw.strip())

            parsed = json.loads(raw)

            if not isinstance(parsed, list):
                return []

            # Validate each item is a non-empty string and prefix for display
            signals = []
            for item in parsed:
                if isinstance(item, str) and item.strip():
                    signals.append(f"Market signal: {item.strip()}")

            return signals[:3]  # Enforce cap of 3 signals

        except (json.JSONDecodeError, Exception):
            # If parsing fails entirely, fall back to returning nothing
            # rather than surfacing a garbled partial string
            return []

    def batch_analyze(
        self, companies: list[FinancialMetrics]
    ) -> list[CapitalRaisePrediction]:
        """
        Analyze multiple companies.

        Args:
            companies: List of FinancialMetrics objects

        Returns:
            List of CapitalRaisePrediction objects
        """
        results = []
        for company in companies:
            try:
                result = self.analyze(company)
                results.append(result)
            except Exception as e:
                print(f"Error analyzing {company.ticker} ({company.company_name}): {e}")
                continue
        return results

    def get_alerts(
        self, predictions: list[CapitalRaisePrediction]
    ) -> list[CapitalRaisePrediction]:
        """
        Filter to companies above threshold that need monitoring.

        Args:
            predictions: List of predictions

        Returns:
            Companies with score > 50 (sorted by score descending)
        """
        alerts = [p for p in predictions if p.above_threshold]
        return sorted(alerts, key=lambda p: p.likelihood_score, reverse=True)
