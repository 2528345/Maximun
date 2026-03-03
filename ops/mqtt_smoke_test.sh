#!/usr/bin/env bash
set -euo pipefail

echo "[smoke] Enviando transcripcion de prueba"
podman exec gateway-mqtt sh -c 'mosquitto_pub -h localhost -p 1883 -t perception/audio/transcription -m "{\"text\":\"genera un script de backup\"}"'

sleep 2

echo "[smoke] Ultimos logs cognitive-core"
podman logs --tail 25 cognitive-core || true
