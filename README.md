# Trading Strategy Research

A Python project testing one trading idea across several markets.

## Goal

Test whether a **liquidity-sweep reversal** setup can work across SPY, QQQ, AAPL, Bitcoin, and Ethereum.

## What I built

- Python backtesting engine
- Historical price loader using `yfinance`
- Trading fees and slippage
- In-sample and out-of-sample testing
- Buy-and-hold comparison
- Return, Sharpe ratio, drawdown, win rate, and trade-count metrics
- Multi-asset validation

The backtest only uses data available at that time. It does not use future prices to make trades.

## Final strategy

The final strategy is called `confirmed_sweep`.

It looks for a liquidity sweep reversal. A buy is only allowed when price is above its 100-bar average. This helps avoid buying against a larger downtrend.

## Out-of-sample results

| Asset | Trades | Win Rate | Strategy Return | Sharpe | Max Drawdown |
|---|---:|---:|---:|---:|---:|
| SPY | 5 | 100.0% | 10.99% | 0.71 | -4.83% |
| QQQ | 6 | 83.33% | 5.07% | 0.21 | -18.61% |
| AAPL | 5 | 60.0% | 9.11% | 0.33 | -15.45% |
| BTC-USD | 5 | 60.0% | 48.32% | 1.25 | -13.47% |
| ETH-USD | 6 | 83.33% | 20.82% | 0.67 | -18.00% |

Across all five assets: **27 trades, 21 wins, 6 losses**.

## Main takeaway

The strategy had positive out-of-sample returns on all five assets, which is worth studying further.

But the sample is still small, some test periods overlap, and every result was below buy-and-hold on total return. So this is **research evidence, not a proven trading strategy**.

## How to run

Install packages:

```bash
pip install -r requirements.txt
```

Run one backtest:

```bash
python backtest.py --ticker SPY --start 2010-01-01 --end 2024-01-01 --strategy confirmed_sweep
```

Run the five-asset test:

```bash
python validate_multi_asset.py
```

## Files

```text
backtest.py               Runs one backtest
validate_multi_asset.py   Runs the five-asset test
strategy.py               Trading rules
engine.py                 Trade simulation
metrics.py                Performance metrics
data/loader.py             Loads market data
results/                   Report, charts, and results
```

## Note

This is an educational research project based on historical data. Past results do not guarantee future performance.
