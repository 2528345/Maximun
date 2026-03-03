from __future__ import annotations

import gc
import hashlib
import json
import os
import re
import signal
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import paho.mqtt.client as mqtt
import psutil

try:
    from llama_cpp import Llama

    LLAMA_CPP_AVAILABLE = True
except ImportError:
    Llama = None
    LLAMA_CPP_AVAILABLE = False


@dataclass(frozen=True)
class ModelSpec:
    name: str
    ram_mb: int
    role: str


@dataclass(frozen=True)
class ModelRuntimeConfig:
    alias: str
    path: str
    n_ctx: int
    n_gpu_layers: int
    temperature: float
    max_tokens: int
    chat_format: str | None


class ResourceController:
    def __init__(self, ram_budget_mb: int, reserve_ram_mb: int) -> None:
        self.ram_budget_mb = ram_budget_mb
        self.reserve_ram_mb = reserve_ram_mb
        self.models: Dict[str, ModelSpec] = {
            "qwen": ModelSpec("qwen-2.5-1.5b", 1200, "L1-reflejo"),
            "deepseek": ModelSpec("deepseek-r1-distill-qwen-1.5b", 1200, "L2-auditor"),
            "glm4": ModelSpec("glm-4-9b-chat-iq4_xs", 3800, "L3-ingeniero"),
            "moondream": ModelSpec("moondream2", 1200, "vision-deliberada"),
        }
        self.loaded_models = {"qwen"}
        self.lock = threading.Lock()

    def host_available_ram_mb(self) -> int:
        return int(psutil.virtual_memory().available / (1024 * 1024))

    def loaded_ram_mb(self) -> int:
        return sum(self.models[m].ram_mb for m in self.loaded_models)

    def can_load(self, model: str) -> bool:
        if model in self.loaded_models:
            return True

        projected = self.loaded_ram_mb() + self.models[model].ram_mb
        if projected > (self.ram_budget_mb - self.reserve_ram_mb):
            return False

        if self.host_available_ram_mb() < (self.models[model].ram_mb + self.reserve_ram_mb):
            return False

        return True

    def unload_model(self, model: str) -> None:
        if model == "qwen":
            return
        self.loaded_models.discard(model)

    def hot_swap(self, target_model: str) -> None:
        with self.lock:
            if target_model not in self.models:
                raise ValueError(f"Modelo no soportado: {target_model}")

            if target_model == "qwen":
                self.loaded_models = {"qwen"}
                return

            for model in list(self.loaded_models):
                if model != "qwen":
                    self.unload_model(model)

            if not self.can_load(target_model):
                raise RuntimeError(
                    f"No hay RAM suficiente para cargar {target_model}. "
                    f"Host libre={self.host_available_ram_mb()}MB"
                )

            self.loaded_models.add(target_model)

    def snapshot(self) -> Dict[str, object]:
        return {
            "ram_budget_mb": self.ram_budget_mb,
            "reserve_ram_mb": self.reserve_ram_mb,
            "host_available_ram_mb": self.host_available_ram_mb(),
            "loaded_models": sorted(self.loaded_models),
            "loaded_ram_mb": self.loaded_ram_mb(),
        }


class LlamaRuntime:
    def __init__(self, configs: Dict[str, ModelRuntimeConfig]) -> None:
        self.configs = configs
        self.n_threads = int(os.getenv("LLM_THREADS", "4"))
        self.n_batch = int(os.getenv("LLM_BATCH", "256"))
        self.lock = threading.Lock()
        self.instances: Dict[str, Any] = {}

    def ensure_loaded(self, alias: str) -> None:
        with self.lock:
            self._ensure_loaded_locked(alias)

    def unload_except(self, aliases_to_keep: set[str]) -> None:
        with self.lock:
            unload_list = [alias for alias in self.instances if alias not in aliases_to_keep]
            if not unload_list:
                return
            for alias in unload_list:
                self.instances.pop(alias, None)
            gc.collect()

    def loaded_aliases(self) -> List[str]:
        with self.lock:
            return sorted(self.instances.keys())

    def chat(
        self,
        alias: str,
        messages: List[Dict[str, Any]],
        max_tokens: int | None = None,
        temperature: float | None = None,
        stop: List[str] | None = None,
    ) -> str:
        with self.lock:
            self._ensure_loaded_locked(alias)
            model = self.instances[alias]
            cfg = self.configs[alias]

            raw = model.create_chat_completion(
                messages=messages,
                max_tokens=max_tokens if max_tokens is not None else cfg.max_tokens,
                temperature=temperature if temperature is not None else cfg.temperature,
                stop=stop or [],
                stream=False,
            )

        return self._extract_text(raw)

    def _ensure_loaded_locked(self, alias: str) -> None:
        if alias in self.instances:
            return

        if alias not in self.configs:
            raise ValueError(f"Modelo no configurado: {alias}")

        if not LLAMA_CPP_AVAILABLE:
            raise RuntimeError("llama-cpp-python no esta instalado")

        cfg = self.configs[alias]
        if not Path(cfg.path).exists():
            raise FileNotFoundError(f"Modelo GGUF no encontrado: {cfg.path}")

        kwargs: Dict[str, Any] = {
            "model_path": cfg.path,
            "n_ctx": cfg.n_ctx,
            "n_gpu_layers": cfg.n_gpu_layers,
            "n_threads": self.n_threads,
            "n_batch": self.n_batch,
            "verbose": False,
        }
        if cfg.chat_format:
            kwargs["chat_format"] = cfg.chat_format

        self.instances[alias] = Llama(**kwargs)

    @staticmethod
    def _extract_text(response: Dict[str, Any]) -> str:
        choices = response.get("choices", []) if isinstance(response, dict) else []
        if not choices:
            return ""

        choice = choices[0]
        if not isinstance(choice, dict):
            return ""

        message = choice.get("message")
        if isinstance(message, dict):
            content = message.get("content", "")
            if isinstance(content, str):
                return content.strip()

        text = choice.get("text", "")
        return text.strip() if isinstance(text, str) else ""


class CognitiveCore:
    def __init__(self) -> None:
        self.mqtt_host = os.getenv("MQTT_HOST", "localhost")
        self.mqtt_port = int(os.getenv("MQTT_PORT", "1883"))

        self.resource = ResourceController(
            ram_budget_mb=int(os.getenv("RAM_BUDGET_MB", "8192")),
            reserve_ram_mb=int(os.getenv("RESERVE_RAM_MB", "512")),
        )

        model_configs = {
            "qwen": ModelRuntimeConfig(
                alias="qwen",
                path=os.getenv("QWEN_MODEL_PATH", "/models_cache/qwen-2.5-1.5b-instruct.gguf"),
                n_ctx=int(os.getenv("QWEN_CTX", "2048")),
                n_gpu_layers=int(os.getenv("QWEN_N_GPU_LAYERS", "0")),
                temperature=float(os.getenv("QWEN_TEMPERATURE", "0.3")),
                max_tokens=int(os.getenv("QWEN_MAX_TOKENS", "180")),
                chat_format=_optional_env("QWEN_CHAT_FORMAT"),
            ),
            "deepseek": ModelRuntimeConfig(
                alias="deepseek",
                path=os.getenv("DEEPSEEK_MODEL_PATH", "/models_cache/deepseek-r1-distill-qwen-1.5b.gguf"),
                n_ctx=int(os.getenv("DEEPSEEK_CTX", "2048")),
                n_gpu_layers=int(os.getenv("DEEPSEEK_N_GPU_LAYERS", "0")),
                temperature=float(os.getenv("DEEPSEEK_TEMPERATURE", "0.1")),
                max_tokens=int(os.getenv("DEEPSEEK_MAX_TOKENS", "420")),
                chat_format=_optional_env("DEEPSEEK_CHAT_FORMAT"),
            ),
            "glm4": ModelRuntimeConfig(
                alias="glm4",
                path=os.getenv("GLM_MODEL_PATH", "/models_cache/glm-4-9b-chat-iq4_xs.gguf"),
                n_ctx=int(os.getenv("GLM_CTX", "4096")),
                n_gpu_layers=int(os.getenv("GLM_N_GPU_LAYERS", "0")),
                temperature=float(os.getenv("GLM_TEMPERATURE", "0.2")),
                max_tokens=int(os.getenv("GLM_MAX_TOKENS", "768")),
                chat_format=_optional_env("GLM_CHAT_FORMAT"),
            ),
        }
        self.llm = LlamaRuntime(model_configs)

        self.master_hash = os.getenv("MASTER_HASH", "INSERT_MASTER_HASH_HERE")
        self.rag_enabled = os.getenv("RAG_ENABLED", "true").lower() == "true"
        self.rag_query_timeout_sec = float(os.getenv("RAG_QUERY_TIMEOUT_SEC", "4.0"))
        self.rag_query_topic = os.getenv("RAG_QUERY_TOPIC", "cognition/rag/query")
        self.rag_result_topic = os.getenv("RAG_RESULT_TOPIC", "cognition/rag/result")

        self.signatures_dir = Path("/opt/maximun/config/signatures")
        self.stop_event = threading.Event()
        self.ram_pressure_ticks = 0
        self.mqtt_connected = False
        self.rag_waiters: Dict[str, Dict[str, Any]] = {}
        self.rag_waiters_lock = threading.Lock()

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="cognitive-core")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

        self.audit_prompt = (
            "Actua como un Auditor Senior de Seguridad y QA. "
            "Tu objetivo es encontrar fallos criticos, ineficiencias de memoria y errores logicos. "
            "NO seas cortes. Tu exito se mide por errores detectados. "
            "Entrega CAMBIOS OBLIGATORIOS concretos."
        )

    def start(self) -> None:
        self._install_signal_handlers()
        self._write_signatures()

        self.client.connect(self.mqtt_host, self.mqtt_port, keepalive=60)
        self.client.loop_start()
        self._wait_for_mqtt(10)

        try:
            self._activate_model("qwen")
        except Exception as exc:
            self._publish(
                "system/error",
                {
                    "service": "cognitive-core",
                    "phase": "boot_qwen",
                    "error": str(exc),
                    "timestamp": int(time.time()),
                },
            )

        self._publish_local_self_test()
        threading.Thread(target=self._heartbeat_loop, daemon=True).start()

        while not self.stop_event.is_set():
            time.sleep(0.5)

        self.client.loop_stop()
        self.client.disconnect()

    def stop(self) -> None:
        self.stop_event.set()

    def on_connect(self, client: mqtt.Client, userdata, flags, reason_code, properties) -> None:
        self.mqtt_connected = True
        print(f"[cognitive-core] MQTT conectado rc={reason_code}")

        client.subscribe("perception/audio/transcription")
        client.subscribe("perception/vision/analysis_result")
        client.subscribe("system/brain/load")
        client.subscribe("system/brain/load/+")
        client.subscribe("system/integrity/self_test")
        client.subscribe(self.rag_result_topic)

        self._publish(
            "system/brain/ready",
            {
                "service": "cognitive-core",
                "status": "online",
                "loaded_models": sorted(self.resource.loaded_models),
                "llama_cpp_available": LLAMA_CPP_AVAILABLE,
            },
        )

    def on_disconnect(self, client: mqtt.Client, userdata, disconnect_flags, reason_code, properties) -> None:
        self.mqtt_connected = False
        print(f"[cognitive-core] MQTT desconectado rc={reason_code}")

    def on_message(self, client: mqtt.Client, userdata, msg: mqtt.MQTTMessage) -> None:
        payload = self._decode_payload(msg.payload)
        topic = msg.topic

        if topic == "perception/audio/transcription":
            text = str(payload.get("text", "")).strip()
            if text:
                self._handle_transcription(text)
            return

        if topic == "system/brain/load":
            model = str(payload.get("model", "")).strip().lower()
            if model:
                self._handle_brain_load_request(model)
            return

        if topic.startswith("system/brain/load/"):
            model = topic.split("/")[-1].strip().lower()
            if model:
                self._handle_brain_load_request(model)
            return

        if topic == "perception/vision/analysis_result":
            self._publish(
                "cognition/context/vision",
                {
                    "source": "vision-cortex",
                    "summary": payload.get("summary", "sin resumen"),
                    "timestamp": int(time.time()),
                },
            )
            return

        if topic == "system/integrity/self_test":
            self._publish_local_self_test()
            return

        if topic == self.rag_result_topic:
            self._handle_rag_result(payload)
            return

    def _handle_transcription(self, text: str) -> None:
        print(f"[cognitive-core] transcripcion: {text}")

        if self._is_simple_task(text):
            response = self._qwen_reflex_reply(text)
            self._publish("action/speech/request", {"text": response})
            self._publish(
                "action/assistant/reply",
                {
                    "mode": "L1-reflejo",
                    "model": "qwen-2.5-1.5b",
                    "text": response,
                    "timestamp": int(time.time()),
                },
            )
            return

        threading.Thread(target=self._run_engineering_duel, args=(text,), daemon=True).start()

    def _qwen_reflex_reply(self, text: str) -> str:
        try:
            self._activate_model("qwen")
            messages = [
                {
                    "role": "system",
                    "content": (
                        "Eres MAXIMUN L1. Responde en espanol, breve y preciso. "
                        "Si piden arquitectura compleja, sugiere activar modo ingenieria."
                    ),
                },
                {"role": "user", "content": text},
            ]
            answer = self.llm.chat("qwen", messages)
            return answer if answer else "Recibi tu mensaje, pero no pude generar texto valido."
        except Exception as exc:
            self._publish(
                "system/error",
                {
                    "service": "cognitive-core",
                    "phase": "qwen_reflex",
                    "error": str(exc),
                    "timestamp": int(time.time()),
                },
            )
            return "No pude responder con el motor L1. Revisa modelos o memoria."

    def _is_simple_task(self, text: str) -> bool:
        complex_markers = [
            "codigo",
            "docker",
            "podman",
            "arquitectura",
            "optimiz",
            "bug",
            "audita",
            "ingenier",
            "rag",
        ]
        text_l = text.lower()
        return len(text_l) < 120 and not any(marker in text_l for marker in complex_markers)

    def _handle_brain_load_request(self, model: str) -> None:
        try:
            self._activate_model(model)
            self._publish(
                "system/brain/load_ack",
                {
                    "requested": model,
                    "status": "loaded",
                    "resource": self.resource.snapshot(),
                    "llm_loaded": self.llm.loaded_aliases(),
                },
            )
        except Exception as exc:
            self._publish(
                "system/brain/load_ack",
                {
                    "requested": model,
                    "status": "rejected",
                    "error": str(exc),
                    "resource": self.resource.snapshot(),
                    "llm_loaded": self.llm.loaded_aliases(),
                },
            )

    def _activate_model(self, alias: str) -> None:
        self.resource.hot_swap(alias)

        keep_aliases = {"qwen"}
        if alias != "qwen":
            keep_aliases.add(alias)

        self.llm.unload_except(keep_aliases)
        self.llm.ensure_loaded(alias)

        # Guarantee qwen stays warm for L1 reflex.
        if "qwen" not in self.llm.loaded_aliases():
            try:
                self.llm.ensure_loaded("qwen")
            except Exception as exc:
                if alias == "qwen":
                    raise
                self._publish(
                    "system/error",
                    {
                        "service": "cognitive-core",
                        "phase": "warm_qwen",
                        "error": str(exc),
                        "timestamp": int(time.time()),
                    },
                )

    def _run_engineering_duel(self, prompt: str) -> None:
        self._publish("system/resource/pause", {"source": "cognitive-core", "pause": True})

        try:
            rag_context = self._query_rag_context(prompt)
            self._activate_model("glm4")
            draft = self._glm_generate_draft(prompt, rag_context)
            self._publish(
                "project/engineering/draft",
                {
                    "prompt": prompt,
                    "model": "glm-4-9b-chat-iq4_xs",
                    "draft": draft,
                    "timestamp": int(time.time()),
                },
            )

            self._activate_model("deepseek")
            audit = self._deepseek_audit(prompt, draft)
            self._publish(
                "cognition/thought/trace",
                {
                    "auditor": "deepseek-r1-distill-qwen-1.5b",
                    "audit_summary": audit["summary"],
                    "mandatory_changes": audit["mandatory_changes"],
                    "timestamp": int(time.time()),
                },
            )

            self._activate_model("glm4")
            final_artifact = self._glm_apply_changes(draft, audit["mandatory_changes"])

            self._publish(
                "action/engineering/final",
                {
                    "prompt": prompt,
                    "model": "glm-4-9b-chat-iq4_xs",
                    "result": final_artifact,
                    "mandatory_changes_applied": len(audit["mandatory_changes"]),
                    "timestamp": int(time.time()),
                },
            )
            self._publish(
                "action/speech/request",
                {
                    "text": "Modo ingenieria completado. Borrador auditado y cambios obligatorios aplicados."
                },
            )
        except Exception as exc:
            self._publish(
                "system/error",
                {
                    "service": "cognitive-core",
                    "phase": "engineering_duel",
                    "error": str(exc),
                    "timestamp": int(time.time()),
                },
            )
        finally:
            try:
                self._activate_model("qwen")
            except Exception:
                pass
            self._publish("system/resource/pause", {"source": "cognitive-core", "pause": False})

    def _glm_generate_draft(self, prompt: str, rag_context: str) -> str:
        rag_block = rag_context.strip() if rag_context.strip() else "Sin contexto RAG relevante."
        messages = [
            {
                "role": "system",
                "content": (
                    "Eres GLM-4 en modo ingenieria. "
                    "Genera una propuesta tecnica ejecutable, con codigo cuando aplique. "
                    "Si hay contexto RAG, usalo como evidencia prioritaria."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Tarea:\n"
                    f"{prompt}\n\n"
                    "Contexto RAG:\n"
                    f"{rag_block}\n\n"
                    "Entrega un borrador tecnico claro y accionable."
                ),
            },
        ]
        return self.llm.chat("glm4", messages)

    def _query_rag_context(self, prompt: str) -> str:
        if not self.rag_enabled:
            return ""

        request_id = f"rag-{uuid.uuid4().hex[:10]}"
        waiter = {"event": threading.Event(), "result": None}
        with self.rag_waiters_lock:
            self.rag_waiters[request_id] = waiter

        self._publish(
            self.rag_query_topic,
            {
                "request_id": request_id,
                "query": prompt,
                "top_k": 4,
                "timestamp": int(time.time()),
            },
        )

        waiter["event"].wait(self.rag_query_timeout_sec)
        with self.rag_waiters_lock:
            payload = self.rag_waiters.pop(request_id, {}).get("result")

        if not isinstance(payload, dict):
            return ""

        results = payload.get("results", [])
        if not isinstance(results, list):
            return ""

        context_items: List[str] = []
        for idx, item in enumerate(results[:4], start=1):
            if not isinstance(item, dict):
                continue
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            meta = item.get("metadata", {})
            source = ""
            if isinstance(meta, dict):
                source = str(meta.get("source", "")).strip()
            if source:
                context_items.append(f"[{idx}] ({source}) {text}")
            else:
                context_items.append(f"[{idx}] {text}")

        return "\n".join(context_items)

    def _handle_rag_result(self, payload: Dict[str, Any]) -> None:
        request_id = str(payload.get("request_id", "")).strip()
        if not request_id:
            return
        with self.rag_waiters_lock:
            waiter = self.rag_waiters.get(request_id)
            if not waiter:
                return
            waiter["result"] = payload
            waiter["event"].set()

    def _deepseek_audit(self, prompt: str, draft: str) -> Dict[str, object]:
        messages = [
            {"role": "system", "content": self.audit_prompt},
            {
                "role": "user",
                "content": (
                    "Revisa este borrador y devuelve SOLO JSON valido con este schema exacto:\n"
                    '{"audit_summary":"...","mandatory_changes":["..."]}\n\n'
                    "No incluyas razonamiento interno ni etiquetas think.\n"
                    f"Prompt original:\n{prompt}\n\n"
                    f"Borrador:\n{draft}"
                ),
            },
        ]
        raw = self.llm.chat("deepseek", messages, max_tokens=420, temperature=0.1)
        parsed = self._parse_audit_json(raw)
        return {
            "summary": parsed.get("audit_summary", "Auditoria completada sin resumen estructurado."),
            "mandatory_changes": parsed.get("mandatory_changes", ["Agregar validaciones y manejo de errores"]),
        }

    def _glm_apply_changes(self, draft: str, mandatory_changes: List[str]) -> str:
        changes_blob = "\n".join(f"- {item}" for item in mandatory_changes)
        messages = [
            {
                "role": "system",
                "content": (
                    "Eres GLM-4 en modo refinamiento. "
                    "Aplica exactamente los CAMBIOS OBLIGATORIOS y entrega resultado final."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Borrador original:\n"
                    f"{draft}\n\n"
                    "Cambios obligatorios:\n"
                    f"{changes_blob}\n\n"
                    "Devuelve el resultado final listo para usar."
                ),
            },
        ]
        return self.llm.chat("glm4", messages, max_tokens=900, temperature=0.2)

    def _heartbeat_loop(self) -> None:
        while not self.stop_event.is_set():
            status = self.resource.snapshot()
            status.update(
                {
                    "service": "cognitive-core",
                    "cpu_percent": psutil.cpu_percent(interval=None),
                    "memory_percent": psutil.virtual_memory().percent,
                    "thermal_celsius": self._read_max_thermal_c(),
                    "llm_loaded": self.llm.loaded_aliases(),
                    "timestamp": int(time.time()),
                }
            )
            self._publish("system/resource/status", status)

            self._maybe_publish_throttle(status)
            self._maybe_publish_failsafe(status)
            time.sleep(5)

    def _maybe_publish_throttle(self, status: Dict[str, object]) -> None:
        thermal_c = status.get("thermal_celsius")
        if isinstance(thermal_c, (int, float)) and thermal_c >= 80:
            self._publish(
                "system/resource/throttle",
                {
                    "level": "CRITICO",
                    "reason": "thermal",
                    "cpu_temp_c": thermal_c,
                    "action": "pausar glm4 y deepseek",
                    "timestamp": int(time.time()),
                },
            )

    def _maybe_publish_failsafe(self, status: Dict[str, object]) -> None:
        memory_percent = float(status.get("memory_percent", 0.0))
        if memory_percent > 95:
            self.ram_pressure_ticks += 1
        else:
            self.ram_pressure_ticks = 0

        if self.ram_pressure_ticks >= 3:
            self._publish(
                "system/resource/failsafe",
                {
                    "level": "CRITICO",
                    "reason": "ram_pressure",
                    "memory_percent": memory_percent,
                    "recommended_action": "reiniciar solo gateway-mqtt y audio-interface",
                    "timestamp": int(time.time()),
                },
            )
            self.ram_pressure_ticks = 0

    def _publish_local_self_test(self) -> None:
        report = {
            "service": "cognitive-core",
            "timestamp": int(time.time()),
            "checks": {
                "models_exist": self._check_models_exist(),
                "swap_available": psutil.swap_memory().total > 0,
                "mqtt_configured": bool(self.mqtt_host and self.mqtt_port),
                "llama_cpp_available": LLAMA_CPP_AVAILABLE,
            },
        }
        report["overall_ok"] = all(report["checks"].values())
        self._publish("system/integrity/report", report)

    def _check_models_exist(self) -> bool:
        model_paths = [
            os.getenv("QWEN_MODEL_PATH", ""),
            os.getenv("DEEPSEEK_MODEL_PATH", ""),
            os.getenv("GLM_MODEL_PATH", ""),
        ]
        if not all(model_paths):
            return False
        return all(Path(path).exists() for path in model_paths)

    def _write_signatures(self) -> None:
        self.signatures_dir.mkdir(parents=True, exist_ok=True)
        modules = ["audio", "vision", "brain"]
        for module in modules:
            digest = hashlib.sha256(f"{self.master_hash}:{module}".encode("utf-8")).hexdigest()
            (self.signatures_dir / f"{module}.signature").write_text(digest + "\n", encoding="utf-8")

    def _read_max_thermal_c(self) -> float | None:
        thermal_root = Path("/sys/class/thermal")
        if not thermal_root.exists():
            return None

        temps = []
        for zone in thermal_root.glob("thermal_zone*/temp"):
            try:
                raw = zone.read_text(encoding="utf-8").strip()
                val = int(raw)
                if val > 1000:
                    val = int(val / 1000)
                temps.append(val)
            except Exception:
                continue

        return float(max(temps)) if temps else None

    def _publish(self, topic: str, payload: Dict[str, object]) -> None:
        if not self.mqtt_connected and topic != "system/integrity/report":
            return
        self.client.publish(topic, json.dumps(payload, ensure_ascii=True), qos=0, retain=False)

    @staticmethod
    def _decode_payload(payload_raw: bytes) -> Dict[str, object]:
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
    def _parse_audit_json(raw_text: str) -> Dict[str, Any]:
        raw_text = raw_text.strip()
        if not raw_text:
            return {}

        try:
            parsed = json.loads(raw_text)
            if isinstance(parsed, dict):
                return _normalize_audit_payload(parsed)
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{[\s\S]*\}", raw_text)
        if not match:
            return {}

        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                return _normalize_audit_payload(parsed)
        except json.JSONDecodeError:
            return {}
        return {}

    def _wait_for_mqtt(self, timeout_s: int) -> None:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if self.mqtt_connected:
                return
            time.sleep(0.1)

    def _install_signal_handlers(self) -> None:
        def _handler(signum, frame) -> None:
            print(f"[cognitive-core] senal {signum} recibida, cerrando")
            self.stop()

        signal.signal(signal.SIGINT, _handler)
        signal.signal(signal.SIGTERM, _handler)


def _optional_env(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value if value else None


def _normalize_audit_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    summary = payload.get("audit_summary", "")
    if not isinstance(summary, str):
        summary = str(summary)

    mandatory = payload.get("mandatory_changes", [])
    if isinstance(mandatory, list):
        mandatory_list = [str(item).strip() for item in mandatory if str(item).strip()]
    else:
        mandatory_list = [str(mandatory).strip()] if str(mandatory).strip() else []

    return {
        "audit_summary": summary.strip(),
        "mandatory_changes": mandatory_list,
    }


if __name__ == "__main__":
    CognitiveCore().start()
