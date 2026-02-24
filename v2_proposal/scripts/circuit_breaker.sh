#!/bin/sh
# MAXIMUN - Circuit Breaker SSD
# Protege el sistema moviendo logs o desmontando HDD si hay saturación.

SSD_MOUNT="/opt/maximun"
HDD_MOUNT="/mnt/hdd"
THRESHOLD_SSD=85
THRESHOLD_HDD=95
INTERVAL=30

echo "[CIRCUIT] Iniciando circuit breaker..."

while true; do
    # Uso SSD
    SSD_USED=$(df "$SSD_MOUNT" | awk 'NR==2 {print $5}' | sed 's/%//')
    
    # Uso HDD (si está montado)
    if mountpoint -q "$HDD_MOUNT" 2>/dev/null; then
        HDD_USED=$(df "$HDD_MOUNT" | awk 'NR==2 {print $5}' | sed 's/%//')
    else
        HDD_USED=0
    fi

    # SSD casi lleno → mover logs viejos
    if [ "$SSD_USED" -gt "$THRESHOLD_SSD" ]; then
        echo "[CIRCUIT] SSD >${THRESHOLD_SSD}% → moviendo logs antiguos"
        find "$SSD_MOUNT/logs" -name "*.log.*" -mtime +1 -type f \
            -exec mv {} "$HDD_MOUNT/rag/backups/" \; 2>/dev/null || true
        echo "[CIRCUIT] Logs movidos $(date)" >> "$SSD_MOUNT/logs/circuit.log"
    fi

    # HDD lleno o ausente → desmonta para proteger integridad
    if [ "$HDD_USED" -gt "$THRESHOLD_HDD" ] || ! mountpoint -q "$HDD_MOUNT"; then
        echo "[CIRCUIT] HDD problema → desmontando"
        umount -f "$HDD_MOUNT" 2>/dev/null || true
        echo "[CIRCUIT] HDD desmontado $(date)" >> "$SSD_MOUNT/logs/circuit.log"
    fi
    
    sleep "$INTERVAL"
done
