"""
BTC Arbitrage Strategy - Sequential arbitrage on Bitcoin price prediction markets.

Strategy:
1. First, buy UP (or the cheaper side)
2. Wait for prices to move
3. When spread reaches target profit (e.g., 5%), buy DOWN to lock in arbitrage
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
from loguru import logger

from .base import BaseStrategy, TradeSignal, Signal


class BTCArbitrageStrategy(BaseStrategy):
    """
    BTC Sequential Arbitrage Strategy.

    This strategy:
    1. First buys one side (UP) when price is favorable
    2. Monitors prices and waits for opportunity
    3. Buys the other side (DOWN) when combined cost gives target profit

    Example:
    - Step 1: Buy UP at 0.45
    - Step 2: Wait... DOWN drops to 0.50
    - Step 3: Total = 0.95 → 5% profit locked in
    """

    def __init__(
        self,
        target_profit: float = 0.05,
        max_position_per_side: float = 50.0,
        target_timeframe: str = "1h",
        initial_buy_threshold: float = 0.55
    ):
        """
        Initialize the BTC sequential arbitrage strategy.

        Args:
            target_profit: Target profit to trigger second buy (e.g., 0.05 = 5%)
            max_position_per_side: Maximum USDC per side (UP or DOWN)
            target_timeframe: Timeframe to target ("1h", "4h", "24h")
            initial_buy_threshold: Max price to buy first side (e.g., 0.55 = 55 cents)
        """
        super().__init__(name="BTCArbitrageStrategy")
        self.target_profit = target_profit
        self.max_position_per_side = max_position_per_side
        self.target_timeframe = target_timeframe
        self.initial_buy_threshold = initial_buy_threshold

        # Track our position state
        # State: "waiting" -> "holding_first" -> "completed"
        self.state = "waiting"
        self.first_position: Optional[Dict] = None  # {side, token_id, price, amount, time}

        # Current market info for dashboard
        self.current_market_info: Optional[Dict] = None

        # Data persistence
        self.data_file = Path("data/btc_arb_state.json")
        self._load_state()

    def _load_state(self):
        """Load saved state from file."""
        if self.data_file.exists():
            try:
                with open(self.data_file) as f:
                    data = json.load(f)
                    self.state = data.get("state", "waiting")
                    self.first_position = data.get("first_position")
                    logger.info(f"Loaded BTC arb state: {self.state}")
                    if self.first_position:
                        logger.info(f"Existing position: {self.first_position['side']} @ {self.first_position['price']}")
            except Exception as e:
                logger.warning(f"Could not load state: {e}")

    def _save_state(self):
        """Save state to file."""
        self.data_file.parent.mkdir(exist_ok=True)
        try:
            with open(self.data_file, "w") as f:
                json.dump({
                    "state": self.state,
                    "first_position": self.first_position
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save state: {e}")

    def _is_btc_price_market(self, market: Dict) -> bool:
        """Check if a market is a BTC price prediction market."""
        question = market.get("question", "").lower()
        description = market.get("description", "").lower()

        btc_keywords = ["bitcoin", "btc"]
        price_keywords = ["price", "above", "below", "over", "under", "reach"]
        timeframe_keywords = {
            "1h": ["1 hour", "1h", "one hour", "hourly"],
            "4h": ["4 hour", "4h", "four hour"],
            "24h": ["24 hour", "24h", "daily", "today"]
        }

        is_btc = any(kw in question or kw in description for kw in btc_keywords)
        is_price = any(kw in question or kw in description for kw in price_keywords)

        target_kws = timeframe_keywords.get(self.target_timeframe, [])
        is_target_timeframe = any(kw in question or kw in description for kw in target_kws)

        return is_btc and is_price and is_target_timeframe

    def _get_up_down_tokens(self, market: Dict) -> Optional[Tuple[Dict, Dict]]:
        """Extract UP (YES) and DOWN (NO) tokens from a market."""
        tokens = market.get("tokens", [])
        if len(tokens) != 2:
            return None

        up_token = None
        down_token = None

        for token in tokens:
            outcome = token.get("outcome", "").lower()
            if outcome == "yes":
                up_token = token
            elif outcome == "no":
                down_token = token

        if up_token and down_token:
            return (up_token, down_token)
        return None

    def analyze(self, market: Dict[str, Any], orderbook: Dict[str, Any]) -> Optional[TradeSignal]:
        """Standard analyze method (not used for this strategy)."""
        return None

    def analyze_with_client(self, market: Dict[str, Any], client) -> List[TradeSignal]:
        """
        Analyze market for sequential arbitrage.

        Returns a signal based on current state:
        - If waiting: Look for good entry on first side
        - If holding_first: Check if we can complete arbitrage with profit
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
            market_id = market.get("condition_id", "")

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
            total_cost = up_price + down_price

            # Update dashboard info
            self.current_market_info = {
                "question": market.get("question", ""),
                "condition_id": market_id,
                "up_token_id": up_id,
                "down_token_id": down_id,
                "up_price": up_price,
                "down_price": down_price,
                "total_cost": total_cost,
                "state": self.state,
                "first_position": self.first_position,
                "potential_profit": None,
                "timestamp": datetime.now().isoformat()
            }

            # === STATE MACHINE ===

            if self.state == "waiting":
                # Look for good entry on the cheaper side
                return self._analyze_first_buy(
                    market_id, up_id, down_id, up_price, down_price
                )

            elif self.state == "holding_first":
                # Check if we can complete arbitrage
                return self._analyze_second_buy(
                    market_id, up_id, down_id, up_price, down_price
                )

            return []

        except Exception as e:
            logger.error(f"Error in BTC sequential arbitrage: {e}")
            return []

    def _analyze_first_buy(
        self,
        market_id: str,
        up_id: str,
        down_id: str,
        up_price: float,
        down_price: float
    ) -> List[TradeSignal]:
        """Analyze for first buy opportunity."""

        # Buy the cheaper side if price is below threshold
        if up_price <= down_price and up_price <= self.initial_buy_threshold:
            logger.info(
                f"[Step 1] Good entry for UP @ {up_price:.3f} "
                f"(threshold: {self.initial_buy_threshold})"
            )

            return [TradeSignal(
                signal=Signal.BUY,
                token_id=up_id,
                market_id=market_id,
                price=up_price,
                confidence=0.8,
                reason=f"BTC Arb Step 1: Buy UP @ {up_price:.3f}",
                amount=self.max_position_per_side
            )]

        elif down_price < up_price and down_price <= self.initial_buy_threshold:
            logger.info(
                f"[Step 1] Good entry for DOWN @ {down_price:.3f} "
                f"(threshold: {self.initial_buy_threshold})"
            )

            return [TradeSignal(
                signal=Signal.BUY,
                token_id=down_id,
                market_id=market_id,
                price=down_price,
                confidence=0.8,
                reason=f"BTC Arb Step 1: Buy DOWN @ {down_price:.3f}",
                amount=self.max_position_per_side
            )]

        logger.debug(
            f"Waiting for better entry... UP={up_price:.3f}, DOWN={down_price:.3f}, "
            f"threshold={self.initial_buy_threshold}"
        )
        return []

    def _analyze_second_buy(
        self,
        market_id: str,
        up_id: str,
        down_id: str,
        up_price: float,
        down_price: float
    ) -> List[TradeSignal]:
        """Analyze for second buy to complete arbitrage."""

        if not self.first_position:
            logger.warning("State is holding_first but no position found, resetting")
            self.state = "waiting"
            self._save_state()
            return []

        first_side = self.first_position["side"]
        first_price = self.first_position["price"]

        # Determine second side price
        if first_side == "UP":
            second_side = "DOWN"
            second_token_id = down_id
            second_price = down_price
        else:
            second_side = "UP"
            second_token_id = up_id
            second_price = up_price

        # Calculate potential profit
        total_cost = first_price + second_price
        potential_profit = 1 - total_cost
        profit_pct = (potential_profit / total_cost) * 100 if total_cost > 0 else 0

        # Update dashboard
        if self.current_market_info:
            self.current_market_info["potential_profit"] = profit_pct
            self.current_market_info["first_side"] = first_side
            self.current_market_info["first_price"] = first_price

        logger.info(
            f"[Step 2] Checking... First: {first_side} @ {first_price:.3f}, "
            f"Second: {second_side} @ {second_price:.3f}, "
            f"Total: {total_cost:.3f}, Profit: {profit_pct:.1f}%"
        )

        # Check if profit target is reached
        if potential_profit >= self.target_profit:
            logger.success(
                f"[Step 2] ARBITRAGE COMPLETE! "
                f"Total cost: {total_cost:.3f}, Profit: {profit_pct:.1f}%"
            )

            return [TradeSignal(
                signal=Signal.BUY,
                token_id=second_token_id,
                market_id=market_id,
                price=second_price,
                confidence=1.0,
                reason=f"BTC Arb Step 2: Buy {second_side} @ {second_price:.3f}, LOCK {profit_pct:.1f}% profit!",
                amount=self.max_position_per_side
            )]

        logger.debug(
            f"Waiting for {self.target_profit*100:.0f}% profit... "
            f"Current: {profit_pct:.1f}%"
        )
        return []

    def on_trade_executed(self, trade: Dict):
        """
        Called when a trade is executed. Updates strategy state.

        Args:
            trade: Trade details {type, token_id, price, amount, ...}
        """
        if trade.get("type") != "BUY":
            return

        token_id = trade.get("token_id", "")
        price = trade.get("price", 0)

        # Check if this is our market
        if not self.current_market_info:
            return

        up_id = self.current_market_info.get("up_token_id", "")
        down_id = self.current_market_info.get("down_token_id", "")

        if token_id not in [up_id, down_id]:
            return

        if self.state == "waiting":
            # First buy executed
            side = "UP" if token_id == up_id else "DOWN"
            self.first_position = {
                "side": side,
                "token_id": token_id,
                "price": price,
                "amount": trade.get("amount", 0),
                "time": datetime.now().isoformat()
            }
            self.state = "holding_first"
            self._save_state()

            logger.success(f"[State] First position recorded: {side} @ {price:.3f}")

        elif self.state == "holding_first":
            # Second buy executed - arbitrage complete!
            self.state = "completed"
            self._save_state()

            first_price = self.first_position["price"] if self.first_position else 0
            total_cost = first_price + price
            profit_pct = ((1 - total_cost) / total_cost) * 100

            logger.success(
                f"[State] ARBITRAGE COMPLETED! "
                f"Total invested: ${total_cost:.3f}, Guaranteed profit: {profit_pct:.1f}%"
            )

            # Reset for next round after a delay
            self.state = "waiting"
            self.first_position = None
            self._save_state()

    def reset(self):
        """Reset strategy state to start fresh."""
        self.state = "waiting"
        self.first_position = None
        self._save_state()
        logger.info("BTC Arbitrage strategy reset to initial state")

    def get_btc_market_info(self) -> Optional[Dict]:
        """Get current BTC market info for dashboard."""
        return self.current_market_info

    def get_stats(self) -> Dict[str, Any]:
        """Get strategy statistics."""
        return {
            "name": self.name,
            "state": self.state,
            "target_profit": f"{self.target_profit*100:.0f}%",
            "max_position_per_side": self.max_position_per_side,
            "target_timeframe": self.target_timeframe,
            "initial_buy_threshold": self.initial_buy_threshold,
            "first_position": self.first_position,
            "is_active": self.is_active
        }


# Global instance
btc_arbitrage_strategy = BTCArbitrageStrategy()
