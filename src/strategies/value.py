"""
Value trading strategy.
Looks for undervalued markets based on probability assessment.
"""

from typing import Optional, Dict, Any, List
from loguru import logger

from .base import BaseStrategy, TradeSignal, Signal


class ValueStrategy(BaseStrategy):
    """
    Value-based trading strategy.

    This strategy analyzes market prices and looks for opportunities
    where the market price seems to deviate from reasonable probability.
    """

    def __init__(
        self,
        min_edge: float = 0.10,
        max_price: float = 0.85,
        min_price: float = 0.15
    ):
        """
        Initialize the value strategy.

        Args:
            min_edge: Minimum edge required to trade (e.g., 0.10 = 10%)
            max_price: Maximum price to buy (avoid near-certain outcomes)
            min_price: Minimum price to consider (avoid extreme longshots)
        """
        super().__init__(name="ValueStrategy")
        self.min_edge = min_edge
        self.max_price = max_price
        self.min_price = min_price
        self.watched_markets: Dict[str, Dict] = {}

    def set_fair_value(self, token_id: str, fair_value: float, notes: str = ""):
        """
        Set the fair value estimate for a token.

        Args:
            token_id: The token ID
            fair_value: Estimated fair probability (0-1)
            notes: Optional notes about the assessment
        """
        self.watched_markets[token_id] = {
            "fair_value": fair_value,
            "notes": notes
        }
        logger.info(f"Set fair value for {token_id[:8]}... to {fair_value:.2f}")

    def analyze(self, market: Dict[str, Any], orderbook: Dict[str, Any]) -> Optional[TradeSignal]:
        """
        Analyze market for value opportunities.

        Args:
            market: Market data
            orderbook: Orderbook data

        Returns:
            TradeSignal if value opportunity found
        """
        if not self.is_active:
            return None

        try:
            tokens = market.get("tokens", [])
            if not tokens:
                return None

            for token in tokens:
                token_id = token.get("token_id")
                if not token_id:
                    continue

                # Skip if we don't have a fair value estimate
                if token_id not in self.watched_markets:
                    continue

                fair_value = self.watched_markets[token_id]["fair_value"]

                # Get current price
                asks = orderbook.get("asks", [])
                bids = orderbook.get("bids", [])

                if not asks and not bids:
                    continue

                best_ask = float(asks[0]["price"]) if asks else None
                best_bid = float(bids[0]["price"]) if bids else None

                # Check for buy opportunity (market undervalued)
                if best_ask and self.min_price <= best_ask <= self.max_price:
                    edge = fair_value - best_ask
                    if edge >= self.min_edge:
                        confidence = min(edge / (self.min_edge * 2), 1.0)
                        return TradeSignal(
                            signal=Signal.BUY,
                            token_id=token_id,
                            market_id=market.get("condition_id", ""),
                            price=best_ask,
                            confidence=confidence,
                            reason=f"Value buy: market @ {best_ask:.2f}, fair value {fair_value:.2f}, edge {edge:.2%}"
                        )

                # Check for sell opportunity (market overvalued)
                if best_bid:
                    edge = best_bid - fair_value
                    if edge >= self.min_edge:
                        confidence = min(edge / (self.min_edge * 2), 1.0)
                        return TradeSignal(
                            signal=Signal.SELL,
                            token_id=token_id,
                            market_id=market.get("condition_id", ""),
                            price=best_bid,
                            confidence=confidence,
                            reason=f"Value sell: market @ {best_bid:.2f}, fair value {fair_value:.2f}, edge {edge:.2%}"
                        )

            return None

        except Exception as e:
            logger.error(f"Error in value analysis: {e}")
            return None

    def remove_watch(self, token_id: str):
        """Remove a token from the watch list."""
        if token_id in self.watched_markets:
            del self.watched_markets[token_id]
            logger.info(f"Removed {token_id[:8]}... from watch list")

    def get_watched_markets(self) -> Dict[str, Dict]:
        """Get all watched markets with fair values."""
        return self.watched_markets.copy()

    def get_stats(self) -> Dict[str, Any]:
        """Get strategy statistics."""
        return {
            "name": self.name,
            "min_edge": self.min_edge,
            "max_price": self.max_price,
            "min_price": self.min_price,
            "watched_markets": len(self.watched_markets),
            "is_active": self.is_active
        }
