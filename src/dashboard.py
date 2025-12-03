"""
Dashboard module - Real-time terminal interface for monitoring the bot.
"""

import os
import sys
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn
from loguru import logger

from .config import config
from .bot import trading_bot


class Dashboard:
    """Real-time terminal dashboard for the trading bot."""

    def __init__(self):
        self.console = Console()
        self.is_running = False
        self.refresh_rate = 2  # seconds
        self.stats = {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "total_pnl": 0.0,
            "best_trade": 0.0,
            "worst_trade": 0.0,
            "start_time": None,
            "start_balance": 0.0
        }

    def _create_header(self) -> Panel:
        """Create the header panel."""
        grid = Table.grid(expand=True)
        grid.add_column(justify="left")
        grid.add_column(justify="center")
        grid.add_column(justify="right")

        mode = "[yellow]DRY RUN[/yellow]" if config.trading.dry_run else "[green]LIVE[/green]"
        status = "[green]● RUNNING[/green]" if trading_bot.is_running else "[red]● STOPPED[/red]"

        grid.add_row(
            "[bold blue]Polymarket Trading Bot[/bold blue]",
            f"Mode: {mode}",
            status
        )

        return Panel(grid, style="white on blue")

    def _create_balance_panel(self) -> Panel:
        """Create balance and P&L panel."""
        balance = trading_bot.client.get_balance() if trading_bot.client._initialized else 0

        # Calculate session P&L
        if self.stats["start_balance"] > 0:
            session_pnl = balance - self.stats["start_balance"] if balance else 0
            session_pnl_pct = (session_pnl / self.stats["start_balance"]) * 100
        else:
            session_pnl = 0
            session_pnl_pct = 0

        pnl_color = "green" if session_pnl >= 0 else "red"

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Label", style="cyan")
        table.add_column("Value", justify="right")

        table.add_row("Balance", f"[bold]${balance:.2f}[/bold]" if balance else "N/A")
        table.add_row("Session P&L", f"[{pnl_color}]${session_pnl:+.2f} ({session_pnl_pct:+.1f}%)[/{pnl_color}]")
        table.add_row("Total P&L", f"[{pnl_color}]${self.stats['total_pnl']:+.2f}[/{pnl_color}]")

        return Panel(table, title="[bold]💰 Balance[/bold]", border_style="green")

    def _create_stats_panel(self) -> Panel:
        """Create trading statistics panel."""
        win_rate = 0
        if self.stats["total_trades"] > 0:
            win_rate = (self.stats["winning_trades"] / self.stats["total_trades"]) * 100

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Label", style="cyan")
        table.add_column("Value", justify="right")

        table.add_row("Total Trades", str(self.stats["total_trades"]))
        table.add_row("Winning", f"[green]{self.stats['winning_trades']}[/green]")
        table.add_row("Losing", f"[red]{self.stats['losing_trades']}[/red]")
        table.add_row("Win Rate", f"{win_rate:.1f}%")
        table.add_row("Best Trade", f"[green]${self.stats['best_trade']:+.2f}[/green]")
        table.add_row("Worst Trade", f"[red]${self.stats['worst_trade']:+.2f}[/red]")

        return Panel(table, title="[bold]📊 Statistics[/bold]", border_style="blue")

    def _create_positions_table(self) -> Panel:
        """Create positions table."""
        table = Table(
            title=None,
            show_header=True,
            header_style="bold cyan",
            border_style="dim"
        )

        table.add_column("Market", style="white", max_width=25)
        table.add_column("Side", justify="center")
        table.add_column("Entry", justify="right")
        table.add_column("Current", justify="right")
        table.add_column("Size", justify="right")
        table.add_column("P&L", justify="right")
        table.add_column("P&L %", justify="right")

        positions = trading_bot.get_positions_summary()

        if not positions:
            table.add_row(
                "[dim]No open positions[/dim]", "", "", "", "", "", ""
            )
        else:
            for pos in positions:
                pnl = pos.get("pnl", 0)
                pnl_pct = pos.get("pnl_pct", 0)
                pnl_style = "green" if pnl >= 0 else "red"

                # Determine side from position data
                side = pos.get("side", "BUY")
                side_style = "green" if side == "BUY" else "red"

                table.add_row(
                    pos.get("token_id", "")[:20] + "...",
                    f"[{side_style}]{side}[/{side_style}]",
                    f"${pos.get('entry_price', 0):.3f}",
                    f"${pos.get('current_price', 0):.3f}" if pos.get('current_price') else "N/A",
                    f"{pos.get('size', 0):.2f}",
                    f"[{pnl_style}]${pnl:+.2f}[/{pnl_style}]",
                    f"[{pnl_style}]{pnl_pct:+.1f}%[/{pnl_style}]"
                )

        return Panel(table, title="[bold]📈 Open Positions[/bold]", border_style="yellow")

    def _create_trades_table(self) -> Panel:
        """Create recent trades table."""
        table = Table(
            show_header=True,
            header_style="bold cyan",
            border_style="dim"
        )

        table.add_column("Time", style="dim")
        table.add_column("Type", justify="center")
        table.add_column("Market", max_width=20)
        table.add_column("Price", justify="right")
        table.add_column("Amount", justify="right")
        table.add_column("P&L", justify="right")

        # Get last 10 trades
        trades = trading_bot.trade_history[-10:] if trading_bot.trade_history else []

        if not trades:
            table.add_row("[dim]No trades yet[/dim]", "", "", "", "", "")
        else:
            for trade in reversed(trades):
                trade_type = trade.get("type", "")
                type_style = "green" if trade_type == "BUY" else "red"

                pnl = trade.get("pnl", 0)
                pnl_str = f"${pnl:+.2f}" if pnl != 0 else "-"
                pnl_style = "green" if pnl > 0 else "red" if pnl < 0 else "dim"

                time_str = trade.get("time", "")
                if time_str:
                    try:
                        dt = datetime.fromisoformat(time_str)
                        time_str = dt.strftime("%H:%M:%S")
                    except:
                        pass

                table.add_row(
                    time_str,
                    f"[{type_style}]{trade_type}[/{type_style}]",
                    trade.get("token_id", "")[:16] + "...",
                    f"${trade.get('price', 0):.3f}",
                    f"${trade.get('amount', 0):.2f}" if trade.get('amount') else f"{trade.get('size', 0):.2f}",
                    f"[{pnl_style}]{pnl_str}[/{pnl_style}]"
                )

        return Panel(table, title="[bold]📜 Recent Trades[/bold]", border_style="magenta")

    def _create_btc_panel(self) -> Panel:
        """Create BTC market info panel."""
        from .strategies.btc_arbitrage import btc_arbitrage_strategy

        info = btc_arbitrage_strategy.get_btc_market_info()
        stats = btc_arbitrage_strategy.get_stats()

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Label", style="cyan")
        table.add_column("Value", justify="right")

        # Show current state
        state = stats.get("state", "waiting")
        state_colors = {"waiting": "yellow", "holding_first": "blue", "completed": "green"}
        state_labels = {"waiting": "Waiting...", "holding_first": "Holding 1st", "completed": "Done!"}
        state_color = state_colors.get(state, "white")
        state_label = state_labels.get(state, state)
        table.add_row("State", f"[{state_color}]{state_label}[/{state_color}]")

        if info:
            table.add_row("UP Price", f"[green]${info.get('up_price', 0):.3f}[/green]")
            table.add_row("DOWN Price", f"[red]${info.get('down_price', 0):.3f}[/red]")

            # If holding first position, show details
            first_pos = stats.get("first_position")
            if first_pos and state == "holding_first":
                first_side = first_pos.get("side", "")
                first_price = first_pos.get("price", 0)
                table.add_row("1st Position", f"[cyan]{first_side} @ ${first_price:.3f}[/cyan]")

                # Calculate potential profit if we buy second now
                up_price = info.get('up_price', 0)
                down_price = info.get('down_price', 0)
                second_price = down_price if first_side == "UP" else up_price
                total_cost = first_price + second_price
                potential_profit = ((1 - total_cost) / total_cost) * 100 if total_cost > 0 else 0

                profit_color = "green" if potential_profit >= 5 else "yellow" if potential_profit > 0 else "red"
                table.add_row("If Buy Now", f"[{profit_color}]{potential_profit:+.1f}%[/{profit_color}]")
                table.add_row("Target", f"[dim]{stats.get('target_profit', '5%')}[/dim]")
            else:
                total = info.get('up_price', 0) + info.get('down_price', 0)
                spread = 1 - total
                spread_color = "green" if spread > 0 else "red"
                table.add_row("Total", f"${total:.3f}")
                table.add_row("Spread", f"[{spread_color}]{spread*100:+.1f}%[/{spread_color}]")
        else:
            table.add_row("[dim]Searching for BTC markets...[/dim]", "")

        return Panel(table, title="[bold]₿ BTC Sequential Arb[/bold]", border_style="orange1")

    def _create_layout(self) -> Layout:
        """Create the dashboard layout."""
        layout = Layout()

        layout.split(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3)
        )

        layout["body"].split_row(
            Layout(name="left"),
            Layout(name="right")
        )

        layout["left"].split(
            Layout(name="balance", size=10),
            Layout(name="btc", size=12),
            Layout(name="stats")
        )

        layout["right"].split(
            Layout(name="positions"),
            Layout(name="trades")
        )

        return layout

    def _render(self) -> Layout:
        """Render the full dashboard."""
        layout = self._create_layout()

        layout["header"].update(self._create_header())
        layout["balance"].update(self._create_balance_panel())
        layout["btc"].update(self._create_btc_panel())
        layout["stats"].update(self._create_stats_panel())
        layout["positions"].update(self._create_positions_table())
        layout["trades"].update(self._create_trades_table())

        # Footer with runtime
        if self.stats["start_time"]:
            runtime = datetime.now() - self.stats["start_time"]
            runtime_str = str(runtime).split('.')[0]
        else:
            runtime_str = "00:00:00"

        footer = Table.grid(expand=True)
        footer.add_column(justify="left")
        footer.add_column(justify="center")
        footer.add_column(justify="right")
        footer.add_row(
            f"Runtime: {runtime_str}",
            "[dim]Press Ctrl+C to stop[/dim]",
            f"Updated: {datetime.now().strftime('%H:%M:%S')}"
        )
        layout["footer"].update(Panel(footer, style="dim"))

        return layout

    def update_stats_from_trade(self, trade: Dict):
        """Update statistics after a trade."""
        self.stats["total_trades"] += 1

        pnl = trade.get("pnl", 0)
        if pnl > 0:
            self.stats["winning_trades"] += 1
            if pnl > self.stats["best_trade"]:
                self.stats["best_trade"] = pnl
        elif pnl < 0:
            self.stats["losing_trades"] += 1
            if pnl < self.stats["worst_trade"]:
                self.stats["worst_trade"] = pnl

        self.stats["total_pnl"] += pnl

    def run(self):
        """Run the dashboard with live updates."""
        self.is_running = True
        self.stats["start_time"] = datetime.now()

        # Get starting balance
        if trading_bot.client._initialized:
            self.stats["start_balance"] = trading_bot.client.get_balance() or 0

        try:
            with Live(self._render(), refresh_per_second=1, screen=True) as live:
                while self.is_running and trading_bot.is_running:
                    live.update(self._render())
                    time.sleep(self.refresh_rate)
        except KeyboardInterrupt:
            self.is_running = False

    def stop(self):
        """Stop the dashboard."""
        self.is_running = False


# Global dashboard instance
dashboard = Dashboard()
