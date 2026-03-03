from __future__ import annotations

import base64
import json
import os
import signal
import threading
import time
from pathlib import Path
from typing import Any, Dict, List

import paho.mqtt.client as mqtt

try:
    import cv2
    import numpy as np
    import onnxruntime as ort

    YOLO_DEPS_AVAILABLE = True
except ImportError:
    cv2 = None
    np = None
    ort = None
    YOLO_DEPS_AVAILABLE = False

try:
    from llama_cpp import Llama
    from llama_cpp.llama_chat_format import MoondreamChatHandler

    MOONDREAM_DEPS_AVAILABLE = True
except ImportError:
    Llama = None
    MoondreamChatHandler = None
    MOONDREAM_DEPS_AVAILABLE = False


COCO_CLASSES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat", "traffic light",
    "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow",
    "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
    "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket", "bottle",
    "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
    "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch", "potted plant", "bed",
    "dining table", "toilet", "tv", "laptop", "mouse", "remote", "keyboard", "cell phone", "microwave", "oven",
    "toaster", "sink", "refrigerator", "book", "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush",
]


class MoondreamRuntime:
    def __init__(self, model_path: str, mmproj_path: str, n_ctx: int, n_gpu_layers: int, max_tokens: int) -> None:
        self.model_path = model_path
        self.mmproj_path = mmproj_path
        self.n_ctx = n_ctx
        self.n_gpu_layers = n_gpu_layers
        self.max_tokens = max_tokens

        self.lock = threading.Lock()
        self.model: Any | None = None

    def describe_jpeg(self, image_jpeg: bytes, prompt: str) -> str:
        with self.lock:
            self._ensure_loaded_locked()
            data_uri = "data:image/jpeg;base64," + base64.b64encode(image_jpeg).decode("ascii")
            raw = self.model.create_chat_completion(
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": data_uri}},
                        ],
                    }
                ],
                max_tokens=self.max_tokens,
                temperature=0.2,
                stream=False,
            )
        return _extract_llm_text(raw)

    def _ensure_loaded_locked(self) -> None:
        if self.model is not None:
            return

        if not MOONDREAM_DEPS_AVAILABLE:
            raise RuntimeError("llama-cpp-python con soporte moondream no disponible")
        if not Path(self.model_path).exists():
            raise FileNotFoundError(f"Modelo Moondream no encontrado: {self.model_path}")
        if not Path(self.mmproj_path).exists():
            raise FileNotFoundError(f"MMProj Moondream no encontrado: {self.mmproj_path}")

        chat_handler = MoondreamChatHandler(clip_model_path=self.mmproj_path)
        self.model = Llama(
            model_path=self.model_path,
            chat_handler=chat_handler,
            n_ctx=self.n_ctx,
            n_gpu_layers=self.n_gpu_layers,
            n_threads=int(os.getenv("MOONDREAM_THREADS", "4")),
            n_batch=int(os.getenv("MOONDREAM_BATCH", "128")),
            verbose=False,
        )


class VisionCortex:
    def __init__(self) -> None:
        self.mqtt_host = os.getenv("MQTT_HOST", "localhost")
        self.mqtt_port = int(os.getenv("MQTT_PORT", "1883"))

        self.yolo_model_path = os.getenv("YOLO_MODEL_PATH", "/models_cache/yolov8n.onnx")
        self.yolo_conf_th = float(os.getenv("YOLO_CONF_THRESHOLD", "0.35"))
        self.yolo_iou_th = float(os.getenv("YOLO_IOU_THRESHOLD", "0.45"))

        self.moondream_model_path = os.getenv(
            "MOONDREAM_MODEL_PATH", "/models_cache/moondream2-text-model-f16.gguf"
        )
        self.moondream_mmproj_path = os.getenv(
            "MOONDREAM_MMPROJ_PATH", "/models_cache/moondream2-mmproj-f16.gguf"
        )
        self.moondream_enabled = os.getenv("MOONDREAM_ENABLED", "true").lower() == "true"

        self.ram_interlock_mb = int(os.getenv("RAM_INTERLOCK_MB", "1536"))
        self.reflex_interval_sec = float(os.getenv("VISION_REFLEX_INTERVAL_SEC", "2.0"))
        self.camera_index = int(os.getenv("CAMERA_INDEX", "0"))

        self.last_resource_status: Dict[str, Any] = {}
        self.stop_event = threading.Event()
        self.mqtt_connected = False

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="vision-cortex")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

        self.yolo_session: Any | None = None
        self.yolo_input_name = ""
        self.yolo_input_h = 640
        self.yolo_input_w = 640

        self.camera_lock = threading.Lock()
        self.camera: Any | None = None

        self.latest_frame_lock = threading.Lock()
        self.latest_frame_jpeg: bytes | None = None

        self.moondream = MoondreamRuntime(
            model_path=self.moondream_model_path,
            mmproj_path=self.moondream_mmproj_path,
            n_ctx=int(os.getenv("MOONDREAM_CTX", "2048")),
            n_gpu_layers=int(os.getenv("MOONDREAM_N_GPU_LAYERS", "0")),
            max_tokens=int(os.getenv("MOONDREAM_MAX_TOKENS", "180")),
        )

        self.last_error_ts = 0.0

    def start(self) -> None:
        self._install_signal_handlers()
        self.client.connect(self.mqtt_host, self.mqtt_port, keepalive=60)
        self.client.loop_start()

        threading.Thread(target=self._reflex_loop, daemon=True).start()

        while not self.stop_event.is_set():
            time.sleep(0.5)

        self._release_camera()
        self.client.loop_stop()
        self.client.disconnect()

    def stop(self) -> None:
        self.stop_event.set()

    def on_connect(self, client: mqtt.Client, userdata, flags, reason_code, properties) -> None:
        self.mqtt_connected = True
        print(f"[vision-cortex] MQTT conectado rc={reason_code}")

        client.subscribe("system/resource/status")
        client.subscribe("perception/vision/request_analysis")

        self._publish(
            "system/vision/ready",
            {
                "service": "vision-cortex",
                "yolo_model": self.yolo_model_path,
                "moondream_model": self.moondream_model_path,
                "status": "online",
                "yolo_deps_available": YOLO_DEPS_AVAILABLE,
                "moondream_deps_available": MOONDREAM_DEPS_AVAILABLE,
            },
        )

    def on_disconnect(self, client: mqtt.Client, userdata, disconnect_flags, reason_code, properties) -> None:
        self.mqtt_connected = False
        print(f"[vision-cortex] MQTT desconectado rc={reason_code}")

    def on_message(self, client: mqtt.Client, userdata, msg: mqtt.MQTTMessage) -> None:
        payload = self._decode_payload(msg.payload)

        if msg.topic == "system/resource/status":
            self.last_resource_status = payload
            return

        if msg.topic == "perception/vision/request_analysis":
            frame_hint = str(payload.get("frame_hint", "escena_general"))
            request_id = str(payload.get("request_id", f"req-{int(time.time())}"))
            prompt = str(
                payload.get(
                    "prompt",
                    f"Describe en espanol la escena actual. Contexto adicional: {frame_hint}",
                )
            )
            threading.Thread(
                target=self._run_deliberate_analysis,
                args=(request_id, frame_hint, prompt),
                daemon=True,
            ).start()

    def _reflex_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                frame = self._read_frame()
                if frame is None:
                    time.sleep(0.5)
                    continue

                detections = self._run_yolo(frame)
                self._cache_frame_jpeg(frame)

                labels = sorted({det["label"] for det in detections})
                top = detections[:5]

                self._publish(
                    "perception/vision/detection",
                    {
                        "model": "yolov8n.onnx",
                        "objects": labels,
                        "top_detections": top,
                        "priority": "low",
                        "timestamp": int(time.time()),
                    },
                )

                if any(label in {"person", "laptop", "keyboard", "mouse", "cell phone"} for label in labels):
                    self._publish(
                        "perception/vision/trigger",
                        {
                            "reason": "objeto_interes_detectado",
                            "objects": labels,
                            "timestamp": int(time.time()),
                        },
                    )

            except Exception as exc:
                self._publish_error("reflex", str(exc))

            time.sleep(self.reflex_interval_sec)

    def _run_deliberate_analysis(self, request_id: str, frame_hint: str, prompt: str) -> None:
        status = self.last_resource_status
        free_ram_mb = int(status.get("host_available_ram_mb", 0))
        loaded_models = status.get("loaded_models", []) if isinstance(status.get("loaded_models"), list) else []

        if "glm4" in loaded_models and free_ram_mb < self.ram_interlock_mb:
            self._publish(
                "perception/vision/analysis_skipped",
                {
                    "request_id": request_id,
                    "reason": "interbloqueo_ram",
                    "free_ram_mb": free_ram_mb,
                    "threshold_mb": self.ram_interlock_mb,
                    "glm4_active": True,
                    "timestamp": int(time.time()),
                },
            )
            return

        if not self.moondream_enabled:
            self._publish(
                "perception/vision/analysis_skipped",
                {
                    "request_id": request_id,
                    "reason": "moondream_desactivado",
                    "timestamp": int(time.time()),
                },
            )
            return

        frame_jpeg = self._get_latest_frame_jpeg()
        if frame_jpeg is None:
            frame = self._read_frame()
            if frame is None:
                self._publish(
                    "perception/vision/analysis_skipped",
                    {
                        "request_id": request_id,
                        "reason": "sin_frame_disponible",
                        "timestamp": int(time.time()),
                    },
                )
                return
            self._cache_frame_jpeg(frame)
            frame_jpeg = self._get_latest_frame_jpeg()

        try:
            summary = self.moondream.describe_jpeg(frame_jpeg, prompt)
            self._publish(
                "perception/vision/analysis_result",
                {
                    "request_id": request_id,
                    "model": "moondream2",
                    "frame_hint": frame_hint,
                    "summary": summary,
                    "timestamp": int(time.time()),
                },
            )
        except Exception as exc:
            self._publish_error("deliberate", str(exc))
            self._publish(
                "perception/vision/analysis_skipped",
                {
                    "request_id": request_id,
                    "reason": "error_moondream",
                    "error": str(exc),
                    "timestamp": int(time.time()),
                },
            )

    def _init_yolo(self) -> None:
        if self.yolo_session is not None:
            return
        if not YOLO_DEPS_AVAILABLE:
            raise RuntimeError("Dependencias de YOLO no disponibles (opencv/numpy/onnxruntime)")
        if not Path(self.yolo_model_path).exists():
            raise FileNotFoundError(f"Modelo YOLO no encontrado: {self.yolo_model_path}")

        self.yolo_session = ort.InferenceSession(
            self.yolo_model_path,
            providers=["CPUExecutionProvider"],
        )
        input_meta = self.yolo_session.get_inputs()[0]
        self.yolo_input_name = input_meta.name

        shape = input_meta.shape
        if len(shape) >= 4:
            h_dim = shape[2]
            w_dim = shape[3]
            self.yolo_input_h = int(h_dim) if isinstance(h_dim, int) and h_dim > 0 else 640
            self.yolo_input_w = int(w_dim) if isinstance(w_dim, int) and w_dim > 0 else 640

    def _run_yolo(self, frame: Any) -> List[Dict[str, Any]]:
        self._init_yolo()

        original_h, original_w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (self.yolo_input_w, self.yolo_input_h))
        tensor = resized.astype(np.float32) / 255.0
        tensor = np.transpose(tensor, (2, 0, 1))[None, :, :, :]

        outputs = self.yolo_session.run(None, {self.yolo_input_name: tensor})
        pred = outputs[0]

        if pred.ndim != 3:
            return []

        # Support both [1, 84, N] and [1, N, 84].
        if pred.shape[1] < pred.shape[2]:
            pred = np.transpose(pred, (0, 2, 1))

        rows = pred[0]
        boxes: List[List[int]] = []
        confidences: List[float] = []
        class_ids: List[int] = []

        for row in rows:
            if row.shape[0] < 6:
                continue

            if row.shape[0] == 84:
                class_scores = row[4:]
                confidence = float(np.max(class_scores))
                class_id = int(np.argmax(class_scores))
            else:
                objectness = float(row[4])
                class_scores = row[5:]
                if class_scores.size == 0:
                    confidence = objectness
                    class_id = 0
                else:
                    class_conf = float(np.max(class_scores))
                    confidence = objectness * class_conf
                    class_id = int(np.argmax(class_scores))

            if confidence < self.yolo_conf_th:
                continue

            cx, cy, bw, bh = map(float, row[:4])
            x = int((cx - bw / 2.0) * (original_w / self.yolo_input_w))
            y = int((cy - bh / 2.0) * (original_h / self.yolo_input_h))
            w = int(bw * (original_w / self.yolo_input_w))
            h = int(bh * (original_h / self.yolo_input_h))

            boxes.append([x, y, max(1, w), max(1, h)])
            confidences.append(confidence)
            class_ids.append(class_id)

        if not boxes:
            return []

        idxs = cv2.dnn.NMSBoxes(boxes, confidences, self.yolo_conf_th, self.yolo_iou_th)
        if len(idxs) == 0:
            return []

        flat_idxs = np.array(idxs).reshape(-1).tolist()
        detections: List[Dict[str, Any]] = []
        for idx in flat_idxs:
            class_id = class_ids[idx]
            label = COCO_CLASSES[class_id] if 0 <= class_id < len(COCO_CLASSES) else f"class_{class_id}"
            detections.append(
                {
                    "label": label,
                    "confidence": round(float(confidences[idx]), 3),
                    "bbox": boxes[idx],
                }
            )

        detections.sort(key=lambda item: item["confidence"], reverse=True)
        return detections

    def _read_frame(self) -> Any | None:
        if not YOLO_DEPS_AVAILABLE:
            raise RuntimeError("OpenCV no disponible")

        with self.camera_lock:
            if self.camera is None:
                self.camera = cv2.VideoCapture(self.camera_index)
                if not self.camera.isOpened():
                    self.camera.release()
                    self.camera = None
                    raise RuntimeError(f"No se pudo abrir /dev/video{self.camera_index}")

            ok, frame = self.camera.read()
            if not ok:
                return None
            return frame

    def _release_camera(self) -> None:
        with self.camera_lock:
            if self.camera is not None:
                self.camera.release()
                self.camera = None

    def _cache_frame_jpeg(self, frame: Any) -> None:
        ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if not ok:
            return
        with self.latest_frame_lock:
            self.latest_frame_jpeg = encoded.tobytes()

    def _get_latest_frame_jpeg(self) -> bytes | None:
        with self.latest_frame_lock:
            return self.latest_frame_jpeg

    def _publish_error(self, phase: str, error: str) -> None:
        now = time.time()
        if now - self.last_error_ts < 5:
            return
        self.last_error_ts = now
        self._publish(
            "system/error",
            {
                "service": "vision-cortex",
                "phase": phase,
                "error": error,
                "timestamp": int(now),
            },
        )

    def _publish(self, topic: str, payload: dict) -> None:
        if not self.mqtt_connected:
            return
        self.client.publish(topic, json.dumps(payload, ensure_ascii=True), qos=0, retain=False)

    @staticmethod
    def _decode_payload(payload_raw: bytes) -> dict:
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
            print(f"[vision-cortex] senal {signum} recibida, cerrando")
            self.stop()

        signal.signal(signal.SIGINT, _handler)
        signal.signal(signal.SIGTERM, _handler)


def _extract_llm_text(response: Dict[str, Any]) -> str:
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


if __name__ == "__main__":
    VisionCortex().start()
