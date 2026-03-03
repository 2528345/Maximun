#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROFILES_DIR="$ROOT_DIR/config/runtime_profiles"
ENV_FILE="$ROOT_DIR/.env"
ENV_TEMPLATE="$ROOT_DIR/.env.example"

usage() {
  cat <<USAGE
Uso:
  ./ops/apply_runtime_profile.sh <perfil>
  ./ops/apply_runtime_profile.sh --list

Perfiles disponibles:
  lenovo330s_stable
  lenovo330s_engineering
USAGE
}

list_profiles() {
  echo "Perfiles encontrados en $PROFILES_DIR:"
  for file in "$PROFILES_DIR"/*.env; do
    [[ -f "$file" ]] || continue
    base="$(basename "$file" .env)"
    echo "  - $base"
  done
}

if [[ "${1:-}" == "--list" || "${1:-}" == "-l" ]]; then
  list_profiles
  exit 0
fi

if [[ $# -ne 1 ]]; then
  usage
  exit 1
fi

profile="$1"
profile_file="$PROFILES_DIR/${profile}.env"
if [[ ! -f "$profile_file" ]]; then
  echo "[FATAL] Perfil no encontrado: $profile"
  list_profiles
  exit 2
fi

if [[ ! -f "$ENV_FILE" ]]; then
  if [[ -f "$ENV_TEMPLATE" ]]; then
    cp "$ENV_TEMPLATE" "$ENV_FILE"
    echo "[INFO] Se creo .env desde .env.example"
  else
    : >"$ENV_FILE"
    echo "[INFO] Se creo .env vacio"
  fi
fi

timestamp="$(date +%Y%m%d_%H%M%S)"
backup="$ROOT_DIR/.env.backup_${timestamp}"
cp "$ENV_FILE" "$backup"
echo "[INFO] Backup creado: $backup"

tmp="$(mktemp)"
cp "$ENV_FILE" "$tmp"

mapfile -t keys < <(grep -E '^[A-Z0-9_]+=' "$profile_file" | cut -d= -f1)
for key in "${keys[@]}"; do
  sed -i "/^${key}=/d" "$tmp"
done

{
  echo
  echo "# Applied profile: $profile ($(date -Iseconds))"
  cat "$profile_file"
} >>"$tmp"

mv "$tmp" "$ENV_FILE"
echo "[OK] Perfil aplicado en .env: $profile"

if grep -q '^MAXIMUN_RUNTIME_PROFILE=' "$ENV_FILE"; then
  active="$(grep '^MAXIMUN_RUNTIME_PROFILE=' "$ENV_FILE" | tail -n1 | cut -d= -f2-)"
  echo "[OK] Perfil activo: $active"
fi

echo
echo "Siguiente paso recomendado:"
echo "  ./ops/check_system_consistency.sh"
