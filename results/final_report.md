# Trading Strategy Research — Final Report

## Question

Can one liquidity-sweep reversal strategy show useful results across different markets?

## Strategy

The final strategy is `confirmed_sweep`.

It looks for a liquidity sweep reversal and only allows a buy when price is above its 100-bar average.

## Test setup

- **Assets:** SPY, QQQ, AAPL, BTC-USD, ETH-USD
- **Stocks/ETFs:** 2010–2023
- **Crypto:** 2018–2023
- **Split:** first 80% for development, last 20% for out-of-sample testing
- **Costs:** 5 bps fee + 2 bps slippage per fill
- **Starting capital:** $10,000 per test

## Out-of-sample results

| Asset | Trades | Win Rate | Return | Sharpe | Max Drawdown |
|---|---:|---:|---:|---:|---:|
| SPY | 5 | 100.0% | 10.99% | 0.71 | -4.83% |
| QQQ | 6 | 83.33% | 5.07% | 0.21 | -18.61% |
| AAPL | 5 | 60.0% | 9.11% | 0.33 | -15.45% |
| BTC-USD | 5 | 60.0% | 48.32% | 1.25 | -13.47% |
| ETH-USD | 6 | 83.33% | 20.82% | 0.67 | -18.00% |

## Combined result

- **27 trades**
- **21 wins / 6 losses**
- **77.78% win rate**
- **Average win:** +5.86%
- **Average loss:** -5.08%
- **Estimated expectancy per trade:** +3.43%

## What I learned

The strategy showed positive out-of-sample returns on all five assets, so the idea is worth testing more.

The main weakness is the small sample. Some test periods also overlap, so the 27 trades are not fully independent.

The strategy also made less total return than buy-and-hold on every asset tested.

## Conclusion

The project found **interesting evidence**, but not enough to call the strategy proven.

The next step would be to test more trades, more market conditions, and non-overlapping time periods.
