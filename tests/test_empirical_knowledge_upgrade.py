import pytest
from datetime import datetime, timezone, timedelta
from app.memory.knowledge_base import EmpiricalKnowledgeBase
from app.memory.knowledge_discovery import KnowledgeDiscoveryEngine
from app.memory.knowledge_retriever import ContextualKnowledgeRetriever
from app.memory.experience_memory import ExperienceMemory
from fastapi.testclient import TestClient
from app.api.server import app

client = TestClient(app)

@pytest.fixture
def isolated_kb(tmp_path):
    storage = str(tmp_path / "isolated_kb.json")
    return EmpiricalKnowledgeBase(storage_path=storage)

def test_schema_validation_and_versioning(isolated_kb):
    item_id = isolated_kb.add_knowledge_item({
        "title": "Gold ADX Compression Trap",
        "category": "FAILURE_ANALYSIS",
        "finding": "Gold breakouts below ADX 18 have high failure rate",
        "applicable_symbols": ["XAU/USD"],
        "applicable_asset_classes": ["COMMODITIES"],
        "applicable_timeframes": ["15M"],
        "applicable_regimes": ["CHOPPY", "RANGING"],
        "sample_size": 30,
        "success_count": 9,
        "failure_count": 21,
        "win_rate": 30.0,
        "expectancy_r": -0.45,
        "status": "HYPOTHESIS"
    })
    
    item = isolated_kb.get_item_detail(item_id)
    assert item is not None
    assert item["version"] == "1.0.0"
    assert item["applicable_asset_classes"] == ["COMMODITIES"]
    assert item["applicable_timeframes"] == ["15M"]
    assert len(item["version_history"]) == 1
    assert item["freshness_score"] == 1.0

    # Promote to EXPERIMENTAL
    isolated_kb.update_item_status(item_id, "EXPERIMENTAL", "Promoted to experimental test phase")
    updated = isolated_kb.get_item_detail(item_id)
    assert updated["status"] == "EXPERIMENTAL"
    assert updated["version"] == "1.1.0"
    assert len(updated["version_history"]) == 2
    assert "EXPERIMENTAL" in updated["version_history"][0]["status"]

def test_automated_discovery_cluster_mining(isolated_kb):
    discovery_engine = KnowledgeDiscoveryEngine(kb=isolated_kb)

    # Mock 8 choppy trades with high loss rate
    mock_experiences = []
    for i in range(8):
        mock_experiences.append({
            "experience_id": f"exp-{i}",
            "symbol": "XAU/USD",
            "direction": "LONG",
            "outcome_status": "LOSS_SL" if i < 6 else "WIN_TP1",
            "realized_r": -1.0 if i < 6 else 2.0,
            "engine_evidence": {
                "MarketRegime": {"metrics": {"regime": "CHOPPY"}}
            },
            "created_at": datetime.now(timezone.utc).isoformat()
        })

    res = discovery_engine.run_discovery_scan(experiences=mock_experiences)
    assert res["status"] == "SUCCESS"
    assert res["candidates_discovered_count"] >= 1
    assert len(res["new_hypotheses_added"]) >= 1

    # Verify newly added hypothesis exists in KB
    new_hypo_id = res["new_hypotheses_added"][0]
    hypo_item = isolated_kb.get_item_detail(new_hypo_id)
    assert hypo_item["status"] == "HYPOTHESIS"
    assert hypo_item["sample_size"] == 8
    assert hypo_item["failure_count"] == 6

def test_sample_size_promotion_gates(isolated_kb):
    discovery_engine = KnowledgeDiscoveryEngine(kb=isolated_kb)
    
    # 1. Create a candidate rule with sample N=10 (remains HYPOTHESIS)
    item_id = isolated_kb.add_knowledge_item({
        "title": "Currency Divergence Surge",
        "category": "STRATEGY_RULE",
        "finding": "Strong CS diff yields high win rate",
        "sample_size": 10,
        "win_rate": 70.0,
        "expectancy_r": 0.85,
        "status": "HYPOTHESIS"
    })
    
    gates_res = discovery_engine.evaluate_promotion_gates()
    assert gates_res["promoted_to_experimental"] == 0
    assert isolated_kb.get_item_detail(item_id)["status"] == "HYPOTHESIS"

    # 2. Increase sample size to N=14 (Passes Gate 1: HYPOTHESIS -> EXPERIMENTAL)
    isolated_kb.get_item_detail(item_id)["sample_size"] = 14
    gates_res_2 = discovery_engine.evaluate_promotion_gates()
    assert gates_res_2["promoted_to_experimental"] == 1
    assert isolated_kb.get_item_detail(item_id)["status"] == "EXPERIMENTAL"

    # 3. Increase sample size to N=28 (Passes Gate 2: EXPERIMENTAL -> VALIDATED)
    isolated_kb.get_item_detail(item_id)["sample_size"] = 28
    gates_res_3 = discovery_engine.evaluate_promotion_gates()
    assert gates_res_3["promoted_to_validated"] == 1
    assert isolated_kb.get_item_detail(item_id)["status"] == "VALIDATED"

def test_unvalidated_hypotheses_excluded_from_retrieval(isolated_kb):
    retriever = ContextualKnowledgeRetriever(kb=isolated_kb)

    # Add a hypothesis
    isolated_kb.add_knowledge_item({
        "title": "Unvalidated Test Hypothesis",
        "category": "STRATEGY_RULE",
        "finding": "Unproven idea",
        "applicable_symbols": ["EUR/USD"],
        "status": "HYPOTHESIS"
    })

    # Add a validated rule
    isolated_kb.add_knowledge_item({
        "title": "Validated London Breakout Rule",
        "category": "STRATEGY_RULE",
        "finding": "Proven rule",
        "applicable_symbols": ["EUR/USD"],
        "status": "VALIDATED"
    })

    # Live retrieval should ONLY return VALIDATED items
    retrieved = retriever.retrieve_relevant_knowledge("EUR/USD", regime="NORMAL")
    assert len(retrieved) == 1
    assert retrieved[0]["status"] == "VALIDATED"
    assert retrieved[0]["title"] == "Validated London Breakout Rule"
    assert "retrieval_reason" in retrieved[0]

def test_contextual_retriever_multi_dimensional_matching(isolated_kb):
    retriever = ContextualKnowledgeRetriever(kb=isolated_kb)

    isolated_kb.add_knowledge_item({
        "title": "Forex EUR/USD 15M Trending Rule",
        "category": "STRATEGY_RULE",
        "finding": "EUR/USD 15M specific momentum continuation",
        "applicable_symbols": ["EUR/USD"],
        "applicable_asset_classes": ["FOREX"],
        "applicable_timeframes": ["15M"],
        "applicable_regimes": ["TRENDING"],
        "status": "VALIDATED",
        "sample_size": 50,
        "freshness_score": 1.0
    })

    isolated_kb.add_knowledge_item({
        "title": "Crypto BTC 4H Macro Rule",
        "category": "STRATEGY_RULE",
        "finding": "BTC 4H halving momentum",
        "applicable_symbols": ["BTC-USD"],
        "applicable_asset_classes": ["CRYPTO"],
        "applicable_timeframes": ["4H"],
        "applicable_regimes": ["HIGH_VOLATILITY"],
        "status": "VALIDATED",
        "sample_size": 40,
        "freshness_score": 1.0
    })

    # Match EUR/USD 15M Forex
    res_fx = retriever.retrieve_relevant_knowledge(
        symbol="EUR/USD",
        regime="TRENDING",
        timeframe="15M",
        asset_class="FOREX"
    )
    assert len(res_fx) == 1
    assert res_fx[0]["title"] == "Forex EUR/USD 15M Trending Rule"
    assert "Exact symbol (EUR/USD)" in res_fx[0]["retrieval_reason"]

    # Match BTC 4H Crypto
    res_crypto = retriever.retrieve_relevant_knowledge(
        symbol="BTC-USD",
        regime="HIGH_VOLATILITY",
        timeframe="4H",
        asset_class="CRYPTO"
    )
    assert len(res_crypto) == 1
    assert res_crypto[0]["title"] == "Crypto BTC 4H Macro Rule"
    assert "Asset class (CRYPTO)" in res_crypto[0]["retrieval_reason"]

def test_usage_and_outcome_attribution_tracking(isolated_kb):
    item_id = isolated_kb.add_knowledge_item({
        "title": "London NY Overlap FVG Retest",
        "category": "STRATEGY_RULE",
        "finding": "81% continuation probability",
        "status": "VALIDATED"
    })

    # 1. Record Usage on signal creation
    isolated_kb.record_knowledge_usage(
        item_id=item_id,
        signal_id="SIG-ATTRIB-001",
        symbol="EUR/USD",
        regime="NORMAL",
        timeframe="15M"
    )
    item = isolated_kb.get_item_detail(item_id)
    assert item["usage_stats"]["times_applied"] == 1
    assert "SIG-ATTRIB-001" in item["usage_stats"]["signals_attributed"]

    # 2. Record Outcome when trade resolves (WIN)
    isolated_kb.record_knowledge_outcome(
        signal_id="SIG-ATTRIB-001",
        outcome="WIN_TP1",
        realized_r=2.0
    )
    updated = isolated_kb.get_item_detail(item_id)
    assert updated["usage_stats"]["attributed_wins"] == 1
    assert updated["usage_stats"]["attributed_losses"] == 0
    assert updated["usage_stats"]["attributed_win_rate"] == 100.0
    assert updated["usage_stats"]["attributed_avg_r"] == 2.0

def test_time_decay_freshness_scoring(isolated_kb):
    # Add an old rule unconfirmed for 90 days
    old_time = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
    item_id = isolated_kb.add_knowledge_item({
        "title": "Aged Macro Hypothesis",
        "category": "MACRO_RELATIONSHIP",
        "finding": "Old correlation",
        "status": "VALIDATED",
        "last_confirmed_at": old_time,
        "last_reviewed_at": old_time
    })

    decay_res = isolated_kb.evaluate_freshness_and_decay(half_life_days=45.0)
    assert decay_res["total_evaluated"] >= 1
    
    item = isolated_kb.get_item_detail(item_id)
    # 90 days elapsed on 45-day half-life -> freshness ~ 0.25 < 0.35 threshold
    assert item["freshness_score"] < 0.35
    assert item["status"] == "REQUIRES_REVIEW"
    assert "Automatic decay" in item["version_history"][0]["reason"]

def test_a_b_attribution_analytics(isolated_kb):
    isolated_kb.add_knowledge_item({
        "title": "Attributed Rule A",
        "category": "STRATEGY_RULE",
        "status": "VALIDATED",
        "usage_stats": {
            "times_retrieved": 10,
            "times_applied": 5,
            "signals_attributed": ["SIG-1", "SIG-2", "SIG-3", "SIG-4", "SIG-5"],
            "attributed_wins": 4,
            "attributed_losses": 1,
            "attributed_win_rate": 80.0,
            "attributed_avg_r": 1.6
        }
    })

    analytics = isolated_kb.get_attribution_analytics()
    assert analytics["total_knowledge_items"] == 1
    assert analytics["knowledge_attributed_win_rate"] == 80.0
    assert analytics["baseline_win_rate"] == 58.2
    assert analytics["edge_delta_win_rate"] == 21.8
    assert analytics["edge_delta_r"] == 0.45

def test_rest_api_knowledge_endpoints():
    # 1. GET /api/knowledge
    res = client.get("/api/knowledge?status=VALIDATED")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert data["count"] >= 1

    # 2. GET /api/knowledge/analytics
    res_a = client.get("/api/knowledge/analytics")
    assert res_a.status_code == 200
    analytics = res_a.json()
    assert "knowledge_attributed_win_rate" in analytics
    assert "baseline_win_rate" in analytics

    # 3. POST /api/knowledge/recalculate
    res_r = client.post("/api/knowledge/recalculate")
    assert res_r.status_code == 200
    assert res_r.json()["status"] == "SUCCESS"

    # 4. GET /api/knowledge/item/{item_id}
    first_id = data["items"][0]["item_id"]
    res_detail = client.get(f"/api/knowledge/item/{first_id}")
    assert res_detail.status_code == 200
    assert res_detail.json()["item"]["item_id"] == first_id
