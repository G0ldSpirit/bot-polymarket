"""
Arbitrage trading strategy.
Looks for mispriced markets where YES + NO prices don't sum to 1.
"""

from typing import Optional, Dict, Any, List, Tuple
from loguru import logger

from .base import BaseStrategy, TradeSignal, Signal


class ArbitrageStrategy(BaseStrategy):
    """
    Arbitrage-based trading strategy.

    This strategy looks for arbitrage opportunities in prediction markets
    where the sum of YES and NO token prices deviates from 1.
    """

    def __init__(self, min_spread: float = 0.02, min_profit: float = 0.01):
        """
        Initialize the arbitrage strategy.

        Args:
            min_spread: Minimum spread to consider (e.g., 0.02 = 2%)
            min_profit: Minimum expected profit after fees (e.g., 0.01 = 1%)
        """
        super().__init__(name="ArbitrageStrategy")
        self.min_spread = min_spread
        self.min_profit = min_profit

    def _get_token_prices(
        self,
        market: Dict[str, Any],
        orderbooks: Dict[str, Dict[str, Any]]
    ) -> Optional[Tuple[str, float, str, float]]:
        """
        Get YES and NO token prices from orderbooks.

        Returns:
            Tuple of (yes_token_id, yes_price, no_token_id, no_price) or None
        """
        tokens = market.get("tokens", [])
        if len(tokens) != 2:
            return None

        yes_token = None
        no_token = None

        for token in tokens:
            outcome = token.get("outcome", "").lower()
            if outcome == "yes":
                yes_token = token
            elif outcome == "no":
                no_token = token

        if not yes_token or not no_token:
            return None

        yes_id = yes_token.get("token_id")
        no_id = no_token.get("token_id")

        if yes_id not in orderbooks or no_id not in orderbooks:
            return None

        yes_book = orderbooks[yes_id]
        no_book = orderbooks[no_id]

        # Get best ask prices (cost to buy)
        yes_asks = yes_book.get("asks", [])
        no_asks = no_book.get("asks", [])

        if not yes_asks or not no_asks:
            return None

        yes_price = float(yes_asks[0]["price"])
        no_price = float(no_asks[0]["price"])

        return (yes_id, yes_price, no_id, no_price)

    def analyze(self, market: Dict[str, Any], orderbook: Dict[str, Any]) -> Optional[TradeSignal]:
        """
        Analyze market for arbitrage opportunities.

        Note: This method needs both YES and NO orderbooks. The orderbook parameter
        should be a dict containing both token orderbooks keyed by token_id.

        Args:
            market: Market data
            orderbook: Dict of orderbooks keyed by token_id

        Returns:
            TradeSignal if arbitrage opportunity found
        """
        if not self.is_active:
            return None

        try:
            tokens = market.get("tokens", [])
            if len(tokens) != 2:
                return None

            # Check if orderbook is keyed by token_id (multi-orderbook format)
            if not isinstance(orderbook, dict):
                return None

            # Try to detect if this is a single orderbook or multi-orderbook
            if "bids" in orderbook and "asks" in orderbook:
                # Single orderbook format - can't do arbitrage analysis
                return None

            prices = self._get_token_prices(market, orderbook)
            if not prices:
                return None

            yes_id, yes_price, no_id, no_price = prices
            total_cost = yes_price + no_price

            logger.debug(
                f"Market {market.get('question', '')[:30]}... "
                f"YES: {yes_price:.3f}, NO: {no_price:.3f}, Total: {total_cost:.3f}"
            )

            # Arbitrage opportunity: if total < 1, we can profit by buying both
            if total_cost < (1 - self.min_spread):
                expected_profit = 1 - total_cost
                if expected_profit >= self.min_profit:
                    # Buy the cheaper one
                    if yes_price < no_price:
                        return TradeSignal(
                            signal=Signal.BUY,
                            token_id=yes_id,
                            market_id=market.get("condition_id", ""),
                            price=yes_price,
                            confidence=min(expected_profit / 0.1, 1.0),
                            reason=f"Arbitrage opportunity: total cost {total_cost:.3f}, expected profit {expected_profit:.2%}"
                        )
                    else:
                        return TradeSignal(
                            signal=Signal.BUY,
                            token_id=no_id,
                            market_id=market.get("condition_id", ""),
                            price=no_price,
                            confidence=min(expected_profit / 0.1, 1.0),
                            reason=f"Arbitrage opportunity: total cost {total_cost:.3f}, expected profit {expected_profit:.2%}"
                        )

            # Overpriced market: if total > 1, one side is overvalued
            elif total_cost > (1 + self.min_spread):
                # This indicates we might want to sell if we have positions
                overpricing = total_cost - 1
                if overpricing >= self.min_profit:
                    # Sell the more expensive one
                    if yes_price > no_price:
                        return TradeSignal(
                            signal=Signal.SELL,
                            token_id=yes_id,
                            market_id=market.get("condition_id", ""),
                            price=yes_price,
                            confidence=min(overpricing / 0.1, 1.0),
                            reason=f"Overpriced market: total cost {total_cost:.3f}, overpricing {overpricing:.2%}"
                        )
                    else:
                        return TradeSignal(
                            signal=Signal.SELL,
                            token_id=no_id,
                            market_id=market.get("condition_id", ""),
                            price=no_price,
                            confidence=min(overpricing / 0.1, 1.0),
                            reason=f"Overpriced market: total cost {total_cost:.3f}, overpricing {overpricing:.2%}"
                        )

            return None

        except Exception as e:
            logger.error(f"Error in arbitrage analysis: {e}")
            return None

    def get_stats(self) -> Dict[str, Any]:
        """Get strategy statistics."""
        return {
            "name": self.name,
            "min_spread": self.min_spread,
            "min_profit": self.min_profit,
            "is_active": self.is_active
        }
