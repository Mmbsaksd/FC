import logging
from typing import Dict, List, Optional
from app.parallel.base_engine import BaseAnalysisEngine

logger = logging.getLogger(__name__)

class AnalysisEngineRegistry:
    """
    Central registry for managing, discovering, and executing parallel analysis engines.
    """
    def __init__(self):
        self._engines: Dict[str, BaseAnalysisEngine] = {}

    def register(self, engine: BaseAnalysisEngine) -> None:
        """Registers a new parallel analysis engine."""
        self._engines[engine.name] = engine
        logger.info(f"Registered parallel analysis engine: '{engine.name}' (enabled={engine.enabled})")

    def unregister(self, name: str) -> None:
        """Unregisters an engine by name."""
        if name in self._engines:
            del self._engines[name]

    def get_engine(self, name: str) -> Optional[BaseAnalysisEngine]:
        """Retrieves an engine by name."""
        return self._engines.get(name)

    def get_all_engines(self, enabled_only: bool = True) -> List[BaseAnalysisEngine]:
        """Returns all registered engines."""
        if enabled_only:
            return [eng for eng in self._engines.values() if eng.enabled]
        return list(self._engines.values())

    def enable_engine(self, name: str) -> bool:
        if name in self._engines:
            self._engines[name].enabled = True
            return True
        return False

    def disable_engine(self, name: str) -> bool:
        if name in self._engines:
            self._engines[name].enabled = False
            return True
        return False
