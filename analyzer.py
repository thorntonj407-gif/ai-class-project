"""Main analyzer that orchestrates scoring and AI-powered signal analysis."""

import os
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

        Looks for:
        - Management language ("exploring strategic options", "financing")
        - Strategic shifts
        - Financing mentions
        - Acquisition/divestiture activity
        """
        combined_text = ""
        if transcript:
            combined_text += f"EARNINGS CALL:\n{transcript}\n\n"
        if news:
            combined_text += f"RECENT NEWS:\n{news}\n\n"

        if not combined_text or self.llm is None:
            return []

        from langchain_core.prompts import PromptTemplate
        prompt_template = PromptTemplate(
            input_variables=["company_name", "text"],
            template="""Analyze the following earnings call transcript and/or news for {company_name}
            and identify any signals that suggest the company may be considering a capital raise
            (IPO, secondary offering, private fundraise, etc.).

            Look for:
            - Explicit mentions of "financing", "capital raise", "equity raise", "exploring strategic options"
            - References to growth investments needing capital
            - Management commentary on funding needs or strategic changes
            - Mergers, acquisitions, or divestitures
            - New product launches requiring investment

            Text to analyze:
            {text}

            Provide 2-3 specific signals/quotes that suggest capital raise likelihood, or "No clear signals" if none found.
            Be concise and factual.""",
        )

        chain = prompt_template | self.llm
        response = chain.invoke(
            {
                "company_name": metrics.company_name,
                "text": combined_text[:3000],  # Limit to 3000 chars
            }
        )

        # Extract signals from LLM response
        response_text = response.content.lower()
        signals = []

        if "no clear signals" in response_text:
            return signals

        # Parse response - take the main text as market signal
        if response_text:
            # Clean up and add as market signal
            signal = f"Market signal: {response.content[:100]}..."
            signals.append(signal)

        return signals

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
