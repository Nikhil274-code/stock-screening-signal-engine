import asyncio
import random
import yfinance as yf
from config import TICKER, UPDATE_INTERVAL

class PriceStreamer:
    """
    Handles the 'Observation' layer.
    Streams real-time price updates for the ticker.
    """
    def __init__(self, ticker, simulation_mode=True):
        self.ticker = ticker
        self.simulation_mode = simulation_mode
        self.current_price = None

    async def get_latest_price(self):
        """
        In a real app, this would be a WebSocket message.
        For this project, we fetch from yfinance and add noise to simulate real-time movement.
        """
        if self.simulation_mode:
            # Fetch current price as base
            ticker_obj = yf.Ticker(self.ticker)
            # We get the 'fast_info' for the latest price
            try:
                base_price = ticker_obj.fast_info['last_price']
            except:
                # Fallback if fast_info fails
                base_price = ticker_obj.history(period="1d")['Close'].iloc[-1]

            # Add small random volatility to simulate a live ticker
            volatility = base_price * 0.001 # 0.1% movement
            self.current_price = base_price + random.uniform(-volatility, volatility)
        else:
            # PLACEHOLDER for real WebSocket integration (e.g., Alpaca, Polygon)
            # async with websockets.connect(URL) as ws:
            #    msg = await ws.recv()
            #    self.current_price = parse(msg)
            raise NotImplementedError("Real-time WebSocket mode requires a paid API key.")

        return self.current_price

    async def stream(self, callback):
        """
        Infinite loop that fetches price and sends it to the callback function.
        """
        print(f"[Streamer] Starting real-time stream for {self.ticker}...")
        while True:
            price = await self.get_latest_price()
            await callback(price)
            await asyncio.sleep(UPDATE_INTERVAL)
