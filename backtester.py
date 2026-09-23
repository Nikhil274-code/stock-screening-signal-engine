"""Backtester for the CURRENT engine (technical-only).

Simulates the live rule logic (trend + MACD consensus, NSEI regime gate,
trend-break exit, 8% emergency stop) with transaction costs and per-trade
risk capping. Reports account equity, not raw PnL, so the numbers are honest.
"""
import numpy as np
import pandas as pd
import yfinance as yf
from config import BULLISH, BEARISH, NEUTRAL

COST = 0.001        # 0.1% per leg (STT + slippage proxy)
RISK_PER_TRADE = 0.01   # 1% of account risked per trade
EMERGENCY_STOP = 0.08   # stop-loss distance used for sizing
INITIAL_CAPITAL = 100_000
CONF_THRESHOLD = 55


class Backtester:
    def __init__(self, ticker, start=None, end=None):
        self.ticker = ticker
        self.start = start
        self.end = end
        self.regime_cache = {}

    def _regime_at(self, nclose, d):
        before = nclose[nclose.index < d]
        if len(before) < 50:
            return NEUTRAL
        sma50 = before.rolling(50).mean().iloc[-1]
        last = before.iloc[-1]
        if last > sma50 * 1.01: return BULLISH
        if last < sma50 * 0.99: return BEARISH
        return NEUTRAL

    def _index_close(self):
        if "USD" in self.ticker:
            idx = yf.download("^GSPC", period="5y", progress=False)
        else:
            idx = yf.download("^NSEI", period="5y", progress=False)
        return idx["Close"].squeeze() if not idx.empty else pd.Series(dtype=float)

    def _signal(self, df, i):
        close = df["Close"].squeeze()
        short = close.rolling(20).mean().iloc[i]
        med = close.rolling(50).mean().iloc[i]
        curr = float(close.iloc[i])
        if not np.isnan(short) and not np.isnan(med):
            trend_dir = BULLISH if short > med else BEARISH
            trend_conf = min(100, abs(short - med) / max(med, 1e-9) / 0.02 * 100)
        else:
            return NEUTRAL, 0.0
        e12 = close.ewm(span=12, adjust=False).mean().iloc[i]
        e26 = close.ewm(span=26, adjust=False).mean().iloc[i]
        macd = e12 - e26
        sig = (close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()).ewm(
            span=9, adjust=False).mean().iloc[i]
        mom_dir = BULLISH if macd > sig else BEARISH
        mom_conf = min(100, abs(macd - sig) / max(curr * 0.01, 1e-9) * 100)
        counts = {}
        for d, c in [(trend_dir, trend_conf), (mom_dir, mom_conf)]:
            counts[d] = counts.get(d, 0) + 1
        final_dir, votes = max(counts.items(), key=lambda x: x[1])
        if votes == 1:
            return final_dir, 0.0
        return final_dir, min(100, (trend_conf + mom_conf) / 2)

    def run(self):
        df = yf.download(self.ticker, start=self.start, end=self.end, progress=False)
        if df.empty:
            return {"error": "No data"}
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        close = df["Close"].squeeze()
        nclose = self._index_close()

        equity = INITIAL_CAPITAL
        trades = []
        state = None
        entry = peak = None
        position_notional = 0.0

        for i in range(50, len(df)):
            d = df.index[i]
            price = float(close.iloc[i])

            if state is None:
                reg = self._regime_at(nclose, d)
                if reg != BEARISH:
                    dir_, conf = self._signal(df, i)
                    if dir_ == BULLISH and conf >= CONF_THRESHOLD:
                        entry = peak = price
                        entry_date = d
                        state = "LONG"
                        # Size so that a full emergency stop loses RISK_PER_TRADE.
                        position_notional = equity * (RISK_PER_TRADE / EMERGENCY_STOP)
                continue

            peak = max(peak, price)
            sma20 = close.rolling(20).mean().iloc[i]
            trend_break = not np.isnan(sma20) and price < sma20
            crash = price <= peak * (1 - EMERGENCY_STOP)
            if trend_break or crash or i == len(df) - 1:
                exit_price = price
                gross_ret = (exit_price - entry) / entry
                net_ret = gross_ret - 2 * COST
                pnl = position_notional * net_ret
                equity += pnl
                trades.append({
                    "entry_date": str(entry_date.date()),
                    "exit_date": d,
                    "entry": round(entry, 2),
                    "exit": round(exit_price, 2),
                    "gross_ret": round(gross_ret * 100, 2),
                    "net_ret": round(net_ret * 100, 2),
                    "equity": round(equity, 2),
                    "reason": "crash" if crash else "trend_break",
                })
                state = None

        n = len(trades)
        wins = sum(1 for t in trades if t["net_ret"] > 0)
        gross = sum(t["gross_ret"] for t in trades)
        net = sum(t["net_ret"] for t in trades)
        return {
            "ticker": self.ticker,
            "trades": n,
            "win_rate": round(wins / n, 4) if n else 0,
            "avg_net_ret_pct": round(net / n, 2) if n else 0,
            "gross_pnl_pct": round(gross, 2),
            "net_pnl_pct": round(net, 2),
            "account_return_pct": round(((equity - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100, 2),
            "final_equity": round(equity, 2),
            "trade_log": trades,
        }


    def _nse_buyhold_return(self):
        df = yf.download(self.ticker, start=self.start, end=self.end, progress=False)
        if df.empty:
            return 0
        c = df["Close"].squeeze()
        return round((c.iloc[-1] / c.iloc[0] - 1) * 100, 2)


def main():
    import sys
    ticker = sys.argv[1] if len(sys.argv) > 1 else "RELIANCE.NS"
    start = sys.argv[2] if len(sys.argv) > 2 else None
    end = sys.argv[3] if len(sys.argv) > 3 else None
    bt = Backtester(ticker, start=start, end=end)
    res = bt.run()
    for k, v in res.items():
        if k != "trade_log":
            print(f"{k}: {v}")
    print(f"buyhold_return_pct: {bt._nse_buyhold_return()}")


if __name__ == "__main__":
    main()