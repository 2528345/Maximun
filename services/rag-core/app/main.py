from __future__ import annotations

import hashlib
import json
import os
import re
import signal
import threading
import time
from collections import OrderedDict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Deque, Dict, Iterable, List

import paho.mqtt.client as mqtt

try:
    import chromadb
    from chromadb.config import Settings

    CHROMA_AVAILABLE = True
except ImportError:
    chromadb = None
    Settings = None
    CHROMA_AVAILABLE = False

try:
    from chromadb.utils import embedding_functions

    CHROMA_EMBED_FN_AVAILABLE = True
except ImportError:
    embedding_functions = None
    CHROMA_EMBED_FN_AVAILABLE = False

try:
    from pypdf import PdfReader

    PDF_AVAILABLE = True
except ImportError:
    PdfReader = None
    PDF_AVAILABLE = False

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    np = None
    NUMPY_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer

    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SentenceTransformer = None
    SENTENCE_TRANSFORMERS_AVAILABLE = False

try:
    from .self_protection import ThreatDetector as AdvancedThreatDetector

    ADVANCED_THREAT_DETECTOR_AVAILABLE = True
except Exception:
    AdvancedThreatDetector = None
    ADVANCED_THREAT_DETECTOR_AVAILABLE = False


class CircuitBreakerOpenException(RuntimeError):
    pass


class CircuitBreaker:
    def __init__(self, failure_threshold: int, timeout_duration: float, name: str) -> None:
        self.failure_threshold = max(1, failure_threshold)
        self.timeout_duration = max(1.0, timeout_duration)
        self.name = name

        self.lock = threading.Lock()
        self.failures = 0
        self.open_until = 0.0

    def call(self, func: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with self.lock:
                now = time.time()
                if self.open_until > now:
                    raise CircuitBreakerOpenException(
                        f"Circuit {self.name} open for {self.open_until - now:.1f}s"
                    )

            try:
                output = func(*args, **kwargs)
            except Exception:
                with self.lock:
                    self.failures += 1
                    if self.failures >= self.failure_threshold:
                        self.open_until = time.time() + self.timeout_duration
                raise

            with self.lock:
                self.failures = 0
                self.open_until = 0.0
            return output

        return wrapper

    def get_stats(self) -> Dict[str, Any]:
        with self.lock:
            now = time.time()
            return {
                "name": self.name,
                "failure_threshold": self.failure_threshold,
                "failures": self.failures,
                "is_open": self.open_until > now,
                "remaining_open_sec": max(0.0, self.open_until - now),
            }


class StructuredLogger:
    def __init__(self, logs_path: Path) -> None:
        self.logs_path = logs_path
        self.logs_path.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()

    def log_interaction(
        self,
        interaction_id: str,
        user_id: str,
        query: str,
        results: List[Dict[str, Any]],
        processing_time: float,
        from_cache: bool = False,
        optimizations: List[str] | None = None,
    ) -> None:
        payload = {
            "type": "interaction",
            "timestamp": _utc_now_iso(),
            "interaction_id": interaction_id,
            "user_id": user_id,
            "query": query,
            "result_count": len(results),
            "processing_time": round(processing_time, 6),
            "from_cache": from_cache,
            "optimizations": optimizations or [],
        }
        self._append("interactions.jsonl", payload)

    def log_feedback(
        self,
        interaction_id: str,
        feedback_type: str,
        feedback_value: float,
        user_id: str,
    ) -> None:
        payload = {
            "type": "feedback",
            "timestamp": _utc_now_iso(),
            "interaction_id": interaction_id,
            "feedback_type": feedback_type,
            "feedback_value": float(feedback_value),
            "user_id": user_id,
        }
        self._append("feedback.jsonl", payload)

    def _append(self, file_name: str, payload: Dict[str, Any]) -> None:
        line = json.dumps(payload, ensure_ascii=True)
        with self.lock:
            (self.logs_path / file_name).open("a", encoding="utf-8").write(line + "\n")


class ThreatDetector:
    def __init__(self) -> None:
        self.high_patterns = [
            re.compile(r"\brm\s+-rf\b", re.IGNORECASE),
            re.compile(r"\bmkfs\b", re.IGNORECASE),
            re.compile(r"<\s*script", re.IGNORECASE),
            re.compile(r"\bdrop\s+table\b", re.IGNORECASE),
            re.compile(r"\bwget\s+\S+\s*\|\s*sh\b", re.IGNORECASE),
        ]
        self.medium_patterns = [
            re.compile(r"\bpassword\b", re.IGNORECASE),
            re.compile(r"\btoken\b", re.IGNORECASE),
            re.compile(r"\bprivate key\b", re.IGNORECASE),
            re.compile(r"\bapi[_-]?key\b", re.IGNORECASE),
        ]
        self.stats = {"high": 0, "medium": 0, "clean": 0}

    def analyze_content(self, content: str, metadata: Dict[str, Any]) -> Dict[str, str]:
        text = f"{metadata} {content[:8000]}"
        return self._analyze_text(text)

    def analyze_query(self, query_text: str) -> Dict[str, str]:
        return self._analyze_text(query_text)

    def get_stats(self) -> Dict[str, int]:
        return dict(self.stats)

    def _analyze_text(self, text: str) -> Dict[str, str]:
        for pattern in self.high_patterns:
            if pattern.search(text):
                self.stats["high"] += 1
                return {"threat_level": "high", "threat_type": pattern.pattern}

        for pattern in self.medium_patterns:
            if pattern.search(text):
                self.stats["medium"] += 1
                return {"threat_level": "medium", "threat_type": pattern.pattern}

        self.stats["clean"] += 1
        return {"threat_level": "low", "threat_type": "none"}


class LightweightRLAgent:
    def __init__(self, models_path: Path) -> None:
        self.models_path = models_path
        self.models_path.mkdir(parents=True, exist_ok=True)
        self.state_file = self.models_path / "rl_state.json"

        self.lock = threading.Lock()
        self.doc_scores: Dict[str, float] = {}
        self.interaction_docs: Dict[str, List[str]] = {}
        self.feedback_events = 0

    def load_state(self) -> None:
        if not self.state_file.exists():
            return
        try:
            raw = json.loads(self.state_file.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                score_map = raw.get("doc_scores", {})
                if isinstance(score_map, dict):
                    self.doc_scores = {
                        str(k): float(v)
                        for k, v in score_map.items()
                        if isinstance(k, str) and isinstance(v, (int, float))
                    }
                self.feedback_events = int(raw.get("feedback_events", 0))
        except Exception:
            pass

    def save_state(self) -> None:
        payload = {
            "doc_scores": self.doc_scores,
            "feedback_events": self.feedback_events,
            "saved_at": _utc_now_iso(),
        }
        self.state_file.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    def register_interaction(self, interaction_id: str, doc_hashes: Iterable[str]) -> None:
        clean = [h for h in doc_hashes if h]
        if not clean:
            return
        with self.lock:
            self.interaction_docs[interaction_id] = clean[:50]
            if len(self.interaction_docs) > 1000:
                first = next(iter(self.interaction_docs))
                self.interaction_docs.pop(first, None)

    def update_from_feedback(
        self,
        interaction_id: str,
        feedback_value: float,
        feedback_type: str,
    ) -> None:
        val = max(-1.0, min(1.0, float(feedback_value)))
        with self.lock:
            docs = self.interaction_docs.get(interaction_id, [])
            for doc_hash in docs:
                old = float(self.doc_scores.get(doc_hash, 0.0))
                new_score = max(-1.5, min(1.5, old * 0.85 + val * 0.15))
                self.doc_scores[doc_hash] = new_score

            if len(self.doc_scores) > 20000:
                keys = list(self.doc_scores.keys())[:5000]
                for key in keys:
                    self.doc_scores.pop(key, None)

            self.feedback_events += 1

        if feedback_type in {"explicit", "implicit"}:
            self.save_state()

    def get_document_feedback_score(self, doc_hash: str) -> float:
        return float(self.doc_scores.get(doc_hash, 0.0))

    def get_optimized_params(self, query_text: str, context: Dict[str, Any] | None) -> Dict[str, Any]:
        text_len = len(query_text.strip())
        if text_len < 80:
            top_k_hint = 3
        elif text_len < 220:
            top_k_hint = 4
        else:
            top_k_hint = 5

        filters = None
        if isinstance(context, dict):
            source = context.get("source")
            if isinstance(source, str) and source.strip():
                filters = {"source": source.strip()}

        return {
            "filters": filters,
            "top_k_hint": top_k_hint,
            "optimizations": ["query_length_hint"],
        }

    def get_stats(self) -> Dict[str, Any]:
        return {
            "doc_scores": len(self.doc_scores),
            "tracked_interactions": len(self.interaction_docs),
            "feedback_events": self.feedback_events,
        }


class PredictiveScaler:
    def __init__(self) -> None:
        self.latencies: Deque[float] = deque(maxlen=120)

    def record_latency(self, value_sec: float) -> None:
        if value_sec <= 0:
            return
        self.latencies.append(float(value_sec))

    def recommend_top_k(self, base_top_k: int) -> int:
        top_k = max(1, min(12, int(base_top_k)))
        if not self.latencies:
            return top_k

        avg = sum(self.latencies) / len(self.latencies)
        if avg > 1.8:
            return max(2, top_k - 1)
        if avg < 0.7:
            return min(8, top_k + 1)
        return top_k

    def get_stats(self) -> Dict[str, Any]:
        if not self.latencies:
            return {"samples": 0, "avg_latency_sec": 0.0}
        avg = sum(self.latencies) / len(self.latencies)
        return {"samples": len(self.latencies), "avg_latency_sec": round(avg, 4)}


class IntelligentWebScraper:
    def __init__(self, cache_path: Path, enabled: bool = False) -> None:
        self.cache_path = cache_path
        self.cache_path.mkdir(parents=True, exist_ok=True)
        self.enabled = enabled

    def scrape_url(self, url: str) -> Dict[str, Any]:
        if not self.enabled:
            return {"success": False, "error": "web_scraping_disabled"}
        return {"success": False, "error": "not_implemented_offline_first", "url": url}

    def get_stats(self) -> Dict[str, Any]:
        return {"enabled": self.enabled, "cache_path": str(self.cache_path)}


class IntelligentRAGDatabase:
    def __init__(self) -> None:
        self.storage_root = Path(os.getenv("RAG_STORAGE_ROOT", "/rag_store"))
        self.vector_db_path = Path(os.getenv("RAG_CHROMA_PATH", str(self.storage_root / "chroma")))
        self.docs_path = Path(os.getenv("RAG_DOCS_PATH", str(self.storage_root / "docs")))
        self.logs_path = Path(os.getenv("RAG_LOGS_PATH", str(self.storage_root / "logs")))
        self.models_path = Path(os.getenv("RAG_MODELS_PATH", str(self.storage_root / "models")))
        self.ram_cache_path = Path(os.getenv("RAG_RAM_CACHE_PATH", "/dev/shm/maximun_rag_cache"))

        self.collection_name = os.getenv("RAG_COLLECTION", "maximun_memory")
        self.default_top_k = int(os.getenv("RAG_TOP_K", "4"))
        self.max_doc_chars = int(os.getenv("RAG_MAX_DOC_CHARS", "6000"))
        self.chunk_size_words = int(os.getenv("RAG_CHUNK_SIZE_WORDS", "220"))
        self.chunk_overlap_words = int(os.getenv("RAG_CHUNK_OVERLAP_WORDS", "50"))
        self.auto_ingest_on_boot = _env_bool("RAG_AUTO_INGEST_ON_BOOT", True)
        self.query_cache_max = int(os.getenv("RAG_QUERY_CACHE_MAX", "120"))
        self.query_cache_ttl_sec = int(os.getenv("RAG_QUERY_CACHE_TTL_SEC", "900"))
        self.max_file_mb = int(os.getenv("RAG_MAX_FILE_MB", "30"))

        self.requested_backend = os.getenv("RAG_EMBED_BACKEND", "hash").strip().lower()
        self.embedding_model_name = os.getenv("RAG_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        self.hash_embedding_dim = int(os.getenv("RAG_HASH_EMBED_DIM", "384"))

        allowed_exts = os.getenv("RAG_ALLOWED_EXTENSIONS", "pdf,md,markdown,txt,rst")
        self.allowed_extensions = {
            f".{x.strip().lower().lstrip('.')}" for x in allowed_exts.split(",") if x.strip()
        }

        for path in [
            self.storage_root,
            self.vector_db_path,
            self.docs_path,
            self.logs_path,
            self.models_path,
            self.ram_cache_path,
        ]:
            path.mkdir(parents=True, exist_ok=True)

        self.chroma_client: Any | None = None
        self.collection: Any | None = None
        self.collection_lock = threading.Lock()

        self.logger = StructuredLogger(self.logs_path)
        self.rl_agent = LightweightRLAgent(self.models_path)
        self.threat_detector = self._create_threat_detector()
        self.web_scraper = IntelligentWebScraper(
            self.storage_root / "web_cache",
            enabled=_env_bool("RAG_ENABLE_WEB_SCRAPING", False),
        )
        self.scaler = PredictiveScaler()

        self.chroma_cb = CircuitBreaker(5, 30.0, "chroma")
        self.embedding_cb = CircuitBreaker(3, 60.0, "embedding")

        self.embed_backend = "hash"
        self.embedding_model: Any | None = None
        self.default_embedding_fn: Any | None = None

        self.processed_manifest = self.logs_path / "processed_docs.jsonl"
        self.processed_documents: set[str] = set()
        self.query_cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self.query_cache_disk_dir = self.ram_cache_path / "query_cache"
        self.query_cache_disk_dir.mkdir(parents=True, exist_ok=True)

        self._load_processed_manifest()
        self.rl_agent.load_state()

        self._resolve_embedding_backend()
        self._init_collection()

        if self.auto_ingest_on_boot:
            self.ingest_path(str(self.docs_path), recursive=True)

    def _create_threat_detector(self) -> Any:
        if ADVANCED_THREAT_DETECTOR_AVAILABLE and AdvancedThreatDetector is not None:
            try:
                secure_root = self.storage_root / "security"
                return AdvancedThreatDetector(storage_path=secure_root)
            except Exception:
                pass
        return ThreatDetector()

    def _resolve_embedding_backend(self) -> None:
        requested = self.requested_backend

        if requested in {"sentence", "auto"} and SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                local_only = _env_bool("RAG_EMBEDDING_LOCAL_ONLY", True)
                self.embedding_model = SentenceTransformer(
                    self.embedding_model_name,
                    local_files_only=local_only,
                )
                self.embed_backend = "sentence"
                return
            except Exception:
                self.embedding_model = None

        if requested in {"default", "auto"} and CHROMA_EMBED_FN_AVAILABLE:
            try:
                self.default_embedding_fn = embedding_functions.DefaultEmbeddingFunction()
                self.embed_backend = "default"
                return
            except Exception:
                self.default_embedding_fn = None

        self.embed_backend = "hash"

    def _init_collection(self) -> None:
        if not CHROMA_AVAILABLE:
            return

        @self.chroma_cb.call
        def _init() -> None:
            self.vector_db_path.mkdir(parents=True, exist_ok=True)
            self.chroma_client = chromadb.PersistentClient(
                path=str(self.vector_db_path),
                settings=Settings(anonymized_telemetry=False, allow_reset=True),
            )
            self.collection = self.chroma_client.get_or_create_collection(
                name=self.collection_name,
                metadata={
                    "description": "MAXIMUN RAG Intelligent",
                    "embedding_backend": self.embed_backend,
                },
            )

        try:
            _init()
        except CircuitBreakerOpenException:
            pass

    def add_document(self, content: str, metadata: Dict[str, Any], source: str = "manual") -> bool:
        content = str(content or "").strip()
        if not content:
            return False

        threat = self.threat_detector.analyze_content(content, metadata)
        if threat["threat_level"] == "high":
            return False

        doc_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if doc_hash in self.processed_documents:
            return True

        chunks = self._chunk_text(content)
        if not chunks:
            return False

        chunk_texts = [chunk["text"] for chunk in chunks]
        chunk_embeddings = self._embed_texts(chunk_texts)

        ids: List[str] = []
        docs: List[str] = []
        metas: List[Dict[str, Any]] = []
        for idx, chunk in enumerate(chunks):
            ids.append(f"{doc_hash}_{idx}")
            docs.append(chunk["text"])
            metas.append(
                {
                    **metadata,
                    "doc_hash": doc_hash,
                    "chunk_index": idx,
                    "chunk_start": chunk["start"],
                    "chunk_end": chunk["end"],
                    "source": source,
                    "indexed_at": int(time.time()),
                }
            )

        if self.collection is None:
            return False

        try:
            @self.chroma_cb.call
            def _upsert() -> None:
                with self.collection_lock:
                    self.collection.upsert(
                        ids=ids,
                        documents=docs,
                        metadatas=metas,
                        embeddings=chunk_embeddings,
                    )

            _upsert()
        except Exception:
            return False

        self.processed_documents.add(doc_hash)
        self._append_processed_manifest(doc_hash, metadata.get("path", ""))
        return True

    def upsert_documents(self, payload: Dict[str, Any], source: str = "manual") -> Dict[str, Any]:
        items = self._normalize_documents_payload(payload)
        if not items:
            return {
                "status": "ignored",
                "reason": "empty_payload",
                "upserted": 0,
                "failed": 0,
                "timestamp": int(time.time()),
            }

        upserted = 0
        failed = 0
        for item in items:
            path_raw = str(item.get("path", "")).strip()
            if path_raw:
                text = self._extract_text_from_file(Path(path_raw))
                if not text:
                    failed += 1
                    continue
                metadata = item.get("metadata", {})
                if not isinstance(metadata, dict):
                    metadata = {}
                metadata.update({"path": path_raw, "title": Path(path_raw).name})
                if self.add_document(text, metadata=metadata, source="filesystem"):
                    upserted += 1
                else:
                    failed += 1
                continue

            text = str(item.get("text", "")).strip()
            metadata = item.get("metadata", {})
            if not isinstance(metadata, dict):
                metadata = {}
            if self.add_document(text, metadata=metadata, source=source):
                upserted += 1
            else:
                failed += 1

        total = self.collection.count() if self.collection is not None else 0
        return {
            "status": "upserted" if upserted > 0 else "failed",
            "upserted": upserted,
            "failed": failed,
            "total": int(total),
            "timestamp": int(time.time()),
        }

    def query(
        self,
        query_text: str,
        n_results: int = 5,
        user_id: str = "anonymous",
        request_id: str | None = None,
        context: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        started = time.time()
        request_id = request_id or f"rag-{int(started * 1000)}"
        query_text = str(query_text or "").strip()

        if not query_text:
            return {
                "request_id": request_id,
                "query": query_text,
                "results": [],
                "status": "empty_query",
                "timestamp": int(time.time()),
            }

        threat = self.threat_detector.analyze_query(query_text)
        if threat["threat_level"] == "high":
            return {
                "request_id": request_id,
                "query": query_text,
                "results": [],
                "status": "blocked",
                "error": "query_blocked_by_security",
                "timestamp": int(time.time()),
            }

        cache_key = hashlib.sha256(f"{query_text}|{n_results}".encode("utf-8")).hexdigest()
        if cache_key in self.query_cache:
            cached = dict(self.query_cache[cache_key])
            cached["from_cache"] = True
            self.logger.log_interaction(
                interaction_id=str(cached.get("interaction_id", request_id)),
                user_id=user_id,
                query=query_text,
                results=cached.get("results", []),
                from_cache=True,
                processing_time=time.time() - started,
                optimizations=cached.get("optimizations_applied", []),
            )
            return cached
        disk_cached = self._cache_get_disk(cache_key)
        if disk_cached is not None:
            disk_cached["from_cache"] = True
            self._cache_set(cache_key, disk_cached)
            self.logger.log_interaction(
                interaction_id=str(disk_cached.get("interaction_id", request_id)),
                user_id=user_id,
                query=query_text,
                results=disk_cached.get("results", []),
                from_cache=True,
                processing_time=time.time() - started,
                optimizations=disk_cached.get("optimizations_applied", []),
            )
            return disk_cached

        if self.collection is None:
            return {
                "request_id": request_id,
                "query": query_text,
                "results": [],
                "status": "rag_unavailable",
                "timestamp": int(time.time()),
            }

        optimized = self.rl_agent.get_optimized_params(query_text, context)
        target_k = max(1, min(12, int(n_results or self.default_top_k)))
        target_k = max(target_k, int(optimized.get("top_k_hint", target_k)))
        target_k = self.scaler.recommend_top_k(target_k)

        try:
            query_emb = self._embed_texts([query_text])[0]

            @self.chroma_cb.call
            def _search() -> Dict[str, Any]:
                with self.collection_lock:
                    return self.collection.query(
                        query_embeddings=[query_emb],
                        n_results=target_k,
                        where=optimized.get("filters"),
                        include=["documents", "metadatas", "distances"],
                    )

            raw = _search()
        except Exception as exc:
            return {
                "request_id": request_id,
                "query": query_text,
                "results": [],
                "status": "error",
                "error": str(exc),
                "timestamp": int(time.time()),
            }

        ranked = self._rerank_results(raw)
        formatted = self._format_results(ranked)
        elapsed = time.time() - started
        self.scaler.record_latency(elapsed)

        interaction_id = f"{user_id}_{int(started)}_{request_id}"
        doc_hashes = [
            str(item.get("metadata", {}).get("doc_hash", ""))
            for item in formatted
            if isinstance(item.get("metadata"), dict)
        ]
        self.rl_agent.register_interaction(interaction_id, doc_hashes)

        response = {
            "request_id": request_id,
            "interaction_id": interaction_id,
            "query": query_text,
            "results": formatted,
            "status": "ok",
            "total_found": len(formatted),
            "processing_time": round(elapsed, 6),
            "from_cache": False,
            "optimizations_applied": optimized.get("optimizations", []),
            "timestamp": int(time.time()),
        }

        self._cache_set(cache_key, response)
        self.logger.log_interaction(
            interaction_id=interaction_id,
            user_id=user_id,
            query=query_text,
            results=formatted,
            processing_time=elapsed,
            optimizations=optimized.get("optimizations", []),
        )
        return response

    def delete_documents(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.collection is None:
            return {
                "status": "rag_unavailable",
                "deleted": 0,
                "timestamp": int(time.time()),
            }

        ids_obj = payload.get("ids")
        ids: List[str]
        if isinstance(ids_obj, list):
            ids = [str(x).strip() for x in ids_obj if str(x).strip()]
        else:
            single = str(payload.get("id", "")).strip()
            ids = [single] if single else []

        doc_hash = str(payload.get("doc_hash", "")).strip()

        if not ids and not doc_hash:
            return {
                "status": "missing_ids",
                "deleted": 0,
                "timestamp": int(time.time()),
            }

        try:
            with self.collection_lock:
                if ids:
                    self.collection.delete(ids=ids)
                elif doc_hash:
                    self.collection.delete(where={"doc_hash": doc_hash})
            total = self.collection.count()
            return {
                "status": "deleted",
                "deleted": len(ids) if ids else 1,
                "total": int(total),
                "timestamp": int(time.time()),
            }
        except Exception as exc:
            return {
                "status": "error",
                "error": str(exc),
                "deleted": 0,
                "timestamp": int(time.time()),
            }

    def ingest_path(self, base_path: str, recursive: bool = True) -> Dict[str, Any]:
        root = Path(base_path or str(self.docs_path))
        if not root.exists():
            return {
                "status": "missing_path",
                "path": str(root),
                "indexed_files": 0,
                "failed_files": 0,
                "timestamp": int(time.time()),
            }

        indexed = 0
        failed = 0

        iterator = root.rglob("*") if recursive else root.glob("*")
        for file_path in iterator:
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in self.allowed_extensions:
                continue
            text = self._extract_text_from_file(file_path)
            if not text:
                failed += 1
                continue

            meta = {
                "path": str(file_path),
                "title": file_path.name,
                "size_bytes": file_path.stat().st_size,
                "mtime": int(file_path.stat().st_mtime),
            }
            if self.add_document(text, metadata=meta, source="filesystem"):
                indexed += 1
            else:
                failed += 1

        total = self.collection.count() if self.collection is not None else 0
        return {
            "status": "ingested",
            "path": str(root),
            "indexed_files": indexed,
            "failed_files": failed,
            "total": int(total),
            "timestamp": int(time.time()),
        }

    def provide_feedback(
        self,
        interaction_id: str,
        feedback_type: str,
        feedback_value: float,
        user_id: str,
    ) -> Dict[str, Any]:
        self.logger.log_feedback(
            interaction_id=interaction_id,
            feedback_type=feedback_type,
            feedback_value=feedback_value,
            user_id=user_id,
        )
        self.rl_agent.update_from_feedback(interaction_id, feedback_value, feedback_type)
        return {
            "status": "feedback_saved",
            "interaction_id": interaction_id,
            "feedback_type": feedback_type,
            "feedback_value": float(feedback_value),
            "timestamp": int(time.time()),
        }

    def rebuild_index(self) -> Dict[str, Any]:
        self._init_collection()
        total = self.collection.count() if self.collection is not None else 0
        return {
            "status": "rebuilt",
            "total": int(total),
            "timestamp": int(time.time()),
        }

    def get_system_stats(self) -> Dict[str, Any]:
        total_docs = self.collection.count() if self.collection is not None else 0
        threat_stats = self.threat_detector.get_stats()
        threat_stats["engine"] = (
            "advanced_self_protection" if ADVANCED_THREAT_DETECTOR_AVAILABLE else "basic_threat_detector"
        )
        return {
            "database": {
                "total_documents": int(total_docs),
                "processed_documents": len(self.processed_documents),
                "cache_size": len(self.query_cache),
                "storage_root": str(self.storage_root),
                "vector_db_path": str(self.vector_db_path),
                "docs_path": str(self.docs_path),
                "ram_cache_path": str(self.ram_cache_path),
            },
            "embedding": {
                "backend": self.embed_backend,
                "model": self.embedding_model_name if self.embed_backend == "sentence" else self.embed_backend,
            },
            "reinforcement_learning": self.rl_agent.get_stats(),
            "threat_protection": threat_stats,
            "predictive_scaler": self.scaler.get_stats(),
            "web_scraping": self.web_scraper.get_stats(),
            "circuit_breakers": {
                "chromadb": self.chroma_cb.get_stats(),
                "embedding": self.embedding_cb.get_stats(),
            },
            "timestamp": _utc_now_iso(),
        }

    def get_self_test_report(self) -> Dict[str, Any]:
        checks = {
            "chroma_available": CHROMA_AVAILABLE,
            "collection_ready": self.collection is not None,
            "storage_root_exists": self.storage_root.exists(),
            "vector_db_path_exists": self.vector_db_path.exists(),
            "docs_path_exists": self.docs_path.exists(),
            "ram_cache_path_exists": self.ram_cache_path.exists(),
            "pdf_parser_available": PDF_AVAILABLE,
            "numpy_available": NUMPY_AVAILABLE,
            "advanced_threat_detector_available": ADVANCED_THREAT_DETECTOR_AVAILABLE,
        }
        return {
            "service": "rag-core",
            "timestamp": int(time.time()),
            "checks": checks,
            "overall_ok": all(checks.values()),
        }

    def _chunk_text(self, text: str) -> List[Dict[str, Any]]:
        words = text.split()
        if not words:
            return []

        chunk_size = max(60, self.chunk_size_words)
        overlap = max(0, min(chunk_size // 2, self.chunk_overlap_words))

        chunks: List[Dict[str, Any]] = []
        start = 0
        while start < len(words):
            end = min(len(words), start + chunk_size)
            chunk_text = " ".join(words[start:end]).strip()
            if chunk_text and len(chunk_text) > 60:
                chunks.append({"text": chunk_text[: self.max_doc_chars], "start": start, "end": end})
            if end >= len(words):
                break
            start = max(start + 1, end - overlap)

        return chunks

    def _embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        @self.embedding_cb.call
        def _embed() -> List[List[float]]:
            if self.embed_backend == "sentence" and self.embedding_model is not None:
                vectors = self.embedding_model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
                if NUMPY_AVAILABLE:
                    arr = np.asarray(vectors, dtype=np.float32)
                    return arr.tolist()
                return [[float(v) for v in vec] for vec in vectors]

            if self.embed_backend == "default" and self.default_embedding_fn is not None:
                vectors = self.default_embedding_fn(texts)
                if NUMPY_AVAILABLE:
                    arr = np.asarray(vectors, dtype=np.float32)
                    return arr.tolist()
                return [[float(v) for v in vec] for vec in vectors]

            return [self._hash_embed(text) for text in texts]

        try:
            return _embed()
        except Exception:
            self.embed_backend = "hash"
            return [self._hash_embed(text) for text in texts]

    def _hash_embed(self, text: str) -> List[float]:
        dim = max(64, self.hash_embedding_dim)
        if NUMPY_AVAILABLE:
            vec = np.zeros(dim, dtype=np.float32)
        else:
            vec = [0.0 for _ in range(dim)]

        for token in re.findall(r"[a-zA-Z0-9_]{2,}", text.lower()):
            h = int(hashlib.sha1(token.encode("utf-8")).hexdigest()[:8], 16)
            idx = h % dim
            if NUMPY_AVAILABLE:
                vec[idx] += 1.0
            else:
                vec[idx] = float(vec[idx]) + 1.0

        if NUMPY_AVAILABLE:
            norm = float(np.linalg.norm(vec))
            if norm > 0:
                vec /= norm
            return vec.tolist()

        norm = sum(float(x) * float(x) for x in vec) ** 0.5
        if norm > 0:
            vec = [float(x) / norm for x in vec]
        return [float(x) for x in vec]

    def _rerank_results(self, raw_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        docs = raw_results.get("documents", [[]])
        metas = raw_results.get("metadatas", [[]])
        dists = raw_results.get("distances", [[]])

        if not docs or not docs[0]:
            return []

        ranked: List[Dict[str, Any]] = []
        for idx, doc in enumerate(docs[0]):
            meta = metas[0][idx] if metas and metas[0] and idx < len(metas[0]) else {}
            dist = dists[0][idx] if dists and dists[0] and idx < len(dists[0]) else 1.0

            base_score = 1.0 - float(dist if isinstance(dist, (int, float)) else 1.0)
            if base_score < 0:
                base_score = 0.0

            doc_hash = str(meta.get("doc_hash", "")) if isinstance(meta, dict) else ""
            feedback_boost = self.rl_agent.get_document_feedback_score(doc_hash)

            recency_boost = 0.0
            if isinstance(meta, dict):
                indexed_at = meta.get("indexed_at")
                if isinstance(indexed_at, (int, float)):
                    age_hours = max(0.0, (time.time() - float(indexed_at)) / 3600.0)
                    recency_boost = max(0.0, 0.25 - min(0.25, age_hours / 720.0))

            final_score = base_score * (1.0 + feedback_boost + recency_boost)
            ranked.append(
                {
                    "text": str(doc),
                    "metadata": meta if isinstance(meta, dict) else {},
                    "distance": float(dist if isinstance(dist, (int, float)) else 1.0),
                    "score": float(final_score),
                }
            )

        ranked.sort(key=lambda item: item["score"], reverse=True)
        return ranked

    def _format_results(self, ranked_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        output: List[Dict[str, Any]] = []
        for idx, item in enumerate(ranked_results):
            output.append(
                {
                    "rank": idx + 1,
                    "text": item["text"],
                    "metadata": item.get("metadata", {}),
                    "distance": round(float(item.get("distance", 1.0)), 6),
                    "score": round(float(item.get("score", 0.0)), 6),
                }
            )
        return output

    def _extract_text_from_file(self, file_path: Path) -> str:
        if not file_path.exists() or not file_path.is_file():
            return ""

        try:
            if file_path.stat().st_size > self.max_file_mb * 1024 * 1024:
                return ""
        except Exception:
            return ""

        suffix = file_path.suffix.lower()

        try:
            if suffix == ".pdf":
                if not PDF_AVAILABLE:
                    return ""
                reader = PdfReader(str(file_path))
                pages = []
                for page in reader.pages:
                    text = page.extract_text() or ""
                    if text.strip():
                        pages.append(text)
                return "\n".join(pages)

            if suffix in {".md", ".markdown", ".txt", ".rst", ".json", ".yml", ".yaml"}:
                return file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return ""

        return ""

    def _normalize_documents_payload(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        docs_obj = payload.get("documents")
        if isinstance(docs_obj, list):
            out: List[Dict[str, Any]] = []
            for item in docs_obj:
                if isinstance(item, dict):
                    out.append(item)
            return out

        if isinstance(payload, dict) and ("text" in payload or "path" in payload):
            return [payload]
        return []

    def _cache_set(self, key: str, payload: Dict[str, Any]) -> None:
        self.query_cache[key] = dict(payload)
        self.query_cache.move_to_end(key)
        while len(self.query_cache) > self.query_cache_max:
            self.query_cache.popitem(last=False)
        self._cache_set_disk(key, payload)

    def _cache_file_path(self, key: str) -> Path:
        safe_key = re.sub(r"[^a-zA-Z0-9_-]", "_", key)
        return self.query_cache_disk_dir / f"{safe_key}.json"

    def _cache_get_disk(self, key: str) -> Dict[str, Any] | None:
        path = self._cache_file_path(key)
        if not path.exists():
            return None

        try:
            age = time.time() - path.stat().st_mtime
            if age > self.query_cache_ttl_sec:
                path.unlink(missing_ok=True)
                return None

            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
        except Exception:
            return None
        return None

    def _cache_set_disk(self, key: str, payload: Dict[str, Any]) -> None:
        try:
            path = self._cache_file_path(key)
            path.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
            self._prune_disk_cache()
        except Exception:
            return

    def _prune_disk_cache(self) -> None:
        try:
            files = [p for p in self.query_cache_disk_dir.glob("*.json") if p.is_file()]
            if len(files) <= self.query_cache_max:
                return
            files.sort(key=lambda p: p.stat().st_mtime)
            for item in files[: len(files) - self.query_cache_max]:
                item.unlink(missing_ok=True)
        except Exception:
            return

    def _load_processed_manifest(self) -> None:
        if not self.processed_manifest.exists():
            return

        try:
            with self.processed_manifest.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    doc_hash = str(item.get("doc_hash", "")).strip()
                    if doc_hash:
                        self.processed_documents.add(doc_hash)
        except Exception:
            return

    def _append_processed_manifest(self, doc_hash: str, path_hint: str) -> None:
        payload = {
            "doc_hash": doc_hash,
            "path": path_hint,
            "indexed_at": int(time.time()),
        }
        line = json.dumps(payload, ensure_ascii=True)
        self.processed_manifest.open("a", encoding="utf-8").write(line + "\n")


class IntelligentRAGService:
    def __init__(self) -> None:
        self.mqtt_host = os.getenv("MQTT_HOST", "localhost")
        self.mqtt_port = int(os.getenv("MQTT_PORT", "1883"))

        self.stop_event = threading.Event()
        self.mqtt_connected = False

        self.rag_db = IntelligentRAGDatabase()

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="rag-core")
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message

    def start(self) -> None:
        self._install_signal_handlers()

        self.client.connect(self.mqtt_host, self.mqtt_port, keepalive=60)
        self.client.loop_start()

        while not self.stop_event.is_set():
            time.sleep(0.5)

        self.client.loop_stop()
        self.client.disconnect()

    def stop(self) -> None:
        self.stop_event.set()

    def on_connect(self, client: mqtt.Client, userdata, flags, reason_code, properties) -> None:
        self.mqtt_connected = True
        print(f"[rag-core] MQTT conectado rc={reason_code}")

        client.subscribe("cognition/rag/query")
        client.subscribe("cognition/rag/upsert")
        client.subscribe("cognition/rag/delete")
        client.subscribe("cognition/rag/index/rebuild")
        client.subscribe("cognition/rag/feedback")
        client.subscribe("cognition/rag/ingest_path")
        client.subscribe("cognition/rag/stats/get")
        client.subscribe("system/integrity/self_test")

        self._publish(
            "system/rag/ready",
            {
                "service": "rag-core",
                "status": "online",
                "collection": self.rag_db.collection_name,
                "chroma_available": CHROMA_AVAILABLE,
                "embedding_backend": self.rag_db.embed_backend,
                "docs_path": str(self.rag_db.docs_path),
                "timestamp": int(time.time()),
            },
        )

    def on_disconnect(self, client: mqtt.Client, userdata, disconnect_flags, reason_code, properties) -> None:
        self.mqtt_connected = False
        print(f"[rag-core] MQTT desconectado rc={reason_code}")

    def on_message(self, client: mqtt.Client, userdata, msg: mqtt.MQTTMessage) -> None:
        payload = self._decode_payload(msg.payload)
        topic = msg.topic

        try:
            if topic == "cognition/rag/query":
                threading.Thread(target=self._handle_query, args=(payload,), daemon=True).start()
                return

            if topic == "cognition/rag/upsert":
                threading.Thread(target=self._handle_upsert, args=(payload,), daemon=True).start()
                return

            if topic == "cognition/rag/delete":
                threading.Thread(target=self._handle_delete, args=(payload,), daemon=True).start()
                return

            if topic == "cognition/rag/index/rebuild":
                threading.Thread(target=self._handle_rebuild, daemon=True).start()
                return

            if topic == "cognition/rag/feedback":
                threading.Thread(target=self._handle_feedback, args=(payload,), daemon=True).start()
                return

            if topic == "cognition/rag/ingest_path":
                threading.Thread(target=self._handle_ingest_path, args=(payload,), daemon=True).start()
                return

            if topic == "cognition/rag/stats/get":
                self._publish("cognition/rag/status", self.rag_db.get_system_stats())
                return

            if topic == "system/integrity/self_test":
                self._publish("system/integrity/report", self.rag_db.get_self_test_report())
                return
        except Exception as exc:
            self._publish_error("message", str(exc))

    def _handle_query(self, payload: Dict[str, Any]) -> None:
        request_id = str(payload.get("request_id", f"rag-{int(time.time() * 1000)}"))
        result = self.rag_db.query(
            query_text=str(payload.get("query", "")),
            n_results=int(payload.get("top_k", payload.get("n_results", self.rag_db.default_top_k))),
            user_id=str(payload.get("user_id", "anonymous")),
            request_id=request_id,
            context=payload.get("context") if isinstance(payload.get("context"), dict) else None,
        )
        self._publish("cognition/rag/result", result)

    def _handle_upsert(self, payload: Dict[str, Any]) -> None:
        source = str(payload.get("source", "manual"))
        status = self.rag_db.upsert_documents(payload, source=source)
        self._publish("cognition/rag/index/status", status)

    def _handle_delete(self, payload: Dict[str, Any]) -> None:
        status = self.rag_db.delete_documents(payload)
        self._publish("cognition/rag/index/status", status)

    def _handle_rebuild(self) -> None:
        status = self.rag_db.rebuild_index()
        self._publish("cognition/rag/index/status", status)

    def _handle_feedback(self, payload: Dict[str, Any]) -> None:
        status = self.rag_db.provide_feedback(
            interaction_id=str(payload.get("interaction_id", "")),
            feedback_type=str(payload.get("feedback_type", "explicit")),
            feedback_value=float(payload.get("feedback_value", 0.0)),
            user_id=str(payload.get("user_id", "anonymous")),
        )
        self._publish("cognition/rag/index/status", status)

    def _handle_ingest_path(self, payload: Dict[str, Any]) -> None:
        base_path = str(payload.get("path", str(self.rag_db.docs_path)))
        recursive = bool(payload.get("recursive", True))
        status = self.rag_db.ingest_path(base_path=base_path, recursive=recursive)
        self._publish("cognition/rag/index/status", status)

    def _publish_error(self, phase: str, error: str) -> None:
        self._publish(
            "system/error",
            {
                "service": "rag-core",
                "phase": phase,
                "error": error,
                "timestamp": int(time.time()),
            },
        )

    def _publish(self, topic: str, payload: Dict[str, Any]) -> None:
        if not self.mqtt_connected and topic != "system/integrity/report":
            return
        self.client.publish(topic, json.dumps(payload, ensure_ascii=True), qos=0, retain=False)

    @staticmethod
    def _decode_payload(payload_raw: bytes) -> Dict[str, Any]:
        if not payload_raw:
            return {}

        text = payload_raw.decode("utf-8", errors="replace").strip()
        if not text:
            return {}

        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        return {"text": text}

    def _install_signal_handlers(self) -> None:
        def _handler(signum, frame) -> None:
            print(f"[rag-core] senal {signum} recibida, cerrando")
            self.stop()

        signal.signal(signal.SIGINT, _handler)
        signal.signal(signal.SIGTERM, _handler)


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    IntelligentRAGService().start()
