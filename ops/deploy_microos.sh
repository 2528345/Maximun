#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

RUNTIME_PROFILE=""
if [[ "${1:-}" == "--profile" && -n "${2:-}" ]]; then
  RUNTIME_PROFILE="$2"
fi

if ! command -v podman >/dev/null 2>&1; then
  echo "[FATAL] podman no encontrado"
  exit 2
fi

mkdir -p "$ROOT_DIR/config/signatures"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "[INFO] Se creo .env desde .env.example"
fi

if [[ -n "$RUNTIME_PROFILE" ]]; then
  echo "[INFO] Aplicando perfil runtime solicitado: $RUNTIME_PROFILE"
  ./ops/apply_runtime_profile.sh "$RUNTIME_PROFILE"
elif ! grep -q '^MAXIMUN_RUNTIME_PROFILE=' .env; then
  echo "[INFO] .env sin perfil runtime; aplicando perfil por defecto lenovo330s_stable"
  ./ops/apply_runtime_profile.sh lenovo330s_stable
else
  active_profile="$(grep '^MAXIMUN_RUNTIME_PROFILE=' .env | tail -n1 | cut -d= -f2-)"
  echo "[INFO] Perfil runtime activo en .env: ${active_profile}"
fi

echo "[INFO] Configurando layout SSD/RAM..."
./ops/storage_tier_setup.sh

echo "[INFO] Ejecutando chequeo de consistencia..."
set +e
./ops/check_system_consistency.sh
status=$?
set -e
if [[ "$status" -eq 1 ]]; then
  echo "[WARN] Consistencia valida con advertencias."
elif [[ "$status" -ne 0 ]]; then
  echo "[FATAL] Inconsistencias criticas detectadas."
  exit "$status"
fi

echo "[INFO] Ejecutando preflight..."
if ! ./ops/preflight_host_check.sh; then
  echo "[WARN] Preflight con advertencias. Revisa modelos/dispositivos y vuelve a correr."
  exit 1
fi

enable_ui="${ENABLE_UI:-false}"
enable_vision="${ENABLE_VISION:-false}"
if [[ -f .env ]]; then
  env_enable_ui="$(grep '^ENABLE_UI=' .env | tail -n1 | cut -d= -f2- || true)"
  env_enable_vision="$(grep '^ENABLE_VISION=' .env | tail -n1 | cut -d= -f2- || true)"
  [[ -n "$env_enable_ui" ]] && enable_ui="$env_enable_ui"
  [[ -n "$env_enable_vision" ]] && enable_vision="$env_enable_vision"
fi

services=(gateway-mqtt rag-core cognitive-core audio-interface)
if [[ "${enable_ui,,}" == "true" ]]; then
  services+=(dashboard)
fi
if [[ "${enable_vision,,}" == "true" ]]; then
  services+=(vision-cortex)
fi

echo "[INFO] Build y arranque"
podman compose build
echo "[INFO] Servicios a iniciar: ${services[*]}"
podman compose up -d "${services[@]}"
podman compose ps

echo
echo "[OK] Despliegue inicial terminado"
echo "Siguiente paso: ./ops/test_by_module.sh"
