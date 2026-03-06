#!/usr/bin/env bash
set -euo pipefail

MQTT_USER="${MQTT_USER:-}"
MQTT_PASS="${MQTT_PASS:-}"

if [[ -f .env ]]; then
  env_mqtt_user="$(grep '^MQTT_USERNAME=' .env | tail -n1 | cut -d= -f2- || true)"
  env_mqtt_pass="$(grep '^MQTT_PASSWORD=' .env | tail -n1 | cut -d= -f2- || true)"
  env_mqtt_ops_user="$(grep '^MQTT_OPS_USERNAME=' .env | tail -n1 | cut -d= -f2- || true)"
  env_mqtt_ops_pass="$(grep '^MQTT_OPS_PASSWORD=' .env | tail -n1 | cut -d= -f2- || true)"
  [[ -n "$env_mqtt_ops_user" ]] && env_mqtt_user="$env_mqtt_ops_user"
  [[ -n "$env_mqtt_ops_pass" ]] && env_mqtt_pass="$env_mqtt_ops_pass"
  [[ -n "$env_mqtt_user" ]] && MQTT_USER="$env_mqtt_user"
  [[ -n "$env_mqtt_pass" ]] && MQTT_PASS="$env_mqtt_pass"
fi

auth_args=""
if [[ -n "$MQTT_USER" ]]; then
  auth_args="$auth_args -u '$MQTT_USER'"
fi
if [[ -n "$MQTT_PASS" ]]; then
  auth_args="$auth_args -P '$MQTT_PASS'"
fi

echo "[smoke] Enviando transcripcion de prueba"
podman exec gateway-mqtt sh -c "mosquitto_pub -h localhost -p 1883 ${auth_args} -t perception/audio/transcription -m '{\"text\":\"genera un script de backup\"}'"

sleep 2

echo "[smoke] Ultimos logs cognitive-core"
podman logs --tail 25 cognitive-core || true
