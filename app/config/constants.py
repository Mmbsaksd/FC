"""
Application Constants and Defaults
"""

# Tracked High-Liquidity Core Universe (Six Core Markets Only)
TRACKED_INSTRUMENTS = [
    {"symbol": "EURUSD=X", "name": "EUR/USD", "type": "FOREX", "base": "EUR", "quote": "USD", "pip_size": 0.0001, "oanda_symbol": "EUR_USD"},
    {"symbol": "GBPUSD=X", "name": "GBP/USD", "type": "FOREX", "base": "GBP", "quote": "USD", "pip_size": 0.0001, "oanda_symbol": "GBP_USD"},
    {"symbol": "USDJPY=X", "name": "USD/JPY", "type": "FOREX", "base": "USD", "quote": "JPY", "pip_size": 0.01, "oanda_symbol": "USD_JPY"},
    {"symbol": "GC=F",     "name": "Gold",    "type": "COMMODITY", "base": "XAU", "quote": "USD", "pip_size": 0.10, "oanda_symbol": "XAU_USD"},
    {"symbol": "BTC-USD",  "name": "Bitcoin (BTC)",  "type": "CRYPTO", "base": "BTC", "quote": "USD", "pip_size": 1.00, "oanda_symbol": "BTC_USD"},
    {"symbol": "ETH-USD",  "name": "Ethereum (ETH)", "type": "CRYPTO", "base": "ETH", "quote": "USD", "pip_size": 0.10, "oanda_symbol": "ETH_USD"}
]

# Universe Classifications (Core Only)
CORE_INSTRUMENT_SYMBOLS = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "GC=F", "BTC-USD", "ETH-USD"]
SECONDARY_INSTRUMENT_SYMBOLS = []

# Major Currencies for Strength Matrix (Core FX Pairs)
MAJOR_CURRENCIES = ["USD", "EUR", "GBP", "JPY"]

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
