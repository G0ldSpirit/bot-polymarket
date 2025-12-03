"""
Configuration module for the Polymarket Trading Bot.
Loads settings from environment variables.
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv
from loguru import logger

# Load environment variables
load_dotenv()


@dataclass
class TradingConfig:
    """Trading configuration parameters."""
    max_trade_amount: float = 100.0
    min_profit_percentage: float = 2.0
    max_open_positions: int = 5
    stop_loss_percentage: float = 10.0
    take_profit_percentage: float = 20.0
    trading_interval: int = 60
    dry_run: bool = True


@dataclass
class APIConfig:
    """API configuration parameters."""
    host: str = "https://clob.polymarket.com"
    ws_host: str = "wss://ws-subscriptions-clob.polymarket.com/ws"
    chain_id: int = 137


class Config:
    """Main configuration class."""

    def __init__(self):
        self.private_key = os.getenv("PRIVATE_KEY", "")
        self.log_level = os.getenv("LOG_LEVEL", "INFO")

        self.api = APIConfig(
            host=os.getenv("POLYMARKET_HOST", "https://clob.polymarket.com"),
            ws_host=os.getenv("POLYMARKET_WS_HOST", "wss://ws-subscriptions-clob.polymarket.com/ws"),
            chain_id=int(os.getenv("CHAIN_ID", "137"))
        )

        self.trading = TradingConfig(
            max_trade_amount=float(os.getenv("MAX_TRADE_AMOUNT", "100")),
            min_profit_percentage=float(os.getenv("MIN_PROFIT_PERCENTAGE", "2.0")),
            max_open_positions=int(os.getenv("MAX_OPEN_POSITIONS", "5")),
            stop_loss_percentage=float(os.getenv("STOP_LOSS_PERCENTAGE", "10")),
            take_profit_percentage=float(os.getenv("TAKE_PROFIT_PERCENTAGE", "20")),
            trading_interval=int(os.getenv("TRADING_INTERVAL", "60")),
            dry_run=os.getenv("DRY_RUN", "true").lower() == "true"
        )

    def validate(self) -> bool:
        """Validate the configuration."""
        if not self.private_key:
            logger.error("PRIVATE_KEY is required")
            return False

        if len(self.private_key) != 64:
            logger.error("PRIVATE_KEY must be 64 characters (without 0x prefix)")
            return False

        return True

    def display(self):
        """Display current configuration (hiding sensitive data)."""
        logger.info("=== Configuration ===")
        logger.info(f"API Host: {self.api.host}")
        logger.info(f"Chain ID: {self.api.chain_id}")
        logger.info(f"Max Trade Amount: ${self.trading.max_trade_amount}")
        logger.info(f"Min Profit %: {self.trading.min_profit_percentage}%")
        logger.info(f"Max Open Positions: {self.trading.max_open_positions}")
        logger.info(f"Stop Loss: {self.trading.stop_loss_percentage}%")
        logger.info(f"Take Profit: {self.trading.take_profit_percentage}%")
        logger.info(f"Trading Interval: {self.trading.trading_interval}s")
        logger.info(f"Dry Run Mode: {self.trading.dry_run}")
        logger.info("====================")


# Global configuration instance
config = Config()
