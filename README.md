# Rule-Based Stock Screening & Signal Engine

A Python-based stock screening and signal engine designed to evaluate stocks using transparent technical-analysis rules, market-regime filters, risk controls, and backtesting.

> **Note:** This project is for educational and research purposes only. It is not financial advice or a recommendation to buy or sell securities.

---

## Overview

This project explores systematic stock screening without relying entirely on black-box machine learning.

The system combines:

- Technical trend indicators
- Momentum analysis
- Market-regime filtering
- USD/INR conditions
- Realized-volatility controls
- Rule-based entry and exit signals
- Stock ranking
- Backtesting with transaction costs
- Prediction verification and analysis
- Data storage and streaming components

The goal is to create a transparent decision system where each signal can be traced back to explicit rules.

---

## Core Strategy

### Trend Analysis

The engine evaluates the relationship between:

- SMA20 — 20-day simple moving average
- SMA50 — 50-day simple moving average

The relative position and crossover structure are used as part of the trend signal.

An oversold condition can also influence the trend component when price falls sufficiently below the SMA50.

### Momentum

MACD is used to evaluate momentum:

- EMA12
- EMA26
- EMA9 signal line

The MACD relationship contributes to the overall signal confidence.

### Market Regime

The system uses the NSE index (`^NSEI`) to classify the broader market environment as:

- BULLISH
- BEARISH
- NEUTRAL

The market-regime filter helps prevent signals that conflict with the broader market trend.

### Currency Filter

USD/INR conditions are incorporated as an additional macro filter.

The system can restrict long signals when INR weakness exceeds the configured trend threshold.

### Volatility Control

20-day realized volatility is monitored.

When recent volatility becomes significantly elevated relative to its normal level, signal confidence is reduced.

---

## Signal & Risk Controls

The strategy includes explicit risk-management rules.

### Entry

Signals require a minimum confidence threshold of:

```text
55%
Exits

Positions can exit based on:

SMA20 trend deterioration
SMA50 conditions during bullish regimes
Peak-price drawdown

The project uses an:

8% peak drawdown exit
Transaction Costs

Backtesting accounts for:

0.1% per side

in transaction costs.

Stock Ranking

The screening system also ranks stocks using multiple factors, including:

Price position relative to SMA20
2-week momentum
1-month momentum
3-month momentum
SMA20/SMA50 trend structure
Recent SMA20/SMA50 breakouts

A composite ranking score combines these signals to prioritize stocks for further analysis.

Machine Learning Exploration

An ML-based approach was explored during development.

During testing, the model/preprocessing behavior did not align with the project's objective of preserving meaningful price movement.

The approach was therefore shifted toward a more interpretable rule-based system using explicit technical indicators, regime filters, and risk controls.

This made it easier to understand why a particular stock received a signal.

Backtesting

The project includes a dedicated backtesting component for evaluating the strategy historically.

Backtesting incorporates transaction costs so that results are not evaluated purely on theoretical price movements.

The project structure separates strategy logic, analysis, data handling, and verification components to make experimentation easier.
Technologies
Python
Pandas
NumPy
Technical Analysis
Backtesting
HTML
JavaScript
SQLite / database storage
Financial market data
Key Design Principles
Interpretability

Signals are generated using explicit rules rather than an opaque prediction model.

Risk Awareness

The system incorporates:

Market regime
Volatility
Currency conditions
Trend-based exits
Drawdown controls
Transaction costs
Modular Architecture

Different responsibilities are separated into individual Python modules for easier testing and development.

Disclaimer

This project is an educational software project for exploring quantitative analysis, technical indicators, systematic screening, and backtesting.

It does not constitute financial, investment, or trading advice.

Past backtest results do not guarantee future performance.

License

This project is licensed under the MIT License.
