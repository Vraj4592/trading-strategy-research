"""
Strategy logic lives here, isolated from data loading and execution.
A strategy takes the price history up to and including "today" and
returns a signal: "BUY", "SELL", or "HOLD".

Swap MovingAverageCrossover for your own rules (SMC/ICT structure
breaks, liquidity sweeps, FVGs, whatever) — the engine doesn't care
how the decision is made, only what it returns.
"""

import pandas as pd


class Strategy:
    """Base class. Subclass and implement decide()."""

    name = "base"

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add any indicator columns here. Called once on the full df."""
        return df

    def decide(self, df: pd.DataFrame, i: int) -> str:
        """
        df: the prepared DataFrame
        i:  integer index of "today" (only df.iloc[:i+1] is visible —
            do not look ahead past i)
        returns: "BUY", "SELL", or "HOLD"
        """
        raise NotImplementedError


class MovingAverageCrossover(Strategy):
    """
    Simple, well-known baseline: go long when the fast SMA crosses
    above the slow SMA, exit when it crosses back below.
    Use this to validate the pipeline before wiring in a real edge.
    """

    name = "ma_crossover"

    def __init__(self, fast: int = 20, slow: int = 50):
        self.fast = fast
        self.slow = slow

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["sma_fast"] = df["Close"].rolling(self.fast).mean()
        df["sma_slow"] = df["Close"].rolling(self.slow).mean()
        return df

    def decide(self, df: pd.DataFrame, i: int) -> str:
        if i < self.slow:
            return "HOLD"
        fast_now, slow_now = df["sma_fast"].iloc[i], df["sma_slow"].iloc[i]
        fast_prev, slow_prev = df["sma_fast"].iloc[i - 1], df["sma_slow"].iloc[i - 1]
        if pd.isna(fast_prev) or pd.isna(slow_prev):
            return "HOLD"
        crossed_up = fast_prev <= slow_prev and fast_now > slow_now
        crossed_down = fast_prev >= slow_prev and fast_now < slow_now
        if crossed_up:
            return "BUY"
        if crossed_down:
            return "SELL"
        return "HOLD"


class BreakoutRange(Strategy):
    """
    Second example baseline: buy when price breaks above the highest
    high of the last `lookback` bars (momentum breakout), exit when it
    breaks below the lowest low. A closer cousin to structure-break
    style rules than a moving average is, without needing swing-point
    detection yet.
    """

    name = "breakout_range"

    def __init__(self, lookback: int = 20):
        self.lookback = lookback

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["range_high"] = df["High"].rolling(self.lookback).max().shift(1)
        df["range_low"] = df["Low"].rolling(self.lookback).min().shift(1)
        return df

    def decide(self, df: pd.DataFrame, i: int) -> str:
        if i < self.lookback:
            return "HOLD"
        close = df["Close"].iloc[i]
        rng_high = df["range_high"].iloc[i]
        rng_low = df["range_low"].iloc[i]
        if pd.isna(rng_high) or pd.isna(rng_low):
            return "HOLD"
        if close > rng_high:
            return "BUY"
        if close < rng_low:
            return "SELL"
        return "HOLD"


class LiquiditySweepReversal(Strategy):
    """
    SMC/ICT-style: price sweeps below a recent swing low (grabs resting
    stop-loss liquidity) then closes back above it the same bar or the
    next — read as a false breakdown / reversal. Mirror logic on the
    short side: sweep above a recent swing high then close back below.

    swing_lookback: bars used to define "the recent swing low/high"
                     (the lowest low / highest high of the last N bars,
                     excluding the current bar)
    confirm_bars:    how many bars the sweep has to close back inside
                      the range to count as confirmed (1 = same bar)
    """

    name = "liquidity_sweep"

    def __init__(self, swing_lookback: int = 15, confirm_bars: int = 1):
        self.swing_lookback = swing_lookback
        self.confirm_bars = confirm_bars

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        # swing levels computed from bars BEFORE today only (shift(1))
        df["swing_low"] = df["Low"].rolling(self.swing_lookback).min().shift(1)
        df["swing_high"] = df["High"].rolling(self.swing_lookback).max().shift(1)
        return df

    def decide(self, df: pd.DataFrame, i: int) -> str:
        if i < self.swing_lookback + self.confirm_bars:
            return "HOLD"

        low, high, close = df["Low"].iloc[i], df["High"].iloc[i], df["Close"].iloc[i]
        swing_low = df["swing_low"].iloc[i]
        swing_high = df["swing_high"].iloc[i]
        if pd.isna(swing_low) or pd.isna(swing_high):
            return "HOLD"

        # Bullish sweep: wicked below the recent swing low, closed back above it
        swept_low = low < swing_low
        reclaimed_low = close > swing_low
        if swept_low and reclaimed_low:
            return "BUY"

        # Bearish sweep: wicked above the recent swing high, closed back below it
        swept_high = high > swing_high
        reclaimed_high = close < swing_high
        if swept_high and reclaimed_high:
            return "SELL"

        return "HOLD"


class ConfirmedSweep(Strategy):
    """
    Combination strategy: only takes a liquidity-sweep BUY when price is
    also trading above its own longer-term average — i.e. the reversal
    has to line up with the broader trend, not fight it. Filters out
    sweeps that happen inside a downtrend, which is where liquidity_sweep
    alone tends to lose.

    swing_lookback: same as LiquiditySweepReversal — defines the recent
                     swing low/high for the sweep
    trend_lookback:  bars used for the trend filter (a simple average);
                      BUY signals are only kept if Close > this average
    """

    name = "confirmed_sweep"

    def __init__(self, swing_lookback: int = 15, trend_lookback: int = 100):
        self.swing_lookback = swing_lookback
        self.trend_lookback = trend_lookback

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["swing_low"] = df["Low"].rolling(self.swing_lookback).min().shift(1)
        df["swing_high"] = df["High"].rolling(self.swing_lookback).max().shift(1)
        df["trend_avg"] = df["Close"].rolling(self.trend_lookback).mean()
        return df

    def decide(self, df: pd.DataFrame, i: int) -> str:
        if i < max(self.swing_lookback, self.trend_lookback) + 1:
            return "HOLD"

        low, high, close = df["Low"].iloc[i], df["High"].iloc[i], df["Close"].iloc[i]
        swing_low = df["swing_low"].iloc[i]
        swing_high = df["swing_high"].iloc[i]
        trend_avg = df["trend_avg"].iloc[i]
        if pd.isna(swing_low) or pd.isna(swing_high) or pd.isna(trend_avg):
            return "HOLD"

        # Bullish sweep, only taken if price is above its own trend average
        swept_low = low < swing_low
        reclaimed_low = close > swing_low
        if swept_low and reclaimed_low and close > trend_avg:
            return "BUY"

        # Exit unconditionally on the bearish sweep (no trend filter on exits —
        # getting out fast matters more than confirming the exit direction)
        swept_high = high > swing_high
        reclaimed_high = close < swing_high
        if swept_high and reclaimed_high:
            return "SELL"

        return "HOLD"


STRATEGIES = {
    "ma_crossover": MovingAverageCrossover,
    "breakout_range": BreakoutRange,
    "liquidity_sweep": LiquiditySweepReversal,
    "confirmed_sweep": ConfirmedSweep,
}
