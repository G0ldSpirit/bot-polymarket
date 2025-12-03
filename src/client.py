"""
Polymarket API Client module.
Handles all interactions with the Polymarket CLOB API.
"""

from typing import Optional, List, Dict, Any
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds, OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY, SELL
from eth_account import Account
from loguru import logger

from .config import config


class PolymarketClient:
    """Client for interacting with Polymarket CLOB API."""

    def __init__(self):
        self.client: Optional[ClobClient] = None
        self.address: Optional[str] = None
        self._initialized = False

    def initialize(self) -> bool:
        """Initialize the client with credentials."""
        try:
            # Create account from private key
            account = Account.from_key(config.private_key)
            self.address = account.address

            logger.info(f"Initializing client for address: {self.address}")

            # Initialize CLOB client
            self.client = ClobClient(
                host=config.api.host,
                key=config.private_key,
                chain_id=config.api.chain_id
            )

            # Derive API credentials
            self.client.set_api_creds(self.client.derive_api_key())

            self._initialized = True
            logger.success("Polymarket client initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize client: {e}")
            return False

    def get_markets(self, next_cursor: str = "") -> Dict[str, Any]:
        """Get available markets."""
        if not self._initialized:
            raise RuntimeError("Client not initialized")

        try:
            return self.client.get_markets(next_cursor=next_cursor)
        except Exception as e:
            logger.error(f"Failed to get markets: {e}")
            return {"data": [], "next_cursor": ""}

    def get_market(self, condition_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific market by condition ID."""
        if not self._initialized:
            raise RuntimeError("Client not initialized")

        try:
            return self.client.get_market(condition_id)
        except Exception as e:
            logger.error(f"Failed to get market {condition_id}: {e}")
            return None

    def get_orderbook(self, token_id: str) -> Optional[Dict[str, Any]]:
        """Get orderbook for a token."""
        if not self._initialized:
            raise RuntimeError("Client not initialized")

        try:
            return self.client.get_order_book(token_id)
        except Exception as e:
            logger.error(f"Failed to get orderbook: {e}")
            return None

    def get_price(self, token_id: str, side: str = BUY) -> Optional[float]:
        """Get the current best price for a token."""
        if not self._initialized:
            raise RuntimeError("Client not initialized")

        try:
            orderbook = self.get_orderbook(token_id)
            if not orderbook:
                return None

            if side == BUY:
                asks = orderbook.get("asks", [])
                if asks:
                    return float(asks[0]["price"])
            else:
                bids = orderbook.get("bids", [])
                if bids:
                    return float(bids[0]["price"])

            return None
        except Exception as e:
            logger.error(f"Failed to get price: {e}")
            return None

    def get_balance(self) -> Optional[float]:
        """Get USDC balance."""
        if not self._initialized:
            raise RuntimeError("Client not initialized")

        try:
            # Get collateral balance
            balance_info = self.client.get_balance_allowance()
            return float(balance_info.get("balance", 0)) / 1e6  # USDC has 6 decimals
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return None

    def get_positions(self) -> List[Dict[str, Any]]:
        """Get current positions."""
        if not self._initialized:
            raise RuntimeError("Client not initialized")

        try:
            return self.client.get_positions() or []
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return []

    def create_order(
        self,
        token_id: str,
        side: str,
        price: float,
        size: float,
        order_type: OrderType = OrderType.GTC
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new order.

        Args:
            token_id: The token ID to trade
            side: BUY or SELL
            price: Price per share (0-1)
            size: Number of shares
            order_type: Order type (GTC, FOK, GTD)

        Returns:
            Order response or None if failed
        """
        if not self._initialized:
            raise RuntimeError("Client not initialized")

        try:
            logger.info(f"Creating {side} order: {size} shares @ ${price}")

            if config.trading.dry_run:
                logger.warning("[DRY RUN] Order would be placed but dry run is enabled")
                return {"dry_run": True, "side": side, "price": price, "size": size}

            # Build and sign the order
            order_args = OrderArgs(
                token_id=token_id,
                price=price,
                size=size,
                side=side,
                fee_rate_bps=0
            )

            signed_order = self.client.create_order(order_args)
            response = self.client.post_order(signed_order, order_type)

            logger.success(f"Order placed successfully: {response}")
            return response

        except Exception as e:
            logger.error(f"Failed to create order: {e}")
            return None

    def buy(self, token_id: str, amount_usdc: float, price: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Buy shares of a token.

        Args:
            token_id: The token ID to buy
            amount_usdc: Amount in USDC to spend
            price: Optional limit price (uses market price if not specified)

        Returns:
            Order response or None if failed
        """
        if price is None:
            price = self.get_price(token_id, BUY)
            if price is None:
                logger.error("Could not determine market price")
                return None

        # Calculate size (number of shares)
        size = amount_usdc / price

        return self.create_order(token_id, BUY, price, size)

    def sell(self, token_id: str, size: float, price: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Sell shares of a token.

        Args:
            token_id: The token ID to sell
            size: Number of shares to sell
            price: Optional limit price (uses market price if not specified)

        Returns:
            Order response or None if failed
        """
        if price is None:
            price = self.get_price(token_id, SELL)
            if price is None:
                logger.error("Could not determine market price")
                return None

        return self.create_order(token_id, SELL, price, size)

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing order."""
        if not self._initialized:
            raise RuntimeError("Client not initialized")

        try:
            if config.trading.dry_run:
                logger.warning(f"[DRY RUN] Would cancel order {order_id}")
                return True

            self.client.cancel(order_id)
            logger.success(f"Order {order_id} cancelled")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order: {e}")
            return False

    def cancel_all_orders(self) -> bool:
        """Cancel all open orders."""
        if not self._initialized:
            raise RuntimeError("Client not initialized")

        try:
            if config.trading.dry_run:
                logger.warning("[DRY RUN] Would cancel all orders")
                return True

            self.client.cancel_all()
            logger.success("All orders cancelled")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel all orders: {e}")
            return False

    def get_open_orders(self) -> List[Dict[str, Any]]:
        """Get all open orders."""
        if not self._initialized:
            raise RuntimeError("Client not initialized")

        try:
            return self.client.get_orders() or []
        except Exception as e:
            logger.error(f"Failed to get open orders: {e}")
            return []


# Global client instance
polymarket_client = PolymarketClient()
