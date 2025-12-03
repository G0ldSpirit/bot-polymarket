#!/usr/bin/env python3
"""
Polymarket Trading Bot - Main Entry Point

A bot that automatically buys and sells on Polymarket prediction markets.
"""

import sys
import click
from loguru import logger
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from src.config import config
from src.bot import trading_bot
from src.strategies import MomentumStrategy, ArbitrageStrategy, ValueStrategy

console = Console()


def setup_logging():
    """Configure logging."""
    logger.remove()
    logger.add(
        sys.stderr,
        level=config.log_level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>"
    )
    logger.add(
        "logs/bot_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="7 days",
        level="DEBUG"
    )


@click.group()
def cli():
    """Polymarket Trading Bot - Automated prediction market trading."""
    setup_logging()


@cli.command()
@click.option("--momentum/--no-momentum", default=True, help="Enable momentum strategy")
@click.option("--arbitrage/--no-arbitrage", default=True, help="Enable arbitrage strategy")
@click.option("--value/--no-value", default=False, help="Enable value strategy")
def start(momentum: bool, arbitrage: bool, value: bool):
    """Start the trading bot."""
    console.print(Panel.fit(
        "[bold green]Polymarket Trading Bot[/bold green]\n"
        "Automated prediction market trading",
        border_style="green"
    ))

    # Initialize bot
    if not trading_bot.initialize():
        console.print("[bold red]Failed to initialize bot. Check your configuration.[/bold red]")
        sys.exit(1)

    # Add strategies
    if momentum:
        trading_bot.add_strategy(MomentumStrategy())

    if arbitrage:
        trading_bot.add_strategy(ArbitrageStrategy())

    if value:
        trading_bot.add_strategy(ValueStrategy())

    if not trading_bot.strategies:
        console.print("[bold yellow]Warning: No strategies enabled![/bold yellow]")

    # Display status
    status = trading_bot.get_status()
    console.print(f"\n[cyan]Balance:[/cyan] ${status['balance']:.2f}" if status['balance'] else "")
    console.print(f"[cyan]Strategies:[/cyan] {', '.join(status['strategies'])}")
    console.print(f"[cyan]Dry Run:[/cyan] {'Yes' if status['dry_run'] else 'No'}")

    if status['dry_run']:
        console.print("\n[yellow]Running in DRY RUN mode - no real trades will be executed[/yellow]")

    console.print("\n[green]Starting bot... Press Ctrl+C to stop[/green]\n")

    # Run the bot
    trading_bot.run()


@cli.command()
def status():
    """Show bot status and positions."""
    if not trading_bot.initialize():
        console.print("[bold red]Failed to initialize. Check configuration.[/bold red]")
        return

    status = trading_bot.get_status()

    # Status table
    status_table = Table(title="Bot Status")
    status_table.add_column("Property", style="cyan")
    status_table.add_column("Value", style="green")

    status_table.add_row("Running", "Yes" if status['is_running'] else "No")
    status_table.add_row("Dry Run", "Yes" if status['dry_run'] else "No")
    status_table.add_row("Balance", f"${status['balance']:.2f}" if status['balance'] else "N/A")
    status_table.add_row("Position Value", f"${status['position_value']:.2f}")
    status_table.add_row("Open Positions", str(status['open_positions']))
    status_table.add_row("Total Trades", str(status['total_trades']))

    console.print(status_table)

    # Positions table
    positions = trading_bot.get_positions_summary()
    if positions:
        pos_table = Table(title="Open Positions")
        pos_table.add_column("Token", style="cyan")
        pos_table.add_column("Entry", style="yellow")
        pos_table.add_column("Current", style="yellow")
        pos_table.add_column("Size", style="blue")
        pos_table.add_column("P&L", style="green")
        pos_table.add_column("P&L %", style="green")

        for pos in positions:
            pnl_style = "green" if pos['pnl'] >= 0 else "red"
            pos_table.add_row(
                pos['token_id'],
                f"${pos['entry_price']:.3f}",
                f"${pos['current_price']:.3f}" if pos['current_price'] else "N/A",
                f"{pos['size']:.2f}",
                f"[{pnl_style}]${pos['pnl']:.2f}[/{pnl_style}]",
                f"[{pnl_style}]{pos['pnl_pct']:.1f}%[/{pnl_style}]"
            )

        console.print(pos_table)
    else:
        console.print("\n[yellow]No open positions[/yellow]")


@cli.command()
@click.argument("token_id")
@click.argument("amount", type=float)
@click.option("--price", type=float, default=None, help="Limit price (uses market price if not specified)")
def buy(token_id: str, amount: float, price: float):
    """Manually buy shares of a token."""
    if not trading_bot.initialize():
        console.print("[bold red]Failed to initialize. Check configuration.[/bold red]")
        return

    console.print(f"[cyan]Buying ${amount} of {token_id[:16]}...[/cyan]")

    result = trading_bot.client.buy(token_id, amount, price)
    if result:
        console.print("[green]Order placed successfully![/green]")
        console.print(result)
    else:
        console.print("[red]Order failed[/red]")


@cli.command()
@click.argument("token_id")
@click.argument("size", type=float)
@click.option("--price", type=float, default=None, help="Limit price (uses market price if not specified)")
def sell(token_id: str, size: float, price: float):
    """Manually sell shares of a token."""
    if not trading_bot.initialize():
        console.print("[bold red]Failed to initialize. Check configuration.[/bold red]")
        return

    console.print(f"[cyan]Selling {size} shares of {token_id[:16]}...[/cyan]")

    result = trading_bot.client.sell(token_id, size, price)
    if result:
        console.print("[green]Order placed successfully![/green]")
        console.print(result)
    else:
        console.print("[red]Order failed[/red]")


@cli.command()
@click.option("--limit", default=10, help="Number of markets to show")
def markets(limit: int):
    """List available markets."""
    if not trading_bot.initialize():
        console.print("[bold red]Failed to initialize. Check configuration.[/bold red]")
        return

    console.print("[cyan]Fetching markets...[/cyan]\n")

    response = trading_bot.client.get_markets()
    markets_data = response.get("data", [])[:limit]

    table = Table(title=f"Top {limit} Markets")
    table.add_column("Question", style="cyan", max_width=50)
    table.add_column("Condition ID", style="yellow", max_width=20)
    table.add_column("Tokens", style="green")

    for market in markets_data:
        question = market.get("question", "N/A")[:50]
        condition_id = market.get("condition_id", "N/A")[:20]
        tokens = len(market.get("tokens", []))
        table.add_row(question, condition_id, str(tokens))

    console.print(table)


@cli.command()
@click.argument("token_id")
def orderbook(token_id: str):
    """Show orderbook for a token."""
    if not trading_bot.initialize():
        console.print("[bold red]Failed to initialize. Check configuration.[/bold red]")
        return

    book = trading_bot.client.get_orderbook(token_id)
    if not book:
        console.print("[red]Could not fetch orderbook[/red]")
        return

    # Bids table
    bids = book.get("bids", [])[:10]
    asks = book.get("asks", [])[:10]

    table = Table(title=f"Orderbook for {token_id[:16]}...")
    table.add_column("Bid Price", style="green")
    table.add_column("Bid Size", style="green")
    table.add_column("Ask Price", style="red")
    table.add_column("Ask Size", style="red")

    max_rows = max(len(bids), len(asks))
    for i in range(max_rows):
        bid_price = f"${float(bids[i]['price']):.3f}" if i < len(bids) else ""
        bid_size = f"{float(bids[i]['size']):.2f}" if i < len(bids) else ""
        ask_price = f"${float(asks[i]['price']):.3f}" if i < len(asks) else ""
        ask_size = f"{float(asks[i]['size']):.2f}" if i < len(asks) else ""
        table.add_row(bid_price, bid_size, ask_price, ask_size)

    console.print(table)


@cli.command()
def cancel_all():
    """Cancel all open orders."""
    if not trading_bot.initialize():
        console.print("[bold red]Failed to initialize. Check configuration.[/bold red]")
        return

    if click.confirm("Are you sure you want to cancel all open orders?"):
        if trading_bot.client.cancel_all_orders():
            console.print("[green]All orders cancelled[/green]")
        else:
            console.print("[red]Failed to cancel orders[/red]")


if __name__ == "__main__":
    cli()
