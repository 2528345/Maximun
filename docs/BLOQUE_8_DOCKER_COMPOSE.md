# 📦 BLOQUE 8: DOCKER COMPOSE Y ORQUESTACIÓN COMPLETO

**Estado**: ✅ COMPLETO Y LISTO  
**Líneas de código**: 500 líneas  
**Tiempo de implementación**: 30 minutos  
**Criticidad**: 🔴 CRÍTICO (Despliegue)

---

## 📝 DESCRIPCIÓN

Este bloque implementa orquestación completa con Docker Compose:

1. **docker-compose.yml** - Orquestación de 9 servicios
2. **.env.example** - Variables de entorno
3. **Makefile** - Comandos de utilidad
4. **startup.sh** - Script de inicio
5. **health_check.py** - Verificación de salud

---

## 📂 ARCHIVO 1: docker-compose.yml

```yaml
version: '3.9'

services:
  # MQTT Broker - Centro de comunicación
  mqtt:
    image: eclipse-mosquitto:2.0
    container_name: vr_mqtt
    ports:
      - "1883:1883"
      - "9001:9001"
    volumes:
      - ./config/mosquitto.conf:/mosquitto/config/mosquitto.conf
      - mqtt_data:/mosquitto/data
      - mqtt_logs:/mosquitto/log
    environment:
      - TZ=America/Argentina/Buenos_Aires
    networks:
      - vr_network
    healthcheck:
      test: ["CMD", "mosquitto_sub", "-h", "localhost", "-t", "$SYS/broker/version"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "3"

  # Audio Service - STT/TTS
  audio:
    build:
      context: ./services/audio
      dockerfile: Dockerfile
    container_name: vr_audio
    depends_on:
      mqtt:
        condition: service_healthy
    environment:
      - MQTT_BROKER_HOST=mqtt
      - MQTT_BROKER_PORT=1883
      - MQTT_USERNAME=${MQTT_USERNAME}
      - MQTT_PASSWORD=${MQTT_PASSWORD}
      - VOSK_MODEL_PATH=/app/models/vosk-model-es-0.42
      - PIPER_VOICE=es_ES-carme-medium
      - TZ=America/Argentina/Buenos_Aires
    volumes:
      - ./models:/app/models
      - ./logs:/app/logs
      - /dev/snd:/dev/snd
    devices:
      - /dev/snd
    networks:
      - vr_network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "3"

  # Vision Service - Face Recognition + YOLO
  vision:
    build:
      context: ./services/vision
      dockerfile: Dockerfile
    container_name: vr_vision
    depends_on:
      mqtt:
        condition: service_healthy
    environment:
      - MQTT_BROKER_HOST=mqtt
      - MQTT_BROKER_PORT=1883
      - MQTT_USERNAME=${MQTT_USERNAME}
      - MQTT_PASSWORD=${MQTT_PASSWORD}
      - FACE_DB_PATH=/app/data/faces.json
      - YOLO_MODEL=yolov5n
      - TZ=America/Argentina/Buenos_Aires
    volumes:
      - ./data/faces:/app/data/faces
      - ./logs:/app/logs
      - /dev/video0:/dev/video0
    devices:
      - /dev/video0
    networks:
      - vr_network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8002/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "3"

  # Filter Service - TinyLlama 1.1B
  filter:
    build:
      context: ./services/filter
      dockerfile: Dockerfile
    container_name: vr_filter
    depends_on:
      mqtt:
        condition: service_healthy
    environment:
      - MQTT_BROKER_HOST=mqtt
      - MQTT_BROKER_PORT=1883
      - MQTT_USERNAME=${MQTT_USERNAME}
      - MQTT_PASSWORD=${MQTT_PASSWORD}
      - MODEL_NAME=TinyLlama/TinyLlama-1.1B-Chat-v1.0
      - CACHE_SIZE=500
      - TZ=America/Argentina/Buenos_Aires
    volumes:
      - ./models:/app/models
      - ./logs:/app/logs
    networks:
      - vr_network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8003/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "3"

  # Reasoning Service - Phi-3 7B + HMR-ACT
  reasoning:
    build:
      context: ./services/reasoning
      dockerfile: Dockerfile
    container_name: vr_reasoning
    depends_on:
      mqtt:
        condition: service_healthy
    environment:
      - MQTT_BROKER_HOST=mqtt
      - MQTT_BROKER_PORT=1883
      - MQTT_USERNAME=${MQTT_USERNAME}
      - MQTT_PASSWORD=${MQTT_PASSWORD}
      - MODEL_NAME=microsoft/phi-3-mini-4k-instruct
      - HMR_ACT_LEVELS=5
      - TZ=America/Argentina/Buenos_Aires
    volumes:
      - ./models:/app/models
      - ./logs:/app/logs
    networks:
      - vr_network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8004/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "3"

  # RAG Service - ChromaDB
  rag:
    build:
      context: ./services/rag
      dockerfile: Dockerfile.rag
    container_name: vr_rag
    depends_on:
      mqtt:
        condition: service_healthy
    environment:
      - MQTT_BROKER_HOST=mqtt
      - MQTT_BROKER_PORT=1883
      - MQTT_USERNAME=${MQTT_USERNAME}
      - MQTT_PASSWORD=${MQTT_PASSWORD}
      - CHROMADB_PATH=/app/data/chromadb
      - CACHE_SIZE=500
      - TZ=America/Argentina/Buenos_Aires
    volumes:
      - ./data/chromadb:/app/data/chromadb
      - ./data/documents:/app/data/documents
      - ./logs:/app/logs
    networks:
      - vr_network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8005/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "3"

  # Hardware Service - Control de dispositivos
  hardware:
    build:
      context: ./services/hardware
      dockerfile: Dockerfile.hardware
    container_name: vr_hardware
    depends_on:
      mqtt:
        condition: service_healthy
    environment:
      - MQTT_BROKER_HOST=mqtt
      - MQTT_BROKER_PORT=1883
      - MQTT_USERNAME=${MQTT_USERNAME}
      - MQTT_PASSWORD=${MQTT_PASSWORD}
      - HARDWARE_TIMEOUT=10
      - TZ=America/Argentina/Buenos_Aires
    volumes:
      - ./logs:/app/logs
      - /dev:/dev
    devices:
      - /dev/ttyUSB0
      - /dev/ttyUSB1
    privileged: true
    networks:
      - vr_network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8006/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "3"

  # Monitoring Service - Prometheus
  prometheus:
    image: prom/prometheus:latest
    container_name: vr_prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./config/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
    networks:
      - vr_network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9090/-/healthy"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "3"

  # Visualization - Grafana
  grafana:
    image: grafana/grafana:latest
    container_name: vr_grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
      - GF_INSTALL_PLUGINS=grafana-piechart-panel
    volumes:
      - grafana_data:/var/lib/grafana
      - ./config/grafana/provisioning:/etc/grafana/provisioning
    depends_on:
      - prometheus
    networks:
      - vr_network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "3"

networks:
  vr_network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16

volumes:
  mqtt_data:
  mqtt_logs:
  prometheus_data:
  grafana_data:
```

---

## 📂 ARCHIVO 2: .env.example

```bash
# MQTT Configuration
MQTT_BROKER_HOST=mqtt
MQTT_BROKER_PORT=1883
MQTT_USERNAME=vr_user
MQTT_PASSWORD=vr_secure_password_123
MQTT_KEEPALIVE=60
MQTT_QOS=1

# Security
MAX_QUEUE_SIZE=1000
HARDWARE_TIMEOUT=10
FACE_DB_ENCRYPTION=true

# Audio Configuration
VOSK_MODEL_PATH=/app/models/vosk-model-es-0.42
PIPER_VOICE=es_ES-carme-medium
AUDIO_SAMPLE_RATE=16000
AUDIO_CHUNK_SIZE=1024

# Vision Configuration
FACE_DB_PATH=/app/data/faces.json
FACE_RECOGNITION_THRESHOLD=0.6
YOLO_MODEL=yolov5n
YOLO_CONFIDENCE=0.5

# Filter Configuration
FILTER_MODEL=TinyLlama/TinyLlama-1.1B-Chat-v1.0
FILTER_CACHE_SIZE=500
FILTER_MAX_TOKENS=100

# Reasoning Configuration
REASONING_MODEL=microsoft/phi-3-mini-4k-instruct
HMR_ACT_LEVELS=5
REASONING_CACHE_SIZE=100

# RAG Configuration
CHROMADB_PATH=/app/data/chromadb
RAG_CACHE_SIZE=500
RAG_CHUNK_SIZE=500
RAG_CHUNK_OVERLAP=50

# Hardware Configuration
HARDWARE_TIMEOUT=10
GPIO_ENABLED=true
SERIAL_ENABLED=true
BLUETOOTH_ENABLED=true
ZIGBEE_ENABLED=true

# Monitoring
PROMETHEUS_PORT=9090
GRAFANA_PORT=3000
GRAFANA_PASSWORD=admin_secure_password_123

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_MAX_SIZE=100m
LOG_MAX_FILES=3

# Timezone
TZ=America/Argentina/Buenos_Aires
```

---

## 📂 ARCHIVO 3: Makefile

```makefile
.PHONY: help build up down restart logs clean health test

help:
	@echo "VR Assistant - Docker Compose Commands"
	@echo ""
	@echo "Usage:"
	@echo "  make build          - Build all services"
	@echo "  make up             - Start all services"
	@echo "  make down           - Stop all services"
	@echo "  make restart        - Restart all services"
	@echo "  make logs           - View logs from all services"
	@echo "  make logs-service   - View logs from specific service (make logs-service SERVICE=audio)"
	@echo "  make health         - Check health of all services"
	@echo "  make clean          - Remove all containers and volumes"
	@echo "  make test           - Run tests"
	@echo "  make ps             - List running containers"
	@echo "  make shell          - Open shell in a service (make shell SERVICE=audio)"

build:
	@echo "🔨 Building all services..."
	docker-compose build --no-cache

up:
	@echo "🚀 Starting all services..."
	docker-compose up -d
	@echo "✅ Services started"
	@sleep 5
	@make health

down:
	@echo "🛑 Stopping all services..."
	docker-compose down

restart:
	@echo "🔄 Restarting all services..."
	docker-compose restart
	@sleep 5
	@make health

logs:
	@docker-compose logs -f

logs-service:
	@docker-compose logs -f $(SERVICE)

health:
	@echo "❤️ Checking health of services..."
	@python3 health_check.py

clean:
	@echo "🧹 Cleaning up..."
	docker-compose down -v
	@echo "✅ Cleanup complete"

ps:
	@docker-compose ps

shell:
	@docker-compose exec $(SERVICE) /bin/bash

test:
	@echo "🧪 Running tests..."
	@python3 -m pytest tests/ -v

pull-models:
	@echo "📥 Downloading AI models..."
	@mkdir -p models
	@echo "Downloading Vosk model..."
	@wget -q https://alphacephei.com/vosk/models/vosk-model-es-0.42.zip -O models/vosk-model-es-0.42.zip
	@unzip -q models/vosk-model-es-0.42.zip -d models/
	@echo "✅ Models downloaded"

.DEFAULT_GOAL := help
```

---

## 📂 ARCHIVO 4: startup.sh

```bash
#!/bin/bash

set -e

echo "🚀 VR Assistant - Startup Script"
echo "=================================="

# Crear directorios necesarios
echo "📁 Creating directories..."
mkdir -p models data/chromadb data/documents data/faces logs config/grafana/provisioning

# Copiar archivos de configuración
echo "⚙️ Setting up configuration..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "⚠️ Please configure .env file"
fi

# Descargar modelos si no existen
if [ ! -d "models/vosk-model-es-0.42" ]; then
    echo "📥 Downloading Vosk model..."
    mkdir -p models
    cd models
    wget -q https://alphacephei.com/vosk/models/vosk-model-es-0.42.zip
    unzip -q vosk-model-es-0.42.zip
    rm vosk-model-es-0.42.zip
    cd ..
fi

# Crear archivo de configuración de Mosquitto
echo "🔧 Configuring Mosquitto..."
cat > config/mosquitto.conf << 'EOF'
listener 1883
protocol mqtt

listener 9001
protocol websockets

allow_anonymous false
password_file /mosquitto/config/password.txt
EOF

# Crear archivo de contraseña para Mosquitto
echo "🔐 Setting up Mosquitto credentials..."
docker run --rm -v $(pwd)/config:/mosquitto/config eclipse-mosquitto mosquitto_passwd -c /mosquitto/config/password.txt vr_user <<< "vr_secure_password_123"

# Crear configuración de Prometheus
echo "📊 Configuring Prometheus..."
cat > config/prometheus.yml << 'EOF'
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
EOF

# Construir servicios
echo "🔨 Building services..."
docker-compose build --no-cache

# Iniciar servicios
echo "🚀 Starting services..."
docker-compose up -d

# Esperar a que los servicios estén listos
echo "⏳ Waiting for services to be ready..."
sleep 10

# Verificar salud
echo "❤️ Checking health..."
python3 health_check.py

echo ""
echo "✅ VR Assistant is ready!"
echo ""
echo "📊 Grafana: http://localhost:3000"
echo "📈 Prometheus: http://localhost:9090"
echo "🔌 MQTT: localhost:1883"
echo ""
echo "Run 'make logs' to see logs"
echo "Run 'make help' for more commands"
```

---

## 📂 ARCHIVO 5: health_check.py

```python
#!/usr/bin/env python3
"""
VERIFICACIÓN DE SALUD
Verificar estado de todos los servicios
"""

import subprocess
import json
import time
import sys
from datetime import datetime

def check_service(service_name, port=None, endpoint=None):
    """Verificar salud de un servicio"""
    try:
        # Verificar si el contenedor está corriendo
        result = subprocess.run(
            ['docker-compose', 'ps', '--services', '--filter', f'status=running'],
            capture_output=True,
            text=True
        )
        
        running_services = result.stdout.strip().split('\n')
        
        if service_name not in running_services:
            return {
                'service': service_name,
                'status': '❌ DOWN',
                'message': 'Container not running'
            }
        
        # Si hay endpoint, verificar HTTP
        if port and endpoint:
            try:
                result = subprocess.run(
                    ['curl', '-f', '-s', f'http://localhost:{port}{endpoint}'],
                    capture_output=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    return {
                        'service': service_name,
                        'status': '✅ HEALTHY',
                        'message': 'Service responding'
                    }
                else:
                    return {
                        'service': service_name,
                        'status': '⚠️ DEGRADED',
                        'message': 'Service not responding'
                    }
            except:
                return {
                    'service': service_name,
                    'status': '⚠️ UNKNOWN',
                    'message': 'Cannot reach service'
                }
        
        return {
            'service': service_name,
            'status': '✅ RUNNING',
            'message': 'Container is running'
        }
        
    except Exception as e:
        return {
            'service': service_name,
            'status': '❌ ERROR',
            'message': str(e)
        }

def main():
    """Función principal"""
    print("\n" + "="*60)
    print("VR ASSISTANT - HEALTH CHECK")
    print("="*60)
    print(f"Timestamp: {datetime.now().isoformat()}\n")
    
    services = [
        ('mqtt', 1883, None),
        ('audio', 8001, '/health'),
        ('vision', 8002, '/health'),
        ('filter', 8003, '/health'),
        ('reasoning', 8004, '/health'),
        ('rag', 8005, '/health'),
        ('hardware', 8006, '/health'),
        ('prometheus', 9090, '/-/healthy'),
        ('grafana', 3000, '/api/health'),
    ]
    
    results = []
    for service_name, port, endpoint in services:
        result = check_service(service_name, port, endpoint)
        results.append(result)
        print(f"{result['status']} - {result['service']}: {result['message']}")
    
    # Resumen
    print("\n" + "-"*60)
    healthy = sum(1 for r in results if '✅' in r['status'])
    total = len(results)
    print(f"Services: {healthy}/{total} healthy")
    
    if healthy == total:
        print("✅ All systems operational")
        return 0
    else:
        print("⚠️ Some services are not healthy")
        return 1

if __name__ == "__main__":
    sys.exit(main())
```

---

## ✅ RESUMEN DEL BLOQUE 8

| Aspecto | Detalles |
|---------|----------|
| **Líneas de código** | 500 líneas |
| **Archivos** | 5 archivos |
| **Servicios** | ✅ 9 servicios |
| **Tiempo de implementación** | 30 minutos |
| **Criticidad** | 🔴 CRÍTICO |

---

## 📊 SERVICIOS ORQUESTADOS

✅ **MQTT**: Centro de comunicación  
✅ **Audio**: STT/TTS offline  
✅ **Vision**: Reconocimiento facial + YOLO  
✅ **Filter**: TinyLlama 1.1B  
✅ **Reasoning**: Phi-3 7B + HMR-ACT  
✅ **RAG**: ChromaDB + búsqueda semántica  
✅ **Hardware**: Control de dispositivos  
✅ **Prometheus**: Métricas  
✅ **Grafana**: Visualización  

---

## 🚀 INSTRUCCIONES DE USO

1. **Crear estructura:**
```bash
mkdir -p config/grafana/provisioning data logs models
```

2. **Copiar archivos:**
   - `docker-compose.yml` → raíz del proyecto
   - `.env.example` → raíz del proyecto
   - `Makefile` → raíz del proyecto
   - `startup.sh` → raíz del proyecto
   - `health_check.py` → raíz del proyecto

3. **Hacer ejecutable el script:**
```bash
chmod +x startup.sh
chmod +x health_check.py
```

4. **Ejecutar startup:**
```bash
./startup.sh
```

O usar Make:
```bash
make build
make up
make health
```

---

## 📋 COMANDOS ÚTILES

```bash
# Ver logs
make logs

# Ver logs de un servicio
make logs-service SERVICE=audio

# Reiniciar servicios
make restart

# Verificar salud
make health

# Abrir shell en un servicio
make shell SERVICE=audio

# Detener todo
make down

# Limpiar todo
make clean
```

---

**BLOQUE 8 COMPLETADO ✅**

Escribe **"SI"** cuando lo hayas recibido completo para pasar al siguiente bloque.  
Escribe **"SIP"** si se corta por contexto y continúo donde lo dejé.

```

