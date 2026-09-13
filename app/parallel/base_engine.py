from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod
from datetime import datetime, timezone

@dataclass
class MarketSnapshot:
    """
    Unified immutable market snapshot representing market state at a specific timestamp.
    """
    timestamp: str
    symbol: str
    symbol_name: str
    asset_class: str
    price: float
    bid: float
    ask: float
    spread_pips: float
    timeframe: str
    candles: Any  # pandas DataFrame of candles
    session: str
    pip_size: float
    base_currency: str
    quote_currency: str
    is_crypto: bool = False
    data_quality_status: str = "VALID"

@dataclass
class AnalysisResult:
    """
    Standardized result returned by every parallel analysis engine.
    """
    engine_name: str
    status: str  # "SUCCESS", "FAILED", "TIMED_OUT", "UNAVAILABLE"
    score: float  # 0.0 to 100.0
    direction: str  # "LONG", "SHORT", "NEUTRAL"
    confidence: float  # 0.0 to 1.0
    evidence: List[str] = field(default_factory=list)
    contradictions: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0
    error_message: Optional[str] = None

    @property
    def execution_time_ms(self) -> float:
        return self.latency_ms

class BaseAnalysisEngine(ABC):
    """
    Abstract Base Class for all parallel analysis engines.
    """
    def __init__(self, name: str, enabled: bool = True, timeout_seconds: float = 3.0):
        self.name = name
        self.enabled = enabled
        self.timeout_seconds = timeout_seconds

    @abstractmethod
    def analyze(self, snapshot: MarketSnapshot) -> AnalysisResult:
        """
        Executes analysis on the provided market snapshot.
        Must return an AnalysisResult instance.
        """
        pass
