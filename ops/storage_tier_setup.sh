#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"

DATA_ROOT_DEFAULT="/opt/maximun/data"
RAG_RAM_CACHE_DEFAULT="/dev/shm/maximun_rag_cache"
RAG_SSD_BUDGET_GB_DEFAULT=80

data_root="$DATA_ROOT_DEFAULT"
rag_ram_cache="$RAG_RAM_CACHE_DEFAULT"
ssd_budget_gb="$RAG_SSD_BUDGET_GB_DEFAULT"

if [[ -f "$ENV_FILE" ]]; then
  env_data_root="$(grep '^MAXIMUN_DATA_ROOT=' "$ENV_FILE" | tail -n1 | cut -d= -f2- || true)"
  env_ram_cache="$(grep '^RAG_RAM_CACHE_PATH=' "$ENV_FILE" | tail -n1 | cut -d= -f2- || true)"
  env_budget="$(grep '^RAG_SSD_BUDGET_GB=' "$ENV_FILE" | tail -n1 | cut -d= -f2- || true)"
  [[ -n "$env_data_root" ]] && data_root="$env_data_root"
  [[ -n "$env_ram_cache" ]] && rag_ram_cache="$env_ram_cache"
  [[ -n "$env_budget" ]] && ssd_budget_gb="$env_budget"
fi

ok() { echo "[OK]   $*"; }
warn() { echo "[WARN] $*"; }
info() { echo "[INFO] $*"; }

info "Data root: $data_root"
info "RAG RAM cache: $rag_ram_cache"
info "RAG SSD budget objetivo: ${ssd_budget_gb}GB"

mkdir -p "$data_root/models_cache"
mkdir -p "$data_root/projects"
mkdir -p "$data_root/rag_store/chroma"
mkdir -p "$data_root/rag_store/docs"
mkdir -p "$data_root/rag_store/logs"
mkdir -p "$data_root/rag_store/models"
ok "Estructura SSD creada en $data_root"

mkdir -p "$rag_ram_cache"
ok "Cache RAM creada en $rag_ram_cache"

if command -v df >/dev/null 2>&1; then
  free_gb="$(df -BG "$data_root" | awk 'NR==2 {gsub("G", "", $4); print $4+0}')"
  if [[ -n "$free_gb" ]]; then
    if (( free_gb >= ssd_budget_gb )); then
      ok "Espacio libre SSD ${free_gb}GB (>= ${ssd_budget_gb}GB)"
    else
      warn "Espacio libre SSD ${free_gb}GB (< ${ssd_budget_gb}GB)"
    fi
  fi
fi

if command -v lsblk >/dev/null 2>&1; then
  dev="$(df -P "$data_root" | awk 'NR==2 {print $1}')"
  if [[ -n "$dev" ]]; then
    rota="$(lsblk -no ROTA "$dev" 2>/dev/null | head -n1 || true)"
    if [[ "$rota" == "0" ]]; then
      ok "Particion de datos detectada en SSD/NVMe (ROTA=0)"
    elif [[ "$rota" == "1" ]]; then
      warn "Particion de datos en disco rotacional (ROTA=1)"
    else
      warn "No se pudo determinar tipo de disco para $dev"
    fi
  fi
fi

echo
echo "Sugerencia:"
echo "  ./ops/check_system_consistency.sh"
echo "  ./ops/preflight_host_check.sh"
