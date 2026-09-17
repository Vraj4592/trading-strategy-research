"""
Turns a BacktestResult into the numbers that actually matter:
total return, max drawdown, win rate, trade count, Sharpe, and a
buy-and-hold comparison over the same window.
"""

import numpy as np
import pandas as pd

from engine import BacktestResult


def max_drawdown(equity: pd.Series) -> float:
    running_max = equity.cummax()
    drawdown = (equity - running_max) / running_max
    return drawdown.min()  # negative number, e.g. -0.18 = -18%


def sharpe_ratio(equity: pd.Series, periods_per_year: int = 252,
                  risk_free: float = 0.0) -> float:
    daily_returns = equity.pct_change().dropna()
    if daily_returns.std() == 0 or daily_returns.empty:
        return 0.0
    excess = daily_returns - (risk_free / periods_per_year)
    return (excess.mean() / excess.std()) * np.sqrt(periods_per_year)


def buy_and_hold_return(price_series: pd.Series) -> float:
    return (price_series.iloc[-1] / price_series.iloc[0]) - 1


def summarize(result: BacktestResult, price_series: pd.Series) -> dict:
    equity = result.equity_curve
    total_return = (equity.iloc[-1] / result.starting_capital) - 1
    wins = [t for t in result.trades if t.pnl > 0]
    losses = [t for t in result.trades if t.pnl <= 0]
    win_rate = len(wins) / len(result.trades) if result.trades else 0.0
    avg_win = np.mean([t.return_pct for t in wins]) if wins else 0.0
    avg_loss = np.mean([t.return_pct for t in losses]) if losses else 0.0
    stopped_out = sum(1 for t in result.trades if t.exit_reason == "stop_loss")

    return {
        "strategy_total_return_pct": round(total_return * 100, 2),
        "buy_and_hold_return_pct": round(buy_and_hold_return(price_series) * 100, 2),
        "max_drawdown_pct": round(max_drawdown(equity) * 100, 2),
        "sharpe_ratio": round(sharpe_ratio(equity), 2),
        "num_trades": len(result.trades),
        "num_stopped_out": stopped_out,
        "win_rate_pct": round(win_rate * 100, 2),
        "avg_win_pct": round(avg_win * 100, 2),
        "avg_loss_pct": round(avg_loss * 100, 2),
        "ending_equity": round(equity.iloc[-1], 2),
    }


def print_summary(title: str, summary: dict) -> None:
    print(f"\n=== {title} ===")
    for k, v in summary.items():
        print(f"{k:30s}: {v}")


def weaknesses_report(summary: dict) -> list:
    """Plain-language flags for the honesty section of the writeup."""
    flags = []
    if summary["num_trades"] < 20:
        flags.append(
            f"Only {summary['num_trades']} trades — sample size is too small "
            f"to trust the win rate or Sharpe estimate."
        )
    if summary["strategy_total_return_pct"] < summary["buy_and_hold_return_pct"]:
        flags.append("Strategy underperformed buy-and-hold over this window.")
    if summary["max_drawdown_pct"] < -25:
        flags.append(
            f"Max drawdown of {summary['max_drawdown_pct']}% is large — "
            f"check if this is survivable with real capital and psychology."
        )
    if summary["sharpe_ratio"] < 0.5:
        flags.append("Sharpe ratio is weak — returns aren't compensating for volatility.")
    if not flags:
        flags.append("No major red flags in-sample — the real test is the out-of-sample window.")
    return flags
