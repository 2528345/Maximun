#!/usr/bin/env bash
set -euo pipefail

# openSUSE MicroOS bootstrap helper for MAXIMUN V5.1
# Use --apply to run commands automatically (requires sudo privileges).

APPLY=false
if [[ "${1:-}" == "--apply" ]]; then
  APPLY=true
fi

cmds=(
  "sudo transactional-update dup"
  "sudo transactional-update pkg install podman podman-compose git curl jq awk sed grep coreutils shadow util-linux ripgrep unzip"
  "sudo transactional-update pkg install python311 python311-pip"
  "sudo transactional-update pkg install alsa-utils v4l-utils"
)

echo "== MAXIMUN V5.1 / openSUSE MicroOS bootstrap =="
echo "Host esperado: openSUSE MicroOS (inmutable)"
echo

if grep -qi opensuse /etc/os-release 2>/dev/null; then
  echo "[OK] openSUSE detectado"
else
  echo "[WARN] Este host no parece openSUSE"
fi

echo
if [[ "$APPLY" == true ]]; then
  echo "Aplicando bootstrap..."
  for c in "${cmds[@]}"; do
    echo "> $c"
    eval "$c"
  done
  echo
  echo "[INFO] Reinicia el sistema para aplicar cambios de transactional-update"
else
  echo "Comandos sugeridos:"
  for c in "${cmds[@]}"; do
    echo "  $c"
  done
  echo
  echo "Ejecuta este script con --apply cuando quieras automatizar:"
  echo "  ./ops/microos_bootstrap.sh --apply"
fi
