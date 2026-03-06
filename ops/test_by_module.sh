#!/usr/bin/env bash
set -euo pipefail

BROKER_CONTAINER="${BROKER_CONTAINER:-gateway-mqtt}"
TIMEOUT_SEC="${TIMEOUT_SEC:-12}"
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

pass=0
warn=0

ok() {
  echo "[OK]   $*"
  pass=$((pass + 1))
}

ng() {
  echo "[WARN] $*"
  warn=$((warn + 1))
}

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "[FATAL] falta comando: $1"
    exit 2
  fi
}

need podman
need timeout

mqtt_wait_topic() {
  local topic="$1"
  local out_file="$2"
  local auth_args=""
  if [[ -n "$MQTT_USER" ]]; then
    auth_args="$auth_args -u '$MQTT_USER'"
  fi
  if [[ -n "$MQTT_PASS" ]]; then
    auth_args="$auth_args -P '$MQTT_PASS'"
  fi
  timeout "$TIMEOUT_SEC" podman exec "$BROKER_CONTAINER" sh -c \
    "mosquitto_sub -h localhost -p 1883 ${auth_args} -t '$topic' -C 1 -W $TIMEOUT_SEC" >"$out_file" 2>&1
}

mqtt_pub() {
  local topic="$1"
  local payload="$2"
  local auth_args=""
  if [[ -n "$MQTT_USER" ]]; then
    auth_args="$auth_args -u '$MQTT_USER'"
  fi
  if [[ -n "$MQTT_PASS" ]]; then
    auth_args="$auth_args -P '$MQTT_PASS'"
  fi
  podman exec "$BROKER_CONTAINER" sh -c \
    "mosquitto_pub -h localhost -p 1883 ${auth_args} -t '$topic' -m '$payload'"
}

service_running() {
  local name="$1"
  podman ps --format '{{.Names}}' | grep -qx "$name"
}

echo "== Test por modulo (V5.1) =="

modules=(gateway-mqtt cognitive-core vision-cortex audio-interface rag-core iot-gateway maximun-dashboard)
for m in "${modules[@]}"; do
  if service_running "$m"; then
    ok "contenedor activo: $m"
  else
    ng "contenedor caido/no encontrado: $m"
  fi
done

if ! service_running "$BROKER_CONTAINER"; then
  echo "[FATAL] broker no disponible (${BROKER_CONTAINER})"
  exit 1
fi

# 1) gateway-mqtt
if mqtt_pub "health/ping" '{"ping":"ok"}' >/dev/null 2>&1; then
  ok "gateway-mqtt publica mensajes"
else
  ng "gateway-mqtt no pudo publicar"
fi

# 2) cognitive-core readiness + reflex path
out1=$(mktemp)
out2=$(mktemp)
out3=$(mktemp)
trap 'rm -f "$out1" "$out2" "$out3"' EXIT

if mqtt_wait_topic "system/brain/ready" "$out1"; then
  ok "cognitive-core emite system/brain/ready"
else
  ng "cognitive-core no emitio system/brain/ready"
fi

# simple reflex request
(mqtt_wait_topic "action/assistant/reply" "$out2") &
sub_pid=$!
sleep 1
mqtt_pub "perception/audio/transcription" '{"text":"hola maximun"}' || true
if wait "$sub_pid"; then
  ok "cognitive-core responde por L1 reflex"
else
  ng "cognitive-core no respondio en action/assistant/reply"
fi

# 3) audio-interface speech output path
(mqtt_wait_topic "action/speech/played" "$out3") &
sub_pid=$!
sleep 1
mqtt_pub "action/speech/request" '{"text":"prueba de voz"}' || true
if wait "$sub_pid"; then
  ok "audio-interface procesa TTS y publica action/speech/played"
else
  ng "audio-interface no publico action/speech/played"
fi

# 4) vision-cortex readiness + deliberate analysis
out4=$(mktemp)
out5=$(mktemp)
trap 'rm -f "$out1" "$out2" "$out3" "$out4" "$out5"' EXIT

if mqtt_wait_topic "system/vision/ready" "$out4"; then
  ok "vision-cortex emite system/vision/ready"
else
  ng "vision-cortex no emitio system/vision/ready"
fi

(
  auth_args=""
  if [[ -n "$MQTT_USER" ]]; then
    auth_args="$auth_args -u '$MQTT_USER'"
  fi
  if [[ -n "$MQTT_PASS" ]]; then
    auth_args="$auth_args -P '$MQTT_PASS'"
  fi
  timeout "$TIMEOUT_SEC" podman exec "$BROKER_CONTAINER" sh -c \
    "mosquitto_sub -h localhost -p 1883 ${auth_args} -t 'perception/vision/analysis_result' -C 1 -W $TIMEOUT_SEC" >"$out5" 2>&1 || \
  timeout "$TIMEOUT_SEC" podman exec "$BROKER_CONTAINER" sh -c \
    "mosquitto_sub -h localhost -p 1883 ${auth_args} -t 'perception/vision/analysis_skipped' -C 1 -W $TIMEOUT_SEC" >"$out5" 2>&1
) &
sub_pid=$!
sleep 1
mqtt_pub "perception/vision/request_analysis" '{"request_id":"module-test-1","prompt":"Describe la escena"}' || true
if wait "$sub_pid"; then
  ok "vision-cortex responde a analisis deliberado (result o skipped)"
else
  ng "vision-cortex no respondio a analisis deliberado"
fi

# 5) rag-core readiness + query path
out6=$(mktemp)
out7=$(mktemp)
out8=$(mktemp)
trap 'rm -f "$out1" "$out2" "$out3" "$out4" "$out5" "$out6" "$out7" "$out8"' EXIT

if mqtt_wait_topic "system/rag/ready" "$out6"; then
  ok "rag-core emite system/rag/ready"
else
  ng "rag-core no emitio system/rag/ready"
fi

(mqtt_wait_topic "cognition/rag/result" "$out7") &
sub_pid=$!
sleep 1
mqtt_pub "cognition/rag/query" '{"request_id":"rag-test-1","query":"preferencias del usuario","top_k":2}' || true
if wait "$sub_pid"; then
  ok "rag-core responde consultas en cognition/rag/result"
else
  ng "rag-core no respondio consulta"
fi

# RAG ingestion path command
(mqtt_wait_topic "cognition/rag/index/status" "$out8") &
sub_pid=$!
sleep 1
mqtt_pub "cognition/rag/ingest_path" '{"path":"/rag_store/docs","recursive":true}' || true
if wait "$sub_pid"; then
  ok "rag-core acepta ingestion por path y publica index/status"
else
  ng "rag-core no respondio al comando ingest_path"
fi

# 6) dashboard port
if service_running "maximun-dashboard"; then
  if command -v curl >/dev/null 2>&1; then
    if curl -fsS "http://localhost:5173" >/dev/null 2>&1; then
      ok "dashboard accesible en http://localhost:5173"
    else
      ng "dashboard no accesible en puerto 5173"
    fi
  else
    ng "curl no disponible; no se pudo probar dashboard"
  fi
else
  ng "dashboard no activo (ENABLE_UI=false o contenedor caido)"
fi

# 7) iot-gateway readiness + command path
if service_running "iot-gateway"; then
  out9=$(mktemp)
  out10=$(mktemp)
  trap 'rm -f "$out1" "$out2" "$out3" "$out4" "$out5" "$out6" "$out7" "$out8" "$out9" "$out10"' EXIT

  if mqtt_wait_topic "system/iot/ready" "$out9"; then
    ok "iot-gateway emite system/iot/ready"
  else
    ng "iot-gateway no emitio system/iot/ready"
  fi

  (mqtt_wait_topic "iot/gateway/response" "$out10") &
  sub_pid=$!
  sleep 1
  mqtt_pub "iot/bluetooth/scan/request" '{"request_id":"iot-test-1"}' || true
  if wait "$sub_pid"; then
    ok "iot-gateway procesa scan bluetooth y responde por iot/gateway/response"
  else
    ng "iot-gateway no respondio al scan bluetooth"
  fi
else
  ng "iot-gateway no activo (ENABLE_IOT=false o contenedor caido)"
fi

echo
printf "Resumen: %d OK, %d WARN\n" "$pass" "$warn"
if (( warn > 0 )); then
  exit 1
fi
