#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVICE_DIR="${HOME}/.config/systemd/user"
SERVICE_FILE="${SERVICE_DIR}/maximun-autocheck.service"

mkdir -p "$SERVICE_DIR"

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=MAXIMUN modular autocheck daemon
After=default.target

[Service]
Type=simple
WorkingDirectory=${ROOT_DIR}
ExecStart=/usr/bin/env bash -lc '${ROOT_DIR}/ops/autocheck_modules.sh --daemon'
Restart=always
RestartSec=5
Environment=AUTOCHECK_INTERVAL_SEC=25

[Install]
WantedBy=default.target
EOF

echo "[INFO] Servicio creado: ${SERVICE_FILE}"

if command -v systemctl >/dev/null 2>&1; then
  systemctl --user daemon-reload
  systemctl --user enable --now maximun-autocheck.service
  echo "[OK] Servicio habilitado e iniciado (usuario): maximun-autocheck.service"
  systemctl --user status --no-pager --lines=10 maximun-autocheck.service || true
else
  echo "[WARN] systemctl no disponible; instala/activa systemd user y ejecuta manualmente."
fi

