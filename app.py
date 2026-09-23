from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import asyncio
import yfinance as yf
import pandas as pd
import numpy as np
from config import TICKER, BULLISH, BEARISH, NEUTRAL
from analyzer import MorningAnalyzer
from engine import SignalEngine
from backtester import Backtester
import os
import time
import database as db

def clean_ticker(ticker):
    """Removes .NS from ticker for display purposes."""
    return ticker.replace(".NS", "") if ticker else ticker

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state for relative ranking
GLOBAL_RANKINGS = {}
GLOBAL_SCORES = {}
RANKINGS_CACHE_TIME = 0
RANKINGS_DURATION = 3600
GLOBAL_MACRO_DF = None
MACRO_CACHE_DURATION = 3600
MACRO_CACHE_TIME = 0

# GLOBAL DELTA CACHE
GLOBAL_DELTAS = {}
DELTAS_CACHE_TIME = 0
DELTAS_CACHE_DURATION = 300 # 5 minutes


# Moved to module level for stability with asyncio.to_thread
def get_ticker_score(ticker, global_df=None):
    """Calculates a directional score for a stock using the rule engine.
    Engine fetch its own 1y history (30 days would leave SMA50 NaN and force
    every stock to BEARISH). Score = +confidence, -confidence, or 0."""
    try:
        thesis = {'prediction': BULLISH, 'reason': '', 'support': 0.0,
                  'resistance': 0.0, 'start_price': 0.0}
        engine = SignalEngine(ticker, thesis)
        direction, confidence = engine.get_consensus_confidence()
        score = confidence if direction == BULLISH else (-confidence if direction == BEARISH else 0)
        return ticker, score
    except Exception as e:
        return ticker, 0

async def refresh_global_rankings():
    global GLOBAL_RANKINGS, GLOBAL_SCORES, RANKINGS_CACHE_TIME, GLOBAL_MACRO_DF, MACRO_CACHE_TIME
    if time.time() - RANKINGS_CACHE_TIME < RANKINGS_DURATION:
        return

    print("[System] Refreshing global market rankings (Ultra-Fast Mode)...")

    # 1. Fetch Global Macro Data ONCE for all stocks
    global_tickers = ["^VIX", "CL=F", "INR=X"]
    try:
        g_data = await asyncio.to_thread(yf.download, global_tickers, period="1y", progress=False)
        if isinstance(g_data['Close'], pd.DataFrame):
            global_close = g_data['Close']
        else:
            global_close = g_data['Close'].to_frame()
        GLOBAL_MACRO_DF = pd.DataFrame({
            'VIX': global_close['^VIX'],
            'OIL': global_close['CL=F'],
            'USDINR': global_close['INR=X']
        })
        MACRO_CACHE_TIME = time.time()
    except Exception as e:
        print(f"[System] Global macro fetch failed: {e}")

    all_scores = {}
    chunk_size = 15
    for i in range(0, len(STOCK_LIST), chunk_size):
        chunk = STOCK_LIST[i:i + chunk_size]
        tasks = [asyncio.to_thread(get_ticker_score, ticker, GLOBAL_MACRO_DF) for ticker in chunk]
        results = await asyncio.gather(*tasks)
        for ticker, score in results:
            all_scores[ticker] = score
        print(f"  Processed {min(i + chunk_size, len(STOCK_LIST))}/{len(STOCK_LIST)} stocks...")
        await asyncio.sleep(0.5) # Reduced sleep for speed

    sorted_tickers = sorted(all_scores.keys(), key=lambda x: all_scores[x], reverse=True)
    GLOBAL_SCORES = all_scores

    # Honest classification: the engine's own verdict, with the same confidence
    # threshold the live engine uses (55). No market-balancing median split —
    # in a bear regime most stocks come back NEUTRAL, and that is correct.
    GLOBAL_RANKINGS = {}
    for ticker, score in all_scores.items():
        if score >= 55:
            GLOBAL_RANKINGS[ticker] = "BULLISH"
        elif score <= -55:
            GLOBAL_RANKINGS[ticker] = "BEARISH"
        else:
            GLOBAL_RANKINGS[ticker] = "NEUTRAL"

    RANKINGS_CACHE_TIME = time.time()
    db.save_rankings(GLOBAL_RANKINGS)
    print(f"[System] Global rankings updated for {len(STOCK_LIST)} stocks.")
    # keep sorted copy for the frontend's "top picks" ordering
    GLOBAL_SCORES = all_scores

# CLEANED Stock List (140+ Valid Unique NSE Stocks)
# Removed: SUREX.NS (Invalid), Fixed: ZYDUSLIFE.NS, TATACONSUM.NS
STOCK_LIST = list(set([
    "SBIN.NS", "PNB.NS", "CANBK.NS", "UNIONBANK.NS", "BANKBARODA.NS", "UCOBANK.NS", "CENTRALBK.NS", "INDIANB.NS", "YESBANK.NS", "IDFCFIRSTB.NS",
    "FEDERALBNK.NS", "BANDHANBNK.NS", "IDBI.NS", "MUTHOOTFIN.NS", "MANAPPURAM.NS", "PFC.NS", "RECLTD.NS", "HUDCO.NS",
    "IRFC.NS", "LICI.NS", "CDSL.NS", "CAMS.NS", "JIOFIN.NS", "NTPC.NS", "POWERGRID.NS", "ONGC.NS", "OIL.NS", "IOC.NS",
    "BPCL.NS", "GAIL.NS", "TATAPOWER.NS", "ADANIGREEN.NS", "SJVN.NS", "NHPC.NS", "JSWENERGY.NS", "TATASTEEL.NS", "HINDALCO.NS", "VEDL.NS",
    "NMDC.NS", "SAIL.NS", "COALINDIA.NS", "NATIONALUM.NS", "HINDZINC.NS", "AUROPHARMA.NS", "GLENMARK.NS", "ZYDUSLIFE.NS", "LUPIN.NS", "SANOFI.NS",
    "BIOCON.NS", "IPCALAB.NS", "GRANULES.NS", "ITC.NS", "VBL.NS", "GODREJCP.NS", "COLPAL.NS", "DABUR.NS", "MARICO.NS", "BATAINDIA.NS",
    "VGUARD.NS", "HAVELLS.NS", "CROMPTON.NS", "DIXON.NS", "KEI.NS", "WIPRO.NS", "ZENSARTECH.NS", "HFCL.NS", "BSOFT.NS", "TATACOMM.NS",
    "ASHOKLEY.NS", "MOTHERSON.NS", "EXIDEIND.NS", "UNOMINDA.NS", "Swaraj.NS", "JKTYRE.NS", "TVSMOTOR.NS",
    "RVNL.NS", "MAZDOCK.NS", "COCHINSHIP.NS", "BSE.NS", "MCX.NS", "SUNTV.NS", "ZEEL.NS", "PVRINOX.NS", "UBL.NS", "IDEA.NS",
    "SREEL.NS", "SANOFI.NS", "BEL.NS", "BHEL.NS", "JSWENERGY.NS", "CDSL.NS", "RELAXO.NS", "TATASTEEL.NS"
]))

DATA_CACHE = {}
CACHE_DURATION = 300

def get_cached_data(ticker):
    if ticker in DATA_CACHE:
        timestamp, data = DATA_CACHE[ticker]
        if time.time() - timestamp < CACHE_DURATION:
            return data
    return None

def set_cached_data(ticker, data):
    DATA_CACHE[ticker] = (time.time(), data)

def clean_ticker(ticker):
    """Removes .NS from ticker for display purposes."""
    return ticker.replace(".NS", "") if ticker else ticker

def get_company_name(ticker):
    """Retrieves the company name for a ticker, returning the ticker if not found."""
    name = db.get_stock_name(ticker)
    if name == ticker:
        try:
            info = yf.Ticker(ticker).info
            name = info.get('longName', ticker)
            db.save_stock_name(ticker, name)
        except:
            pass
    return name

@app.get("/watchlist")
async def get_watchlist():
    try:
        tickers = db.get_watchlist()
        stock_data = []
        if tickers:
            data = yf.download(tickers, period="2d", progress=False)
            close_prices = data['Close'] if not data.empty else pd.DataFrame()
            if isinstance(close_prices, pd.Series):
                close_prices = close_prices.to_frame()

            for ticker in tickers:
                delta = 0
                if not close_prices.empty and ticker in close_prices.columns:
                    prices = close_prices[ticker].dropna()
                    if len(prices) >= 2:
                        delta = ((prices.iloc[-1] - prices.iloc[-2]) / prices.iloc[-2]) * 100

                stock_data.append({
                    "ticker": clean_ticker(ticker),
                    "name": db.get_stock_name(ticker),
                    "delta": round(delta, 2),
                    "signal": GLOBAL_RANKINGS.get(ticker, "NEUTRAL")
                })
        return {"stocks": stock_data}
    except Exception as e:
        print(f"Error fetching watchlist: {e}")
        return {"stocks": []}

@app.post("/watchlist/{ticker}")
async def add_to_watchlist(ticker: str):
    try:
        db.add_to_watchlist(ticker)
        return {"status": "added"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/watchlist/{ticker}")
async def remove_from_watchlist(ticker: str):
    try:
        db.remove_from_watchlist(ticker)
        return {"status": "removed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/top-picks")
async def get_top_picks():
    try:
        await refresh_global_rankings()
        top_tickers = [t for t, s in GLOBAL_SCORES.items() if GLOBAL_RANKINGS.get(t) == "BULLISH"]
        top_tickers.sort(key=lambda t: GLOBAL_SCORES[t], reverse=True)
        top_10 = top_tickers[:10]

        if not top_10:
            return {"stocks": []}

        data = yf.download(top_10, period="2d", progress=False)
        close_prices = data['Close'] if not data.empty else pd.DataFrame()
        if isinstance(close_prices, pd.Series):
            close_prices = close_prices.to_frame()

        stock_data = []
        for ticker in top_10:
            delta = 0
            if not close_prices.empty and ticker in close_prices.columns:
                prices = close_prices[ticker].dropna()
                if len(prices) >= 2:
                    delta = ((prices.iloc[-1] - prices.iloc[-2]) / prices.iloc[-2]) * 100

            stock_data.append({
                "ticker": clean_ticker(ticker),
                "name": db.get_stock_name(ticker),
                "delta": round(delta, 2),
                "signal": "BULLISH",
                "score": round(GLOBAL_SCORES.get(ticker, 0), 2)
            })
        return {"stocks": stock_data}
    except Exception as e:
        print(f"Error fetching top picks: {e}")
        return {"stocks": []}

@app.get("/stocks")
async def get_stocks(background_tasks: BackgroundTasks):
    try:
        # 1. Trigger rankings update in background
        background_tasks.add_task(refresh_global_rankings)

        # 2. Fetch rankings from DB immediately to ensure instant load
        rankings_from_db = db.get_all_rankings()

        # 3. Fetch real-time deltas for all stocks in batch
        stock_data = []
        try:
            data = yf.download(STOCK_LIST, period="2d", progress=False)
            close_prices = data['Close'] if not data.empty else pd.DataFrame()
            if isinstance(close_prices, pd.Series):
                close_prices = close_prices.to_frame()
        except Exception as e:
            print(f"[Server] Error fetching batch deltas: {e}")
            close_prices = pd.DataFrame()

        for ticker in STOCK_LIST:
            delta = 0.0
            if not close_prices.empty and ticker in close_prices.columns:
                prices = close_prices[ticker].dropna()
                if len(prices) >= 2:
                    delta = ((prices.iloc[-1] - prices.iloc[-2]) / prices.iloc[-2]) * 100

            stock_data.append({
                "ticker": clean_ticker(ticker),
                "name": db.get_stock_name(ticker),
                "delta": round(delta, 2),
                "signal": rankings_from_db.get(ticker, GLOBAL_RANKINGS.get(ticker, "NEUTRAL"))
            })

        return {"stocks": stock_data}
    except Exception as e:
        print(f"[Server ERROR] /stocks failed: {e}")
        return {"stocks": []}

@app.get("/health")
async def health_check():
    return {"status": "online", "timestamp": time.time()}

@app.get("/")
async def root():
    return FileResponse("index.html")

def fetch_info(ticker):
    try:
        return yf.Ticker(ticker).info
    except:
        return {}

def fetch_history_1y(ticker):
    try:
        df = yf.download(ticker, period="1y", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except:
        return pd.DataFrame()

def fetch_history_2d(ticker):
    try:
        df = yf.download(ticker, period="2d", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except:
        return pd.DataFrame()

@app.get("/full_analysis/{ticker}")
async def get_full_analysis(ticker: str):
    # Normalize ticker: ensure it ends with .NS for NSE stocks
    if not ticker.endswith(".NS"):
        ticker = f"{ticker}.NS"

    cached = get_cached_data(ticker)
    if cached:
        return cached


    try:
        print(f"[Server] Analyzing {ticker}...")

        # 1. Optimized Data Fetching
        # Instead of 3 requests, we do 2. We fetch 1y history and derive 2d from it.
        hist_1y_task = asyncio.to_thread(fetch_history_1y, ticker)

        # Use cached info if available, otherwise fetch it
        cached_info = db.get_stock_info(ticker)
        if cached_info:
            info = cached_info
            info_task = asyncio.sleep(0) # No-op to keep gather structure
        else:
            info_task = asyncio.to_thread(fetch_info, ticker)

        info, df = await asyncio.gather(info_task, hist_1y_task)

        # If we just fetched info, save it for next time
        if not cached_info and info:
            db.save_stock_info(ticker, info)

        if df is None or df.empty:
            raise HTTPException(status_code=404, detail="Ticker not found")

        info_data = {
            "market_cap": info.get("marketCap", "N/A") if info else "N/A",
            "pe_ratio": info.get("trailingPE", "N/A") if info else "N/A",
            "div_yield": info.get("dividendYield", "N/A") if info else "N/A",
            "high_52w": info.get("fiftyTwoWeekHigh", "N/A") if info else "N/A",
            "low_52w": info.get("fiftyTwoWeekLow", "N/A") if info else "N/A",
            "avg_volume": info.get("averageVolume", "N/A") if info else "N/A",
            "sector": info.get("sector", "N/A") if info else "N/A",
            "industry": info.get("industry", "N/A") if info else "N/A",
        }

        regime = GLOBAL_RANKINGS.get(ticker, NEUTRAL)

        analyzer = MorningAnalyzer(ticker)
        thesis = analyzer.get_thesis()
        engine = SignalEngine(ticker, thesis)
        _, confidence = engine.get_consensus_confidence(df=df, global_df=GLOBAL_MACRO_DF)



        chart_df = df.tail(30)
        dates = chart_df.index.strftime('%Y-%m-%d').tolist()
        prices = chart_df['Close'].tolist()

        # Calculate delta from the already fetched 1y dataframe
        delta = 0
        if len(df) >= 2:
            close_prices = df['Close']
            if isinstance(close_prices, pd.DataFrame):
                close_prices = close_prices.iloc[:, 0]
            delta = ((close_prices.iloc[-1] - close_prices.iloc[-2]) / close_prices.iloc[-2]) * 100

        prediction_data = {
            "prediction": regime,
            "macro_regime": regime,
            "confidence": f"{confidence:.1f}%",
            "confidence_raw": confidence,
            "delta": round(delta, 2),
            "support": round(thesis['support'], 2),
            "resistance": round(thesis['resistance'], 2),
            "reason": thesis['reason'],
            "current_price": round(df['Close'].iloc[-1], 2),
            "hold_time": thesis['hold_time'],
            "exit_signal": thesis['exit_signal']
        }

        final_response = {
            "info": info_data,
            "name": get_company_name(ticker),
            "chart": {"dates": dates, "prices": prices},
            "prediction": prediction_data
        }

        set_cached_data(ticker, final_response)
        print(f"[Server] Analysis complete for {ticker}")
        return final_response

    except Exception as e:
        print(f"[Server ERROR] Analysis failed for {ticker}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.get("/backtest/{ticker}")
async def get_backtest(ticker: str, days: int = 30):
    try:
        def run_bt():
            bt = Backtester(ticker)
            return bt.run_simulation(days=days)

        result = await asyncio.to_thread(run_bt)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backtest failed: {str(e)}")

@app.get("/info/{ticker}")
async def get_info(ticker: str):
    # Normalize ticker: ensure it ends with .NS for NSE stocks
    if not ticker.endswith(".NS"):
        ticker = f"{ticker}.NS"

    cached = get_cached_data(ticker)
    if cached: return cached["info"]
    stock = yf.Ticker(ticker)
    info = stock.info
    return {"market_cap": info.get("marketCap", "N/A"), "pe_ratio": info.get("trailingPE", "N/A"), "div_yield": info.get("dividendYield", "N/A"), "high_52w": info.get("fiftyTwoWeekHigh", "N/A"), "low_52w": info.get("fiftyTwoWeekLow", "N/A"), "avg_volume": info.get("averageVolume", "N/A"), "sector": info.get("sector", "N/A"), "industry": info.get("industry", "N/A")}

@app.get("/predict/{ticker}")
async def get_prediction(ticker: str):
    # Normalize ticker: ensure it ends with .NS for NSE stocks
    if not ticker.endswith(".NS"):
        ticker = f"{ticker}.NS"

    cached = get_cached_data(ticker)
    if cached: return cached["prediction"]


    try:
        await refresh_global_rankings()
        prediction = GLOBAL_RANKINGS.get(ticker, "NEUTRAL")
        return {"prediction": prediction, "reason": "Relative Market Strength Analysis."}
    except:
        pass

    return {"prediction": "NEUTRAL", "reason": "Insufficient data or conflicting signals."}

@app.get("/history/{ticker}")
async def get_history(ticker: str, period: str = "1mo"):
    # Normalize ticker: ensure it ends with .NS for NSE stocks
    if not ticker.endswith(".NS"):
        ticker = f"{ticker}.NS"

    period_map = {
        "1D": "1d",
        "1W": "5d",
        "1M": "1mo",
        "6M": "6mo",
        "1Y": "1y",
        "ALL": "max"
    }
    yf_period = period_map.get(period, "1mo")
    try:
        df = yf.download(ticker, period=yf_period, progress=False)
        if df.empty: raise HTTPException(status_code=404, detail="No data found")
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        return {
            "dates": df.index.strftime('%Y-%m-%d').tolist(),
            "prices": df['Close'].tolist()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8080)
