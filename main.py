import asyncio
from analyzer import MorningAnalyzer
from streamer import PriceStreamer
from engine import SignalEngine
from config import TICKER

async def main():
    print("--- SENSEI: Stock Event-driven Signal Engine ---")

    try:
        # 1. Morning Analysis Phase
        analyzer = MorningAnalyzer(TICKER)
        thesis = analyzer.get_thesis()

        # 2. Engine Initialization Phase
        engine = SignalEngine(TICKER, thesis)

        # 3. Real-time Streaming Phase
        streamer = PriceStreamer(TICKER)

        # Start the stream and pass the engine's update handler as the callback
        await streamer.stream(engine.on_price_update)

    except KeyboardInterrupt:
        print("\n[System] Shutting down SENSEI...")
    except Exception as e:
        print(f"\n[Error] System failure: {e}")

if __name__ == "__main__":
    # Run the async loop
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
