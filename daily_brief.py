#!/usr/bin/env python3
"""SENSEI daily brief: pre-close actions + post-close P/L verification.

Usage:
    python daily_brief.py          # before close: print regime + per-stock action
    python daily_brief.py verify   # after close:  grade the brief against reality
"""
import sys
import yfinance as yf
import pandas as pd
from config import BULLISH, BEARISH, NEUTRAL
from app import STOCK_LIST

HOLD_DAYS = None  # reserved; the engine trades on trend-break, not time

def regime():
    idx = yf.download("^NSEI", period="1y", progress=False)
    if idx.empty or len(idx) < 60:
        return NEUTRAL
    close = idx['Close'].squeeze()
    last = close.iloc[-1]
    sma50 = close.rolling(50).mean().iloc[-1]
    if last > sma50 * 1.01:
        return BULLISH
    if last < sma50 * 0.99:
        return BEARISH
    return NEUTRAL

def rupee_guard():
    fx = yf.download("INR=X", period="1y", progress=False)
    if fx.empty or len(fx) < 50:
        return None
    if isinstance(fx.columns, pd.MultiIndex):
        fx.columns = fx.columns.get_level_values(0)
    close = fx['Close'].squeeze().dropna()
    last = close.iloc[-1]
    sma50 = close.rolling(50).mean().iloc[-1]
    return "BEARISH" if last > sma50 * 1.005 else "OK"

def stock_verdict(ticker):
    from engine import SignalEngine
    thesis = {'prediction': BULLISH, 'reason': '', 'support': 0.0,
              'resistance': 0.0, 'start_price': 0.0}
    return SignalEngine(ticker, thesis).get_consensus_confidence()

def action_for(direction, confidence):
    if direction == BULLISH and confidence >= 55:
        return "BUY/HOLD"
    if direction == BEARISH and confidence <= 55:
        return "SELL/AVOID"
    return "WAIT"

def brief():
    r = regime()
    guard = rupee_guard()
    print("=" * 64)
    print(f"NSEI regime: {r}   |   USDINR guard: {guard}")
    if r == NEUTRAL:
        print("Regime is NEUTRAL (index near its 50-day trend); per-stock votes decide.")
    elif r == BEARISH:
        print("BEARISH regime -> the engine blocks ALL trades today.")
        print("Projected plan: hold nothing, buy nothing, P/L today = Rs 0 (no trades).")
    else:
        print("BULLISH regime -> per-stock votes below.")
    print("=" * 64)

    counts = {"BUY/HOLD": 0, "SELL/AVOID": 0, "WAIT": 0}
    rows = []
    for i, tk in enumerate(sorted(STOCK_LIST), 1):
        if r == BEARISH:
            direction, confidence = NEUTRAL, 0.0
        else:
            direction, confidence = stock_verdict(tk)
        action = action_for(direction, confidence)
        counts[action] += 1
        rows.append((tk, action, confidence))
        print(f"[{i:>3}/{len(STOCK_LIST)}] {tk:<14} {action:<10} conf={confidence:5.1f}")

    print("=" * 64)
    print(f"Totals: {counts['BUY/HOLD']} buy/hold | {counts['SELL/AVOID']} sell/avoid | {counts['WAIT']} wait")
    print("Sizing: equal weight (no positional sizing in the engine).")
    print("Run 'python daily_brief.py verify' AFTER market close to grade this brief.")

def verify():
    print("[Verify] Fetching today's close vs prior close for", len(STOCK_LIST), "stocks...")
    tickers = sorted(STOCK_LIST) + ["^NSEI"]
    data = yf.download(tickers, period="2d", progress=False, group_by="ticker")
    print("=" * 64)
    rows = []
    for tk in sorted(STOCK_LIST):
        try:
            if isinstance(data.columns, pd.MultiIndex):
                close = data[tk]['Close'].dropna()
            else:
                close = data['Close'][tk].dropna()
            if len(close) < 2:
                print(f"[{tk}] <not enough data>")
                continue
            prev, today = close.iloc[-2], close.iloc[-1]
            delta = (today / prev - 1) * 100
            rows.append((tk, prev, today, delta))
        except Exception as e:
            print(f"[{tk}] <error: {e}>")
    if not rows:
        return

    nsei_prev = nsei_today = None
    try:
        if isinstance(data.columns, pd.MultiIndex):
            nclose = data['^NSEI']['Close'].dropna()
        else:
            nclose = data['Close']['^NSEI'].dropna()
        if len(nclose) >= 2:
            nsei_prev, nsei_today = nclose.iloc[-2], nclose.iloc[-1]
    except Exception:
        pass

    while True:
        action = input("What action did the brief give you today (BUY/HOLD, SELL/AVOID, WAIT)? ").strip().upper()
        if action in ("BUY/HOLD", "SELL/AVOID", "WAIT"):
            break
    nbuy = nhold = nsell = nwait = 0
    pnl = 0.0
    for tk, prev, today, delta in rows:
        if action == "BUY/HOLD":
            pnl += delta
            nbuy += 1
        elif action == "SELL/AVOID":
            pnl += -delta
            nsell += 1
        else:
            nwait += 1
    per_stock = pnl / len(rows) if rows else 0.0

    print("=" * 64)
    print(f"{'Ticker':<14}{'Prior':>10}{'Today':>10}{'Delta%':>9}")
    for tk, prev, today, delta in sorted(rows, key=lambda x: x[3]):
        print(f"{tk:<14}{prev:>10.2f}{today:>10.2f}{delta:>+8.2f}%")
    print("=" * 64)
    print(f"Plan: {action} on {len(rows)} stocks (equal weight Rs 1 each)")
    if nsei_prev:
        nsei_delta = (nsei_today / nsei_prev - 1) * 100
        print(f"Hypothetical day P/L from the brief's plan: {per_stock:+.2f}%  (vs NSEI {nsei_delta:+.2f}%)")
    else:
        print(f"Hypothetical day P/L from the brief's plan: {per_stock:+.2f}%")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "verify":
        verify()
    else:
        brief()