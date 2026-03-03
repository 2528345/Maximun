#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v podman >/dev/null 2>&1; then
  echo "[FATAL] podman no encontrado"
  exit 2
fi

mkdir -p /opt/maximun/data/models_cache
mkdir -p /opt/maximun/data/projects
mkdir -p /opt/maximun/data/rag_store
mkdir -p "$ROOT_DIR/config/signatures"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "[INFO] Se creo .env desde .env.example"
fi

echo "[INFO] Ejecutando preflight..."
if ! ./ops/preflight_host_check.sh; then
  echo "[WARN] Preflight con advertencias. Revisa modelos/dispositivos y vuelve a correr."
  exit 1
fi

echo "[INFO] Build y arranque"
podman compose build
podman compose up -d
podman compose ps

echo
echo "[OK] Despliegue inicial terminado"
echo "Siguiente paso: ./ops/test_by_module.sh"
