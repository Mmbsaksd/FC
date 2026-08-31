import pytest
from app.memory.knowledge_base import EmpiricalKnowledgeBase
from app.memory.knowledge_retriever import ContextualKnowledgeRetriever
from app.memory.experience_memory import ExperienceMemory
from app.engines.outcome_tracker import TradeOutcomeTracker

def test_knowledge_base_crud(tmp_path):
    test_kb_path = str(tmp_path / "test_knowledge_data.json")
    kb = EmpiricalKnowledgeBase(storage_path=test_kb_path)
    
    item_id = kb.add_knowledge_item({
        "title": "GBP/USD Isolated Test Observation",
        "category": "STRATEGY_RULE",
        "finding": "Test finding on cable in temporary isolation",
        "evidence": "Test backtest isolated",
        "applicable_symbols": ["GBP/USD"],
        "applicable_asset_classes": ["FOREX"],
        "applicable_timeframes": ["15M"],
        "applicable_regimes": ["TRENDING"],
        "confidence": "HIGH",
        "status": "VALIDATED"
    })
    assert item_id.startswith("kb-")
    
    retriever = ContextualKnowledgeRetriever(kb=kb)
    items = retriever.retrieve_relevant_knowledge("GBP/USD", regime="TRENDING", limit=2)
    assert len(items) >= 1
    assert any("GBP" in str(it.get("applicable_symbols")) for it in items)

def test_experience_memory_lifecycle(tmp_path):
    test_exp_path = str(tmp_path / "test_experience_data.json")
    exp = ExperienceMemory(storage_path=test_exp_path)
    rec = exp.record_signal_experience(
        signal_id="SIG-TEST-001",
        scan_id="scan-001",
        symbol="EUR/USD",
        direction="LONG",
        entry_price=1.1000,
        stop_loss=1.0980,
        take_profit=1.1040,
        ml_probability=0.72,
        composite_score=78.5,
        llm_reasoning="Strong momentum test",
        engine_evidence={}
    )
    assert rec["outcome_status"] == "ACTIVE_PENDING"

    exp.update_outcome_experience(
        signal_id="SIG-TEST-001",
        outcome_status="WIN_TP1",
        realized_r=2.0,
        mfe_r=2.1,
        mae_r=-0.3,
        holding_period_mins=45
    )

    updated = [r for r in exp.records if r["signal_id"] == "SIG-TEST-001"][0]
    assert updated["outcome_status"] == "WIN_TP1"
    assert updated["realized_r"] == 2.0

def test_outcome_tracker(tmp_path):
    import uuid
    test_outcomes_path = str(tmp_path / "test_outcomes_data.json")
    tracker = TradeOutcomeTracker(storage_path=test_outcomes_path)
    sig_id = f"SIG-TEST-{uuid.uuid4().hex[:8]}"
    active_trade = {
        "signal_id": sig_id,
        "symbol": "EUR/USD",
        "direction": "LONG",
        "entry_price": 1.1000,
        "stop_loss": 1.0980,
        "take_profit_1": 1.1040,
        "status": "OPEN",
        "mfe_r": 0.0,
        "mae_r": 0.0,
        "created_at": "2026-08-31T12:00:00Z"
    }
    tracker.active_signals = [active_trade]

    # Price hits TP
    resolved = tracker.process_price_update([], {"EUR/USD": 1.1045})
    assert len(resolved) == 1
    assert resolved[0]["status"] == "CLOSED"
    assert resolved[0]["outcome"] == "WIN_TP1"
