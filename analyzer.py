import yfinance as yf
import pandas as pd
import numpy as np
from config import LOOKBACK_DAYS, BULLISH, BEARISH, NEUTRAL

class MorningAnalyzer:
    """
    Handles the 'Baseline' analysis.
    Established the morning thesis by looking at historical data.
    """
    def __init__(self, ticker):
        self.ticker = ticker
        self.data = None
        self.support = None
        self.resistance = None

    def fetch_data(self):
        print(f"[Analyzer] Fetching last {LOOKBACK_DAYS} days of data for {self.ticker}...")
        ticker_obj = yf.Ticker(self.ticker)
        self.data = ticker_obj.history(period=f"{LOOKBACK_DAYS}d")
        if self.data.empty:
            raise Exception(f"Could not fetch data for {self.ticker}. Check the ticker symbol.")
        return self.data

    def calculate_levels(self):
        """
        Calculates support and resistance using a combination of
        historical extremes and volatility (Standard Deviation).
        """
        # Use the last 30 days for standard deviation
        std = self.data['Close'].std()
        mean = self.data['Close'].mean()

        # Support = Max(Historical Low, Mean - 2*Std)
        # Resistance = Min(Historical High, Mean + 2*Std)
        self.support = max(self.data['Low'].min(), mean - (2 * std))
        self.resistance = min(self.data['High'].max(), mean + (2 * std))

        print(f"[Analyzer] Levels Established -> Support: {self.support:.2f}, Resistance: {self.resistance:.2f}")
        return self.support, self.resistance

    def get_initial_prediction(self, current_price):
        """
        Determines the starting thesis based on price position and volatility.
        """
        # Dynamic threshold based on volatility
        std = self.data['Close'].std()
        vol_buffer = std * 0.2 # 20% of one std dev

        midpoint = (self.support + self.resistance) / 2

        if current_price <= midpoint - vol_buffer:
            return BULLISH, f"Price is in the lower regime (₹{current_price:.2f}), expecting a bounce."
        elif current_price >= midpoint + vol_buffer:
            return BEARISH, f"Price is in the upper regime (₹{current_price:.2f}), expecting a pullback."
        else:
            return NEUTRAL, "Price is in the balanced neutral zone."

    def get_thesis(self):
        self.fetch_data()
        self.calculate_levels()
        current_price = self.data['Close'].iloc[-1]
        prediction, reason = self.get_initial_prediction(current_price)

        # Calculate volatility for more realistic hold times
        volatility = self.data['Close'].pct_change().std()

        if prediction == BULLISH:
            dist = (self.resistance - current_price) / current_price
            # Hold time = distance / (avg daily return * confidence factor)
            # Conservative estimate: assume 0.5% daily move
            days = int(dist / 0.005) if dist > 0 else 5
            hold_time = f"{max(3, min(days, 14))} - {max(5, min(days + 7, 21))} Days"
            exit_signal = f"Target: ₹{self.resistance:.2f} | Stop: ₹{self.support:.2f}"
        elif prediction == BEARISH:
            dist = (current_price - self.support) / current_price
            days = int(dist / 0.005) if dist > 0 else 5
            hold_time = f"{max(3, min(days, 14))} - {max(5, min(days + 7, 21))} Days"
            exit_signal = f"Target: ₹{self.support:.2f} | Stop: ₹{self.resistance:.2f}"
        else:
            hold_time = "1 - 5 Days"
            exit_signal = "Price break out of range"

        return {
            "prediction": prediction,
            "reason": reason,
            "support": self.support,
            "resistance": self.resistance,
            "start_price": current_price,
            "hold_time": hold_time,
            "exit_signal": exit_signal
        }
