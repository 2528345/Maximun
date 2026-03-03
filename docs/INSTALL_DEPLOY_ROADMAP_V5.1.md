# MAXIMUN V5.1 - Hoja De Ruta Completa (Instalacion y Despliegue)

## 0) Objetivo operativo

Desplegar una arquitectura offline en Lenovo 330s (i5, 8GB RAM) con:

- Bus MQTT central
- Orquestacion cognitiva HMR (Qwen + DeepSeek + GLM)
- Audio local (Faster-Whisper + Piper)
- RAG local en SSD/HDD
- Vision opcional
- IoT Gateway opcional (Bluetooth, Zigbee, Modbus, OPC UA, CAN)

## 1) Pre-requisitos host (openSUSE MicroOS)

1. Instalar openSUSE MicroOS y reiniciar.
2. Preparar paquetes base:

```bash
cd /root/codex
./ops/microos_bootstrap.sh
# Aplicacion automatica opcional (requiere sudo):
# ./ops/microos_bootstrap.sh --apply
```

3. Configurar permisos de dispositivos:

```bash
./ops/host_permissions.sh
```

4. (Opcional) generar certificados TLS para MQTT:

```bash
./ops/generate_mqtt_tls_certs.sh
```

## 1.1) Instalacion automatizada desde USB (zip)

Para un host limpio puedes usar el instalador en 2 etapas:

```bash
# Etapa 1: instala base del host y deja estado
./ops/install_from_usb.sh --prepare --zip /run/media/$USER/USB/Maximun_V5.1_full_with_local.zip

# Reinicia el host (MicroOS aplica transactional-update al reiniciar)

# Etapa 2: extrae zip, aplica perfil, valida y despliega
./ops/install_from_usb.sh --resume
```

## 2) Estrategia de almacenamiento (SSD 256GB + HDD 1TB)

Recomendado para 8GB RAM:

- SSD: metadatos, cache RAG, logs y proyecto activo
- HDD: corpus documental masivo y backup de proyectos

Layout base compatible con compose:

```bash
sudo mkdir -p /opt/maximun/data/{models_cache,projects,rag_store}
sudo mkdir -p /opt/maximun/data/rag_store/{docs,logs,models,chroma}
```

Ajustar tiers (SSD + RAM cache):

```bash
./ops/storage_tier_setup.sh
```

Variables clave:

- `MAXIMUN_DATA_ROOT=/opt/maximun/data`
- `RAG_RAM_CACHE_PATH=/dev/shm/maximun_rag_cache`
- `RAG_SSD_BUDGET_GB=80` (subir o bajar segun espacio)

## 3) Carga de modelos reales

Copiar los artefactos a `/opt/maximun/data/models_cache`:

- `qwen-2.5-1.5b-instruct.gguf`
- `deepseek-r1-distill-qwen-1.5b.gguf`
- `glm-4-9b-chat-iq4_xs.gguf`
- `yolov8n.onnx`
- `moondream2-text-model-f16.gguf`
- `moondream2-mmproj-f16.gguf`
- `es_ES-sharvard-medium.onnx`

Generar checksums:

```bash
./ops/generate_model_checksums.sh
```

## 4) Configuracion runtime (perfil + .env)

1. Crear `.env`:

```bash
cp .env.example .env
```

2. Aplicar perfil recomendado (estable):

```bash
./ops/apply_runtime_profile.sh lenovo330s_stable
```

3. Si necesitas modo ingenieria:

```bash
./ops/apply_runtime_profile.sh lenovo330s_engineering
```

4. Activacion modular:

- `ENABLE_UI=true` para dashboard
- `ENABLE_VISION=true` para vision
- `ENABLE_IOT=true` para iot-gateway

5. Seguridad MQTT recomendada:

- `MQTT_ALLOW_ANONYMOUS=false`
- `MQTT_WS_ALLOW_ANONYMOUS=false`
- definir `MQTT_USERNAME` y `MQTT_PASSWORD`
- para TLS:
  - `MQTT_TLS_ENABLE=true`
  - `MQTT_CLIENT_TLS_ENABLE=true`
  - `MQTT_TLS_CA_FILE=/mosquitto/config/certs/ca.crt`
  - `MQTT_TLS_CERT_FILE=/mosquitto/config/certs/server.crt`
  - `MQTT_TLS_KEY_FILE=/mosquitto/config/certs/server.key`

## 5) Chequeos previos obligatorios

```bash
./ops/check_system_consistency.sh || true
./ops/preflight_host_check.sh
```

## 6) Despliegue

Despliegue guiado (aplica perfil, verifica y levanta servicios):

```bash
./ops/deploy_microos.sh
```

Despliegue con perfil explicito:

```bash
./ops/deploy_microos.sh --profile lenovo330s_stable
```

## 7) Modulo IoT (Bluetooth/Zigbee/Protocolos industriales)

Servicio: `services/iot-gateway`

### 7.1 Topicos MQTT

- Entrada:
  - `iot/gateway/command`
  - `iot/bluetooth/scan/request`
  - `iot/zigbee/scan/request`
  - `iot/industrial/request`
  - `system/resource/pause`
- Salida:
  - `system/iot/ready`
  - `system/iot/status`
  - `iot/gateway/response`
  - `perception/iot/bluetooth/devices`
  - `perception/iot/zigbee/devices`
  - `perception/iot/industrial/data`

### 7.2 Protocolos incluidos

- Bluetooth: escaneo BLE (`bleak`) con fallback simulado
- Zigbee: deteccion de coordinador/puertos seriales (`pyserial`) y fallback simulado
- Industriales:
  - Modbus RTU (`minimalmodbus`)
  - OPC UA (`opcua`)
  - CAN (`python-can`)

### 7.3 Configuracion minima en `.env`

```bash
ENABLE_IOT=true
IOT_SIMULATION=true
IOT_ENABLE_BLUETOOTH=true
IOT_ENABLE_ZIGBEE=true
IOT_ENABLE_INDUSTRIAL=true
IOT_ZIGBEE_SERIAL_PORT=/dev/ttyUSB1
IOT_MODBUS_SERIAL_PORT=/dev/ttyUSB2
IOT_CAN_CHANNEL=can0
IOT_CAN_INTERFACE=socketcan
```

### 7.4 Pruebas rapidas de IoT por MQTT

```bash
# Scan BLE
mosquitto_pub -h localhost -p 1883 -t iot/bluetooth/scan/request -m '{"request_id":"ble-1"}'

# Scan Zigbee
mosquitto_pub -h localhost -p 1883 -t iot/zigbee/scan/request -m '{"request_id":"zig-1"}'

# Modbus (simulado o real)
mosquitto_pub -h localhost -p 1883 -t iot/industrial/request -m '{"request_id":"mb-1","protocol":"modbus","register":100}'

# OPC UA
mosquitto_pub -h localhost -p 1883 -t iot/industrial/request -m '{"request_id":"opc-1","protocol":"opcua","node_id":"ns=2;i=2"}'

# CAN
mosquitto_pub -h localhost -p 1883 -t iot/industrial/request -m '{"request_id":"can-1","protocol":"can","operation":"read"}'
```

## 8) Validacion funcional (workflow local)

1. Smoke general:

```bash
./ops/self_test.sh
./ops/mqtt_smoke_test.sh
```

2. Validacion por modulo:

```bash
./ops/test_by_module.sh
```

3. Control runtime:

```bash
./ops/module_control.sh status all
./ops/module_control.sh logs iot-gateway
```

## 9) Criterios de estabilidad en 8GB

- Mantener `ENABLE_VISION=false` cuando ejecutes sesiones largas de GLM-4.
- Mantener `ENABLE_IOT=false` cuando no uses hardware externo.
- Usar `IOT_SIMULATION=true` para desarrollo desde laptop sin periféricos conectados.
- Mantener swap activa en SSD para hot-swap seguro.

## 10) GitHub workflow (CI)

El workflow (`.github/workflows/python-app.yml`) valida:

- flake8 sobre `services/`
- sintaxis bash de scripts `ops/`
- tests de contrato (`tests/`)

Comandos locales equivalentes:

```bash
pip install -r requirements-dev.txt
flake8 services --count --select=E9,F63,F7,F82 --show-source --statistics
flake8 services --count --exit-zero --max-complexity=12 --max-line-length=120 --statistics
pytest tests -q
```

## 11) Plan de rollback rapido

Si hay saturacion o fallo de modulo:

```bash
./ops/module_control.sh down iot-gateway
./ops/module_control.sh restart cognitive-core
```

Si necesitas volver a base minima:

```bash
./ops/module_control.sh down all
./ops/apply_runtime_profile.sh lenovo330s_stable
./ops/deploy_microos.sh
```
