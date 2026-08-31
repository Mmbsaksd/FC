import pytest
import pandas as pd
from datetime import datetime, timezone
from app.parallel.base_engine import MarketSnapshot
from app.vision.visual_verifier import VisualMarketVerifier

def test_visual_verifier():
    verifier = VisualMarketVerifier(enabled=True)
    df = pd.DataFrame({
        "time": [f"2026-08-30T10:{i:02d}:00Z" for i in range(25)],
        "open": [1.1000 + i*0.0001 for i in range(25)],
        "high": [1.1005 + i*0.0001 for i in range(25)],
        "low": [1.0995 + i*0.0001 for i in range(25)],
        "close": [1.1002 + i*0.0001 for i in range(25)],
        "volume": [1000 for _ in range(25)]
    })

    snap = MarketSnapshot(
        timestamp=datetime.now(timezone.utc).isoformat(),
        symbol="EURUSD=X",
        symbol_name="EUR/USD",
        asset_class="FOREX",
        price=1.1026,
        bid=1.1025,
        ask=1.1027,
        spread_pips=2.0,
        timeframe="15M",
        candles=df,
        session="LONDON",
        pip_size=0.0001,
        base_currency="EUR",
        quote_currency="USD"
    )

    chart = verifier.generate_chart_payload(snap, "LONG", 1.1026, 1.1000, 1.1060)
    assert "candles" in chart
    assert len(chart["candles"]) == 25
    assert "key_levels" in chart

    verif = verifier.verify_candidate_setup(snap, "LONG", 1.1026, 1.1000, 1.1060)
    assert verif["status"] in ["CONFIRMED", "AMBIGUOUS"]
    assert verif["confidence"] >= 0.50
