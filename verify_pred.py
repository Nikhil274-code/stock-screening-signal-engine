#!/usr/bin/env python3
"""Grade the SENSEI prediction snapshot against reality. Run AFTER market close:
    python verify_pred.py
Compares each predicted stock's close now vs its close at prediction time,
then reports hit-rate and equal-weight return vs the NSEI benchmark.
"""
import glob, os, csv
import yfinance as yf
import pandas as pd

d = os.path.dirname(os.path.abspath(__file__))
snaps = sorted(glob.glob(os.path.join(d, "prediction_*.csv")))
if not snaps:
    print("No prediction_*.csv snapshot found.")
    raise SystemExit(1)
snap = snaps[-1]

rows = []
with open(snap, encoding="utf-8") as f:
    for r in csv.DictReader(f):
        rows.append({"ticker": r["ticker"], "close": float(r["close"]), "score": float(r["score"])})

tickers = [r["ticker"] for r in rows]
print(f"Snapshot: {os.path.basename(snap)}  ({len(rows)} stocks)")
print("Fetching current closes...")
data = yf.download(tickers, period="2d", progress=False, group_by="ticker")

results = []
for r in rows:
    tk = r["ticker"]
    last = None
    try:
        c = data[tk]["Close"].dropna()
        if len(c):
            last = float(c.iloc[-1])
    except Exception:
        pass
    if last is None:
        continue
    delta = (last / r["close"] - 1) * 100
    results.append((tk, r["close"], last, delta, r["score"]))

try:
    m = {}
    with open(os.path.join(d, "prediction_meta.txt")) as f:
        for line in f:
            k, v = line.strip().split(": ", 1)
            m[k] = float(v)
except Exception:
    m = {}

nsei = None
try:
    idx = yf.download("^NSEI", period="2d", progress=False, auto_adjust=True)
    ic = idx["Close"].squeeze().dropna()
    if len(ic) and m.get("nsei_close"):
        nsei = (float(ic.iloc[-1]) / m["nsei_close"] - 1) * 100
except Exception:
    pass

if not results:
    print("No data returned.")
    raise SystemExit(1)

up = sum(1 for _, _, _, d, _ in results if d > 0)
avg = sum(r[3] for r in results) / len(results)
print("=" * 60)
print(f"{'Ticker':<16}{'Pred':>9}{'Now':>9}{'Chg%':>8}{'Score':>7}")
for tk, pred, now, d, sc in sorted(results, key=lambda x: x[3], reverse=True):
    print(f"{tk:<16}{pred:>9.2f}{now:>9.2f}{d:>+7.2f}%{sc:>7.2f}")
print("=" * 60)
print(f"Stocks up: {up}/{len(results)} ({up/len(results)*100:.0f}%)")
print(f"Equal-weight return: {avg:+.2f}%")
if nsei is not None:
    print(f"NSEI benchmark:      {nsei:+.2f}%   -> pick list beat NSEI by {avg - nsei:+.2f}%")