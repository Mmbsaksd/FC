"""
Comprehensive Unit & Integration Test Suite for the Six-Core-Market Focus,
Institutional Memory, Hybrid Vector Retrieval, Small-Model Structuring, and Risk Architecture.
"""

import os
import sys
import pytest
import pandas as pd
import numpy as np

from app.config.constants import (
    TRACKED_INSTRUMENTS,
    CORE_INSTRUMENT_SYMBOLS,
    SECONDARY_INSTRUMENT_SYMBOLS
)
from app.config.asset_config import asset_config_manager
from app.parallel.base_engine import MarketSnapshot, AnalysisResult
from app.parallel.aggregator import EvidenceAggregator
from app.memory.vector_store import (
    vector_store,
    LocalVectorStore,
    LocalDeterministicEmbeddingProvider,
    SemanticDocumentFormatter
)
from app.memory.knowledge_ingestion import KnowledgeIngestionPipeline
from app.memory.knowledge_retriever import HybridKnowledgeRetriever
from app.llm.structuring_engine import SmallModelStructuringEngine
from app.llm.decision_engine import LLMDecisionEngine
from app.risk.candidate_qualifier import CandidateQualificationEngine
from app.risk.final_gate import DeterministicFinalRiskGate


def test_six_core_market_universe_configuration():
    """Verify that exactly 6 core markets are active and non-core assets are completely removed."""
    assert len(CORE_INSTRUMENT_SYMBOLS) == 6
    assert set(CORE_INSTRUMENT_SYMBOLS) == {
        "EURUSD=X", "GBPUSD=X", "USDJPY=X", "GC=F", "BTC-USD", "ETH-USD"
    }
    assert SECONDARY_INSTRUMENT_SYMBOLS == []
    assert len(TRACKED_INSTRUMENTS) == 6


def test_vector_store_indexing_and_similarity():
    """Verify embedding generation, document indexing, and cosine similarity ranking."""
    provider = LocalDeterministicEmbeddingProvider(dim=128)
    v1 = provider.embed_text("EURUSD trend continuation long breakout")
    v2 = provider.embed_text("EURUSD trend continuation long breakout")
    v3 = provider.embed_text("Gold commodity geopolitical hedge safe haven")

    # Identical text should produce identical vector
    assert np.allclose(v1, v2)
    # Cosine similarity between identical vectors is 1.0
    sim_same = np.dot(v1, v2)
    assert pytest.approx(sim_same, rel=1e-3) == 1.0

    # Orthogonal semantic topics have lower similarity
    sim_diff = np.dot(v1, v3)
    assert sim_diff < 0.90

    # Test LocalVectorStore indexing
    store = LocalVectorStore(storage_path="data/memory/test_vector_index.json", embedding_provider=provider)
    doc_id = store.add_document(
        doc_id="test-doc-1",
        text="EURUSD London breakout with positive EV and high directional consensus",
        metadata={"applicable_asset_classes": ["FOREX"], "applicable_regimes": ["TRENDING"], "symbol": "EURUSD"},
        doc_type="STRATEGY_RULE",
        validation_status="VALIDATED"
    )
    assert doc_id == "test-doc-1"

    results = store.similarity_search(
        query="EURUSD breakout consensus",
        metadata_filters={"applicable_asset_classes": "FOREX"},
        limit=1
    )
    assert len(results) == 1
    assert results[0][1]["doc_id"] == "test-doc-1"
    assert results[0][0] > 0.30


def test_hybrid_retrieval_provenance_and_filtering():
    """Verify that hybrid retrieval respects metadata filters and tags provenance categories."""
    retriever = HybridKnowledgeRetriever()

    # 1. Query for EUR/USD Forex Breakout
    res_eur = retriever.retrieve_hybrid_knowledge(
        symbol="EUR/USD",
        direction="LONG",
        regime="TRENDING",
        setup_type="MOMENTUM_BREAKOUT",
        timeframe="15M",
        session="LONDON/NY_OVERLAP",
        asset_class="FOREX",
        limit=3
    )
    assert len(res_eur) > 0
    assert all("retrieval_score" in r for r in res_eur)
    assert any("EUR" in str(r.get("applicable_symbols", [])) or "FOREX" in str(r.get("applicable_asset_classes", [])) for r in res_eur)

    # 2. Query for Gold Safe Haven
    res_gold = retriever.retrieve_hybrid_knowledge(
        symbol="Gold",
        direction="LONG",
        regime="HIGH_VOLATILITY_EXPANSION",
        setup_type="SAFE_HAVEN_EXPANSION",
        timeframe="1H",
        session="ALL",
        asset_class="COMMODITY",
        limit=3
    )
    assert len(res_gold) > 0
    assert any("GC=F" in str(r.get("applicable_symbols", [])) or "COMMODITY" in str(r.get("applicable_asset_classes", [])) for r in res_gold)

    # 3. Query for Bitcoin Liquidation
    res_btc = retriever.retrieve_hybrid_knowledge(
        symbol="BTC-USD",
        direction="LONG",
        regime="HIGH_VOLATILITY_EXPANSION",
        setup_type="LIQUIDATION_WICK",
        timeframe="15M",
        session="ALL",
        asset_class="CRYPTO",
        limit=3
    )
    assert len(res_btc) > 0
    assert any("BTC" in str(r.get("applicable_symbols", [])) or "CRYPTO" in str(r.get("applicable_asset_classes", [])) for r in res_btc)


def test_small_model_structuring_engine():
    """Verify that SmallModelStructuringEngine structures situation without making trade decisions."""
    snap = MarketSnapshot(
        timestamp="2026-09-13T12:00:00Z",
        symbol="EURUSD=X",
        symbol_name="EUR/USD",
        asset_class="FOREX",
        price=1.0850,
        bid=1.0849,
        ask=1.0851,
        spread_pips=1.0,
        timeframe="15M",
        candles=pd.DataFrame({"close": [1.0800, 1.0850]}),
        session="LONDON/NY_OVERLAP",
        pip_size=0.0001,
        base_currency="EUR",
        quote_currency="USD",
        is_crypto=False
    )
    
    agg = EvidenceAggregator()
    eng_res = {
        "TechnicalAnalysis": AnalysisResult(engine_name="TechnicalAnalysis", status="SUCCESS", score=80.0, direction="LONG", confidence=0.80, evidence=["Bullish RSI"], contradictions=[], metrics={"setup_type": "MOMENTUM_BREAKOUT"}, latency_ms=10.0),
        "MarketStructure": AnalysisResult(engine_name="MarketStructure", status="SUCCESS", score=75.0, direction="LONG", confidence=0.75, evidence=["Higher Highs"], contradictions=[], metrics={}, latency_ms=10.0),
        "CurrencyStrength": AnalysisResult(engine_name="CurrencyStrength", status="SUCCESS", score=70.0, direction="LONG", confidence=0.70, evidence=["EUR > USD"], contradictions=[], metrics={}, latency_ms=10.0),
        "RiskMetrics": AnalysisResult(engine_name="RiskMetrics", status="SUCCESS", score=80.0, direction="LONG", confidence=0.80, evidence=["Valid R:R"], contradictions=[], metrics={"atr": 0.0020}, latency_ms=10.0),
        "MarketRegime": AnalysisResult(engine_name="MarketRegime", status="SUCCESS", score=60.0, direction="LONG", confidence=0.60, evidence=["Trend expansion"], contradictions=[], metrics={"regime": "TRENDING"}, latency_ms=10.0)
    }
    ctx = agg.aggregate_evidence(snap, eng_res, mode="CANDIDATE")
    ctx.expected_value_r = 0.45

    structured = SmallModelStructuringEngine.structure_situation(
        context=ctx,
        snapshot=snap,
        trade_params={"risk_reward": 2.5, "stop_loss": 1.0820, "take_profit_1": 1.0925},
        ml_probability=0.60
    )

    assert structured.symbol == "EUR/USD"
    assert structured.dominant_direction == "LONG"
    assert structured.directional_consensus > 0.0
    assert "EUR/USD" in structured.retrieval_query
    assert "Direction:LONG" in structured.retrieval_query
    # Structuring layer must NOT output decision enum
    assert not hasattr(structured, "decision")


def test_prompt_injection_safety_and_data_treatment():
    """Verify that external/retrieved knowledge cannot override deterministic risk rules."""
    gate = DeterministicFinalRiskGate(min_rr=2.0)

    # Simulated candidate where LLM claims 'approved' on inverted geometry or negative EV
    corrupt_candidate = {
        "symbol_name": "EUR/USD",
        "direction": "LONG",
        "expected_value_r": -0.25, # Negative EV
        "decision": "TRADE",
        "approved": True
    }
    context_meta = {"asset_class": "FOREX", "spread_pips": 1.0, "data_quality": "VALID"}
    risk_metrics = {"risk_reward": 2.5, "entry_price": 1.0850, "stop_loss": 1.0820, "take_profit_1": 1.0925}

    passed, reason = gate.validate_candidate(corrupt_candidate, context_meta, risk_metrics)
    assert not passed
    assert "Negative Expected Value" in reason

    # Test inverted Long geometry (SL above Entry)
    inverted_risk = {"risk_reward": 2.5, "entry_price": 1.0850, "stop_loss": 1.0900, "take_profit_1": 1.0950}
    corrupt_candidate["expected_value_r"] = +0.50
    passed_geom, reason_geom = gate.validate_candidate(corrupt_candidate, context_meta, inverted_risk)
    assert not passed_geom
    assert "Inverted Long Geometry" in reason_geom


def test_replaying_canonical_vector_retrieval_cases():
    """Verify vector retrieval on 8 canonical trading setups."""
    retriever = HybridKnowledgeRetriever()

    test_cases = [
        ("EUR/USD", "LONG", "TRENDING", "MOMENTUM_BREAKOUT", "FOREX"),
        ("EUR/USD", "SHORT", "HIGH_VOLATILITY_EXPANSION", "FALSE_BREAKOUT", "FOREX"),
        ("Gold", "LONG", "HIGH_VOLATILITY_EXPANSION", "SAFE_HAVEN_EXPANSION", "COMMODITY"),
        ("Gold", "SHORT", "RANGING", "VOLATILITY_EXPANSION", "COMMODITY"),
        ("BTC-USD", "LONG", "HIGH_VOLATILITY_EXPANSION", "LIQUIDATION_WICK", "CRYPTO"),
        ("BTC-USD", "SHORT", "TRENDING", "TREND_FAILURE", "CRYPTO"),
        ("ETH-USD", "LONG", "TRENDING", "HIGH_BETA_BREAKOUT", "CRYPTO"),
        ("ETH-USD", "SHORT", "HIGH_VOLATILITY_EXPANSION", "MOMENTUM_FAILURE", "CRYPTO")
    ]

    for sym, direction, regime, setup, asset in test_cases:
        items = retriever.retrieve_hybrid_knowledge(
            symbol=sym,
            direction=direction,
            regime=regime,
            setup_type=setup,
            asset_class=asset,
            limit=2
        )
        assert len(items) > 0
        assert "retrieval_score" in items[0]
        assert "provenance_category" in items[0]
