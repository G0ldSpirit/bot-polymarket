"""
Base strategy class for the Polymarket Trading Bot.
All strategies should inherit from this class.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
from loguru import logger


class Signal(Enum):
    """Trading signal types."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class TradeSignal:
    """Represents a trading signal."""
    signal: Signal
    token_id: str
    market_id: str
    price: float
    confidence: float  # 0-1
    reason: str
    amount: Optional[float] = None  # Suggested amount in USDC


class BaseStrategy(ABC):
    """
    Base class for trading strategies.

    All strategies must implement the analyze() method which takes
    market data and returns trading signals.
    """

    def __init__(self, name: str = "BaseStrategy"):
        self.name = name
        self.is_active = True
        logger.info(f"Strategy '{name}' initialized")

    @abstractmethod
    def analyze(self, market: Dict[str, Any], orderbook: Dict[str, Any]) -> Optional[TradeSignal]:
        """
        Analyze a market and return a trading signal.

        Args:
            market: Market data from Polymarket API
            orderbook: Orderbook data for the market

        Returns:
            TradeSignal if an opportunity is found, None otherwise
        """
        pass

    def should_buy(self, signal: TradeSignal, current_positions: List[Dict]) -> bool:
        """
        Determine if we should execute a buy based on the signal.

        Args:
            signal: The trading signal
            current_positions: Current open positions

        Returns:
            True if we should buy, False otherwise
        """
        if signal.signal != Signal.BUY:
            return False

        # Check if we already have a position in this market
        for pos in current_positions:
            if pos.get("token_id") == signal.token_id:
                logger.debug(f"Already have position in {signal.token_id}")
                return False

        return signal.confidence >= 0.6

    def should_sell(self, signal: TradeSignal, position: Dict[str, Any]) -> bool:
        """
        Determine if we should execute a sell based on the signal.

        Args:
            signal: The trading signal
            position: Current position data

        Returns:
            True if we should sell, False otherwise
        """
        if signal.signal != Signal.SELL:
            return False

        return signal.confidence >= 0.5

    def calculate_position_size(
        self,
        signal: TradeSignal,
        balance: float,
        max_trade_amount: float
    ) -> float:
        """
        Calculate the position size based on signal confidence and available balance.

        Args:
            signal: The trading signal
            balance: Available balance in USDC
            max_trade_amount: Maximum amount per trade

        Returns:
            Position size in USDC
        """
        # Scale position size based on confidence
        base_amount = min(balance * 0.1, max_trade_amount)  # Max 10% of balance per trade
        scaled_amount = base_amount * signal.confidence

        return round(scaled_amount, 2)

    def activate(self):
        """Activate the strategy."""
        self.is_active = True
        logger.info(f"Strategy '{self.name}' activated")

    def deactivate(self):
        """Deactivate the strategy."""
        self.is_active = False
        logger.info(f"Strategy '{self.name}' deactivated")

    def __str__(self) -> str:
        status = "active" if self.is_active else "inactive"
        return f"{self.name} ({status})"
