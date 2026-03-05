"""Core scoring logic for Capital Raise Detector."""

from models import FinancialMetrics, SignalScores, CapitalRaisePrediction


class CapitalRaiseScorer:
    """Scores companies on likelihood of capital raise using 5 signals."""

    # Thresholds and weights
    LIKELIHOOD_THRESHOLD = 50  # Score > 50 triggers alert
    CONFIDENCE_BASE = 85  # Base confidence (reduced for missing data)

    def score(self, metrics: FinancialMetrics) -> CapitalRaisePrediction:
        """
        Calculate capital raise likelihood score for a company.

        Args:
            metrics: FinancialMetrics object with company financial data

        Returns:
            CapitalRaisePrediction with scores and alert status
        """
        # Calculate individual signal scores
        cash_runway_score = self._score_cash_runway(metrics)
        liquidity_stress_score = self._score_liquidity_stress(metrics)
        debt_maturity_score = self._score_debt_maturity(metrics)
        operational_red_flags_score = self._score_operational_red_flags(metrics)
        market_behavioral_score = self._score_market_behavioral(metrics)

        # Create signal scores object
        signal_scores = SignalScores(
            cash_runway_score=cash_runway_score,
            liquidity_stress_score=liquidity_stress_score,
            debt_maturity_score=debt_maturity_score,
            operational_red_flags_score=operational_red_flags_score,
            market_behavioral_score=market_behavioral_score,
        )

        # Total score
        total_score = (
            cash_runway_score
            + liquidity_stress_score
            + debt_maturity_score
            + operational_red_flags_score
            + market_behavioral_score
        )

        # Determine risk level and drivers
        risk_level = self._determine_risk_level(total_score)
        key_drivers = self._identify_key_drivers(metrics, signal_scores)
        confidence = self._calculate_confidence(metrics)

        return CapitalRaisePrediction(
            ticker=metrics.ticker,
            company_name=metrics.company_name,
            likelihood_score=total_score,
            signal_scores=signal_scores,
            above_threshold=total_score > self.LIKELIHOOD_THRESHOLD,
            risk_level=risk_level,
            key_drivers=key_drivers,
            confidence=confidence,
        )

    def _score_cash_runway(self, metrics: FinancialMetrics) -> float:
        """
        Score cash runway.

        Points:
        - < 6 months: 25 points
        - 6-12 months: 15 points
        - 12-18 months: 5 points
        - > 18 months: 0 points
        """
        if metrics.monthly_burn_rate <= 0:
            # Positive burn rate (cash generation) - no risk
            return 0.0

        runway_months = metrics.cash_and_equivalents / metrics.monthly_burn_rate

        if runway_months < 6:
            return 25.0
        elif runway_months < 12:
            return 15.0
        elif runway_months < 18:
            return 5.0
        else:
            return 0.0

    def _score_liquidity_stress(self, metrics: FinancialMetrics) -> float:
        """
        Score liquidity stress indicators.

        Points based on:
        - Current ratio (< 0.8 = 5 pts)
        - Quick ratio deterioration
        - Working capital status (negative = 2.5 pts)
        """
        score = 0.0

        # Current ratio
        current_ratio = metrics.current_assets / metrics.current_liabilities
        if current_ratio < 0.8:
            score += 5.0
        elif current_ratio < 1.0:
            score += 3.5
        elif current_ratio < 1.2:
            score += 1.5

        # Quick ratio (more conservative)
        quick_ratio = metrics.quick_assets / metrics.current_liabilities
        if quick_ratio < 0.5:
            score += 2.5
        elif quick_ratio < 0.75:
            score += 1.0

        # Working capital
        working_capital = metrics.current_assets - metrics.current_liabilities
        if working_capital < 0:
            score += 2.5
        elif working_capital < metrics.current_liabilities * 0.25:
            score += 1.0

        return min(score, 10.0)  # Cap at 10 points

    def _score_debt_maturity(self, metrics: FinancialMetrics) -> float:
        """
        Score debt maturity profile and covenant risk.

        Points based on:
        - Debt due within 12 months relative to cash (> 50% = 15 pts)
        - Debt due within 6-18 months (> 30% of cash = 5 pts)
        - Credit rating outlook (negative = 5 pts, positive = -2 pts)
        """
        score = 0.0

        # Near-term debt relative to cash
        if metrics.cash_and_equivalents > 0:
            debt_to_cash_ratio = metrics.debt_due_12mo / metrics.cash_and_equivalents
            if debt_to_cash_ratio > 0.5:
                score += 15.0
            elif debt_to_cash_ratio > 0.25:
                score += 8.0
            elif debt_to_cash_ratio > 0.1:
                score += 3.0

        # Medium-term debt maturity
        if metrics.debt_due_6_18mo > metrics.cash_and_equivalents * 0.3:
            score += 5.0

        # Credit rating outlook
        if metrics.credit_rating_outlook == "negative":
            score += 5.0
        elif metrics.credit_rating_outlook == "positive":
            score -= 2.0  # Reduce risk

        return min(score, 25.0)  # Cap at 25 points

    def _score_operational_red_flags(self, metrics: FinancialMetrics) -> float:
        """
        Score operational red flags.

        Points based on:
        - Revenue decline (> 5% = 4 pts, > 10% = 8 pts)
        - Gross margin compression (> 200 bps = 4 pts)
        - Negative operating cash flow for 12m (= 8 pts)
        - Capex exceeding FCF (= 3 pts)
        - Going concern warning (= 8 pts)
        """
        score = 0.0

        # Revenue trend
        revenue_change = (
            (metrics.revenue_trailing_12m - metrics.revenue_prior_year)
            / metrics.revenue_prior_year
        )
        if revenue_change < -0.10:
            score += 8.0
        elif revenue_change < -0.05:
            score += 4.0

        # Gross margin compression
        margin_decline = metrics.prior_gross_margin - metrics.gross_margin
        if margin_decline > 0.02:
            score += 4.0
        elif margin_decline > 0.01:
            score += 2.0

        # Operating cash flow
        if metrics.operating_cash_flow_trailing_12m < 0:
            score += 8.0

        # Capex burden
        fcf = metrics.operating_cash_flow_trailing_12m - metrics.capex_annual
        if fcf < 0 and metrics.capex_annual > 0:
            score += 3.0

        # Going concern warning
        if metrics.auditor_going_concern:
            score += 8.0

        return min(score, 20.0)  # Cap at 20 points

    def _score_market_behavioral(self, metrics: FinancialMetrics) -> float:
        """
        Score market and behavioral signals.

        Points based on:
        - Stock price decline from 52w high (> 30% = 10 pts, > 20% = 6 pts, > 10% = 2 pts)
        - Insider selling activity (high = 10 pts, elevated = 6 pts)
        """
        score = 0.0

        # Stock price relative to 52-week high
        if metrics.stock_price_52w_high > 0:
            price_decline = (
                1 - (metrics.stock_price / metrics.stock_price_52w_high)
            )
            if price_decline > 0.30:
                score += 10.0
            elif price_decline > 0.20:
                score += 6.0
            elif price_decline > 0.10:
                score += 2.0

        # Insider selling activity
        if metrics.insider_selling_activity == "high":
            score += 10.0
        elif metrics.insider_selling_activity == "elevated":
            score += 6.0

        return min(score, 20.0)  # Cap at 20 points

    def _determine_risk_level(self, score: float) -> str:
        """Determine risk level from score."""
        if score >= 75:
            return "critical"
        elif score >= 60:
            return "high"
        elif score >= 40:
            return "medium"
        else:
            return "low"

    def _identify_key_drivers(
        self, metrics: FinancialMetrics, signal_scores: SignalScores
    ) -> list[str]:
        """Identify top 3-5 risk drivers."""
        drivers = []

        # Cash runway
        if signal_scores.cash_runway_score > 12:
            if metrics.monthly_burn_rate > 0:
                runway = metrics.cash_and_equivalents / metrics.monthly_burn_rate
                drivers.append(f"Low cash runway: {runway:.1f} months")

        # Liquidity
        if signal_scores.liquidity_stress_score > 5:
            current_ratio = metrics.current_assets / metrics.current_liabilities
            drivers.append(f"Weak liquidity: Current ratio {current_ratio:.2f}")

        # Debt maturity
        if signal_scores.debt_maturity_score > 10:
            drivers.append(f"${metrics.debt_due_12mo/1e6:.0f}M debt due in 12 months")

        # Operational
        if signal_scores.operational_red_flags_score > 8:
            if metrics.operating_cash_flow_trailing_12m < 0:
                drivers.append("Negative operating cash flow")
            revenue_change = (
                (metrics.revenue_trailing_12m - metrics.revenue_prior_year)
                / metrics.revenue_prior_year
            )
            if revenue_change < -0.05:
                drivers.append(f"Revenue decline: {revenue_change*100:.1f}%")

        # Market signals
        if signal_scores.market_behavioral_score > 5:
            if metrics.insider_selling_activity in ["elevated", "high"]:
                drivers.append(f"Elevated insider selling activity")
            if metrics.stock_price_52w_high > 0:
                price_decline = 1 - (metrics.stock_price / metrics.stock_price_52w_high)
                if price_decline > 0.10:
                    drivers.append(f"Stock down {price_decline*100:.0f}% from 52-week high")

        return drivers[:5]  # Return top 5

    def _calculate_confidence(self, metrics: FinancialMetrics) -> float:
        """Calculate confidence in prediction based on data quality."""
        confidence = self.CONFIDENCE_BASE  # Start at 85

        # Reduce confidence for missing market & behavioral data
        if metrics.stock_price == 0.0 or metrics.stock_price_52w_high == 0.0:
            confidence -= 10  # Can't score stock decline without price data

        if metrics.insider_selling_activity == "normal":
            confidence -= 5  # "normal" is the default when data isn't available

        if metrics.credit_rating is None:
            confidence -= 5  # Missing credit rating weakens debt maturity signal

        # Reduce confidence for missing operational data
        if metrics.revenue_trailing_12m == 0.0:
            confidence -= 10  # No revenue data severely limits scoring

        if metrics.operating_cash_flow_trailing_12m == 0.0:
            confidence -= 5  # OCF is key to burn rate and operational scoring

        return max(confidence, 30.0)  # Floor at 30% — never report near-zero confidence
