"""
Pulls OHLCV data for a ticker and caches it locally as CSV.

Primary source: yfinance (needs internet). If that fails (no connection,
rate limit, ticker not found) and a cached CSV already exists, falls back
to the cache. If you have your own OHLCV CSV (columns: Date, Open, High,
Low, Close, Volume), just drop it in data/cache/<TICKER>_<INTERVAL>.csv
and it will be used automatically.
"""

import os
import pandas as pd

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
os.makedirs(CACHE_DIR, exist_ok=True)


def _cache_path(ticker: str, interval: str) -> str:
    return os.path.join(CACHE_DIR, f"{ticker.upper()}_{interval}.csv")


def load_ohlcv(ticker: str, start: str, end: str, interval: str = "1d",
                force_refresh: bool = False) -> pd.DataFrame:
    """
    Returns a DataFrame indexed by Date with columns:
    Open, High, Low, Close, Volume

    ticker:   e.g. "SPY", "AAPL", "BTC-USD"
    start/end: "YYYY-MM-DD"
    interval: "1d", "1h", "15m", etc. (yfinance-supported intervals)
    """
    path = _cache_path(ticker, interval)

    if not force_refresh and os.path.exists(path):
        df = pd.read_csv(path, parse_dates=["Date"], index_col="Date")
        # Only trust the cache if it actually covers the requested range —
        # otherwise a narrower earlier download silently looks "good enough"
        # for a wider later request.
        covers_start = not df.empty and df.index.min() <= pd.Timestamp(start)
        covers_end = not df.empty and df.index.max() >= pd.Timestamp(end)
        if covers_start and covers_end:
            return df.loc[(df.index >= start) & (df.index <= end)]

    try:
        import yfinance as yf
        raw = yf.download(ticker, start=start, end=end, interval=interval,
                           auto_adjust=True, progress=False)
        if raw.empty:
            raise ValueError(f"No data returned for {ticker}")
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        raw.index.name = "Date"
        raw = raw[["Open", "High", "Low", "Close", "Volume"]]
        raw.to_csv(path)
        return raw
    except Exception as e:
        if os.path.exists(path):
            print(f"[loader] yfinance failed ({e}); using stale cache at {path}")
            df = pd.read_csv(path, parse_dates=["Date"], index_col="Date")
            return df.loc[(df.index >= start) & (df.index <= end)]
        raise RuntimeError(
            f"Could not fetch {ticker} via yfinance and no cache exists at {path}. "
            f"Either connect to the internet, or drop a CSV there with columns "
            f"Date,Open,High,Low,Close,Volume. Original error: {e}"
        )


def generate_synthetic(ticker: str, start: str, end: str, seed: int = 42) -> pd.DataFrame:
    """
    Random-walk OHLCV generator for testing the pipeline offline, with
    no real data source needed. Not for actual research conclusions.
    """
    import numpy as np
    dates = pd.bdate_range(start, end)
    rng = np.random.default_rng(seed)
    n = len(dates)
    returns = rng.normal(0.0003, 0.012, n)
    close = 100 * (1 + returns).cumprod()
    open_ = close * (1 + rng.normal(0, 0.002, n))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.003, n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.003, n)))
    volume = rng.integers(1_000_000, 5_000_000, n)
    df = pd.DataFrame({"Open": open_, "High": high, "Low": low,
                        "Close": close, "Volume": volume}, index=dates)
    df.index.name = "Date"
    path = _cache_path(ticker, "1d")
    df.to_csv(path)
    return df
