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

warn=0
ok() { echo "[OK]   $*"; }
fail() { echo "[WARN] $*"; warn=1; }

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

if [[ -d /opt/maximun/data/projects && -d /opt/maximun/data/rag_store ]]; then
  ok "Directorios de datos presentes"
else
  fail "Falta estructura /opt/maximun/data/{projects,rag_store}"
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
