import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone

from app.parallel.base_engine import MarketSnapshot
from app.ml.feature_extractor import UnifiedFeatureExtractor
from app.ml.pretrained_models import PretrainedFoundationModelAdapter
from app.ml.meta_model import CentralOpportunityMetaModel
from app.ml.dataset_builder import TrainingDatasetBuilder
from app.ml.model_registry import ModelRegistry
from app.ml.retraining_pipeline import ModelRetrainingPipeline

def test_feature_extractor():
    extractor = UnifiedFeatureExtractor()
    
    # Mock candle DataFrame
    df = pd.DataFrame({
        "time": [f"2026-08-30T10:{i:02d}:00Z" for i in range(30)],
        "open": [1.1000 + i*0.0001 for i in range(30)],
        "high": [1.1005 + i*0.0001 for i in range(30)],
        "low": [1.0995 + i*0.0001 for i in range(30)],
        "close": [1.1002 + i*0.0001 for i in range(30)],
        "volume": [1000 + i*10 for i in range(30)]
    })

    snapshot = MarketSnapshot(
        timestamp=datetime.now(timezone.utc).isoformat(),
        symbol="EURUSD=X",
        symbol_name="EUR/USD",
        asset_class="FOREX",
        price=1.1030,
        bid=1.1029,
        ask=1.1031,
        spread_pips=2.0,
        timeframe="15M",
        candles=df,
        session="LONDON",
        pip_size=0.0001,
        base_currency="EUR",
        quote_currency="USD"
    )

    mock_engine_results = {
        "TechnicalAnalysis": {"score": 80.0, "direction": "LONG", "metrics": {"rsi": 58.0, "adx": 28.0}},
        "MarketStructure": {"score": 75.0, "direction": "LONG", "metrics": {"bos": "BULLISH_BOS"}},
        "CurrencyStrength": {"score": 70.0, "direction": "LONG", "metrics": {"strength_diff": 2.2}},
        "RiskMetrics": {"metrics": {"atr": 0.0020, "risk_reward": 2.5}}
    }

    features, vector = extractor.extract_features(snapshot, mock_engine_results)
    assert isinstance(features, dict)
    assert isinstance(vector, list)
    assert features["tech_rsi_14"] == 58.0
    assert features["tech_adx_is_trending"] == 1.0
    assert features["struct_is_bullish_bos"] == 1.0
    assert features["cs_is_strong_divergence"] == 1.0

def test_pretrained_adapter():
    adapter = PretrainedFoundationModelAdapter(enabled=True)
    df = pd.DataFrame({"close": np.linspace(1.1000, 1.1050, 30)})
    
    class MockSnap:
        candles = df

    res = adapter.extract_zero_shot_embeddings(MockSnap(), direction="LONG")
    assert "chronos_drift" in res
    assert "lag_llama_vol_density" in res
    assert "finbert_sentiment" in res
    assert res["finbert_sentiment"] == 0.25

def test_meta_model_inference():
    model = CentralOpportunityMetaModel()
    features = {
        "tech_score_norm": 0.85,
        "struct_score_norm": 0.80,
        "cs_strength_diff_zscore": 1.5,
        "candle_score_norm": 0.75,
        "regime_is_trending": 1.0,
        "macro_score_norm": 0.70,
        "time_is_london_ny_overlap": 1.0,
        "risk_spread_to_atr_ratio": 0.04
    }

    pred = model.predict_probability(features, direction="LONG")
    assert "win_probability" in pred
    assert 0.15 <= pred["win_probability"] <= 0.85
    assert pred["win_probability"] >= 0.55 # Strong features should yield positive win probability
    assert "brier_score" in pred
    assert pred["brier_score"] <= 0.20

def test_dataset_builder_and_labeling():
    builder = TrainingDatasetBuilder()
    
    sample = builder.create_training_example(
        snapshot_time="2026-08-30T12:00:00Z",
        symbol="EUR/USD",
        direction="LONG",
        features={"rsi": 55.0},
        entry_price=1.1000,
        stop_loss=1.0980,
        take_profit=1.1040,
        actual_outcome="WIN_TP1",
        realized_r=2.0
    )
    assert sample["label"] == 1
    assert sample["realized_r"] == 2.0

def test_model_registry_and_gates():
    reg = ModelRegistry()
    prod = reg.get_production_model()
    assert prod is not None
    assert prod["status"] == "PRODUCTION"

    pipeline = ModelRetrainingPipeline()
    res = pipeline.run_retraining_experiment()
    assert "candidate" in res
    assert "all_gates_passed" in res
