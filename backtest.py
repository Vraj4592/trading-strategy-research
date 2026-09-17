"""
CLI entry point. Splits the date range into an in-sample (IS) window
to develop/tune on and an out-of-sample (OOS) window to validate on,
runs both, prints metrics, saves an equity curve chart and a short
markdown report.

Usage:
    python backtest.py --ticker SPY --start 2018-01-01 --end 2024-01-01 \
        --split 2022-01-01 --strategy ma_crossover

    python backtest.py --synthetic --strategy breakout_range
        (no internet needed — runs on generated random-walk data,
         useful to confirm the pipeline itself works)
"""

import argparse
import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from data.loader import load_ohlcv, generate_synthetic
from strategy import STRATEGIES
from engine import run_backtest
from metrics import summarize, print_summary, weaknesses_report

OUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUT_DIR, exist_ok=True)


def plot_equity(is_result, oos_result, buy_hold_is, buy_hold_oos, path):
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(is_result.equity_curve.index, is_result.equity_curve.values,
            label="Strategy (in-sample)", color="#0f766e")
    ax.plot(oos_result.equity_curve.index, oos_result.equity_curve.values,
            label="Strategy (out-of-sample)", color="#0891b2")
    ax.plot(buy_hold_is.index, buy_hold_is.values,
            label="Buy & Hold (in-sample)", color="#a8a29e", linestyle="--")
    ax.plot(buy_hold_oos.index, buy_hold_oos.values,
            label="Buy & Hold (out-of-sample)", color="#78716c", linestyle="--")
    ax.axvline(oos_result.equity_curve.index[0], color="black", linestyle=":", alpha=0.5)
    ax.set_title("Equity Curve: Strategy vs Buy & Hold")
    ax.set_ylabel("Equity ($)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def buy_hold_curve(price_series: pd.Series, starting_capital: float) -> pd.Series:
    units = starting_capital / price_series.iloc[0]
    return price_series * units


def write_report(path, ticker, strat_name, split_date, is_summary, oos_summary,
                  is_flags, oos_flags):
    lines = [
        f"# Trading Strategy Research Report",
        f"",
        f"**Ticker:** {ticker}  ",
        f"**Strategy:** {strat_name}  ",
        f"**In-sample / out-of-sample split:** {split_date}",
        f"",
        f"## In-Sample Results (development window)",
        f"",
    ]
    for k, v in is_summary.items():
        lines.append(f"- **{k}**: {v}")
    lines += ["", "**Weaknesses / caveats (in-sample):**"]
    lines += [f"- {f}" for f in is_flags]

    lines += ["", f"## Out-of-Sample Results (unseen data)", ""]
    for k, v in oos_summary.items():
        lines.append(f"- **{k}**: {v}")
    lines += ["", "**Weaknesses / caveats (out-of-sample):**"]
    lines += [f"- {f}" for f in oos_flags]

    lines += [
        "",
        "## Honest Take",
        "",
        "Out-of-sample performance is the number that matters — in-sample results "
        "are curve-fit by construction. If out-of-sample return, Sharpe, or "
        "drawdown are meaningfully worse than in-sample, the strategy likely "
        "doesn't generalize and needs either simpler rules or a larger sample "
        "before drawing conclusions.",
        "",
        "![Equity Curve](equity_curve.png)",
    ]
    with open(path, "w") as f:
        f.write("\n".join(lines))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ticker", default="SPY")
    p.add_argument("--start", default="2018-01-01")
    p.add_argument("--end", default="2024-01-01")
    p.add_argument("--split", default=None,
                    help="Date that divides in-sample from out-of-sample. "
                         "Defaults to 80%% of the way through the range.")
    p.add_argument("--strategy", default="ma_crossover", choices=STRATEGIES.keys())
    p.add_argument("--capital", type=float, default=10_000.0)
    p.add_argument("--fee-bps", type=float, default=5.0)
    p.add_argument("--slippage-bps", type=float, default=2.0)
    p.add_argument("--stop-loss-pct", type=float, default=None,
                    help="e.g. 0.05 for a 5%% stop-loss from entry. "
                         "Omit to disable (pure signal-based exits).")
    p.add_argument("--synthetic", action="store_true",
                    help="Use generated random-walk data instead of yfinance "
                         "(no internet required, for testing the pipeline).")
    args = p.parse_args()

    if args.synthetic:
        df = generate_synthetic(args.ticker, args.start, args.end)
    else:
        df = load_ohlcv(args.ticker, args.start, args.end)

    if args.split is None:
        split_idx = int(len(df) * 0.8)
        split_date = df.index[split_idx]
    else:
        split_date = pd.Timestamp(args.split)

    is_df = df.loc[df.index < split_date]
    oos_df = df.loc[df.index >= split_date]

    if len(is_df) < 60 or len(oos_df) < 20:
        raise SystemExit(
            f"Not enough data on one side of the split ({len(is_df)} in-sample, "
            f"{len(oos_df)} out-of-sample bars). Widen --start/--end or move --split."
        )

    strat_cls = STRATEGIES[args.strategy]

    is_result = run_backtest(is_df, strat_cls(), starting_capital=args.capital,
                              fee_bps=args.fee_bps, slippage_bps=args.slippage_bps,
                              stop_loss_pct=args.stop_loss_pct)
    oos_result = run_backtest(oos_df, strat_cls(), starting_capital=args.capital,
                               fee_bps=args.fee_bps, slippage_bps=args.slippage_bps,
                               stop_loss_pct=args.stop_loss_pct)

    is_summary = summarize(is_result, is_df["Close"])
    oos_summary = summarize(oos_result, oos_df["Close"])
    is_flags = weaknesses_report(is_summary)
    oos_flags = weaknesses_report(oos_summary)

    print_summary(f"{args.ticker} | {args.strategy} | IN-SAMPLE", is_summary)
    print_summary(f"{args.ticker} | {args.strategy} | OUT-OF-SAMPLE", oos_summary)
    print("\nOut-of-sample caveats:")
    for f in oos_flags:
        print(f" - {f}")

    bh_is = buy_hold_curve(is_df["Close"], args.capital)
    bh_oos = buy_hold_curve(oos_df["Close"], args.capital)
    chart_path = os.path.join(OUT_DIR, "equity_curve.png")
    plot_equity(is_result, oos_result, bh_is, bh_oos, chart_path)

    report_path = os.path.join(OUT_DIR, "report.md")
    write_report(report_path, args.ticker, args.strategy, str(split_date.date()),
                 is_summary, oos_summary, is_flags, oos_flags)

    print(f"\nSaved chart -> {chart_path}")
    print(f"Saved report -> {report_path}")


if __name__ == "__main__":
    main()
