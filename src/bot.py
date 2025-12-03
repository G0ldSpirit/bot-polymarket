"""
Main trading bot module.
Orchestrates the trading process.
"""

import time
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger

from .config import config
from .client import polymarket_client, PolymarketClient
from .strategies import BaseStrategy, MomentumStrategy, ArbitrageStrategy, ValueStrategy, BTCArbitrageStrategy
from .strategies.base import TradeSignal, Signal


class TradingBot:
    """
    Main trading bot class.

    Manages strategies, executes trades, and tracks positions.
    """

    def __init__(self):
        self.client: PolymarketClient = polymarket_client
        self.strategies: List[BaseStrategy] = []
        self.positions: Dict[str, Dict] = {}
        self.trade_history: List[Dict] = []
        self.is_running = False
        self.data_dir = Path("data")
        self.data_dir.mkdir(exist_ok=True)

    def initialize(self) -> bool:
        """Initialize the bot and client."""
        logger.info("Initializing trading bot...")

        # Validate configuration
        if not config.validate():
            return False

        config.display()

        # Initialize client
        if not self.client.initialize():
            return False

        # Load saved positions
        self._load_positions()

        logger.success("Trading bot initialized successfully")
        return True

    def add_strategy(self, strategy: BaseStrategy):
        """Add a trading strategy."""
        self.strategies.append(strategy)
        logger.info(f"Added strategy: {strategy.name}")

    def remove_strategy(self, strategy_name: str):
        """Remove a strategy by name."""
        self.strategies = [s for s in self.strategies if s.name != strategy_name]
        logger.info(f"Removed strategy: {strategy_name}")

    def _load_positions(self):
        """Load positions from file."""
        positions_file = self.data_dir / "positions.json"
        if positions_file.exists():
            try:
                with open(positions_file) as f:
                    self.positions = json.load(f)
                logger.info(f"Loaded {len(self.positions)} positions from file")
            except Exception as e:
                logger.warning(f"Could not load positions: {e}")

    def _save_positions(self):
        """Save positions to file."""
        positions_file = self.data_dir / "positions.json"
        try:
            with open(positions_file, "w") as f:
                json.dump(self.positions, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save positions: {e}")

    def _save_trade(self, trade: Dict):
        """Save a trade to history."""
        self.trade_history.append(trade)
        history_file = self.data_dir / "trades_history.json"
        try:
            with open(history_file, "w") as f:
                json.dump(self.trade_history, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save trade history: {e}")

    def _check_stop_loss_take_profit(self) -> List[TradeSignal]:
        """Check positions for stop loss and take profit triggers."""
        signals = []

        for token_id, position in self.positions.items():
            entry_price = position.get("entry_price", 0)
            current_price = self.client.get_price(token_id, "SELL")

            if current_price is None:
                continue

            # Calculate P&L percentage
            if entry_price > 0:
                pnl_pct = ((current_price - entry_price) / entry_price) * 100
            else:
                continue

            # Check stop loss
            if pnl_pct <= -config.trading.stop_loss_percentage:
                logger.warning(
                    f"Stop loss triggered for {token_id[:8]}... "
                    f"Entry: {entry_price:.3f}, Current: {current_price:.3f}, P&L: {pnl_pct:.1f}%"
                )
                signals.append(TradeSignal(
                    signal=Signal.SELL,
                    token_id=token_id,
                    market_id=position.get("market_id", ""),
                    price=current_price,
                    confidence=1.0,
                    reason=f"Stop loss triggered: {pnl_pct:.1f}%"
                ))

            # Check take profit
            elif pnl_pct >= config.trading.take_profit_percentage:
                logger.info(
                    f"Take profit triggered for {token_id[:8]}... "
                    f"Entry: {entry_price:.3f}, Current: {current_price:.3f}, P&L: {pnl_pct:.1f}%"
                )
                signals.append(TradeSignal(
                    signal=Signal.SELL,
                    token_id=token_id,
                    market_id=position.get("market_id", ""),
                    price=current_price,
                    confidence=1.0,
                    reason=f"Take profit triggered: {pnl_pct:.1f}%"
                ))

        return signals

    def _execute_signal(self, signal: TradeSignal) -> bool:
        """Execute a trading signal."""
        try:
            if signal.signal == Signal.BUY:
                # Calculate position size
                balance = self.client.get_balance() or 0
                amount = min(
                    config.trading.max_trade_amount,
                    balance * 0.1 * signal.confidence
                )

                if amount < 1:  # Minimum $1 trade
                    logger.warning("Insufficient balance for trade")
                    return False

                # Check max positions
                if len(self.positions) >= config.trading.max_open_positions:
                    logger.warning("Maximum positions reached")
                    return False

                # Execute buy
                result = self.client.buy(signal.token_id, amount, signal.price)
                if result:
                    # Track position
                    self.positions[signal.token_id] = {
                        "market_id": signal.market_id,
                        "entry_price": signal.price,
                        "amount": amount,
                        "size": amount / signal.price,
                        "entry_time": datetime.now().isoformat(),
                        "reason": signal.reason
                    }
                    self._save_positions()

                    # Save trade
                    self._save_trade({
                        "type": "BUY",
                        "token_id": signal.token_id,
                        "price": signal.price,
                        "amount": amount,
                        "time": datetime.now().isoformat(),
                        "reason": signal.reason
                    })

                    logger.success(f"BUY executed: {amount:.2f} USDC @ {signal.price:.3f}")
                    return True

            elif signal.signal == Signal.SELL:
                if signal.token_id not in self.positions:
                    logger.warning(f"No position to sell for {signal.token_id[:8]}...")
                    return False

                position = self.positions[signal.token_id]
                size = position.get("size", 0)

                if size <= 0:
                    return False

                # Execute sell
                result = self.client.sell(signal.token_id, size, signal.price)
                if result:
                    # Calculate P&L
                    entry_price = position.get("entry_price", 0)
                    pnl = (signal.price - entry_price) * size

                    # Save trade
                    self._save_trade({
                        "type": "SELL",
                        "token_id": signal.token_id,
                        "price": signal.price,
                        "size": size,
                        "pnl": pnl,
                        "time": datetime.now().isoformat(),
                        "reason": signal.reason
                    })

                    # Remove position
                    del self.positions[signal.token_id]
                    self._save_positions()

                    logger.success(f"SELL executed: {size:.2f} shares @ {signal.price:.3f}, P&L: ${pnl:.2f}")
                    return True

            return False

        except Exception as e:
            logger.error(f"Error executing signal: {e}")
            return False

    def run_once(self):
        """Run one iteration of the trading loop."""
        logger.debug("Running trading iteration...")

        # Check stop loss / take profit first
        sl_tp_signals = self._check_stop_loss_take_profit()
        for signal in sl_tp_signals:
            self._execute_signal(signal)

        # Get markets
        markets_response = self.client.get_markets()
        markets = markets_response.get("data", [])

        if not markets:
            logger.warning("No markets available")
            return

        logger.debug(f"Analyzing {len(markets)} markets...")

        # Analyze markets with each strategy
        for market in markets[:50]:  # Increased limit for BTC market search
            condition_id = market.get("condition_id")
            if not condition_id:
                continue

            tokens = market.get("tokens", [])
            if not tokens:
                continue

            # Run strategies
            for strategy in self.strategies:
                if not strategy.is_active:
                    continue

                # Special handling for BTC Arbitrage strategy
                if isinstance(strategy, BTCArbitrageStrategy):
                    signals = strategy.analyze_with_client(market, self.client)
                    for signal in signals:
                        logger.info(f"Signal from {strategy.name}: {signal.signal.value} - {signal.reason}")
                        if signal.signal == Signal.BUY:
                            self._execute_signal(signal)
                    continue

                # Get orderbook for first token
                token_id = tokens[0].get("token_id")
                if not token_id:
                    continue

                orderbook = self.client.get_orderbook(token_id)
                if not orderbook:
                    continue

                signal = strategy.analyze(market, orderbook)
                if signal:
                    logger.info(f"Signal from {strategy.name}: {signal.signal.value} - {signal.reason}")

                    # Check if we should execute
                    if signal.signal == Signal.BUY:
                        if strategy.should_buy(signal, list(self.positions.values())):
                            self._execute_signal(signal)
                    elif signal.signal == Signal.SELL:
                        if signal.token_id in self.positions:
                            position = self.positions[signal.token_id]
                            if strategy.should_sell(signal, position):
                                self._execute_signal(signal)

    def run(self):
        """Run the trading bot continuously."""
        self.is_running = True
        logger.info("Starting trading bot...")

        try:
            while self.is_running:
                self.run_once()
                time.sleep(config.trading.trading_interval)
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        finally:
            self.is_running = False
            self._save_positions()
            logger.info("Trading bot stopped")

    def stop(self):
        """Stop the trading bot."""
        self.is_running = False
        logger.info("Stopping trading bot...")

    def get_status(self) -> Dict[str, Any]:
        """Get current bot status."""
        balance = self.client.get_balance() if self.client._initialized else None

        # Calculate total position value
        position_value = 0
        for token_id, pos in self.positions.items():
            current_price = self.client.get_price(token_id, "SELL") if self.client._initialized else None
            if current_price:
                position_value += pos.get("size", 0) * current_price

        return {
            "is_running": self.is_running,
            "strategies": [str(s) for s in self.strategies],
            "open_positions": len(self.positions),
            "balance": balance,
            "position_value": position_value,
            "total_trades": len(self.trade_history),
            "dry_run": config.trading.dry_run
        }

    def get_positions_summary(self) -> List[Dict]:
        """Get summary of all positions."""
        summary = []
        for token_id, pos in self.positions.items():
            current_price = self.client.get_price(token_id, "SELL") if self.client._initialized else None
            entry_price = pos.get("entry_price", 0)

            pnl = 0
            pnl_pct = 0
            if current_price and entry_price > 0:
                pnl = (current_price - entry_price) * pos.get("size", 0)
                pnl_pct = ((current_price - entry_price) / entry_price) * 100

            summary.append({
                "token_id": token_id[:16] + "...",
                "entry_price": entry_price,
                "current_price": current_price,
                "size": pos.get("size", 0),
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "entry_time": pos.get("entry_time")
            })

        return summary


# Global bot instance
trading_bot = TradingBot()
