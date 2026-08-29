import sys
import os

# Add project root directory to sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import streamlit as st
import pandas as pd

from app.config.constants import TRACKED_INSTRUMENTS
from app.providers.yahoo_provider import YahooMarketDataProvider
from app.engines.currency_strength import CurrencyStrengthEngine
from app.engines.technical_engine import TechnicalAnalysisEngine

st.set_page_config(page_title="AI Market Intelligence Scanner", layout="wide")

st.title("📊 AI Market Intelligence & Trading Scanner")
st.caption("Forex, Commodities & Currency Strength Monitor — 8 GB RAM Optimized")

# Sidebar - Controls
st.sidebar.header("Scanner Controls")
if st.sidebar.button("🚀 Run Live Market Scan"):
    with st.spinner("Fetching market data and evaluating setups..."):
        from scripts.run_scanner import run_market_scan
        run_market_scan()
        st.success("Scan Complete!")

# Section 1: Currency Strength Matrix
st.subheader("💪 Currency Strength Matrix (8 Majors)")
provider = YahooMarketDataProvider()
cs_engine = CurrencyStrengthEngine(provider=provider)

with st.spinner("Calculating currency strength..."):
    scores = cs_engine.calculate_currency_strength(timeframe="1H")
    
cols = st.columns(8)
for i, (curr, score) in enumerate(scores.items()):
    cols[i].metric(label=curr, value=f"{score:+.2f}")

# Section 2: Market Monitor Table
st.subheader("📈 Tracked Instruments Monitor")
monitor_data = []
for inst in TRACKED_INSTRUMENTS:
    sym = inst["symbol"]
    df = provider.fetch_ohlcv(sym, timeframe="15M", limit=30)
    if not df.empty:
        tech = TechnicalAnalysisEngine.evaluate_technical_score(df)
        monitor_data.append({
            "Symbol": inst["name"],
            "Price": tech.get("close", 0.0),
            "Direction": tech.get("direction", "NEUTRAL"),
            "Tech Score": tech.get("score", 50.0),
            "RSI (14)": round(tech.get("rsi", 50.0), 1),
            "ADX (14)": round(tech.get("adx", 20.0), 1),
            "Setup": tech.get("setup_type", "NONE")
        })

if monitor_data:
    st.dataframe(pd.DataFrame(monitor_data), use_container_width=True)

st.info("System is configured in Alert-Only Mode. No automated trades will be executed.")
