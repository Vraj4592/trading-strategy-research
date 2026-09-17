"""Reproduce the five-asset out-of-sample validation used in the final report."""

import json
from pathlib import Path

from data.loader import load_ohlcv
from engine import run_backtest
from metrics import summarize
from strategy import ConfirmedSweep

ASSETS = {
    "SPY": "2010-01-01",
    "QQQ": "2010-01-01",
    "AAPL": "2010-01-01",
    "BTC-USD": "2018-01-01",
    "ETH-USD": "2018-01-01",
}
END = "2024-01-01"
CAPITAL = 10_000.0
FEE_BPS = 5.0
SLIPPAGE_BPS = 2.0


def clean_number(value):
    """Convert numpy scalar values to normal Python values for JSON output."""
    return value.item() if hasattr(value, "item") else value


def main():
    per_ticker = []
    all_returns = []

    for ticker, start in ASSETS.items():
        df = load_ohlcv(ticker, start, END)
        split_index = int(len(df) * 0.8)
        split_date = df.index[split_index]
        oos = df.loc[df.index >= split_date]

        result = run_backtest(
            oos,
            ConfirmedSweep(),
            starting_capital=CAPITAL,
            fee_bps=FEE_BPS,
            slippage_bps=SLIPPAGE_BPS,
        )
        summary = {k: clean_number(v) for k, v in summarize(result, oos["Close"]).items()}
        summary["ticker"] = ticker
        summary["oos_start"] = str(split_date.date())
        per_ticker.append(summary)
        all_returns.extend(clean_number(t.return_pct) for t in result.trades)

    wins = [r for r in all_returns if r > 0]
    losses = [r for r in all_returns if r <= 0]
    total = len(all_returns)
    win_rate = len(wins) / total if total else 0.0
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    expectancy = win_rate * avg_win + (1 - win_rate) * avg_loss

    pooled = {
        "total_trades": total,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(win_rate * 100, 2),
        "avg_win_pct": round(avg_win * 100, 2),
        "avg_loss_pct": round(avg_loss * 100, 2),
        "expectancy_pct": round(expectancy * 100, 2),
    }

    output = {"per_ticker": per_ticker, "pooled": pooled}
    out_path = Path(__file__).parent / "results" / "pooled_oos_reproduced.json"
    out_path.write_text(json.dumps(output, indent=2))

    print("\nFive-asset out-of-sample validation\n")
    for row in per_ticker:
        print(
            f"{row['ticker']:8s} | trades {row['num_trades']:2d} | "
            f"win {row['win_rate_pct']:6.2f}% | return {row['strategy_total_return_pct']:7.2f}% | "
            f"Sharpe {row['sharpe_ratio']:4.2f} | DD {row['max_drawdown_pct']:7.2f}%"
        )
    print("\nPooled:", pooled)
    print(f"Saved -> {out_path}")


if __name__ == "__main__":
    main()
