#!/usr/bin/env bash
set -euo pipefail

DATA_ROOT="/opt/maximun/data"
MQTT_HOST="localhost"
MQTT_PORT="1883"
MQTT_USER="${MQTT_USER:-}"
MQTT_PASS="${MQTT_PASS:-}"

if [[ -f .env ]]; then
  env_data_root="$(grep '^MAXIMUN_DATA_ROOT=' .env | tail -n1 | cut -d= -f2- || true)"
  [[ -n "$env_data_root" ]] && DATA_ROOT="$env_data_root"

  env_mqtt_host="$(grep '^MQTT_HOST=' .env | tail -n1 | cut -d= -f2- || true)"
  [[ -n "$env_mqtt_host" ]] && MQTT_HOST="$env_mqtt_host"

  env_mqtt_port="$(grep '^MQTT_PORT=' .env | tail -n1 | cut -d= -f2- || true)"
  [[ -n "$env_mqtt_port" ]] && MQTT_PORT="$env_mqtt_port"

  env_mqtt_user="$(grep '^MQTT_USERNAME=' .env | tail -n1 | cut -d= -f2- || true)"
  env_mqtt_pass="$(grep '^MQTT_PASSWORD=' .env | tail -n1 | cut -d= -f2- || true)"
  [[ -n "$env_mqtt_user" ]] && MQTT_USER="$env_mqtt_user"
  [[ -n "$env_mqtt_pass" ]] && MQTT_PASS="$env_mqtt_pass"
fi

MODELS_ROOT="${DATA_ROOT}/models_cache"
CHECKSUM_FILE="${MODEL_CHECKSUM_FILE:-${MODELS_ROOT}/model_checksums.sha256}"
REQUIRED_MODELS=(
  "qwen-2.5-1.5b-instruct.gguf"
  "deepseek-r1-distill-qwen-1.5b.gguf"
  "glm-4-9b-chat-iq4_xs.gguf"
  "yolov8n.onnx"
  "moondream2-text-model-f16.gguf"
  "moondream2-mmproj-f16.gguf"
  "es_ES-sharvard-medium.onnx"
)

echo "[self-test] Verificando modelos..."
for model in "${REQUIRED_MODELS[@]}"; do
  if [[ -f "${MODELS_ROOT}/${model}" ]]; then
    echo "  OK  ${model}"
  else
    echo "  MISS ${model}"
  fi
done

echo "[self-test] Verificando checksums (si existe manifest)..."
if [[ -f "$CHECKSUM_FILE" ]]; then
  if (cd "$MODELS_ROOT" && sha256sum -c "$CHECKSUM_FILE" >/tmp/maximun_checksum.log 2>&1); then
    echo "  OK  checksums validos"
  else
    echo "  WARN checksum mismatch o manifest invalido"
    tail -n 20 /tmp/maximun_checksum.log || true
  fi
else
  echo "  WARN no existe manifest de checksum: ${CHECKSUM_FILE}"
fi

echo "[self-test] Verificando RAM/swap..."
free -h

echo "[self-test] Estado de servicios..."
if command -v podman >/dev/null 2>&1; then
  podman compose ps || true
else
  echo "  WARN podman no disponible en este host"
fi

echo "[self-test] Latencia TCP MQTT..."
if command -v python3 >/dev/null 2>&1; then
  mqtt_latency_ms="$(python3 - "$MQTT_HOST" "$MQTT_PORT" <<'PY'
import socket
import sys
import time

host = sys.argv[1]
port = int(sys.argv[2])
t0 = time.time()
try:
    sock = socket.create_connection((host, port), timeout=1.5)
    sock.close()
    print(f"{(time.time() - t0) * 1000:.3f}")
except Exception:
    print("FAIL")
PY
  )"
elif command -v python >/dev/null 2>&1; then
  mqtt_latency_ms="$(python - "$MQTT_HOST" "$MQTT_PORT" <<'PY'
import socket
import sys
import time

host = sys.argv[1]
port = int(sys.argv[2])
t0 = time.time()
try:
    sock = socket.create_connection((host, port), timeout=1.5)
    sock.close()
    print(f"{(time.time() - t0) * 1000:.3f}")
except Exception:
    print("FAIL")
PY
  )"
else
  mqtt_latency_ms="SKIP"
fi

if [[ "$mqtt_latency_ms" == "FAIL" ]]; then
  echo "  WARN no se pudo medir latencia MQTT en ${MQTT_HOST}:${MQTT_PORT}"
elif [[ "$mqtt_latency_ms" == "SKIP" ]]; then
  echo "  WARN no hay python/python3 para medir latencia MQTT"
else
  echo "  INFO latency=${mqtt_latency_ms}ms"
  if awk "BEGIN {exit !($mqtt_latency_ms < 10.0)}"; then
    echo "  OK  latencia MQTT < 10ms"
  else
    echo "  WARN latencia MQTT >= 10ms"
  fi
fi

echo "[self-test] Broker MQTT publish smoke..."
if command -v podman >/dev/null 2>&1; then
  auth_args=""
  if [[ -n "$MQTT_USER" ]]; then
    auth_args="$auth_args -u '$MQTT_USER'"
  fi
  if [[ -n "$MQTT_PASS" ]]; then
    auth_args="$auth_args -P '$MQTT_PASS'"
  fi
  if podman exec gateway-mqtt sh -c "mosquitto_pub -h localhost -p ${MQTT_PORT} ${auth_args} -t health/ping -m ok"; then
    echo "  OK  publish test"
  else
    echo "  WARN no se pudo publicar en broker"
  fi
else
  echo "  WARN podman no disponible; omitiendo publish smoke"
fi
