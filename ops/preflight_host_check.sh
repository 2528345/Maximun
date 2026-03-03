#!/usr/bin/env bash
set -euo pipefail

DATA_ROOT="/opt/maximun/data"
if [[ -f .env ]]; then
  env_data_root="$(grep '^MAXIMUN_DATA_ROOT=' .env | tail -n1 | cut -d= -f2- || true)"
  [[ -n "$env_data_root" ]] && DATA_ROOT="$env_data_root"
fi

MODELS_ROOT="${DATA_ROOT}/models_cache"
RAG_ROOT="${DATA_ROOT}/rag_store"
PROJECTS_ROOT="${DATA_ROOT}/projects"
RAG_DOCS_ROOT="${RAG_ROOT}/docs"
RAG_RAM_CACHE="/dev/shm/maximun_rag_cache"
ENABLE_IOT="false"
IOT_ZIGBEE_SERIAL_PORT="/dev/ttyUSB1"
IOT_MODBUS_SERIAL_PORT="/dev/ttyUSB2"
IOT_CAN_CHANNEL="can0"
if [[ -f .env ]]; then
  env_ram_cache="$(grep '^RAG_RAM_CACHE_PATH=' .env | tail -n1 | cut -d= -f2- || true)"
  [[ -n "$env_ram_cache" ]] && RAG_RAM_CACHE="$env_ram_cache"
  env_enable_iot="$(grep '^ENABLE_IOT=' .env | tail -n1 | cut -d= -f2- || true)"
  env_zigbee_port="$(grep '^IOT_ZIGBEE_SERIAL_PORT=' .env | tail -n1 | cut -d= -f2- || true)"
  env_modbus_port="$(grep '^IOT_MODBUS_SERIAL_PORT=' .env | tail -n1 | cut -d= -f2- || true)"
  env_can_channel="$(grep '^IOT_CAN_CHANNEL=' .env | tail -n1 | cut -d= -f2- || true)"
  [[ -n "$env_enable_iot" ]] && ENABLE_IOT="$env_enable_iot"
  [[ -n "$env_zigbee_port" ]] && IOT_ZIGBEE_SERIAL_PORT="$env_zigbee_port"
  [[ -n "$env_modbus_port" ]] && IOT_MODBUS_SERIAL_PORT="$env_modbus_port"
  [[ -n "$env_can_channel" ]] && IOT_CAN_CHANNEL="$env_can_channel"
fi

REQUIRED_MODELS=(
  "qwen-2.5-1.5b-instruct.gguf"
  "deepseek-r1-distill-qwen-1.5b.gguf"
  "glm-4-9b-chat-iq4_xs.gguf"
  "yolov8n.onnx"
  "moondream2-text-model-f16.gguf"
  "moondream2-mmproj-f16.gguf"
  "es_ES-sharvard-medium.onnx"
)

warn=0
ok() { echo "[OK]   $*"; }
fail() { echo "[WARN] $*"; warn=1; }

if [[ -f .env ]]; then
  active_profile="$(grep '^MAXIMUN_RUNTIME_PROFILE=' .env | tail -n1 | cut -d= -f2- || true)"
  if [[ -n "$active_profile" ]]; then
    ok "Perfil runtime activo: $active_profile"
  fi
fi

ok "Raiz de datos configurada: ${DATA_ROOT}"

if [[ -f /etc/os-release ]]; then
  if grep -qi "opensuse" /etc/os-release; then
    ok "Sistema detectado: openSUSE"
  else
    fail "Este host no parece openSUSE"
  fi
fi

if command -v podman >/dev/null 2>&1; then
  ok "podman disponible"
else
  fail "podman no esta instalado"
fi

if grep -q avx2 /proc/cpuinfo; then
  ok "CPU con AVX2"
else
  fail "CPU sin AVX2 detectado"
fi

mem_mb=$(awk '/MemTotal/ {printf "%d", $2/1024}' /proc/meminfo)
swap_mb=$(awk '/SwapTotal/ {printf "%d", $2/1024}' /proc/meminfo)

if (( mem_mb >= 7600 )); then
  ok "RAM total ${mem_mb}MB"
else
  fail "RAM baja para perfil V5.1 (${mem_mb}MB)"
fi

if (( swap_mb >= 2048 )); then
  ok "Swap total ${swap_mb}MB"
else
  fail "Swap baja (${swap_mb}MB). Recomendado >= 2GB en SSD"
fi

if [[ -d "$PROJECTS_ROOT" && -d "$RAG_ROOT" ]]; then
  ok "Directorios de datos presentes"
else
  fail "Falta estructura ${DATA_ROOT}/{projects,rag_store}"
fi

if [[ -d "$RAG_DOCS_ROOT" ]]; then
  ok "RAG docs path presente: ${RAG_DOCS_ROOT}"
else
  fail "Falta ruta de documentos RAG: ${RAG_DOCS_ROOT}"
fi

if [[ -d "$RAG_RAM_CACHE" ]]; then
  ok "RAG RAM cache presente: ${RAG_RAM_CACHE}"
else
  fail "Falta cache RAM RAG: ${RAG_RAM_CACHE}"
fi

if [[ -d "$MODELS_ROOT" ]]; then
  ok "models_cache disponible"
  for model in "${REQUIRED_MODELS[@]}"; do
    if [[ -f "${MODELS_ROOT}/${model}" ]]; then
      ok "modelo ${model}"
    else
      fail "falta modelo ${model}"
    fi
  done
else
  fail "No existe ${MODELS_ROOT}"
fi

CHECKSUM_FILE="${MODEL_CHECKSUM_FILE:-${MODELS_ROOT}/model_checksums.sha256}"
if [[ -f "$CHECKSUM_FILE" ]]; then
  ok "Manifest de checksum detectado: ${CHECKSUM_FILE}"
else
  fail "Falta manifest de checksum (${CHECKSUM_FILE}). Ejecuta ops/generate_model_checksums.sh"
fi

if [[ -e /dev/snd ]]; then
  ok "/dev/snd disponible"
else
  fail "No existe /dev/snd"
fi

if [[ -e /dev/video0 ]]; then
  ok "/dev/video0 disponible"
else
  fail "No existe /dev/video0"
fi

if [[ "${ENABLE_IOT,,}" == "true" ]]; then
  if command -v bluetoothctl >/dev/null 2>&1; then
    ok "bluetoothctl disponible para diagnostico BLE"
  else
    fail "bluetoothctl no esta instalado (necesario para BLE real)"
  fi

  if [[ -e "$IOT_ZIGBEE_SERIAL_PORT" ]]; then
    ok "Puerto Zigbee disponible: $IOT_ZIGBEE_SERIAL_PORT"
  else
    fail "No existe puerto Zigbee configurado: $IOT_ZIGBEE_SERIAL_PORT"
  fi

  if [[ -e "$IOT_MODBUS_SERIAL_PORT" ]]; then
    ok "Puerto Modbus disponible: $IOT_MODBUS_SERIAL_PORT"
  else
    fail "No existe puerto Modbus configurado: $IOT_MODBUS_SERIAL_PORT"
  fi

  if ip link show "$IOT_CAN_CHANNEL" >/dev/null 2>&1; then
    ok "Canal CAN disponible: $IOT_CAN_CHANNEL"
  else
    fail "Canal CAN no encontrado: $IOT_CAN_CHANNEL"
  fi
fi

if command -v lsblk >/dev/null 2>&1; then
  dev="$(df -P "$DATA_ROOT" | awk 'NR==2 {print $1}')"
  rota="$(lsblk -no ROTA "$dev" 2>/dev/null | head -n1 || true)"
  if [[ "$rota" == "0" ]]; then
    ok "Datos sobre SSD/NVMe (ROTA=0)"
  elif [[ "$rota" == "1" ]]; then
    fail "Datos sobre HDD rotacional (ROTA=1)"
  else
    fail "No se pudo determinar el tipo de disco para ${dev}"
  fi
fi

if command -v df >/dev/null 2>&1; then
  free_gb="$(df -BG "$DATA_ROOT" | awk 'NR==2 {gsub("G", "", $4); print $4+0}')"
  if [[ -n "$free_gb" ]]; then
    if (( free_gb >= 60 )); then
      ok "Espacio libre en SSD ${free_gb}GB"
    else
      fail "Espacio libre bajo en SSD (${free_gb}GB). Recomendado >= 60GB"
    fi
  fi
fi

groups=$(id -Gn 2>/dev/null || true)
if [[ "$groups" == *"audio"* && "$groups" == *"video"* ]]; then
  ok "Usuario en grupos audio/video"
else
  fail "Usuario fuera de audio/video"
fi

if (( warn == 0 )); then
  printf "\nResultado: HOST LISTO para V5.1\n"
else
  printf "\nResultado: HOST CON ADVERTENCIAS\n"
  exit 1
fi
