#!/usr/bin/env python3
"""
Polymarket Trading Bot - Main Entry Point

A bot that automatically buys and sells on Polymarket prediction markets.
"""

import sys
import threading
import click
from loguru import logger
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from src.config import config
from src.bot import trading_bot
from src.strategies import MomentumStrategy, ArbitrageStrategy, ValueStrategy, BTCArbitrageStrategy
from src.dashboard import dashboard

console = Console()


def setup_logging(quiet: bool = False):
    """Configure logging."""
    logger.remove()

    if not quiet:
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
    pass


@cli.command()
@click.option("--momentum/--no-momentum", default=True, help="Enable momentum strategy")
@click.option("--arbitrage/--no-arbitrage", default=True, help="Enable arbitrage strategy")
@click.option("--value/--no-value", default=False, help="Enable value strategy")
def start(momentum: bool, arbitrage: bool, value: bool):
    """Start the trading bot."""
    setup_logging()

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
@click.option("--target-profit", default=0.05, help="Target profit to complete arbitrage (e.g., 0.05 = 5%)")
@click.option("--amount", default=50.0, help="Amount in USDC per side (UP and DOWN)")
@click.option("--timeframe", default="1h", type=click.Choice(["1h", "4h", "24h"]), help="Target timeframe")
@click.option("--entry-threshold", default=0.55, help="Max price for first buy (e.g., 0.55 = 55 cents)")
@click.option("--dashboard/--no-dashboard", default=True, help="Show live dashboard")
def btc(target_profit: float, amount: float, timeframe: str, entry_threshold: float, dashboard: bool):
    """
    Start BTC sequential arbitrage bot.

    Strategy:
    1. First, buy UP (or DOWN) when price is below entry threshold
    2. Wait for prices to move
    3. When profit target is reached, buy the other side to lock in arbitrage
    """
    setup_logging(quiet=dashboard)

    console.print(Panel.fit(
        "[bold orange1]BTC Sequential Arbitrage Bot[/bold orange1]\n"
        f"Timeframe: {timeframe} | Target Profit: {target_profit*100:.0f}% | Amount: ${amount}/side\n"
        f"Entry Threshold: ${entry_threshold:.2f}",
        border_style="orange1"
    ))

    # Initialize bot
    if not trading_bot.initialize():
        console.print("[bold red]Failed to initialize bot. Check your configuration.[/bold red]")
        sys.exit(1)

    # Add BTC arbitrage strategy
    btc_strategy = BTCArbitrageStrategy(
        target_profit=target_profit,
        max_position_per_side=amount,
        target_timeframe=timeframe,
        initial_buy_threshold=entry_threshold
    )
    trading_bot.add_strategy(btc_strategy)

    # Display status
    status = trading_bot.get_status()
    console.print(f"\n[cyan]Balance:[/cyan] ${status['balance']:.2f}" if status['balance'] else "")
    console.print(f"[cyan]Dry Run:[/cyan] {'Yes' if status['dry_run'] else 'No'}")

    # Show strategy state
    strat_stats = btc_strategy.get_stats()
    if strat_stats.get("state") == "holding_first":
        first_pos = strat_stats.get("first_position", {})
        console.print(f"[cyan]Current Position:[/cyan] {first_pos.get('side')} @ ${first_pos.get('price', 0):.3f}")

    if status['dry_run']:
        console.print("\n[yellow]Running in DRY RUN mode - no real trades will be executed[/yellow]")

    console.print("\n[green]Starting BTC arbitrage bot... Press Ctrl+C to stop[/green]\n")

    if dashboard:
        # Run bot in background thread
        bot_thread = threading.Thread(target=trading_bot.run, daemon=True)
        bot_thread.start()

        # Run dashboard in main thread
        from src.dashboard import dashboard as dash
        dash.run()
    else:
        # Run the bot normally
        trading_bot.run()


@cli.command(name="dashboard")
def show_dashboard():
    """Show the live trading dashboard."""
    setup_logging(quiet=True)

    # Initialize bot (but don't run)
    if not trading_bot.initialize():
        console.print("[bold red]Failed to initialize. Check configuration.[/bold red]")
        return

    console.print("[cyan]Loading dashboard...[/cyan]")

    from src.dashboard import dashboard as dash
    dash.run()


@cli.command()
def status():
    """Show bot status and positions."""
    setup_logging()

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
    setup_logging()

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
    setup_logging()

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
@click.option("--btc", is_flag=True, help="Show only BTC markets")
def markets(limit: int, btc: bool):
    """List available markets."""
    setup_logging()

    if not trading_bot.initialize():
        console.print("[bold red]Failed to initialize. Check configuration.[/bold red]")
        return

    console.print("[cyan]Fetching markets...[/cyan]\n")

    response = trading_bot.client.get_markets()
    markets_data = response.get("data", [])

    # Filter for BTC markets if requested
    if btc:
        btc_markets = []
        for market in markets_data:
            question = market.get("question", "").lower()
            if "bitcoin" in question or "btc" in question:
                btc_markets.append(market)
        markets_data = btc_markets
        console.print(f"[yellow]Found {len(markets_data)} BTC markets[/yellow]\n")

    markets_data = markets_data[:limit]

    table = Table(title=f"{'BTC ' if btc else ''}Markets (showing {len(markets_data)})")
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
    setup_logging()

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
    setup_logging()

    if not trading_bot.initialize():
        console.print("[bold red]Failed to initialize. Check configuration.[/bold red]")
        return

    if click.confirm("Are you sure you want to cancel all open orders?"):
        if trading_bot.client.cancel_all_orders():
            console.print("[green]All orders cancelled[/green]")
        else:
            console.print("[red]Failed to cancel orders[/red]")


@cli.command()
def history():
    """Show trade history and statistics."""
    setup_logging()

    if not trading_bot.initialize():
        console.print("[bold red]Failed to initialize. Check configuration.[/bold red]")
        return

    trades = trading_bot.trade_history

    if not trades:
        console.print("[yellow]No trade history yet[/yellow]")
        return

    # Calculate statistics
    total_trades = len(trades)
    buys = [t for t in trades if t.get("type") == "BUY"]
    sells = [t for t in trades if t.get("type") == "SELL"]

    total_pnl = sum(t.get("pnl", 0) for t in sells)
    winning = [t for t in sells if t.get("pnl", 0) > 0]
    losing = [t for t in sells if t.get("pnl", 0) < 0]

    win_rate = (len(winning) / len(sells) * 100) if sells else 0
    avg_win = sum(t.get("pnl", 0) for t in winning) / len(winning) if winning else 0
    avg_loss = sum(t.get("pnl", 0) for t in losing) / len(losing) if losing else 0

    # Stats table
    stats_table = Table(title="Trading Statistics")
    stats_table.add_column("Metric", style="cyan")
    stats_table.add_column("Value", style="green")

    pnl_style = "green" if total_pnl >= 0 else "red"

    stats_table.add_row("Total Trades", str(total_trades))
    stats_table.add_row("Buys", str(len(buys)))
    stats_table.add_row("Sells", str(len(sells)))
    stats_table.add_row("Winning Trades", f"[green]{len(winning)}[/green]")
    stats_table.add_row("Losing Trades", f"[red]{len(losing)}[/red]")
    stats_table.add_row("Win Rate", f"{win_rate:.1f}%")
    stats_table.add_row("Total P&L", f"[{pnl_style}]${total_pnl:+.2f}[/{pnl_style}]")
    stats_table.add_row("Avg Win", f"[green]${avg_win:+.2f}[/green]")
    stats_table.add_row("Avg Loss", f"[red]${avg_loss:+.2f}[/red]")

    console.print(stats_table)

    # Recent trades table
    console.print("\n")
    trades_table = Table(title="Recent Trades (Last 20)")
    trades_table.add_column("Time", style="dim")
    trades_table.add_column("Type", justify="center")
    trades_table.add_column("Token", max_width=20)
    trades_table.add_column("Price", justify="right")
    trades_table.add_column("Amount/Size", justify="right")
    trades_table.add_column("P&L", justify="right")

    for trade in trades[-20:]:
        trade_type = trade.get("type", "")
        type_style = "green" if trade_type == "BUY" else "red"

        pnl = trade.get("pnl", 0)
        pnl_str = f"${pnl:+.2f}" if pnl != 0 else "-"
        pnl_style = "green" if pnl > 0 else "red" if pnl < 0 else "dim"

        time_str = trade.get("time", "")[:19]

        trades_table.add_row(
            time_str,
            f"[{type_style}]{trade_type}[/{type_style}]",
            trade.get("token_id", "")[:16] + "...",
            f"${trade.get('price', 0):.3f}",
            f"${trade.get('amount', 0):.2f}" if trade.get('amount') else f"{trade.get('size', 0):.2f}",
            f"[{pnl_style}]{pnl_str}[/{pnl_style}]"
        )

    console.print(trades_table)


if __name__ == "__main__":
    cli()
