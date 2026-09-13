import pytest
import sqlite3
import json
import os
from typing import Dict, Any

from app.config.constants import (
    TRACKED_INSTRUMENTS,
    CORE_INSTRUMENT_SYMBOLS,
    SECONDARY_INSTRUMENT_SYMBOLS,
    MAJOR_CURRENCIES
)
from app.config.asset_config import asset_config_manager
from app.parallel.aggregator import EvidenceAggregator
from app.risk.risk_engine import RiskEngine
from app.memory.knowledge_retriever import HybridKnowledgeRetriever
from app.storage.sqlite_manager import SQLiteManager
from app.engines.macro_engine import CENTRAL_BANK_RATES
from app.engines.fundamental_engine import FundamentalAnalysisEngine

CORE_SYMBOLS = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "GC=F", "BTC-USD", "ETH-USD"]
DELETED_SYMBOLS = [
    "AUDUSD=X", "USDCAD=X", "USDCHF=X", "NZDUSD=X", "EURGBP=X",
    "CL=F", "WTICO_USD", "SOL-USD", "XRP-USD",
    "AUD/USD", "USD/CAD", "USD/CHF", "NZD/USD", "EUR/GBP", "Crude Oil", "SOL", "XRP"
]

def test_01_active_universe_contains_strictly_six_core_assets():
    """Verify that TRACKED_INSTRUMENTS and CORE_INSTRUMENT_SYMBOLS contain only the 6 core markets."""
    assert len(TRACKED_INSTRUMENTS) == 6
    assert set(CORE_INSTRUMENT_SYMBOLS) == set(CORE_SYMBOLS)
    assert SECONDARY_INSTRUMENT_SYMBOLS == []
    
    tracked_symbols = [inst["symbol"] for inst in TRACKED_INSTRUMENTS]
    assert set(tracked_symbols) == set(CORE_SYMBOLS)


def test_02_asset_config_manager_enforces_core_only():
    """Verify that AssetConfigManager defaults and outputs strictly the 6 core instruments."""
    asset_config_manager.save_config(
        forex_enabled=True,
        commodities_enabled=True,
        crypto_enabled=True,
        universe_mode="CORE",
        core_only=True
    )
    active_insts = asset_config_manager.get_active_instruments()
    active_symbols = [inst["symbol"] for inst in active_insts]
    
    assert len(active_symbols) == 6
    assert set(active_symbols) == set(CORE_SYMBOLS)
    
    sec_insts = asset_config_manager.get_secondary_instruments()
    assert len(sec_insts) == 0


def test_03_major_currencies_and_macro_rates_restricted_to_core():
    """Verify that currency strength and macro rates track only core FX currencies (USD, EUR, GBP, JPY)."""
    expected_currencies = {"USD", "EUR", "GBP", "JPY"}
    assert set(MAJOR_CURRENCIES) == expected_currencies
    assert set(CENTRAL_BANK_RATES.keys()) == expected_currencies


def test_04_negative_tests_deleted_assets_rejected_from_core_universe():
    """Verify that deleted non-core instruments are strictly rejected and not recognized as active."""
    active_symbols = set(CORE_INSTRUMENT_SYMBOLS)
    for deleted in DELETED_SYMBOLS:
        assert deleted not in active_symbols, f"Deleted symbol {deleted} must not be in active core universe"
        
        # Verify provider router / clean sym doesn't recognize as tracked
        found_in_tracked = any(inst["symbol"] == deleted or inst["name"] == deleted for inst in TRACKED_INSTRUMENTS)
        assert not found_in_tracked, f"Deleted symbol {deleted} must not be found in TRACKED_INSTRUMENTS"


def test_05_database_contains_zero_non_core_records():
    """Verify that SQLite database tables contain zero non-core asset records."""
    db_path = "data/trading_system.db"
    if not os.path.exists(db_path):
        pytest.skip("Production DB not found")
        
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    allowed_db_symbols = (
        'EURUSD=X', 'GBPUSD=X', 'USDJPY=X', 'GC=F', 'BTC-USD', 'ETH-USD',
        'EUR_USD', 'GBP_USD', 'USD_JPY', 'XAU_USD', 'BTC_USD', 'ETH_USD',
        'EUR/USD', 'GBP/USD', 'USD/JPY', 'Gold', 'GOLD', 'XAU/USD', 'BTC', 'ETH',
        'Bitcoin (BTC)', 'Ethereum (ETH)'
    )
    placeholders = ",".join(f"'{s}'" for s in allowed_db_symbols)
    
    # Check signals table
    non_core_signals = cur.execute(f"SELECT COUNT(*) FROM signals WHERE symbol NOT IN ({placeholders})").fetchone()[0]
    assert non_core_signals == 0, f"Found {non_core_signals} non-core signals in database"
    
    # Check market_snapshots table
    non_core_snaps = cur.execute(f"SELECT COUNT(*) FROM market_snapshots WHERE symbol NOT IN ({placeholders})").fetchone()[0]
    assert non_core_snaps == 0, f"Found {non_core_snaps} non-core snapshots in database"
    
    # Check engine_analytical_results table
    non_core_eng = cur.execute(f"SELECT COUNT(*) FROM engine_analytical_results WHERE symbol NOT IN ({placeholders})").fetchone()[0]
    assert non_core_eng == 0, f"Found {non_core_eng} non-core engine results in database"
    
    conn.close()


def test_06_memory_stores_contain_zero_non_core_items():
    """Verify that experience memory and paper trades json files contain zero non-core asset items."""
    allowed_symbols = {
        'EURUSD=X', 'GBPUSD=X', 'USDJPY=X', 'GC=F', 'BTC-USD', 'ETH-USD',
        'EUR_USD', 'GBP_USD', 'USD_JPY', 'XAU_USD', 'BTC_USD', 'ETH_USD',
        'EUR/USD', 'GBP/USD', 'USD/JPY', 'Gold', 'GOLD', 'XAU/USD', 'BTC', 'ETH',
        'Bitcoin (BTC)', 'Ethereum (ETH)'
    }
    
    if os.path.exists("experience_memory_data.json"):
        with open("experience_memory_data.json", "r", encoding="utf-8") as f:
            em = json.load(f)
        for item in em:
            sym = item.get("symbol")
            if sym:
                assert sym in allowed_symbols, f"Non-core symbol {sym} in experience_memory_data.json"

    if os.path.exists("paper_trades_data.json"):
        with open("paper_trades_data.json", "r", encoding="utf-8") as f:
            pt = json.load(f)
        for t in pt.get("active_trades", []):
            sym = t.get("symbol")
            if sym:
                assert sym in allowed_symbols, f"Non-core symbol {sym} in active paper trades"


def test_07_all_six_core_assets_pipeline_verification():
    """Verify that all six core assets correctly evaluate across risk engine, weights, and retrieval."""
    risk_engine = RiskEngine()
    retriever = HybridKnowledgeRetriever()
    aggregator = EvidenceAggregator()
    
    test_cases = [
        {"symbol": "EURUSD=X", "price": 1.0850, "atr": 0.0015, "asset_class": "FOREX"},
        {"symbol": "GBPUSD=X", "price": 1.2950, "atr": 0.0020, "asset_class": "FOREX"},
        {"symbol": "USDJPY=X", "price": 154.50, "atr": 0.25,   "asset_class": "FOREX"},
        {"symbol": "GC=F",     "price": 2650.0, "atr": 15.0,   "asset_class": "COMMODITY"},
        {"symbol": "BTC-USD",  "price": 64000.0,"atr": 1200.0, "asset_class": "CRYPTO"},
        {"symbol": "ETH-USD",  "price": 3200.0, "atr": 65.0,   "asset_class": "CRYPTO"},
    ]
    
    for tc in test_cases:
        # 1. Risk calculation
        risk_res = risk_engine.calculate_trade_parameters(
            symbol=tc["symbol"],
            current_price=tc["price"],
            direction="LONG",
            atr=tc["atr"],
            asset_class=tc["asset_class"]
        )
        assert risk_res["valid"] is True, f"Risk calculation failed for {tc['symbol']}"
        assert risk_res["risk_reward"] >= 2.0
        
        # 2. Hybrid retrieval
        knowledge = retriever.retrieve_hybrid_knowledge(
            symbol=tc["symbol"],
            direction="LONG",
            asset_class=tc["asset_class"],
            limit=2
        )
        assert isinstance(knowledge, list), f"Retrieval failed for {tc['symbol']}"
        
        # 3. Weights profile
        weights = aggregator.CANDIDATE_ASSET_PROFILES.get(tc["asset_class"])
        assert weights is not None
        total_w = sum(v["weight"] if isinstance(v, dict) else v for v in weights.values())
        assert abs(total_w - 1.0) < 1e-4
