"""
BTC Arbitrage Strategy - Specialized strategy for Bitcoin price prediction markets.
Buys both UP and DOWN positions to profit from arbitrage opportunities.
"""

import re
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
from loguru import logger

from .base import BaseStrategy, TradeSignal, Signal


class BTCArbitrageStrategy(BaseStrategy):
    """
    BTC Arbitrage Strategy.

    This strategy searches for Bitcoin price prediction markets (1H timeframe)
    and executes arbitrage by buying both UP and DOWN when their combined
    price is less than 1.

    Example: If UP costs 0.45 and DOWN costs 0.48, total = 0.93
    Buying both guarantees a profit of 0.07 (7%) regardless of outcome.
    """

    def __init__(
        self,
        min_spread: float = 0.02,
        max_position_per_side: float = 50.0,
        target_timeframe: str = "1h"
    ):
        """
        Initialize the BTC arbitrage strategy.

        Args:
            min_spread: Minimum spread to trigger arbitrage (e.g., 0.02 = 2%)
            max_position_per_side: Maximum USDC per side (UP or DOWN)
            target_timeframe: Timeframe to target ("1h", "4h", "24h")
        """
        super().__init__(name="BTCArbitrageStrategy")
        self.min_spread = min_spread
        self.max_position_per_side = max_position_per_side
        self.target_timeframe = target_timeframe

        # Cache for BTC markets
        self.btc_markets: List[Dict] = []
        self.last_market_scan = None
        self.scan_interval = timedelta(minutes=5)

        # Track our arbitrage positions
        self.arb_positions: Dict[str, Dict] = {}

        # Current market info for dashboard
        self.current_market_info: Optional[Dict] = None

    def _is_btc_price_market(self, market: Dict) -> bool:
        """Check if a market is a BTC price prediction market."""
        question = market.get("question", "").lower()
        description = market.get("description", "").lower()

        # Keywords to identify BTC price markets
        btc_keywords = ["bitcoin", "btc"]
        price_keywords = ["price", "above", "below", "over", "under", "reach"]
        timeframe_keywords = {
            "1h": ["1 hour", "1h", "one hour", "hourly"],
            "4h": ["4 hour", "4h", "four hour"],
            "24h": ["24 hour", "24h", "daily", "today"]
        }

        # Check if it's a BTC market
        is_btc = any(kw in question or kw in description for kw in btc_keywords)
        is_price = any(kw in question or kw in description for kw in price_keywords)

        # Check timeframe
        target_kws = timeframe_keywords.get(self.target_timeframe, [])
        is_target_timeframe = any(kw in question or kw in description for kw in target_kws)

        return is_btc and is_price and is_target_timeframe

    def _get_up_down_tokens(self, market: Dict) -> Optional[Tuple[Dict, Dict]]:
        """
        Extract UP and DOWN tokens from a market.

        Returns:
            Tuple of (up_token, down_token) or None if not found
        """
        tokens = market.get("tokens", [])
        if len(tokens) != 2:
            return None

        up_token = None
        down_token = None

        for token in tokens:
            outcome = token.get("outcome", "").lower()
            # Polymarket uses "Yes"/"No" but context determines if it's up or down
            # Check the question to determine direction
            if outcome == "yes":
                up_token = token
            elif outcome == "no":
                down_token = token

        if up_token and down_token:
            return (up_token, down_token)
        return None

    def scan_for_btc_markets(self, all_markets: List[Dict]):
        """Scan all markets to find BTC price markets."""
        self.btc_markets = []

        for market in all_markets:
            if self._is_btc_price_market(market):
                self.btc_markets.append(market)
                logger.info(f"Found BTC market: {market.get('question', '')[:50]}...")

        self.last_market_scan = datetime.now()
        logger.info(f"Found {len(self.btc_markets)} BTC price markets")

    def _calculate_arbitrage_opportunity(
        self,
        up_price: float,
        down_price: float
    ) -> Tuple[bool, float, float]:
        """
        Calculate if there's an arbitrage opportunity.

        Args:
            up_price: Price of UP/YES token
            down_price: Price of DOWN/NO token

        Returns:
            Tuple of (is_opportunity, spread, expected_profit_pct)
        """
        total_cost = up_price + down_price
        spread = 1 - total_cost  # Positive spread = profit opportunity

        if total_cost > 0:
            expected_profit_pct = (spread / total_cost) * 100
        else:
            expected_profit_pct = 0

        is_opportunity = spread >= self.min_spread

        return (is_opportunity, spread, expected_profit_pct)

    def analyze(self, market: Dict[str, Any], orderbook: Dict[str, Any]) -> Optional[TradeSignal]:
        """
        Analyze a market for BTC arbitrage opportunities.

        Note: This method expects orderbook to be a dict keyed by token_id
        containing orderbooks for both UP and DOWN tokens.
        """
        if not self.is_active:
            return None

        try:
            # Check if this is a BTC market
            if not self._is_btc_price_market(market):
                return None

            # Get UP and DOWN tokens
            tokens = self._get_up_down_tokens(market)
            if not tokens:
                return None

            up_token, down_token = tokens
            up_id = up_token.get("token_id")
            down_id = down_token.get("token_id")

            # We need orderbooks for both tokens
            # If orderbook is a single orderbook, we can't do arbitrage analysis
            if isinstance(orderbook, dict) and "bids" in orderbook and "asks" in orderbook:
                # Single orderbook - need to fetch the other one externally
                # For now, just store what we have
                return None

            # If we have multi-orderbook format
            if up_id not in orderbook or down_id not in orderbook:
                return None

            up_book = orderbook[up_id]
            down_book = orderbook[down_id]

            # Get best ask prices (cost to buy)
            up_asks = up_book.get("asks", [])
            down_asks = down_book.get("asks", [])

            if not up_asks or not down_asks:
                return None

            up_price = float(up_asks[0]["price"])
            down_price = float(down_asks[0]["price"])

            # Update current market info for dashboard
            self.current_market_info = {
                "question": market.get("question", ""),
                "condition_id": market.get("condition_id", ""),
                "up_token_id": up_id,
                "down_token_id": down_id,
                "up_price": up_price,
                "down_price": down_price,
                "total_cost": up_price + down_price,
                "timestamp": datetime.now().isoformat()
            }

            # Check for arbitrage opportunity
            is_opportunity, spread, profit_pct = self._calculate_arbitrage_opportunity(
                up_price, down_price
            )

            if is_opportunity:
                logger.info(
                    f"BTC Arbitrage opportunity found! "
                    f"UP: {up_price:.3f}, DOWN: {down_price:.3f}, "
                    f"Spread: {spread:.3f}, Profit: {profit_pct:.1f}%"
                )

                # Return signal to buy the cheaper side first
                # The bot should then also buy the other side
                if up_price <= down_price:
                    return TradeSignal(
                        signal=Signal.BUY,
                        token_id=up_id,
                        market_id=market.get("condition_id", ""),
                        price=up_price,
                        confidence=min(profit_pct / 10, 1.0),
                        reason=f"BTC Arbitrage: UP @ {up_price:.3f}, DOWN @ {down_price:.3f}, profit {profit_pct:.1f}%",
                        amount=self.max_position_per_side
                    )
                else:
                    return TradeSignal(
                        signal=Signal.BUY,
                        token_id=down_id,
                        market_id=market.get("condition_id", ""),
                        price=down_price,
                        confidence=min(profit_pct / 10, 1.0),
                        reason=f"BTC Arbitrage: DOWN @ {down_price:.3f}, UP @ {up_price:.3f}, profit {profit_pct:.1f}%",
                        amount=self.max_position_per_side
                    )

            return None

        except Exception as e:
            logger.error(f"Error in BTC arbitrage analysis: {e}")
            return None

    def analyze_with_client(self, market: Dict[str, Any], client) -> List[TradeSignal]:
        """
        Analyze a market using the client to fetch both orderbooks.
        Returns signals for both UP and DOWN if arbitrage is found.
        """
        if not self.is_active:
            return []

        try:
            if not self._is_btc_price_market(market):
                return []

            tokens = self._get_up_down_tokens(market)
            if not tokens:
                return []

            up_token, down_token = tokens
            up_id = up_token.get("token_id")
            down_id = down_token.get("token_id")

            # Fetch both orderbooks
            up_book = client.get_orderbook(up_id)
            down_book = client.get_orderbook(down_id)

            if not up_book or not down_book:
                return []

            up_asks = up_book.get("asks", [])
            down_asks = down_book.get("asks", [])

            if not up_asks or not down_asks:
                return []

            up_price = float(up_asks[0]["price"])
            down_price = float(down_asks[0]["price"])

            # Update dashboard info
            self.current_market_info = {
                "question": market.get("question", ""),
                "condition_id": market.get("condition_id", ""),
                "up_token_id": up_id,
                "down_token_id": down_id,
                "up_price": up_price,
                "down_price": down_price,
                "total_cost": up_price + down_price,
                "timestamp": datetime.now().isoformat()
            }

            # Check arbitrage
            is_opportunity, spread, profit_pct = self._calculate_arbitrage_opportunity(
                up_price, down_price
            )

            if is_opportunity:
                logger.info(
                    f"BTC Arbitrage: UP={up_price:.3f} + DOWN={down_price:.3f} = "
                    f"{up_price + down_price:.3f}, profit={profit_pct:.1f}%"
                )

                signals = []
                confidence = min(profit_pct / 10, 1.0)

                # Buy UP
                signals.append(TradeSignal(
                    signal=Signal.BUY,
                    token_id=up_id,
                    market_id=market.get("condition_id", ""),
                    price=up_price,
                    confidence=confidence,
                    reason=f"BTC Arb UP: {profit_pct:.1f}% profit",
                    amount=self.max_position_per_side
                ))

                # Buy DOWN
                signals.append(TradeSignal(
                    signal=Signal.BUY,
                    token_id=down_id,
                    market_id=market.get("condition_id", ""),
                    price=down_price,
                    confidence=confidence,
                    reason=f"BTC Arb DOWN: {profit_pct:.1f}% profit",
                    amount=self.max_position_per_side
                ))

                return signals

            return []

        except Exception as e:
            logger.error(f"Error analyzing BTC market: {e}")
            return []

    def get_btc_market_info(self) -> Optional[Dict]:
        """Get current BTC market info for dashboard."""
        return self.current_market_info

    def get_stats(self) -> Dict[str, Any]:
        """Get strategy statistics."""
        return {
            "name": self.name,
            "min_spread": self.min_spread,
            "max_position_per_side": self.max_position_per_side,
            "target_timeframe": self.target_timeframe,
            "btc_markets_found": len(self.btc_markets),
            "current_opportunity": self.current_market_info is not None,
            "is_active": self.is_active
        }


# Global instance
btc_arbitrage_strategy = BTCArbitrageStrategy()
