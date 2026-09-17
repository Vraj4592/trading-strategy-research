"""
Walks through price bars one at a time, asks the strategy for a
decision using only data visible up to that point, and simulates
a fill with fees + slippage. No look-ahead: decide(df, i) only ever
sees df.iloc[:i+1].
"""

from dataclasses import dataclass, field
import pandas as pd

from strategy import Strategy


@dataclass
class Trade:
    entry_date: pd.Timestamp
    entry_price: float
    exit_date: pd.Timestamp = None
    exit_price: float = None
    side: str = "LONG"
    size: float = 1.0
    fees_paid: float = 0.0
    exit_reason: str = None  # "signal" or "stop_loss"

    @property
    def pnl(self) -> float:
        if self.exit_price is None:
            return 0.0
        gross = (self.exit_price - self.entry_price) * self.size
        return gross - self.fees_paid

    @property
    def return_pct(self) -> float:
        if self.exit_price is None:
            return 0.0
        return (self.exit_price - self.entry_price) / self.entry_price


@dataclass
class BacktestResult:
    equity_curve: pd.Series
    trades: list = field(default_factory=list)
    starting_capital: float = 10_000.0


def run_backtest(df: pd.DataFrame, strat: Strategy,
                  starting_capital: float = 10_000.0,
                  fee_bps: float = 5.0,
                  slippage_bps: float = 2.0,
                  position_pct: float = 1.0,
                  stop_loss_pct: float = None) -> BacktestResult:
    """
    fee_bps:       round-trip fee in basis points of trade notional (per fill)
    slippage_bps:  extra cost in basis points applied to every fill price
    position_pct:  fraction of capital committed per trade (1.0 = all-in)
    stop_loss_pct: if set (e.g. 0.05 for 5%), exits a LONG position the
                    moment the bar's Low drops that far below entry price,
                    regardless of what the strategy's signal says. None
                    disables it (behavior identical to before this option
                    existed — pure signal-based exits only).
    """
    df = strat.prepare(df).reset_index()
    date_col = df.columns[0]  # "Date"

    cash = starting_capital
    position = None  # Trade or None
    equity_curve = []
    trades = []

    def fill_price(close: float, direction: str) -> float:
        slip = close * (slippage_bps / 10_000)
        return close + slip if direction == "BUY" else close - slip

    for i in range(len(df)):
        close = df["Close"].iloc[i]
        low = df["Low"].iloc[i]
        date = df[date_col].iloc[i]

        # Stop-loss check happens BEFORE the strategy signal: if the bar's
        # low breached the stop, that exit would have happened intrabar,
        # ahead of any end-of-bar signal decision.
        if position is not None and stop_loss_pct is not None:
            stop_price = position.entry_price * (1 - stop_loss_pct)
            if low <= stop_price:
                px = fill_price(stop_price, "SELL")
                notional = px * position.size
                fee = notional * (fee_bps / 10_000)
                position.exit_date = date
                position.exit_price = px
                position.fees_paid += fee
                position.exit_reason = "stop_loss"
                cash += notional - fee
                trades.append(position)
                position = None
                equity_curve.append(cash)
                continue

        signal = strat.decide(df, i)

        if position is None and signal == "BUY":
            px = fill_price(close, "BUY")
            notional = cash * position_pct
            size = notional / px
            fee = notional * (fee_bps / 10_000)
            cash -= (notional + fee)
            position = Trade(entry_date=date, entry_price=px, size=size, fees_paid=fee)

        elif position is not None and signal == "SELL":
            px = fill_price(close, "SELL")
            notional = px * position.size
            fee = notional * (fee_bps / 10_000)
            position.exit_date = date
            position.exit_price = px
            position.fees_paid += fee
            position.exit_reason = "signal"
            cash += notional - fee
            trades.append(position)
            position = None

        # mark-to-market equity: cash + open position value
        if position is not None:
            equity = cash + position.size * close
        else:
            equity = cash
        equity_curve.append(equity)

    # close any still-open position at the last bar so metrics are complete
    if position is not None:
        last_close = df["Close"].iloc[-1]
        px = fill_price(last_close, "SELL")
        notional = px * position.size
        fee = notional * (fee_bps / 10_000)
        position.exit_date = df[date_col].iloc[-1]
        position.exit_price = px
        position.fees_paid += fee
        cash += notional - fee
        trades.append(position)
        equity_curve[-1] = cash

    equity_series = pd.Series(equity_curve, index=df[date_col], name="equity")
    return BacktestResult(equity_curve=equity_series, trades=trades,
                           starting_capital=starting_capital)
