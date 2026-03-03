from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import importlib.util
from pathlib import Path
from typing import Any, List

import paho.mqtt.client as mqtt

try:
    from faster_whisper import WhisperModel

    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    WhisperModel = None
    FASTER_WHISPER_AVAILABLE = False


class AudioInterface:
    def __init__(self) -> None:
        self.mqtt_host = os.getenv("MQTT_HOST", "localhost")
        self.mqtt_port = int(os.getenv("MQTT_PORT", "1883"))

        self.stt_model = os.getenv("FASTER_WHISPER_MODEL", "small")
        self.compute_type = os.getenv("FASTER_WHISPER_COMPUTE_TYPE", "int8")
        self.stt_device = os.getenv("FASTER_WHISPER_DEVICE", "cpu")
        self.stt_cpu_threads = int(os.getenv("STT_CPU_THREADS", "4"))
        self.stt_language = os.getenv("STT_LANGUAGE", "es")
        self.stt_min_chars = int(os.getenv("STT_MIN_CHARS", "3"))

        self.enable_stt_sim = os.getenv("ENABLE_STT_SIMULATOR", "false").lower() == "true"
        self.enable_stt_mic = os.getenv("ENABLE_STT_MIC", "true").lower() == "true"

        self.arecord_bin = os.getenv("ARECORD_BIN", "arecord")
        self.arecord_device = os.getenv("ARECORD_DEVICE", "default")
        self.arecord_seconds = int(os.getenv("ARECORD_SECONDS", "4"))

        self.piper_bin = os.getenv("PIPER_BIN", "piper")
        self.piper_voice = os.getenv("PIPER_VOICE_PATH", "/models_cache/es_ES-sharvard-medium.onnx")
        self.aplay_bin = os.getenv("APLAY_BIN", "aplay")
        self.tts_cooldown_sec = float(os.getenv("TTS_COOLDOWN_SEC", "1.2"))

        self.stop_event = threading.Event()
        self.pause_stt = False
        self.mqtt_connected = False
        self.speaking_until = 0.0

        self.tts_lock = threading.Lock()
        self.whisper_lock = threading.Lock()
        self.whisper_model: Any | None = None
        self.last_stt_error_ts = 0.0

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="audio-interface")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

    def start(self) -> None:
        self._install_signal_handlers()
        self.client.connect(self.mqtt_host, self.mqtt_port, keepalive=60)
        self.client.loop_start()

        if self.enable_stt_sim:
            threading.Thread(target=self._simulated_stt_loop, daemon=True).start()
        elif self.enable_stt_mic:
            threading.Thread(target=self._mic_stt_loop, daemon=True).start()

        while not self.stop_event.is_set():
            time.sleep(0.5)

        self.client.loop_stop()
        self.client.disconnect()

    def stop(self) -> None:
        self.stop_event.set()

    def on_connect(self, client: mqtt.Client, userdata, flags, reason_code, properties) -> None:
        self.mqtt_connected = True
        print(f"[audio-interface] MQTT conectado rc={reason_code}")

        client.subscribe("action/speech/request")
        client.subscribe("system/resource/pause")

        self._publish(
            "system/audio/ready",
            {
                "service": "audio-interface",
                "stt_model": self.stt_model,
                "compute_type": self.compute_type,
                "piper_voice": self.piper_voice,
                "status": "online",
                "faster_whisper_available": FASTER_WHISPER_AVAILABLE,
                "arecord_available": self._command_exists(self.arecord_bin),
                "piper_available": self._command_exists(self.piper_bin),
            },
        )

    def on_disconnect(self, client: mqtt.Client, userdata, disconnect_flags, reason_code, properties) -> None:
        self.mqtt_connected = False
        print(f"[audio-interface] MQTT desconectado rc={reason_code}")

    def on_message(self, client: mqtt.Client, userdata, msg: mqtt.MQTTMessage) -> None:
        payload = self._decode_payload(msg.payload)
        topic = msg.topic

        if topic == "action/speech/request":
            text = str(payload.get("text", "")).strip()
            if text:
                threading.Thread(target=self._tts_speak, args=(text,), daemon=True).start()
            return

        if topic == "system/resource/pause":
            self.pause_stt = bool(payload.get("pause", False))
            print(f"[audio-interface] pausa STT={self.pause_stt}")
            self._publish(
                "system/audio/state",
                {"pause_stt": self.pause_stt, "timestamp": int(time.time())},
            )

    def _mic_stt_loop(self) -> None:
        while not self.stop_event.is_set():
            if self.pause_stt or time.time() < self.speaking_until:
                time.sleep(0.2)
                continue

            audio_path: str | None = None
            try:
                audio_path = self._capture_audio_chunk()
                text = self._transcribe_audio_file(audio_path)
                if len(text) >= self.stt_min_chars:
                    self._publish(
                        "perception/audio/transcription",
                        {
                            "text": text,
                            "model": f"faster-whisper-{self.stt_model}",
                            "compute_type": self.compute_type,
                            "timestamp": int(time.time()),
                        },
                    )
            except Exception as exc:
                self._publish_stt_error(str(exc))
            finally:
                if audio_path:
                    _safe_unlink(audio_path)

    def _capture_audio_chunk(self) -> str:
        if not self._command_exists(self.arecord_bin):
            raise RuntimeError(f"No se encontro binario de captura: {self.arecord_bin}")

        tmp = tempfile.NamedTemporaryFile(prefix="max_stt_", suffix=".wav", delete=False)
        tmp.close()

        cmd = [
            self.arecord_bin,
            "-q",
            "-D",
            self.arecord_device,
            "-f",
            "S16_LE",
            "-r",
            "16000",
            "-c",
            "1",
            "-d",
            str(self.arecord_seconds),
            tmp.name,
        ]
        subprocess.run(cmd, check=True, timeout=self.arecord_seconds + 6)
        return tmp.name

    def _ensure_whisper_model(self) -> None:
        with self.whisper_lock:
            if self.whisper_model is not None:
                return
            if not FASTER_WHISPER_AVAILABLE:
                raise RuntimeError("faster-whisper no esta instalado")

            self.whisper_model = WhisperModel(
                self.stt_model,
                device=self.stt_device,
                compute_type=self.compute_type,
                cpu_threads=self.stt_cpu_threads,
            )

    def _transcribe_audio_file(self, wav_path: str) -> str:
        self._ensure_whisper_model()
        segments, _ = self.whisper_model.transcribe(
            wav_path,
            language=self.stt_language,
            vad_filter=True,
            beam_size=1,
        )
        text = " ".join(seg.text.strip() for seg in segments if seg.text.strip())
        return re.sub(r"\s+", " ", text).strip()

    def _tts_speak(self, text: str) -> None:
        with self.tts_lock:
            wav_file = tempfile.NamedTemporaryFile(prefix="max_tts_", suffix=".wav", delete=False)
            wav_path = wav_file.name
            wav_file.close()

            try:
                self.speaking_until = time.time() + self.tts_cooldown_sec
                self._run_piper(text, wav_path)
                self._play_wav(wav_path)
                self.speaking_until = time.time() + self.tts_cooldown_sec

                self._publish(
                    "action/speech/played",
                    {
                        "text": text,
                        "voice": self.piper_voice,
                        "timestamp": int(time.time()),
                    },
                )
            except Exception as exc:
                self._publish(
                    "system/error",
                    {
                        "service": "audio-interface",
                        "phase": "tts",
                        "error": str(exc),
                        "timestamp": int(time.time()),
                    },
                )
            finally:
                _safe_unlink(wav_path)

    def _run_piper(self, text: str, wav_path: str) -> None:
        if not Path(self.piper_voice).exists():
            raise FileNotFoundError(f"Voz Piper no encontrada: {self.piper_voice}")
        cmd = self._build_piper_command(wav_path)
        subprocess.run(
            cmd,
            input=text.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            timeout=45,
        )

    def _build_piper_command(self, wav_path: str) -> List[str]:
        if self._command_exists(self.piper_bin):
            return [self.piper_bin, "--model", self.piper_voice, "--output_file", wav_path]

        if importlib.util.find_spec("piper") is not None:
            return ["python", "-m", "piper", "--model", self.piper_voice, "--output_file", wav_path]

        raise RuntimeError(f"No se encontro Piper en PATH ni modulo Python. Esperado comando: {self.piper_bin}")

    def _play_wav(self, wav_path: str) -> None:
        if not self._command_exists(self.aplay_bin):
            raise RuntimeError(f"No se encontro binario de reproduccion: {self.aplay_bin}")
        subprocess.run(
            [self.aplay_bin, "-q", wav_path],
            check=True,
            timeout=60,
        )

    def _simulated_stt_loop(self) -> None:
        samples = [
            "hola maximun",
            "necesito revisar un modulo de podman",
            "genera un script de monitoreo",
        ]
        idx = 0
        while not self.stop_event.is_set():
            if not self.pause_stt and time.time() >= self.speaking_until:
                text = samples[idx % len(samples)]
                idx += 1
                self._publish(
                    "perception/audio/transcription",
                    {
                        "text": text,
                        "model": f"faster-whisper-{self.stt_model}-sim",
                        "compute_type": self.compute_type,
                        "timestamp": int(time.time()),
                    },
                )
            time.sleep(20)

    def _publish_stt_error(self, error: str) -> None:
        now = time.time()
        if now - self.last_stt_error_ts < 8:
            return
        self.last_stt_error_ts = now
        self._publish(
            "system/error",
            {
                "service": "audio-interface",
                "phase": "stt",
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

    @staticmethod
    def _command_exists(command: str) -> bool:
        return shutil.which(command) is not None

    def _install_signal_handlers(self) -> None:
        def _handler(signum, frame) -> None:
            print(f"[audio-interface] senal {signum} recibida, cerrando")
            self.stop()

        signal.signal(signal.SIGINT, _handler)
        signal.signal(signal.SIGTERM, _handler)


def _safe_unlink(path: str) -> None:
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


if __name__ == "__main__":
    AudioInterface().start()
