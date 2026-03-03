#!/usr/bin/env bash
set -euo pipefail

MODELS_ROOT="/opt/maximun/data/models_cache"
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

echo "[self-test] Verificando RAM/swap..."
free -h

echo "[self-test] Estado de servicios..."
podman compose ps || true

echo "[self-test] Broker MQTT..."
if podman exec gateway-mqtt sh -c 'mosquitto_pub -h localhost -p 1883 -t health/ping -m ok'; then
  echo "  OK  publish test"
else
  echo "  WARN No se pudo publicar en broker"
fi
