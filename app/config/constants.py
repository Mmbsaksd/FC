"""
Application Constants and Defaults
"""

# Tracked FX Majors and Key Commodities for Initial Scope
TRACKED_INSTRUMENTS = [
    {"symbol": "EURUSD=X", "name": "EUR/USD", "type": "FOREX", "base": "EUR", "quote": "USD", "pip_size": 0.0001, "oanda_symbol": "EUR_USD"},
    {"symbol": "GBPUSD=X", "name": "GBP/USD", "type": "FOREX", "base": "GBP", "quote": "USD", "pip_size": 0.0001, "oanda_symbol": "GBP_USD"},
    {"symbol": "USDJPY=X", "name": "USD/JPY", "type": "FOREX", "base": "USD", "quote": "JPY", "pip_size": 0.01, "oanda_symbol": "USD_JPY"},
    {"symbol": "AUDUSD=X", "name": "AUD/USD", "type": "FOREX", "base": "AUD", "quote": "USD", "pip_size": 0.0001, "oanda_symbol": "AUD_USD"},
    {"symbol": "USDCAD=X", "name": "USD/CAD", "type": "FOREX", "base": "USD", "quote": "CAD", "pip_size": 0.0001, "oanda_symbol": "USD_CAD"},
    {"symbol": "USDCHF=X", "name": "USD/CHF", "type": "FOREX", "base": "USD", "quote": "CHF", "pip_size": 0.0001, "oanda_symbol": "USD_CHF"},
    {"symbol": "NZDUSD=X", "name": "NZD/USD", "type": "FOREX", "base": "NZD", "quote": "USD", "pip_size": 0.0001, "oanda_symbol": "NZD_USD"},
    {"symbol": "EURGBP=X", "name": "EUR/GBP", "type": "FOREX", "base": "EUR", "quote": "GBP", "pip_size": 0.0001, "oanda_symbol": "EUR_GBP"},
    {"symbol": "GC=F",     "name": "Gold",    "type": "COMMODITY", "base": "XAU", "quote": "USD", "pip_size": 0.10, "oanda_symbol": "XAU_USD"},
    {"symbol": "CL=F",     "name": "Crude Oil", "type": "COMMODITY", "base": "WTI", "quote": "USD", "pip_size": 0.01, "oanda_symbol": "WTICO_USD"}
]

# Major Currencies for Strength Matrix
MAJOR_CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"]

# Timeframes Supported
TIMEFRAMES = {
    "15M": "15m",
    "1H": "60m",
    "4H": "1h", # Aggregated from 1h or fetch daily
    "1D": "1d"
}

# Signal Score Thresholds
SCORE_LOG_ONLY = 60.0
SCORE_TELEGRAM_ALERT = 70.0
SCORE_HIGH_VALUE_ALERT = 85.0

# Minimum Acceptable Risk / Reward Ratio
MIN_RISK_REWARD = 2.0
