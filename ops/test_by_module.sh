#!/usr/bin/env bash
set -euo pipefail

BROKER_CONTAINER="${BROKER_CONTAINER:-gateway-mqtt}"
TIMEOUT_SEC="${TIMEOUT_SEC:-12}"

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
  timeout "$TIMEOUT_SEC" podman exec "$BROKER_CONTAINER" sh -c \
    "mosquitto_sub -h localhost -p 1883 -t '$topic' -C 1 -W $TIMEOUT_SEC" >"$out_file" 2>&1
}

mqtt_pub() {
  local topic="$1"
  local payload="$2"
  podman exec "$BROKER_CONTAINER" sh -c \
    "mosquitto_pub -h localhost -p 1883 -t '$topic' -m '$payload'"
}

service_running() {
  local name="$1"
  podman ps --format '{{.Names}}' | grep -qx "$name"
}

echo "== Test por modulo (V5.1) =="

modules=(gateway-mqtt cognitive-core vision-cortex audio-interface rag-core maximun-dashboard)
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
  timeout "$TIMEOUT_SEC" podman exec "$BROKER_CONTAINER" sh -c \
    "mosquitto_sub -h localhost -p 1883 -t 'perception/vision/analysis_result' -C 1 -W $TIMEOUT_SEC" >"$out5" 2>&1 || \
  timeout "$TIMEOUT_SEC" podman exec "$BROKER_CONTAINER" sh -c \
    "mosquitto_sub -h localhost -p 1883 -t 'perception/vision/analysis_skipped' -C 1 -W $TIMEOUT_SEC" >"$out5" 2>&1
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
trap 'rm -f "$out1" "$out2" "$out3" "$out4" "$out5" "$out6" "$out7"' EXIT

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

# 6) dashboard port
if command -v curl >/dev/null 2>&1; then
  if curl -fsS "http://localhost:5173" >/dev/null 2>&1; then
    ok "dashboard accesible en http://localhost:5173"
  else
    ng "dashboard no accesible en puerto 5173"
  fi
else
  ng "curl no disponible; no se pudo probar dashboard"
fi

echo
printf "Resumen: %d OK, %d WARN\n" "$pass" "$warn"
if (( warn > 0 )); then
  exit 1
fi
