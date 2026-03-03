#!/usr/bin/env bash
set -euo pipefail

# Preferimos grupos de dispositivo + udev en lugar de chmod 666 global.
sudo usermod -aG audio,video "$USER"

echo "Reglas udev sugeridas:"
echo 'SUBSYSTEM=="sound", GROUP="audio", MODE="0660"'
echo 'SUBSYSTEM=="video4linux", GROUP="video", MODE="0660"'
echo "Guarda en /etc/udev/rules.d/99-maximun-devices.rules y recarga con:"
echo "  sudo udevadm control --reload-rules && sudo udevadm trigger"
