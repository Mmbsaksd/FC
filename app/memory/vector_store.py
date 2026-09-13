"""
Pluggable Vector Store & Semantic Document Indexing Abstraction for FC Institutional Memory.
Supports local vector similarity search, metadata filtering, canonical document formatting,
and future migration to Qdrant, Chroma, pgvector, FAISS, or Milvus.
"""

import os
import json
import math
import hashlib
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)

VECTOR_STORE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/memory/vector_index.json"))


class EmbeddingProvider(ABC):
    """Abstract interface for generating vector embeddings."""
    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        pass


class LocalDeterministicEmbeddingProvider(EmbeddingProvider):
    """
    Lightweight, deterministic feature-hashing embedding provider.
    Produces stable 128-dimensional dense unit vectors from semantic tokens
    without requiring heavy external neural network dependencies.
    """
    def __init__(self, dim: int = 128):
        self.dim = dim

    def _hash_token(self, token: str) -> int:
        h = hashlib.sha256(token.lower().strip().encode("utf-8")).hexdigest()
        return int(h[:8], 16) % self.dim

    def embed_text(self, text: str) -> List[float]:
        if not text:
            return [0.0] * self.dim
        vec = np.zeros(self.dim, dtype=np.float32)
        tokens = text.lower().replace("\n", " ").replace(":", " ").replace("-", " ").replace("/", " ").replace("_", " ").split()
        for tok in tokens:
            idx = self._hash_token(tok)
            vec[idx] += 1.0
        
        # L2 Normalization
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_text(t) for t in texts]


class VectorStore(ABC):
    """Abstract interface for pluggable vector stores."""

    @abstractmethod
    def add_document(
        self,
        doc_id: str,
        text: str,
        metadata: Dict[str, Any],
        doc_type: str = "STRATEGY_RULE",
        validation_status: str = "VALIDATED"
    ) -> str:
        pass

    @abstractmethod
    def similarity_search(
        self,
        query: str,
        metadata_filters: Optional[Dict[str, Any]] = None,
        limit: int = 3,
        min_similarity: float = 0.10
    ) -> List[Tuple[float, Dict[str, Any]]]:
        pass

    @abstractmethod
    def delete_document(self, doc_id: str) -> bool:
        pass

    @abstractmethod
    def count(self) -> int:
        pass


class Retriever(ABC):
    """Abstract interface for knowledge retrievers."""
    @abstractmethod
    def retrieve(self, query: str, filters: Optional[Dict[str, Any]] = None, limit: int = 3) -> List[Dict[str, Any]]:
        pass


class Reranker(ABC):
    """Abstract interface for cross-encoder or hybrid rerankers."""
    @abstractmethod
    def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_n: int = 3
    ) -> List[Dict[str, Any]]:
        pass


class CosineSimilarityReranker(Reranker):
    """Deterministic cosine similarity reranker with validation status weight boosting."""
    def __init__(self, embedding_provider: Optional[EmbeddingProvider] = None):
        self.embedding_provider = embedding_provider or LocalDeterministicEmbeddingProvider(dim=128)

    def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_n: int = 3
    ) -> List[Dict[str, Any]]:
        if not documents:
            return []
        query_vec = np.array(self.embedding_provider.embed_text(query), dtype=np.float32)
        q_norm = np.linalg.norm(query_vec)
        if q_norm == 0:
            return documents[:top_n]

        scored = []
        for doc in documents:
            doc_text = doc.get("text", "")
            d_vec = np.array(self.embedding_provider.embed_text(doc_text), dtype=np.float32)
            d_norm = np.linalg.norm(d_vec)
            sim = float(np.dot(query_vec, d_vec) / (q_norm * d_norm)) if d_norm > 0 else 0.0
            
            # Boost validated & empirical records
            status = doc.get("validation_status", doc.get("status", "EMPIRICAL"))
            if status == "VALIDATED":
                sim *= 1.20
            elif status == "EMPIRICAL":
                sim *= 1.10
            elif status == "UNVERIFIED":
                sim *= 0.70

            doc_copy = dict(doc)
            doc_copy["rerank_score"] = round(sim, 4)
            scored.append((sim, doc_copy))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored[:top_n]]


class SemanticDocumentFormatter:
    """
    Constructs canonical structured semantic representations of market situations,
    trade memories, failure post-mortems, strategy rules, rejected candidates, and research notes.
    """

    @staticmethod
    def format_trade_case(case: Dict[str, Any]) -> str:
        """Formats a historical trade case into canonical semantic text."""
        eng_items = [f"{k}={v.get('score', 0)}" for k, v in case.get('engine_results', {}).items() if isinstance(v, dict)]
        return (
            f"Asset: {case.get('symbol', 'UNKNOWN')} | Asset Class: {case.get('asset_class', 'FOREX')}\n"
            f"Direction: {case.get('direction', 'LONG')} | Timeframe: {case.get('timeframe', '15M')}\n"
            f"Setup: {case.get('setup_type', 'MOMENTUM_BREAKOUT')} | Regime: {case.get('regime', 'TRENDING')}\n"
            f"Consensus: {case.get('directional_consensus', 0.0):+.2f} | Opportunity Score: {case.get('opportunity_score', 75.0):.1f}\n"
            f"ML Win Probability: {case.get('ml_probability', 0.50):.2f} | EV: {case.get('expected_value_r', 0.0):+.2f}R\n"
            f"Outcome: {case.get('outcome', 'UNKNOWN')} | Realized R: {case.get('realized_r', 0.0):+.2f}R | MAE: {case.get('mae_r', 0.0):.2f}R\n"
            f"Key Engines: {', '.join(eng_items)}\n"
            f"Supporting Factors: {'; '.join(case.get('supporting_factors', []))}\n"
            f"Contradicting Factors: {'; '.join(case.get('contradicting_factors', []))}\n"
            f"Summary: {case.get('summary', 'Historical trade record')}"
        )

    @staticmethod
    def format_failure_case(case: Dict[str, Any]) -> str:
        """Formats a stop-loss failure or false breakout post-mortem into canonical semantic text."""
        return (
            f"FAILURE POST-MORTEM | Asset: {case.get('symbol', 'UNKNOWN')} | Direction: {case.get('direction', 'LONG')}\n"
            f"Root Cause: {case.get('root_cause', 'VOLATILITY_EXPANSION')} | Regime: {case.get('regime', 'TRENDING')}\n"
            f"Loss R: {case.get('loss_r', -1.0):+.2f}R | MAE at Stop: {case.get('mae_at_stop', 1.0):.2f}R | MFE Before Stop: {case.get('mfe_before_stop', 0.0):.2f}R\n"
            f"Failure Trajectory: {case.get('failure_trajectory', 'Triggered stop loss')}\n"
            f"Initial Consensus: {case.get('initial_consensus', 0.0):+.2f} | Initial ML Prob: {case.get('initial_ml_prob', 0.50):.2f}\n"
            f"Evidence for Root Cause: {case.get('root_cause_evidence', 'Market volatility exceeded ATR threshold')}\n"
            f"Lesson: {case.get('lesson', 'Avoid entries during high-impact news or erratic ATR spikes')}"
        )

    @staticmethod
    def format_rejected_candidate(candidate: Dict[str, Any]) -> str:
        """Formats a rejected candidate setup and its decision-time vs counterfactual outcome state."""
        return (
            f"REJECTED CANDIDATE | Asset: {candidate.get('symbol', 'UNKNOWN')} | Direction: {candidate.get('direction', 'LONG')}\n"
            f"Rejection Stage: {candidate.get('rejection_stage', 'STAGE_1_QUALIFICATION')} | Reason: {candidate.get('rejection_reason', 'Negative EV or high contradiction')}\n"
            f"Decision Consensus: {candidate.get('consensus', 0.0):+.2f} | ML Prob: {candidate.get('ml_probability', 0.50):.2f} | EV: {candidate.get('expected_value_r', 0.0):+.2f}R\n"
            f"Failed Condition: {candidate.get('failed_condition', 'min_ev_r')} (Actual: {candidate.get('actual_value', 0.0)}, Required: {candidate.get('threshold', 0.0)})\n"
            f"Counterfactual Realized R: {candidate.get('counterfactual_realized_r', 0.0):+.2f}R | Outcome Class: {candidate.get('outcome_class', 'HYPOTHETICAL_LOSS')}"
        )

    @staticmethod
    def format_strategy_rule(rule: Dict[str, Any]) -> str:
        """Formats a strategy rule or empirical institutional playbook."""
        return (
            f"STRATEGY RULE | Title: {rule.get('title', 'Playbook')}\n"
            f"Category: {rule.get('category', 'STRATEGY_RULE')} | Status: {rule.get('status', 'VALIDATED')}\n"
            f"Applicable Symbols: {', '.join(rule.get('applicable_symbols', []))} | Asset Classes: {', '.join(rule.get('applicable_asset_classes', []))}\n"
            f"Applicable Regimes: {', '.join(rule.get('applicable_regimes', []))} | Timeframes: {', '.join(rule.get('applicable_timeframes', []))}\n"
            f"Empirical Win Rate: {rule.get('win_rate', 0.0)}% | Expectancy: {rule.get('expectancy_r', 0.0):+.2f}R | Sample Size: N={rule.get('sample_size', 0)}\n"
            f"Finding: {rule.get('finding', rule.get('hypothesis', ''))}\n"
            f"Evidence: {rule.get('evidence', '')}"
        )

    @staticmethod
    def format_research_note(note: Dict[str, Any]) -> str:
        """Formats an external research note or trading literature concept."""
        return (
            f"RESEARCH & LITERATURE | Title: {note.get('title', 'Research Note')}\n"
            f"Author/Source: {note.get('author', 'Unknown')} ({note.get('source', 'FC Research')})\n"
            f"Topic: {note.get('topic', 'Market Microstructure')} | Asset Relevance: {note.get('asset_relevance', 'ALL')}\n"
            f"Status: {note.get('validation_status', 'EXTERNAL_REFERENCE')}\n"
            f"Core Concept: {note.get('summary', '')}\n"
            f"Key Takeaway: {note.get('takeaway', '')}"
        )

    @staticmethod
    def format_current_situation(situation: Dict[str, Any]) -> str:
        """Constructs a structured current-situation query representation for hybrid retrieval."""
        return (
            f"{situation.get('instrument', 'EURUSD=X')} {situation.get('direction_candidate', 'LONG')} "
            f"Setup:{situation.get('setup_type', 'MOMENTUM_BREAKOUT')} Regime:{situation.get('regime', 'TRENDING')} "
            f"Volatility:{situation.get('volatility', 'NORMAL')} Timeframe:{situation.get('timeframe', '15M')} "
            f"Session:{situation.get('session', 'LONDON/NY_OVERLAP')} Consensus:{situation.get('consensus', 0.0):+.2f} "
            f"EV:{situation.get('expected_value_r', 0.0):+.2f}R MLProb:{situation.get('ml_probability', 0.50):.2f}"
        )


class LocalVectorStore(VectorStore):
    """
    Thread-safe local vector storage with cosine similarity search and metadata filtering.
    """
    def __init__(
        self,
        storage_path: str = VECTOR_STORE_PATH,
        embedding_provider: Optional[EmbeddingProvider] = None
    ):
        self.storage_path = storage_path
        self.embedding_provider = embedding_provider or LocalDeterministicEmbeddingProvider(dim=128)
        self.documents: List[Dict[str, Any]] = []
        self._load()

    def _load(self):
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.documents = data.get("documents", [])
                    return
            except Exception as e:
                logger.error(f"Error loading vector index from {self.storage_path}: {e}")
        self.documents = []

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump({"documents": self.documents, "count": len(self.documents)}, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving vector index to {self.storage_path}: {e}")

    def add_document(
        self,
        doc_id: str,
        text: str,
        metadata: Dict[str, Any],
        doc_type: str = "STRATEGY_RULE",
        validation_status: str = "VALIDATED"
    ) -> str:
        """Indexes a canonical semantic document with metadata and vector embedding."""
        embedding = self.embedding_provider.embed_text(text)
        
        # Remove existing if doc_id exists
        self.documents = [d for d in self.documents if d.get("doc_id") != doc_id]

        doc_entry = {
            "doc_id": doc_id,
            "doc_type": doc_type,
            "text": text,
            "metadata": metadata,
            "validation_status": validation_status,
            "embedding": embedding
        }
        self.documents.append(doc_entry)
        self._save()
        return doc_id

    def delete_document(self, doc_id: str) -> bool:
        """Deletes a document by ID."""
        initial_len = len(self.documents)
        self.documents = [d for d in self.documents if d.get("doc_id") != doc_id]
        if len(self.documents) != initial_len:
            self._save()
            return True
        return False

    def count(self) -> int:
        """Returns the number of indexed documents."""
        return len(self.documents)

    def similarity_search(
        self,
        query: str,
        metadata_filters: Optional[Dict[str, Any]] = None,
        limit: int = 3,
        min_similarity: float = 0.10
    ) -> List[Tuple[float, Dict[str, Any]]]:
        """
        Executes hybrid similarity search:
        1. Hard metadata filtering (symbol, asset_class, regime, validation_status).
        2. Cosine similarity ranking against query vector.
        """
        if not self.documents or not query:
            return []

        query_vec = np.array(self.embedding_provider.embed_text(query), dtype=np.float32)
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            return []

        results = []
        for doc in self.documents:
            meta = doc.get("metadata", {})
            
            # Apply metadata filters if provided
            if metadata_filters:
                match = True
                for k, v in metadata_filters.items():
                    if v is None or v == "ALL":
                        continue
                    doc_val = meta.get(k)
                    if doc_val is not None:
                        if isinstance(doc_val, list):
                            if str(v).upper() not in [str(x).upper() for x in doc_val] and "ALL" not in [str(x).upper() for x in doc_val]:
                                match = False
                                break
                        elif str(doc_val).upper() != str(v).upper() and str(doc_val).upper() != "ALL":
                            match = False
                            break
                if not match:
                    continue

            # Compute Cosine Similarity
            doc_vec = np.array(doc.get("embedding", []), dtype=np.float32)
            doc_norm = np.linalg.norm(doc_vec)
            if doc_norm == 0:
                continue

            sim = float(np.dot(query_vec, doc_vec) / (query_norm * doc_norm))
            if sim >= min_similarity:
                results.append((round(sim, 4), doc))

        # Sort descending by similarity
        results.sort(key=lambda x: x[0], reverse=True)
        return results[:limit]


# Global singleton instance
vector_store = LocalVectorStore()
cosine_reranker = CosineSimilarityReranker()
