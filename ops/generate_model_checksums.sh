#!/usr/bin/env bash
set -euo pipefail

DATA_ROOT="/opt/maximun/data"
if [[ -f .env ]]; then
  env_data_root="$(grep '^MAXIMUN_DATA_ROOT=' .env | tail -n1 | cut -d= -f2- || true)"
  [[ -n "$env_data_root" ]] && DATA_ROOT="$env_data_root"
fi

MODELS_ROOT="${DATA_ROOT}/models_cache"
OUT_FILE="${1:-${MODELS_ROOT}/model_checksums.sha256}"

if [[ ! -d "$MODELS_ROOT" ]]; then
  echo "[ERROR] models_cache no existe: $MODELS_ROOT"
  exit 2
fi

cd "$MODELS_ROOT"
mapfile -t files < <(find . -maxdepth 1 -type f \( -name "*.gguf" -o -name "*.onnx" \) -printf "%f\n" | sort)

if [[ "${#files[@]}" -eq 0 ]]; then
  echo "[WARN] no hay modelos .gguf/.onnx en $MODELS_ROOT"
  exit 1
fi

sha256sum "${files[@]}" > "$OUT_FILE"
echo "[OK] checksum manifest generado: $OUT_FILE"
