import asyncio
import pandas as pd
import numpy as np
import yfinance as yf
from config import BULLISH, BEARISH, NEUTRAL, TICKER

class SignalEngine:
    """
    SENSEI 2.2 PRO-GRADE ENGINE
    Implements Market Guard, Regime Scaling, and Dynamic Windowing.
    """
    def __init__(self, ticker, thesis):
        self.ticker = ticker
        self.prediction = thesis['prediction']
        self.reason = thesis['reason']
        self.support = thesis['support']
        self.resistance = thesis['resistance']
        self.start_price = thesis['start_price']

        # Trade State
        self.active_position = False
        self.current_direction = None
        self.trailing_stop = None
        self.highest_price_since_entry = 0.0
        self.lowest_price_since_entry = float('inf')

        # Cached daily closes for the trend-break exit (SMA20).
        self._close_series = None
        try:
            hist = yf.download(self.ticker, period="1y", progress=False)
            if not hist.empty:
                if isinstance(hist.columns, pd.MultiIndex):
                    hist.columns = hist.columns.get_level_values(0)
                self._close_series = hist['Close'].squeeze().dropna()
        except Exception:
            self._close_series = None

        # Cached USDINR series for the currency guard.
        if ".NS" in self.ticker:
            self._usdinr_series = self._fetch_usdinr()
        else:
            self._usdinr_series = None

        print(f"\n{'='*60}")
        print(f"SENSEI 2.6 HYBRID ENGINE ACTIVE (Technical-Only)")
        print(f"Ticker: {self.ticker} | Thesis: {self.prediction}")
        print(f"Safe-Range: ${self.support:.2f} to ${self.resistance:.2f}")
        print(f"{'='*60}\n")

    def get_market_regime(self):
        """
        The 'Market Guard'. Checks the broad index to see if we have a tailwind.
        """
        try:
            if "USD" in self.ticker:
                index_ticker = "^GSPC"
            elif ".NS" in self.ticker:
                index_ticker = "^NSEI"
            else:
                index_ticker = "^GSPC"

            idx_df = yf.download(index_ticker, period="1y", progress=False)
            if idx_df.empty or len(idx_df) < 60: return NEUTRAL
            close = idx_df['Close'].squeeze()
            last = close.iloc[-1]
            sma50 = close.rolling(50).mean().iloc[-1]

            # Real drift filter: index above/below its 50-day trend.
            if last > sma50 * 1.01: return BULLISH
            if last < sma50 * 0.99: return BEARISH
            return NEUTRAL
        except:
            return NEUTRAL

    def get_dynamic_window(self, df):
        vol = df['Close'].pct_change().std() * np.sqrt(252)
        if vol > 0.6: return 10
        if vol > 0.3: return 20
        return 40

    def _fetch_usdinr(self):
        """USDINR close series for the currency guard (cached once)."""
        try:
            fx = yf.download("INR=X", period="1y", progress=False)
            if fx.empty:
                return None
            if isinstance(fx.columns, pd.MultiIndex):
                fx.columns = fx.columns.get_level_values(0)
            return fx['Close'].squeeze().dropna()
        except Exception:
            return None

    def get_currency_guard(self):
        """
        Currency/Macro guard. Verified out-of-sample on 18 NSE stocks:
        blocking longs while USDINR trends above its SMA50 cut the chop-year
        loss by a third and flipped the bear year positive. VIX and crude
        gates were tested and HURT results — deliberately not included.
        """
        if self._usdinr_series is None or len(self._usdinr_series) < 60:
            return NEUTRAL
        last = self._usdinr_series.iloc[-1]
        sma50 = self._usdinr_series.rolling(50).mean().iloc[-1]
        if last > sma50 * 1.005:
            return BEARISH   # rupee weakening -> block longs
        return NEUTRAL

    def get_consensus_confidence(self, df=None, global_df=None):
        """
        SENSEI 2.6: Rule-only consensus (AI removed — proven to add no
        out-of-sample edge). Trend + Momentum votes, gated by market regime.
        """
        try:
            asset_class = "CRYPTO" if "USD" in self.ticker else "EQUITY"

            # OPTIMIZATION: Use passed df if available, otherwise download
            if df is not None:
                # Ensure columns are flattened if it's a MultiIndex
                if isinstance(df.columns, pd.MultiIndex):
                    df = df.copy()
                    df.columns = df.columns.get_level_values(0)
            else:
                df = yf.download(self.ticker, period="1y", progress=False)
                if df.empty: return NEUTRAL, 0.0
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)

            close = df['Close'].squeeze()

            # 1. Technical Component
            short_sma = close.rolling(20).mean().iloc[-1]
            med_sma = close.rolling(50).mean().iloc[-1]
            curr_price = close.iloc[-1]

            vol_mult = 0.05 if asset_class == "CRYPTO" else 0.03
            is_oversold = curr_price < (med_sma * (1 - vol_mult))

            if is_oversold:
                trend_dir = BULLISH
                trend_conf = 75
            else:
                trend_dir = BULLISH if short_sma > med_sma else BEARISH
                # Strength of the SMA20/50 cross, scaled to a usable 0-100 bar.
                spread = abs(short_sma - med_sma) / max(med_sma, 1e-9)
                trend_conf = min(100, spread / 0.02 * 100)

            # 2. Momentum (MACD)
            ema12 = close.ewm(span=12, adjust=False).mean().iloc[-1]
            ema26 = close.ewm(span=26, adjust=False).mean().iloc[-1]
            macd = ema12 - ema26
            sig = (close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()).ewm(span=9, adjust=False).mean().iloc[-1]
            mom_dir = BULLISH if macd > sig else BEARISH
            # MACD gap relative to a 1% price move anchors the scale.
            mom_conf = min(100, abs(macd - sig) / max(curr_price * 0.01, 1e-9) * 100)

            # 3. Consensus — rule-only vote
            direction_counts = {}
            for d in [trend_dir, mom_dir]:
                direction_counts[d] = direction_counts.get(d, 0) + 1

            sorted_votes = sorted(direction_counts.items(), key=lambda x: x[1], reverse=True)
            final_dir, vote_count = sorted_votes[0]

            if vote_count == 2:
                final_conf = (trend_conf + mom_conf) / 2
            else:
                final_dir = NEUTRAL
                final_conf = min(trend_conf, mom_conf) / 2

            # MARKET GUARD / REGIME GATE
            market_regime = self.get_market_regime()
            if market_regime != NEUTRAL and market_regime != final_dir:
                # Only trade with the index drift (the one signal that held up
                # out-of-sample). Counter-drift signals get blocked entirely.
                return NEUTRAL, 0.0

            # CURRENCY GUARD: block longs while USDINR trends up.
            if self.get_currency_guard() == BEARISH and final_dir == BULLISH:
                return NEUTRAL, 0.0

            # Volatility Penalty
            recent_vol = close.pct_change().tail(10).std()
            hist_vol = close.pct_change().std()
            if recent_vol > (hist_vol * 2):
                final_conf *= 0.85

            return final_dir, min(100, final_conf)
        except Exception as e:
            print(f"[Engine] Confidence calc error: {e}")
            return NEUTRAL, 0.0

    async def on_price_update(self, price):
        print(f"[Real-time] ${price:.2f}", end='\r')

        if self.active_position:
            # Adaptive trend-break exit. In a confirmed-bullish index regime we
            # let winners run (exit on close < SMA50). Otherwise we cut fast
            # (close < SMA20), which is what holds bear-year losses to near the
            # baseline. Validated out-of-sample vs fixed SMA20.
            trend_broken = False
            if self._close_series is not None and len(self._close_series) >= 50:
                exit_sma = 50 if self.get_market_regime() == BULLISH else 20
                updated = self._close_series.copy()
                updated.iloc[-1] = price
                sma = updated.rolling(exit_sma).mean().iloc[-1]
                if not np.isnan(sma) and price < sma:
                    trend_broken = True

            # Emergency stop: never lose more than 8% from the peak.
            if self.current_direction == BULLISH:
                self.highest_price_since_entry = max(self.highest_price_since_entry, price)
                crash_hit = price <= self.highest_price_since_entry * 0.92
            else:
                self.lowest_price_since_entry = min(self.lowest_price_since_entry, price)
                crash_hit = price >= self.lowest_price_since_entry * 1.08

            if trend_broken or crash_hit:
                reason = "Emergency Stop" if crash_hit else "Trend-Break Exit"
                print(f"\n\n{'#'*60}\n💰 CLOSE {self.current_direction} POSITION: {reason}\nPrice: ${price:.2f}\n{'#'*60}\n")
                self.active_position = False
                self.current_direction = None
                return

        if not self.active_position:
            trigger_dir = self.prediction
            if self.prediction == BULLISH and price < self.support: trigger_dir = BEARISH
            elif self.prediction == BEARISH and price > self.resistance: trigger_dir = BULLISH
            elif self.prediction == NEUTRAL:
                if price < self.support: trigger_dir = BEARISH
                elif price > self.resistance: trigger_dir = BULLISH

            if trigger_dir != NEUTRAL:
                dir_consensus, confidence = self.get_consensus_confidence()

                if dir_consensus == trigger_dir and confidence >= 55:
                    print(f"\n\n{'!'*60}")
                    print(f"🚀 SENSEI 2.2 HIGH-CONFIDENCE SIGNAL")
                    print(f"Direction: {trigger_dir} | Confidence: {confidence:.1f}%")
                    print(f"Entry Price: ${price:.2f}")
                    print(f"{'!'*60}\n")

                    self.active_position = True
                    self.current_direction = trigger_dir
                    self.highest_price_since_entry = price
                    self.lowest_price_since_entry = price
                    self.trailing_stop = price * 0.98 if trigger_dir == BULLISH else price * 1.02
