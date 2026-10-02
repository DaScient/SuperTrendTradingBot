"""
Integration Module: SuperTrend Bot Integration

Demonstrates how to integrate ClaudeTrader with existing SuperTrend trading bots
in the repository.
"""

import re
import sys
from pathlib import Path

# Add parent directories to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from ClaudeTrader.core.engine import ClaudeTrader
from ClaudeTrader.strategies import get_strategy
import logging

logger = logging.getLogger(__name__)


class SuperTrendBotIntegration:
    """
    Integration class for enhancing existing SuperTrend bot with ClaudeTrader AI
    """

    def __init__(self, config_path=None):
        """Initialize integration with ClaudeTrader"""
        self.claude_trader = ClaudeTrader(config_path)
        logger.info("SuperTrend Bot Integration initialized")

    def augment_signals(
        self,
        base_signals,
        llm_analysis=True,
        risk_assessment=True
    ):
        """
        Enhance existing bot signals with AI insights

        Args:
            base_signals: Original signals from SuperTrend bot
            llm_analysis: Whether to add LLM reasoning
            risk_assessment: Whether to add risk analysis

        Returns:
            Enhanced signals with AI insights
        """

        enhanced_signals = []

        for signal in base_signals:
            enhanced = signal.copy()

            if llm_analysis:
                # Get AI reasoning
                query = f"""
                Analyze this trading signal:
                Symbol: {signal.get('symbol')}
                Action: {signal.get('action')}
                Price: {signal.get('price')}
                Indicators: {signal.get('indicators')}

                Provide validation and additional insights.
                """

                response = self.claude_trader.query(query)
                enhanced['ai_reasoning'] = response.response
                enhanced['ai_confidence'] = response.confidence

            if risk_assessment:
                # Add risk assessment
                risk_score = self._assess_risk(signal)
                enhanced['risk_score'] = risk_score
                enhanced['risk_level'] = self._get_risk_level(risk_score)

            enhanced_signals.append(enhanced)

        logger.info(f"Enhanced {len(enhanced_signals)} signals")
        return enhanced_signals

    def execute_with_validation(
        self,
        signal,
        confidence_threshold=0.75
    ):
        """
        Execute trade only if AI validates with sufficient confidence

        The model is asked for an explicit decision and confidence. The trade
        is approved only when it answers EXECUTE with a confidence at or above
        the threshold; anything unparseable is treated as a rejection.

        Args:
            signal: Trading signal to validate
            confidence_threshold: Minimum confidence to execute

        Returns:
            Execution result
        """

        # Get AI validation
        query = f"""
        Should I execute this trade?
        {signal}

        Consider:
        1. Current market conditions
        2. Risk/reward ratio
        3. Technical setup quality
        4. Potential risks

        Explain briefly, then end your answer with exactly these two lines:
        DECISION: EXECUTE or DECISION: SKIP
        CONFIDENCE: <number between 0 and 1>
        """

        response = self.claude_trader.query(query)
        decision, confidence = self._parse_decision(response.response)
        approved = decision == 'EXECUTE' and confidence >= confidence_threshold

        if approved:
            logger.info(f"Trade approved by AI (confidence: {confidence})")
        else:
            logger.warning(f"Trade rejected by AI (decision: {decision}, confidence: {confidence})")

        return {
            'execute': approved,
            'decision': decision,
            'confidence': confidence,
            'reasoning': response.response
        }

    @staticmethod
    def _parse_decision(text):
        """Extract (decision, confidence) from a validation response.

        Returns ('SKIP', 0.0) when the response doesn't follow the format.
        """
        decisions = re.findall(r'DECISION:\s*(EXECUTE|SKIP)', text or '', re.IGNORECASE)
        confidences = re.findall(r'CONFIDENCE:\s*([01](?:\.\d+)?)', text or '', re.IGNORECASE)
        if not decisions or not confidences:
            return 'SKIP', 0.0
        confidence = min(max(float(confidences[-1]), 0.0), 1.0)
        return decisions[-1].upper(), confidence

    def get_position_sizing_advice(self, signal, account_balance, risk_per_trade=0.02):
        """
        Get AI-powered position sizing recommendation

        Size is computed with the fixed-fractional rule (losing ``risk_per_trade``
        of the account if the stop is hit) and capped at the account balance
        (no leverage). The LLM's commentary is returned alongside it.

        Args:
            signal: Trading signal (uses ``price`` and ``stop_loss_pct``)
            account_balance: Current account balance
            risk_per_trade: Fraction of the account to risk

        Returns:
            Position sizing recommendation: ``position_notional`` in account
            currency and ``position_units`` of the asset (when price is known).
        """

        query = f"""
        Recommend position size for this trade:
        Signal: {signal}
        Account Balance: ${account_balance}
        Risk per trade: {risk_per_trade:.1%}

        Consider volatility and signal confidence.
        """

        response = self.claude_trader.query(query)

        risk_amount = account_balance * risk_per_trade
        stop_loss_pct = signal.get('stop_loss_pct', 0.02)
        notional = min(risk_amount / stop_loss_pct, account_balance) if stop_loss_pct > 0 else 0.0
        price = signal.get('price')

        return {
            'position_notional': notional,
            'position_units': notional / price if price else None,
            'risk_amount': risk_amount,
            'reasoning': response.response
        }

    def _assess_risk(self, signal):
        """Assess risk level of a signal"""

        # Simple risk scoring (0-1)
        # Real implementation would be more sophisticated

        risk_factors = {
            'volatility': 0.3,
            'market_regime': 0.3,
            'signal_strength': 0.4
        }

        # Calculate weighted risk score
        risk_score = 0.5  # Base risk

        # Adjust based on signal characteristics
        confidence = signal.get('confidence', 0.5)
        risk_score = risk_score * (2 - confidence)

        return min(max(risk_score, 0), 1)

    def _get_risk_level(self, risk_score):
        """Convert risk score to categorical level"""

        if risk_score < 0.3:
            return 'low'
        elif risk_score < 0.6:
            return 'medium'
        else:
            return 'high'

    def monitor_positions(self, positions):
        """
        Monitor open positions with AI insights

        Args:
            positions: List of open positions

        Returns:
            Monitoring alerts and recommendations
        """

        alerts = []

        for position in positions:
            query = f"""
            Monitor this position:
            {position}

            Should I:
            1. Hold
            2. Take partial profit
            3. Exit completely
            4. Adjust stop loss

            Consider current market conditions.
            """

            response = self.claude_trader.query(query)

            alerts.append({
                'position': position,
                'recommendation': response.response,
                'confidence': response.confidence
            })

        return alerts


def example_usage():
    """Example of using the integration"""

    # Initialize integration
    integration = SuperTrendBotIntegration()

    # Example signal from existing bot
    base_signal = {
        'symbol': 'BTC/USD',
        'action': 'buy',
        'price': 67234.50,
        'confidence': 0.8,
        'indicators': {
            'supertrend': 65000,
            'atr': 1200,
            'rsi': 58
        }
    }

    # Enhance signal with AI
    enhanced_signals = integration.augment_signals(
        [base_signal],
        llm_analysis=True,
        risk_assessment=True
    )

    print("Enhanced Signal:")
    print(enhanced_signals[0])

    # Validate before execution
    validation = integration.execute_with_validation(
        base_signal,
        confidence_threshold=0.75
    )

    print("\nValidation Result:")
    print(validation)

    # Get position sizing advice
    position_advice = integration.get_position_sizing_advice(
        base_signal,
        account_balance=10000
    )

    print("\nPosition Sizing:")
    print(position_advice)


if __name__ == "__main__":
    example_usage()
