from __future__ import annotations

import json
import os
import signal
import threading
import time
from pathlib import Path
from typing import Any, Dict, List

import paho.mqtt.client as mqtt

try:
    import chromadb
    from chromadb.utils import embedding_functions

    CHROMA_AVAILABLE = True
except ImportError:
    chromadb = None
    embedding_functions = None
    CHROMA_AVAILABLE = False


class RAGCore:
    def __init__(self) -> None:
        self.mqtt_host = os.getenv("MQTT_HOST", "localhost")
        self.mqtt_port = int(os.getenv("MQTT_PORT", "1883"))

        self.chroma_path = os.getenv("RAG_CHROMA_PATH", "/rag_store/chroma")
        self.collection_name = os.getenv("RAG_COLLECTION", "maximun_memory")
        self.default_top_k = int(os.getenv("RAG_TOP_K", "4"))
        self.max_chars = int(os.getenv("RAG_MAX_DOC_CHARS", "6000"))

        self.stop_event = threading.Event()
        self.mqtt_connected = False
        self.last_error_ts = 0.0

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="rag-core")
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message

        self.chroma_client: Any | None = None
        self.collection: Any | None = None
        self.collection_lock = threading.Lock()

    def start(self) -> None:
        self._install_signal_handlers()
        self._init_collection()

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
        client.subscribe("system/integrity/self_test")

        self._publish(
            "system/rag/ready",
            {
                "service": "rag-core",
                "status": "online",
                "collection": self.collection_name,
                "chroma_available": CHROMA_AVAILABLE,
                "timestamp": int(time.time()),
            },
        )

    def on_disconnect(self, client: mqtt.Client, userdata, disconnect_flags, reason_code, properties) -> None:
        self.mqtt_connected = False
        print(f"[rag-core] MQTT desconectado rc={reason_code}")

    def on_message(self, client: mqtt.Client, userdata, msg: mqtt.MQTTMessage) -> None:
        payload = self._decode_payload(msg.payload)
        topic = msg.topic

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

        if topic == "system/integrity/self_test":
            self._publish_self_test()

    def _init_collection(self) -> None:
        if not CHROMA_AVAILABLE:
            return

        Path(self.chroma_path).mkdir(parents=True, exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(path=self.chroma_path)

        embedding_fn = embedding_functions.DefaultEmbeddingFunction()
        self.collection = self.chroma_client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )

    def _handle_query(self, payload: Dict[str, Any]) -> None:
        request_id = str(payload.get("request_id", f"rag-{int(time.time() * 1000)}"))
        query = str(payload.get("query", "")).strip()
        top_k = int(payload.get("top_k", self.default_top_k))

        if not query:
            self._publish(
                "cognition/rag/result",
                {
                    "request_id": request_id,
                    "query": query,
                    "results": [],
                    "status": "empty_query",
                    "timestamp": int(time.time()),
                },
            )
            return

        if self.collection is None:
            self._publish(
                "cognition/rag/result",
                {
                    "request_id": request_id,
                    "query": query,
                    "results": [],
                    "status": "rag_unavailable",
                    "timestamp": int(time.time()),
                },
            )
            return

        try:
            with self.collection_lock:
                raw = self.collection.query(
                    query_texts=[query],
                    n_results=max(1, top_k),
                    include=["documents", "metadatas", "distances"],
                )

            documents = raw.get("documents", [[]])[0] if raw.get("documents") else []
            metadatas = raw.get("metadatas", [[]])[0] if raw.get("metadatas") else []
            distances = raw.get("distances", [[]])[0] if raw.get("distances") else []

            results = []
            for idx, doc in enumerate(documents):
                meta = metadatas[idx] if idx < len(metadatas) else {}
                dist = distances[idx] if idx < len(distances) else None
                results.append(
                    {
                        "text": str(doc),
                        "metadata": meta if isinstance(meta, dict) else {},
                        "distance": float(dist) if isinstance(dist, (int, float)) else None,
                    }
                )

            self._publish(
                "cognition/rag/result",
                {
                    "request_id": request_id,
                    "query": query,
                    "results": results,
                    "status": "ok",
                    "timestamp": int(time.time()),
                },
            )
        except Exception as exc:
            self._publish_error("query", str(exc), request_id=request_id)

    def _handle_upsert(self, payload: Dict[str, Any]) -> None:
        if self.collection is None:
            self._publish_error("upsert", "rag_unavailable")
            return

        items = self._normalize_documents_payload(payload)
        if not items:
            self._publish(
                "cognition/rag/index/status",
                {
                    "status": "ignored",
                    "reason": "empty_payload",
                    "timestamp": int(time.time()),
                },
            )
            return

        ids: List[str] = []
        docs: List[str] = []
        metas: List[Dict[str, Any]] = []

        for item in items:
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            doc_id = str(item.get("id", f"doc-{int(time.time() * 1000)}-{len(ids)}"))
            meta = item.get("metadata", {})
            if not isinstance(meta, dict):
                meta = {"raw_metadata": str(meta)}

            ids.append(doc_id)
            docs.append(text[: self.max_chars])
            metas.append(meta)

        if not ids:
            self._publish_error("upsert", "no_valid_documents")
            return

        try:
            with self.collection_lock:
                self.collection.upsert(ids=ids, documents=docs, metadatas=metas)
                count = self.collection.count()

            self._publish(
                "cognition/rag/index/status",
                {
                    "status": "upserted",
                    "upserted": len(ids),
                    "total": count,
                    "timestamp": int(time.time()),
                },
            )
        except Exception as exc:
            self._publish_error("upsert", str(exc))

    def _handle_delete(self, payload: Dict[str, Any]) -> None:
        if self.collection is None:
            self._publish_error("delete", "rag_unavailable")
            return

        ids = payload.get("ids")
        if isinstance(ids, list):
            ids_clean = [str(x).strip() for x in ids if str(x).strip()]
        else:
            single_id = str(payload.get("id", "")).strip()
            ids_clean = [single_id] if single_id else []

        if not ids_clean:
            self._publish_error("delete", "missing_ids")
            return

        try:
            with self.collection_lock:
                self.collection.delete(ids=ids_clean)
                count = self.collection.count()
            self._publish(
                "cognition/rag/index/status",
                {
                    "status": "deleted",
                    "deleted": len(ids_clean),
                    "total": count,
                    "timestamp": int(time.time()),
                },
            )
        except Exception as exc:
            self._publish_error("delete", str(exc))

    def _handle_rebuild(self) -> None:
        try:
            self._init_collection()
            total = self.collection.count() if self.collection is not None else 0
            self._publish(
                "cognition/rag/index/status",
                {
                    "status": "rebuilt",
                    "total": int(total),
                    "timestamp": int(time.time()),
                },
            )
        except Exception as exc:
            self._publish_error("rebuild", str(exc))

    def _publish_self_test(self) -> None:
        report = {
            "service": "rag-core",
            "timestamp": int(time.time()),
            "checks": {
                "chroma_available": CHROMA_AVAILABLE,
                "chroma_path_exists": Path(self.chroma_path).exists(),
                "collection_ready": self.collection is not None,
                "mqtt_configured": bool(self.mqtt_host and self.mqtt_port),
            },
        }
        report["overall_ok"] = all(report["checks"].values())
        self._publish("system/integrity/report", report)

    def _publish_error(self, phase: str, error: str, request_id: str | None = None) -> None:
        now = time.time()
        if now - self.last_error_ts < 3:
            return
        self.last_error_ts = now

        payload: Dict[str, Any] = {
            "service": "rag-core",
            "phase": phase,
            "error": error,
            "timestamp": int(now),
        }
        if request_id:
            payload["request_id"] = request_id
        self._publish("system/error", payload)

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

    @staticmethod
    def _normalize_documents_payload(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        docs_obj = payload.get("documents")
        if isinstance(docs_obj, list):
            normalized: List[Dict[str, Any]] = []
            for item in docs_obj:
                if isinstance(item, dict):
                    normalized.append(item)
            return normalized

        if isinstance(payload, dict) and "text" in payload:
            return [payload]
        return []

    def _install_signal_handlers(self) -> None:
        def _handler(signum, frame) -> None:
            print(f"[rag-core] senal {signum} recibida, cerrando")
            self.stop()

        signal.signal(signal.SIGINT, _handler)
        signal.signal(signal.SIGTERM, _handler)


if __name__ == "__main__":
    RAGCore().start()
