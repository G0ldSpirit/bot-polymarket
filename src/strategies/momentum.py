"""
Momentum trading strategy.
Buys when price is trending up, sells when trending down.
"""

from typing import Optional, Dict, Any, List
from collections import deque
from loguru import logger

from .base import BaseStrategy, TradeSignal, Signal


class MomentumStrategy(BaseStrategy):
    """
    Momentum-based trading strategy.

    This strategy tracks price movements and generates signals
    based on momentum indicators.
    """

    def __init__(self, lookback_period: int = 10, momentum_threshold: float = 0.05):
        """
        Initialize the momentum strategy.

        Args:
            lookback_period: Number of price points to consider
            momentum_threshold: Minimum price change to trigger a signal (e.g., 0.05 = 5%)
        """
        super().__init__(name="MomentumStrategy")
        self.lookback_period = lookback_period
        self.momentum_threshold = momentum_threshold
        self.price_history: Dict[str, deque] = {}

    def _update_price_history(self, token_id: str, price: float):
        """Update price history for a token."""
        if token_id not in self.price_history:
            self.price_history[token_id] = deque(maxlen=self.lookback_period)
        self.price_history[token_id].append(price)

    def _calculate_momentum(self, token_id: str) -> Optional[float]:
        """
        Calculate momentum for a token.

        Returns:
            Momentum value (positive = upward, negative = downward)
            None if not enough data
        """
        if token_id not in self.price_history:
            return None

        prices = list(self.price_history[token_id])
        if len(prices) < 3:
            return None

        # Calculate simple momentum: (current - oldest) / oldest
        oldest = prices[0]
        current = prices[-1]

        if oldest == 0:
            return None

        return (current - oldest) / oldest

    def analyze(self, market: Dict[str, Any], orderbook: Dict[str, Any]) -> Optional[TradeSignal]:
        """
        Analyze market for momentum signals.

        Args:
            market: Market data
            orderbook: Orderbook data

        Returns:
            TradeSignal if momentum opportunity found
        """
        if not self.is_active:
            return None

        try:
            # Extract token IDs and prices from market
            tokens = market.get("tokens", [])
            if not tokens:
                return None

            # For each token in the market
            for token in tokens:
                token_id = token.get("token_id")
                if not token_id:
                    continue

                # Get current price from orderbook
                bids = orderbook.get("bids", [])
                asks = orderbook.get("asks", [])

                if not bids and not asks:
                    continue

                # Use mid price
                best_bid = float(bids[0]["price"]) if bids else 0
                best_ask = float(asks[0]["price"]) if asks else 1
                current_price = (best_bid + best_ask) / 2

                # Update price history
                self._update_price_history(token_id, current_price)

                # Calculate momentum
                momentum = self._calculate_momentum(token_id)
                if momentum is None:
                    continue

                logger.debug(f"Token {token_id[:8]}... momentum: {momentum:.4f}")

                # Generate signal based on momentum
                if momentum >= self.momentum_threshold:
                    # Strong upward momentum - BUY signal
                    confidence = min(abs(momentum) / (self.momentum_threshold * 2), 1.0)
                    return TradeSignal(
                        signal=Signal.BUY,
                        token_id=token_id,
                        market_id=market.get("condition_id", ""),
                        price=best_ask,
                        confidence=confidence,
                        reason=f"Strong upward momentum: {momentum:.2%}"
                    )

                elif momentum <= -self.momentum_threshold:
                    # Strong downward momentum - SELL signal
                    confidence = min(abs(momentum) / (self.momentum_threshold * 2), 1.0)
                    return TradeSignal(
                        signal=Signal.SELL,
                        token_id=token_id,
                        market_id=market.get("condition_id", ""),
                        price=best_bid,
                        confidence=confidence,
                        reason=f"Strong downward momentum: {momentum:.2%}"
                    )

            return None

        except Exception as e:
            logger.error(f"Error in momentum analysis: {e}")
            return None

    def get_stats(self) -> Dict[str, Any]:
        """Get strategy statistics."""
        return {
            "name": self.name,
            "lookback_period": self.lookback_period,
            "momentum_threshold": self.momentum_threshold,
            "tracked_tokens": len(self.price_history),
            "is_active": self.is_active
        }
