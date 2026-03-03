#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker-compose.yml"

critical_fail=0
warn=0

ok() { echo "[OK]   $*"; }
ng() { echo "[WARN] $*"; warn=$((warn + 1)); }
fatal() { echo "[FAIL] $*"; critical_fail=1; }

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    fatal "falta comando requerido: $1"
  fi
}

file_must_exist() {
  local f="$1"
  if [[ -f "$ROOT_DIR/$f" ]]; then
    ok "archivo: $f"
  else
    fatal "falta archivo: $f"
  fi
}

extract_mem_mb() {
  local raw="$1"
  if [[ "$raw" =~ ^([0-9]+)[mM]$ ]]; then
    echo "${BASH_REMATCH[1]}"
    return
  fi
  if [[ "$raw" =~ ^([0-9]+)[gG]$ ]]; then
    echo "$(( ${BASH_REMATCH[1]} * 1024 ))"
    return
  fi
  echo "0"
}

service_mem_mb() {
  local service="$1"
  local line
  line="$(awk -v svc="$service" '
    $0 ~ "^[[:space:]]*" svc ":" {in_svc=1; next}
    in_svc && $0 ~ "^[[:space:]]*[a-zA-Z0-9_-]+:" && $0 !~ "^[[:space:]]+mem_limit:" {if($0 !~ "^[[:space:]]+") in_svc=0}
    in_svc && $0 ~ "mem_limit:" {print $2; exit}
  ' "$COMPOSE_FILE")"
  extract_mem_mb "$line"
}

echo "== MAXIMUN V5.1 Consistency Check =="

need_cmd rg
need_cmd awk

file_must_exist "docker-compose.yml"
file_must_exist "services/cognitive-core/app/main.py"
file_must_exist "services/audio-interface/app/main.py"
file_must_exist "services/vision-cortex/app/main.py"
file_must_exist "services/rag-core/app/main.py"
file_must_exist "services/rag-core/app/self_protection.py"
file_must_exist "services/iot-gateway/app/main.py"
file_must_exist "ops/preflight_host_check.sh"
file_must_exist "ops/storage_tier_setup.sh"
file_must_exist "ops/test_by_module.sh"
file_must_exist "config/runtime_profiles/lenovo330s_stable.env"
file_must_exist "config/runtime_profiles/lenovo330s_engineering.env"

echo
echo "== Servicios esperados =="
for svc in gateway-mqtt cognitive-core audio-interface vision-cortex rag-core iot-gateway dashboard; do
  if awk -v svc="$svc" '
    $1 == "services:" {in_services=1; next}
    in_services && $1 == svc ":" {found=1}
    END {exit found ? 0 : 1}
  ' "$COMPOSE_FILE"; then
    ok "servicio definido: $svc"
  else
    fatal "servicio ausente: $svc"
  fi
done

echo
echo "== Topicos criticos MQTT =="
topic_expectations=(
  "perception/audio/transcription:services/audio-interface/app/main.py:publish"
  "perception/audio/transcription:services/cognitive-core/app/main.py:consume"
  "action/speech/request:services/cognitive-core/app/main.py:publish"
  "action/speech/request:services/audio-interface/app/main.py:consume"
  "system/brain/load/glm4:services/cognitive-core/app/main.py:publish"
  "cognition/rag/query:services/cognitive-core/app/main.py:query"
  "cognition/rag/query:services/rag-core/app/main.py:consume"
  "cognition/rag/result:services/rag-core/app/main.py:publish"
  "cognition/rag/result:services/cognitive-core/app/main.py:consume"
  "system/resource/pause:services/cognitive-core/app/main.py:publish"
  "system/resource/pause:services/audio-interface/app/main.py:consume"
  "action/engineering/approval:services/cognitive-core/app/main.py:consume"
  "cognition/engineering/feedback:services/cognitive-core/app/main.py:consume"
  "system/audit/override:services/cognitive-core/app/main.py:consume"
  "cognition/rag/feedback:services/rag-core/app/main.py:consume"
  "cognition/rag/ingest_path:services/rag-core/app/main.py:consume"
  "RAG_QUERY_CACHE_TTL_SEC:services/rag-core/app/main.py:ram_cache_ttl"
  "iot/bluetooth/scan/request:services/iot-gateway/app/main.py:consume"
  "iot/zigbee/scan/request:services/iot-gateway/app/main.py:consume"
  "iot/industrial/request:services/iot-gateway/app/main.py:consume"
  "perception/iot/bluetooth/devices:services/iot-gateway/app/main.py:publish"
  "perception/iot/zigbee/devices:services/iot-gateway/app/main.py:publish"
  "perception/iot/industrial/data:services/iot-gateway/app/main.py:publish"
  "system/resource/pause:services/iot-gateway/app/main.py:consume"
)

for item in "${topic_expectations[@]}"; do
  topic="${item%%:*}"
  rest="${item#*:}"
  file="${rest%%:*}"
  role="${rest##*:}"
  if rg -n "$topic" "$ROOT_DIR/$file" >/dev/null 2>&1; then
    ok "topic $topic ($role)"
  else
    fatal "topic faltante $topic en $file ($role)"
  fi
done

echo
echo "== Presupuesto de memoria por modo (mem_limit) =="
core_total=$(( \
  $(service_mem_mb gateway-mqtt) + \
  $(service_mem_mb cognitive-core) + \
  $(service_mem_mb audio-interface) + \
  $(service_mem_mb rag-core) \
))
full_total=$(( core_total + $(service_mem_mb vision-cortex) + $(service_mem_mb dashboard) ))
iot_total=$(( core_total + $(service_mem_mb iot-gateway) ))
full_with_iot_total=$(( full_total + $(service_mem_mb iot-gateway) ))

echo "core (gateway+cognitive+audio+rag): ${core_total}MB"
echo "core+iot (+iot-gateway): ${iot_total}MB"
echo "full (+vision+dashboard): ${full_total}MB"
echo "full+iot (+vision+dashboard+iot): ${full_with_iot_total}MB"

if (( core_total > 8192 )); then
  fatal "core supera 8GB; reduce limites o desactiva modulos"
else
  ok "core dentro de 8GB"
fi

if (( full_total > 8192 )); then
  ng "full supera 8GB en limites nominales; usa perfil estable o evita vision/dashboard en modo ingenieria"
else
  ok "full dentro de 8GB"
fi

if (( iot_total > 8192 )); then
  ng "core+iot supera 8GB; reduce limites o manten iot desactivado durante ingenieria"
else
  ok "core+iot dentro de 8GB"
fi

if (( full_with_iot_total > 8192 )); then
  ng "full+iot supera 8GB; activa vision/iot solo por demanda"
else
  ok "full+iot dentro de 8GB"
fi

echo
if (( critical_fail > 0 )); then
  echo "Resultado: INCONSISTENTE (fallos criticos detectados)"
  exit 2
fi

if (( warn > 0 )); then
  echo "Resultado: CONSISTENTE CON ADVERTENCIAS"
  exit 1
fi

echo "Resultado: CONSISTENTE"
