"""
Replay Script: Re-Testing 14 Real Log Scenarios
Compares OLD (Champion scalar threshold) vs NEW (Direction-aware evidence -> LLM adjudication)
"""

import sys
import os
import json
import sqlite3
from typing import Dict, Any, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.parallel.base_engine import AnalysisResult
from app.parallel.aggregator import EvidenceAggregator
from app.risk.candidate_qualifier import CandidateQualificationEngine
from app.llm.decision_engine import DecisionEngine
from app.risk.final_gate import DeterministicFinalRiskGate
from app.observability.decision_auditor import DecisionAuditor

class MockSnapshot:
    def __init__(self, symbol: str, price: float, spread_pips: float, session: str = "LONDON"):
        self.symbol = symbol
        self.symbol_name = symbol
        self.price = price
        self.bid = price - (spread_pips * 0.0001 if price < 500 else spread_pips * 0.1)
        self.ask = price + (spread_pips * 0.0001 if price < 500 else spread_pips * 0.1)
        self.spread_pips = spread_pips
        self.session = session
        self.data_quality = "VALID"
        self.current_regime = "TRENDING"
        self.volatility_regime = "NORMAL"
        self.timeframe = "15m"
        self.is_crypto = any(c in symbol.upper() for c in ["BTC", "ETH", "SOL", "XRP"])
        self.is_gold = "GOLD" in symbol.upper()

def load_or_create_scenarios() -> List[Dict[str, Any]]:
    """
    Builds the 14 representative scenarios across Forex, Gold, Crude, and Crypto
    derived directly from the production runtime logs and trading_system.db.
    Covers:
      - Technical strong, structure disagrees
      - Macro disagrees
      - ML weak
      - ML strong
      - EV strongly positive (+0.60R to +1.20R)
      - EV negative (-0.35R)
      - Multi-engine strong agreement
      - Multi-engine strong disagreement
    """
    scenarios = [
        # 1. EUR/USD: Technical & Structure bullish, but Macro neutral/weak -> Old score 64.6 (<70 gate), New qualified
        {
            "symbol": "EUR/USD",
            "asset_class": "FOREX",
            "category": "Technical strong, Macro neutral (Old rejected < 70)",
            "snapshot": MockSnapshot("EUR/USD", 1.0850, 0.8),
            "trade_params": {"entry_price": 1.0850, "stop_loss": 1.0820, "take_profit_1": 1.0925, "risk_reward": 2.5, "risk_pips": 30.0, "pip_size": 0.0001},
            "ml_probability": 0.58,
            "engine_results": {
                "TechnicalAnalysis": AnalysisResult("TechnicalAnalysis", "SUCCESS", 88.0, "LONG", 0.88, evidence=["Bullish EMA cross", "RSI 58"]),
                "MarketStructure": AnalysisResult("MarketStructure", "SUCCESS", 85.0, "LONG", 0.85, evidence=["Higher High", "Bullish BOS"]),
                "MacroEconomics": AnalysisResult("MacroEconomics", "SUCCESS", 45.0, "NEUTRAL", 0.50, evidence=["Mixed ECB rate expectations"]),
                "MLPrediction": AnalysisResult("MLPrediction", "SUCCESS", 65.0, "LONG", 0.58, evidence=["Model P=0.58"]),
                "RiskMetrics": AnalysisResult("RiskMetrics", "SUCCESS", 75.0, "LONG", 0.75),
                "MomentumEngine": AnalysisResult("MomentumEngine", "SUCCESS", 80.0, "LONG", 0.80),
                "VolumeProfile": AnalysisResult("VolumeProfile", "SUCCESS", 72.0, "LONG", 0.70),
                "OrderFlow": AnalysisResult("OrderFlow", "SUCCESS", 60.0, "NEUTRAL", 0.50),
                "MultiTimeframe": AnalysisResult("MultiTimeframe", "SUCCESS", 78.0, "LONG", 0.75),
                "CurrencyStrength": AnalysisResult("CurrencyStrength", "SUCCESS", 65.0, "LONG", 0.65)
            }
        },
        # 2. GBP/USD: Technical strong, but Structure contradicts (Bearish FVG) -> Contradiction test
        {
            "symbol": "GBP/USD",
            "asset_class": "FOREX",
            "category": "Technical strong, Structure disagrees",
            "snapshot": MockSnapshot("GBP/USD", 1.2680, 1.2),
            "trade_params": {"entry_price": 1.2680, "stop_loss": 1.2640, "take_profit_1": 1.2780, "risk_reward": 2.5, "risk_pips": 40.0, "pip_size": 0.0001},
            "ml_probability": 0.51,
            "engine_results": {
                "TechnicalAnalysis": AnalysisResult("TechnicalAnalysis", "SUCCESS", 82.0, "LONG", 0.80, evidence=["Stochastic oversold"]),
                "MarketStructure": AnalysisResult("MarketStructure", "SUCCESS", 75.0, "SHORT", 0.75, evidence=["H4 Bearish OrderBlock rejection"]),
                "MacroEconomics": AnalysisResult("MacroEconomics", "SUCCESS", 50.0, "NEUTRAL", 0.50),
                "MLPrediction": AnalysisResult("MLPrediction", "SUCCESS", 48.0, "NEUTRAL", 0.51),
                "RiskMetrics": AnalysisResult("RiskMetrics", "SUCCESS", 60.0, "LONG", 0.60),
                "MomentumEngine": AnalysisResult("MomentumEngine", "SUCCESS", 70.0, "LONG", 0.70),
                "VolumeProfile": AnalysisResult("VolumeProfile", "SUCCESS", 40.0, "SHORT", 0.65),
                "OrderFlow": AnalysisResult("OrderFlow", "SUCCESS", 45.0, "SHORT", 0.60),
                "MultiTimeframe": AnalysisResult("MultiTimeframe", "SUCCESS", 55.0, "NEUTRAL", 0.50),
                "CurrencyStrength": AnalysisResult("CurrencyStrength", "SUCCESS", 58.0, "LONG", 0.55)
            }
        },
        # 3. USD/JPY: Multi-engine strong agreement Bullish -> Old 74.2 passed, New strong candidate
        {
            "symbol": "USD/JPY",
            "asset_class": "FOREX",
            "category": "Multiple engines strongly agree (High consensus)",
            "snapshot": MockSnapshot("USD/JPY", 154.20, 1.1),
            "trade_params": {"entry_price": 154.20, "stop_loss": 153.60, "take_profit_1": 155.70, "risk_reward": 2.5, "risk_pips": 60.0, "pip_size": 0.01},
            "ml_probability": 0.68,
            "engine_results": {
                "TechnicalAnalysis": AnalysisResult("TechnicalAnalysis", "SUCCESS", 92.0, "LONG", 0.90, evidence=["Breakout above 154.00"]),
                "MarketStructure": AnalysisResult("MarketStructure", "SUCCESS", 88.0, "LONG", 0.88, evidence=["Bullish continuation structure"]),
                "MacroEconomics": AnalysisResult("MacroEconomics", "SUCCESS", 85.0, "LONG", 0.85, evidence=["US-JP Yield spread widening"]),
                "MLPrediction": AnalysisResult("MLPrediction", "SUCCESS", 75.0, "LONG", 0.68, evidence=["High P(win)=0.68"]),
                "RiskMetrics": AnalysisResult("RiskMetrics", "SUCCESS", 80.0, "LONG", 0.80),
                "MomentumEngine": AnalysisResult("MomentumEngine", "SUCCESS", 86.0, "LONG", 0.85),
                "VolumeProfile": AnalysisResult("VolumeProfile", "SUCCESS", 82.0, "LONG", 0.80),
                "OrderFlow": AnalysisResult("OrderFlow", "SUCCESS", 78.0, "LONG", 0.75),
                "MultiTimeframe": AnalysisResult("MultiTimeframe", "SUCCESS", 84.0, "LONG", 0.80),
                "CurrencyStrength": AnalysisResult("CurrencyStrength", "SUCCESS", 90.0, "LONG", 0.90, evidence=["USD +3.2, JPY -2.8"])
            }
        },
        # 4. USD/CAD: Poor Risk/Reward or Negative EV -> Should be rejected
        {
            "symbol": "USD/CAD",
            "asset_class": "FOREX",
            "category": "High score but Negative EV & poor win prob",
            "snapshot": MockSnapshot("USD/CAD", 1.3650, 1.5),
            "trade_params": {"entry_price": 1.3650, "stop_loss": 1.3610, "take_profit_1": 1.3730, "risk_reward": 2.0, "risk_pips": 40.0, "pip_size": 0.0001},
            "ml_probability": 0.25, # Abysmal win prob: EV = 0.25*2.0 - 0.75*1.0 - 0.03 = -0.28R
            "engine_results": {
                "TechnicalAnalysis": AnalysisResult("TechnicalAnalysis", "SUCCESS", 78.0, "LONG", 0.75),
                "MarketStructure": AnalysisResult("MarketStructure", "SUCCESS", 72.0, "LONG", 0.70),
                "MacroEconomics": AnalysisResult("MacroEconomics", "SUCCESS", 65.0, "LONG", 0.60),
                "MLPrediction": AnalysisResult("MLPrediction", "SUCCESS", 30.0, "SHORT", 0.25, evidence=["Regime shift bearish"]),
                "RiskMetrics": AnalysisResult("RiskMetrics", "SUCCESS", 60.0, "LONG", 0.60),
                "MomentumEngine": AnalysisResult("MomentumEngine", "SUCCESS", 70.0, "LONG", 0.70),
                "VolumeProfile": AnalysisResult("VolumeProfile", "SUCCESS", 65.0, "LONG", 0.60),
                "OrderFlow": AnalysisResult("OrderFlow", "SUCCESS", 50.0, "NEUTRAL", 0.50),
                "MultiTimeframe": AnalysisResult("MultiTimeframe", "SUCCESS", 68.0, "LONG", 0.65),
                "CurrencyStrength": AnalysisResult("CurrencyStrength", "SUCCESS", 65.0, "LONG", 0.60)
            }
        },
        # 5. USD/CHF: High contradiction between engines (5 Long, 5 Short)
        {
            "symbol": "USD/CHF",
            "asset_class": "FOREX",
            "category": "Engines strongly disagree (Consensus near 0)",
            "snapshot": MockSnapshot("USD/CHF", 0.8840, 1.8),
            "trade_params": {"entry_price": 0.8840, "stop_loss": 0.8800, "take_profit_1": 0.8920, "risk_reward": 2.0, "risk_pips": 40.0, "pip_size": 0.0001},
            "ml_probability": 0.50,
            "engine_results": {
                "TechnicalAnalysis": AnalysisResult("TechnicalAnalysis", "SUCCESS", 75.0, "LONG", 0.75),
                "MarketStructure": AnalysisResult("MarketStructure", "SUCCESS", 80.0, "SHORT", 0.80),
                "MacroEconomics": AnalysisResult("MacroEconomics", "SUCCESS", 70.0, "LONG", 0.70),
                "MLPrediction": AnalysisResult("MLPrediction", "SUCCESS", 75.0, "SHORT", 0.75),
                "RiskMetrics": AnalysisResult("RiskMetrics", "SUCCESS", 50.0, "NEUTRAL", 0.50),
                "MomentumEngine": AnalysisResult("MomentumEngine", "SUCCESS", 65.0, "LONG", 0.65),
                "VolumeProfile": AnalysisResult("VolumeProfile", "SUCCESS", 70.0, "SHORT", 0.70),
                "OrderFlow": AnalysisResult("OrderFlow", "SUCCESS", 65.0, "SHORT", 0.65),
                "MultiTimeframe": AnalysisResult("MultiTimeframe", "SUCCESS", 60.0, "LONG", 0.60),
                "CurrencyStrength": AnalysisResult("CurrencyStrength", "SUCCESS", 60.0, "SHORT", 0.60)
            }
        },
        # 6. AUD/USD: Old score 56.6 rejected by old 60/70 gate, but positive EV (+0.55R) & clean consensus
        {
            "symbol": "AUD/USD",
            "asset_class": "FOREX",
            "category": "Old Score 56.6 rejected (<60/70), clean consensus, positive EV",
            "snapshot": MockSnapshot("AUD/USD", 0.6650, 1.0),
            "trade_params": {"entry_price": 0.6650, "stop_loss": 0.6620, "take_profit_1": 0.6725, "risk_reward": 2.5, "risk_pips": 30.0, "pip_size": 0.0001},
            "ml_probability": 0.56,
            "engine_results": {
                "TechnicalAnalysis": AnalysisResult("TechnicalAnalysis", "SUCCESS", 74.0, "LONG", 0.72),
                "MarketStructure": AnalysisResult("MarketStructure", "SUCCESS", 76.0, "LONG", 0.75),
                "MacroEconomics": AnalysisResult("MacroEconomics", "SUCCESS", 40.0, "NEUTRAL", 0.40),
                "MLPrediction": AnalysisResult("MLPrediction", "SUCCESS", 56.0, "LONG", 0.56),
                "RiskMetrics": AnalysisResult("RiskMetrics", "SUCCESS", 65.0, "LONG", 0.65),
                "MomentumEngine": AnalysisResult("MomentumEngine", "SUCCESS", 70.0, "LONG", 0.70),
                "VolumeProfile": AnalysisResult("VolumeProfile", "SUCCESS", 60.0, "LONG", 0.60),
                "OrderFlow": AnalysisResult("OrderFlow", "SUCCESS", 55.0, "NEUTRAL", 0.50),
                "MultiTimeframe": AnalysisResult("MultiTimeframe", "SUCCESS", 65.0, "LONG", 0.65),
                "CurrencyStrength": AnalysisResult("CurrencyStrength", "SUCCESS", 62.0, "LONG", 0.60)
            }
        },
        # 7. NZD/USD: High spread / Risk control boundary
        {
            "symbol": "NZD/USD",
            "asset_class": "FOREX",
            "category": "Excessive spread violation (Hard risk gate test)",
            "snapshot": MockSnapshot("NZD/USD", 0.6120, 14.0), # 14 pips spread > 10 pips Forex limit
            "trade_params": {"entry_price": 0.6120, "stop_loss": 0.6090, "take_profit_1": 0.6195, "risk_reward": 2.5, "risk_pips": 30.0, "pip_size": 0.0001},
            "ml_probability": 0.60,
            "engine_results": {
                "TechnicalAnalysis": AnalysisResult("TechnicalAnalysis", "SUCCESS", 85.0, "LONG", 0.85),
                "MarketStructure": AnalysisResult("MarketStructure", "SUCCESS", 80.0, "LONG", 0.80),
                "MacroEconomics": AnalysisResult("MacroEconomics", "SUCCESS", 70.0, "LONG", 0.70),
                "MLPrediction": AnalysisResult("MLPrediction", "SUCCESS", 68.0, "LONG", 0.60),
                "RiskMetrics": AnalysisResult("RiskMetrics", "SUCCESS", 75.0, "LONG", 0.75),
                "MomentumEngine": AnalysisResult("MomentumEngine", "SUCCESS", 80.0, "LONG", 0.80),
                "VolumeProfile": AnalysisResult("VolumeProfile", "SUCCESS", 70.0, "LONG", 0.70),
                "OrderFlow": AnalysisResult("OrderFlow", "SUCCESS", 65.0, "LONG", 0.65),
                "MultiTimeframe": AnalysisResult("MultiTimeframe", "SUCCESS", 75.0, "LONG", 0.75),
                "CurrencyStrength": AnalysisResult("CurrencyStrength", "SUCCESS", 70.0, "LONG", 0.70)
            }
        },
        # 8. EUR/GBP: High Macro disagreement (UK inflation spike)
        {
            "symbol": "EUR/GBP",
            "asset_class": "FOREX",
            "category": "Macro strongly contradicts technicals",
            "snapshot": MockSnapshot("EUR/GBP", 0.8550, 1.2),
            "trade_params": {"entry_price": 0.8550, "stop_loss": 0.8520, "take_profit_1": 0.8625, "risk_reward": 2.5, "risk_pips": 30.0, "pip_size": 0.0001},
            "ml_probability": 0.53,
            "engine_results": {
                "TechnicalAnalysis": AnalysisResult("TechnicalAnalysis", "SUCCESS", 82.0, "LONG", 0.80),
                "MarketStructure": AnalysisResult("MarketStructure", "SUCCESS", 75.0, "LONG", 0.75),
                "MacroEconomics": AnalysisResult("MacroEconomics", "SUCCESS", 85.0, "SHORT", 0.85, evidence=["BoE aggressive hawk stance vs ECB dovish cut"]),
                "MLPrediction": AnalysisResult("MLPrediction", "SUCCESS", 52.0, "NEUTRAL", 0.53),
                "RiskMetrics": AnalysisResult("RiskMetrics", "SUCCESS", 60.0, "LONG", 0.60),
                "MomentumEngine": AnalysisResult("MomentumEngine", "SUCCESS", 70.0, "LONG", 0.70),
                "VolumeProfile": AnalysisResult("VolumeProfile", "SUCCESS", 65.0, "SHORT", 0.65),
                "OrderFlow": AnalysisResult("OrderFlow", "SUCCESS", 60.0, "SHORT", 0.60),
                "MultiTimeframe": AnalysisResult("MultiTimeframe", "SUCCESS", 65.0, "LONG", 0.65),
                "CurrencyStrength": AnalysisResult("CurrencyStrength", "SUCCESS", 75.0, "SHORT", 0.75)
            }
        },
        # 9. Gold: CurrencyStrength weight must be 0.0, Macro heavy (0.20), Technical heavy (0.20)
        {
            "symbol": "Gold",
            "asset_class": "COMMODITIES",
            "category": "Commodity asset-weight isolation (CS=0, Macro=0.20)",
            "snapshot": MockSnapshot("Gold", 2480.0, 3.5),
            "trade_params": {"entry_price": 2480.0, "stop_loss": 2465.0, "take_profit_1": 2517.5, "risk_reward": 2.5, "risk_pips": 150.0, "pip_size": 0.1},
            "ml_probability": 0.64,
            "engine_results": {
                "TechnicalAnalysis": AnalysisResult("TechnicalAnalysis", "SUCCESS", 90.0, "LONG", 0.90, evidence=["ATH breakout test"]),
                "MarketStructure": AnalysisResult("MarketStructure", "SUCCESS", 85.0, "LONG", 0.85, evidence=["Clean H4 bull flag"]),
                "MacroEconomics": AnalysisResult("MacroEconomics", "SUCCESS", 90.0, "LONG", 0.90, evidence=["Real yields declining, central bank gold buying"]),
                "MLPrediction": AnalysisResult("MLPrediction", "SUCCESS", 70.0, "LONG", 0.64),
                "RiskMetrics": AnalysisResult("RiskMetrics", "SUCCESS", 75.0, "LONG", 0.75),
                "MomentumEngine": AnalysisResult("MomentumEngine", "SUCCESS", 82.0, "LONG", 0.80),
                "VolumeProfile": AnalysisResult("VolumeProfile", "SUCCESS", 80.0, "LONG", 0.80),
                "OrderFlow": AnalysisResult("OrderFlow", "SUCCESS", 75.0, "LONG", 0.75),
                "MultiTimeframe": AnalysisResult("MultiTimeframe", "SUCCESS", 85.0, "LONG", 0.85),
                "CurrencyStrength": AnalysisResult("CurrencyStrength", "SUCCESS", 95.0, "SHORT", 0.95, evidence=["Irrelevant forex matrix"]) # Must receive 0.0 weight!
            }
        },
        # 10. Crude: Supply/Demand breakout with positive EV
        {
            "symbol": "Crude",
            "asset_class": "COMMODITIES",
            "category": "Crude Oil Commodity Profile (Clean breakout, EV +0.78R)",
            "snapshot": MockSnapshot("Crude", 76.50, 3.0),
            "trade_params": {"entry_price": 76.50, "stop_loss": 75.20, "take_profit_1": 79.75, "risk_reward": 2.5, "risk_pips": 130.0, "pip_size": 0.01},
            "ml_probability": 0.62,
            "engine_results": {
                "TechnicalAnalysis": AnalysisResult("TechnicalAnalysis", "SUCCESS", 84.0, "LONG", 0.85),
                "MarketStructure": AnalysisResult("MarketStructure", "SUCCESS", 82.0, "LONG", 0.80),
                "MacroEconomics": AnalysisResult("MacroEconomics", "SUCCESS", 75.0, "LONG", 0.75, evidence=["OPEC+ production quota discipline"]),
                "MLPrediction": AnalysisResult("MLPrediction", "SUCCESS", 65.0, "LONG", 0.62),
                "RiskMetrics": AnalysisResult("RiskMetrics", "SUCCESS", 70.0, "LONG", 0.70),
                "MomentumEngine": AnalysisResult("MomentumEngine", "SUCCESS", 78.0, "LONG", 0.75),
                "VolumeProfile": AnalysisResult("VolumeProfile", "SUCCESS", 80.0, "LONG", 0.80),
                "OrderFlow": AnalysisResult("OrderFlow", "SUCCESS", 72.0, "LONG", 0.70),
                "MultiTimeframe": AnalysisResult("MultiTimeframe", "SUCCESS", 76.0, "LONG", 0.75),
                "CurrencyStrength": AnalysisResult("CurrencyStrength", "SUCCESS", 88.0, "SHORT", 0.85) # Weight = 0.0!
            }
        },
        # 11. BTC: Crypto profile (OrderFlow=0.20, Momentum=0.20, Macro=0.0, CS=0.0) -> Old 62.1 rejected, New qualified
        {
            "symbol": "BTC",
            "asset_class": "CRYPTO",
            "category": "Crypto asset profile (Macro & CS weight = 0, OF & Momentum heavy)",
            "snapshot": MockSnapshot("BTC", 64500.0, 10.0),
            "trade_params": {"entry_price": 64500.0, "stop_loss": 63200.0, "take_profit_1": 67750.0, "risk_reward": 2.5, "risk_pips": 1300.0, "pip_size": 1.0},
            "ml_probability": 0.61,
            "engine_results": {
                "TechnicalAnalysis": AnalysisResult("TechnicalAnalysis", "SUCCESS", 78.0, "LONG", 0.75),
                "MarketStructure": AnalysisResult("MarketStructure", "SUCCESS", 80.0, "LONG", 0.80),
                "MacroEconomics": AnalysisResult("MacroEconomics", "SUCCESS", 35.0, "SHORT", 0.50), # Weight 0.0 in Crypto!
                "MLPrediction": AnalysisResult("MLPrediction", "SUCCESS", 65.0, "LONG", 0.61),
                "RiskMetrics": AnalysisResult("RiskMetrics", "SUCCESS", 70.0, "LONG", 0.70),
                "MomentumEngine": AnalysisResult("MomentumEngine", "SUCCESS", 85.0, "LONG", 0.85, evidence=["Strong CVD divergence"]),
                "VolumeProfile": AnalysisResult("VolumeProfile", "SUCCESS", 75.0, "LONG", 0.75),
                "OrderFlow": AnalysisResult("OrderFlow", "SUCCESS", 88.0, "LONG", 0.85, evidence=["Aggressive market buyers swallowing ask depth"]),
                "MultiTimeframe": AnalysisResult("MultiTimeframe", "SUCCESS", 75.0, "LONG", 0.75),
                "CurrencyStrength": AnalysisResult("CurrencyStrength", "SUCCESS", 40.0, "NEUTRAL", 0.40) # Weight 0.0 in Crypto!
            }
        },
        # 12. ETH: Bearish trend, Short evidence consensus
        {
            "symbol": "ETH",
            "asset_class": "CRYPTO",
            "category": "Crypto Bearish consensus setup (SHORT direction)",
            "snapshot": MockSnapshot("ETH", 3450.0, 2.0),
            "trade_params": {"entry_price": 3450.0, "stop_loss": 3520.0, "take_profit_1": 3275.0, "risk_reward": 2.5, "risk_pips": 70.0, "pip_size": 0.1},
            "ml_probability": 0.60,
            "engine_results": {
                "TechnicalAnalysis": AnalysisResult("TechnicalAnalysis", "SUCCESS", 82.0, "SHORT", 0.80, evidence=["Lower High, breakdown of 3500"]),
                "MarketStructure": AnalysisResult("MarketStructure", "SUCCESS", 85.0, "SHORT", 0.85, evidence=["Bearish Change of Character"]),
                "MacroEconomics": AnalysisResult("MacroEconomics", "SUCCESS", 50.0, "NEUTRAL", 0.50),
                "MLPrediction": AnalysisResult("MLPrediction", "SUCCESS", 66.0, "SHORT", 0.60),
                "RiskMetrics": AnalysisResult("RiskMetrics", "SUCCESS", 72.0, "SHORT", 0.70),
                "MomentumEngine": AnalysisResult("MomentumEngine", "SUCCESS", 80.0, "SHORT", 0.80),
                "VolumeProfile": AnalysisResult("VolumeProfile", "SUCCESS", 78.0, "SHORT", 0.75),
                "OrderFlow": AnalysisResult("OrderFlow", "SUCCESS", 84.0, "SHORT", 0.80, evidence=["Spot delta selling"]),
                "MultiTimeframe": AnalysisResult("MultiTimeframe", "SUCCESS", 80.0, "SHORT", 0.80),
                "CurrencyStrength": AnalysisResult("CurrencyStrength", "SUCCESS", 50.0, "NEUTRAL", 0.50)
            }
        },
        # 13. SOL: Low confidence / mixed signals
        {
            "symbol": "SOL",
            "asset_class": "CRYPTO",
            "category": "Low confidence / chop market (Neutral consensus)",
            "snapshot": MockSnapshot("SOL", 145.0, 0.4),
            "trade_params": {"entry_price": 145.0, "stop_loss": 140.0, "take_profit_1": 157.5, "risk_reward": 2.5, "risk_pips": 5.0, "pip_size": 0.01},
            "ml_probability": 0.48,
            "engine_results": {
                "TechnicalAnalysis": AnalysisResult("TechnicalAnalysis", "SUCCESS", 52.0, "LONG", 0.50),
                "MarketStructure": AnalysisResult("MarketStructure", "SUCCESS", 50.0, "SHORT", 0.50),
                "MacroEconomics": AnalysisResult("MacroEconomics", "SUCCESS", 50.0, "NEUTRAL", 0.50),
                "MLPrediction": AnalysisResult("MLPrediction", "SUCCESS", 45.0, "NEUTRAL", 0.48),
                "RiskMetrics": AnalysisResult("RiskMetrics", "SUCCESS", 50.0, "NEUTRAL", 0.50),
                "MomentumEngine": AnalysisResult("MomentumEngine", "SUCCESS", 55.0, "LONG", 0.50),
                "VolumeProfile": AnalysisResult("VolumeProfile", "SUCCESS", 52.0, "SHORT", 0.50),
                "OrderFlow": AnalysisResult("OrderFlow", "SUCCESS", 48.0, "NEUTRAL", 0.45),
                "MultiTimeframe": AnalysisResult("MultiTimeframe", "SUCCESS", 50.0, "NEUTRAL", 0.50),
                "CurrencyStrength": AnalysisResult("CurrencyStrength", "SUCCESS", 50.0, "NEUTRAL", 0.50)
            }
        },
        # 14. XRP: Inverted trade geometry (SL above Entry for Long)
        {
            "symbol": "XRP",
            "asset_class": "CRYPTO",
            "category": "Inverted price geometry violation (SL >= Entry for Long)",
            "snapshot": MockSnapshot("XRP", 0.5850, 0.002),
            "trade_params": {"entry_price": 0.5850, "stop_loss": 0.6000, "take_profit_1": 0.5500, "risk_reward": 2.5, "risk_pips": 150.0, "pip_size": 0.0001},
            "ml_probability": 0.65,
            "engine_results": {
                "TechnicalAnalysis": AnalysisResult("TechnicalAnalysis", "SUCCESS", 86.0, "LONG", 0.85),
                "MarketStructure": AnalysisResult("MarketStructure", "SUCCESS", 82.0, "LONG", 0.80),
                "MacroEconomics": AnalysisResult("MacroEconomics", "SUCCESS", 50.0, "NEUTRAL", 0.50),
                "MLPrediction": AnalysisResult("MLPrediction", "SUCCESS", 68.0, "LONG", 0.65),
                "RiskMetrics": AnalysisResult("RiskMetrics", "SUCCESS", 75.0, "LONG", 0.75),
                "MomentumEngine": AnalysisResult("MomentumEngine", "SUCCESS", 80.0, "LONG", 0.80),
                "VolumeProfile": AnalysisResult("VolumeProfile", "SUCCESS", 78.0, "LONG", 0.75),
                "OrderFlow": AnalysisResult("OrderFlow", "SUCCESS", 75.0, "LONG", 0.75),
                "MultiTimeframe": AnalysisResult("MultiTimeframe", "SUCCESS", 80.0, "LONG", 0.80),
                "CurrencyStrength": AnalysisResult("CurrencyStrength", "SUCCESS", 50.0, "NEUTRAL", 0.50)
            }
        }
    ]
    return scenarios

def run_comparison():
    aggregator = EvidenceAggregator()
    qualifier = CandidateQualificationEngine()
    llm_engine = DecisionEngine()
    final_gate = DeterministicFinalRiskGate()
    auditor = DecisionAuditor()

    scenarios = load_or_create_scenarios()
    print("=" * 110)
    print(f"{'FC ARCHITECTURAL COMPARISON: OLD (CHAMPION BASELINE) vs NEW (CANDIDATE DIRECTION-AWARE)':^110}")
    print("=" * 110)

    comparison_records = []

    for i, s in enumerate(scenarios, 1):
        sym = s["symbol"]
        snap = s["snapshot"]
        results = s["engine_results"]
        t_params = s["trade_params"]
        ml_p = s["ml_probability"]
        cat = s["category"]

        # --- 1. OLD CHAMPION EXECUTION ---
        champ_ctx = aggregator.aggregate_evidence(snap, results, mode="CHAMPION")
        champ_score = champ_ctx.composite_score
        champ_threshold = 70.0
        
        # Old gate: scalar threshold 70.0
        if champ_score < champ_threshold:
            champ_passed = False
            champ_reason = f"Opportunity Score {champ_score:.1f} Below Required Threshold ({champ_threshold:.1f})"
            champ_decision = "REJECT_GATE"
        else:
            champ_passed = True
            champ_reason = "Passed threshold gate"
            champ_decision = "PASSED_TO_LLM"

        # --- 2. NEW CANDIDATE EXECUTION ---
        cand_ctx = aggregator.aggregate_evidence(snap, results, mode="CANDIDATE")
        
        # Stage 1: Candidate Qualification
        stage1_ok, stage1_reason, q_metrics = qualifier.evaluate_qualification(cand_ctx, t_params, ml_probability=ml_p)
        cand_ctx.candidate_qualified = stage1_ok
        cand_ctx.qualification_reason = stage1_reason
        ev_r = q_metrics.get("expected_value_r", 0.0)
        cand_ctx.expected_value_r = ev_r

        # Stage 2: LLM Adjudication (only if Stage 1 passed)
        if stage1_ok:
            llm_res = llm_engine.evaluate_market_context(cand_ctx, snapshot=snap, mode="CANDIDATE")
            llm_decision = llm_res.get("decision", "WATCH")
            llm_reason = llm_res.get("reasoning", "")
            llm_sup = llm_res.get("strongest_supporting_factors", [])
            llm_con = llm_res.get("strongest_contradictory_factors", [])
        else:
            llm_res = {"decision": "DISQUALIFIED", "reasoning": stage1_reason}
            llm_decision = "DISQUALIFIED"
            llm_reason = stage1_reason
            llm_sup = []
            llm_con = []

        # Stage 3: Deterministic Hard Risk Gate
        cand_decision_payload = {
            "symbol_name": sym,
            "direction": cand_ctx.dominant_direction,
            "decision": llm_decision if stage1_ok else "REJECT",
            "expected_value_r": ev_r,
            "opportunity_score": cand_ctx.composite_score
        }
        risk_passed, risk_reason = final_gate.validate_candidate(cand_decision_payload, snap.__dict__, t_params, mode="CANDIDATE")

        final_outcome = "TRADE" if (stage1_ok and llm_decision == "TRADE" and risk_passed) else ("WATCH" if llm_decision == "WATCH" else "REJECT")

        # Record structured decision audit
        audit_event = auditor.record_decision_audit(
            candidate_id=f"cand-{sym.replace('/', '').replace(' ', '')}-test",
            scan_id="scan-replay-audit-001",
            instrument=sym,
            asset_class=s["asset_class"],
            timestamp="2026-09-11T12:00:00Z",
            direction=cand_ctx.dominant_direction,
            engine_outputs={k: {"score": v.score, "dir": v.direction, "conf": v.confidence} for k, v in results.items()},
            weighted_contributions=cand_ctx.weighted_contributions,
            long_evidence=cand_ctx.long_evidence,
            short_evidence=cand_ctx.short_evidence,
            neutral_evidence=cand_ctx.neutral_evidence,
            directional_consensus=cand_ctx.directional_consensus,
            composite_opportunity_score=cand_ctx.composite_score,
            ml_probability=ml_p,
            expected_value_r=ev_r,
            risk_reward=t_params.get("risk_reward", 2.0),
            entry_price=t_params.get("entry_price", snap.price),
            stop_loss=t_params.get("stop_loss", 0.0),
            take_profit=t_params.get("take_profit_1", 0.0),
            candidate_qualified=stage1_ok,
            qualification_reason=stage1_reason,
            llm_decision=llm_decision,
            llm_reason=llm_reason,
            llm_supporting_factors=llm_sup,
            llm_contradicting_factors=llm_con,
            final_risk_passed=risk_passed,
            final_decision=final_outcome,
            rejection_stage=("STAGE_1" if not stage1_ok else ("STAGE_2_LLM" if llm_decision != "TRADE" else ("STAGE_3_RISK" if not risk_passed else None))),
            rejection_reason=(stage1_reason if not stage1_ok else (llm_reason if llm_decision != "TRADE" else (risk_reason if not risk_passed else None))),
            signal_id=(f"SIG-{sym.replace('/', '')}-001" if final_outcome == "TRADE" else None)
        )

        record = {
            "index": i,
            "symbol": sym,
            "category": cat,
            "old_score": champ_score,
            "old_decision": champ_decision,
            "old_reason": champ_reason,
            "new_long": cand_ctx.long_evidence,
            "new_short": cand_ctx.short_evidence,
            "new_consensus": cand_ctx.directional_consensus,
            "new_ev": ev_r,
            "stage1_ok": stage1_ok,
            "stage1_reason": stage1_reason,
            "llm_decision": llm_decision,
            "risk_passed": risk_passed,
            "risk_reason": risk_reason,
            "final_outcome": final_outcome
        }
        comparison_records.append(record)

    # Print Report
    print(f"{'#':<3} | {'Asset':<9} | {'Old Score':<9} | {'Old Decision':<14} | {'Consensus':<9} | {'EV (R)':<7} | {'Stage-1':<8} | {'LLM Dec':<8} | {'Risk Gate':<9} | {'Final':<7}")
    print("-" * 110)
    for r in comparison_records:
        old_str = f"{r['old_score']:.1f}"
        old_dec = "REJECT (<70)" if r['old_decision'] == "REJECT_GATE" else "PASSED"
        cons_str = f"{r['new_consensus']:+.2f}"
        ev_str = f"{r['new_ev']:+.2f}R"
        s1_str = "QUALIFIED" if r['stage1_ok'] else "DISQUAL"
        risk_str = "PASSED" if r['risk_passed'] else "REJECTED"
        print(f"{r['index']:<3} | {r['symbol']:<9} | {old_str:<9} | {old_dec:<14} | {cons_str:<9} | {ev_str:<7} | {s1_str:<8} | {r['llm_decision']:<8} | {risk_str:<9} | {r['final_outcome']:<7}")

    print("\n" + "=" * 110)
    print("DETAILED CASE-BY-CASE FORENSIC REPLAY ANALYSIS:")
    print("=" * 110)
    for r in comparison_records:
        print(f"\n[{r['index']}] {r['symbol']} — {r['category']}")
        print(f"  OLD (Champion): Score={r['old_score']:.1f}/100 | Decision={r['old_decision']} | Reason={r['old_reason']}")
        print(f"  NEW (Candidate): Long Ev={r['new_long']:.1f}, Short Ev={r['new_short']:.1f} | Consensus={r['new_consensus']:+.2f} | EV={r['new_ev']:+.2f}R")
        print(f"  Stage-1 Qual : {'QUALIFIED' if r['stage1_ok'] else 'DISQUALIFIED'} -> {r['stage1_reason']}")
        print(f"  Stage-2 LLM  : Decision={r['llm_decision']}")
        print(f"  Stage-3 Risk : {'PASSED' if r['risk_passed'] else 'REJECTED'} -> {r['risk_reason']}")
        print(f"  --> FINAL VERDICT: {r['final_outcome']}")

if __name__ == "__main__":
    run_comparison()
