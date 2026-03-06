# Guia Completa De Instalacion Y Despliegue (Novatos) - MAXIMUN V5.1

Esta guia esta pensada para alguien sin experiencia previa en Linux/containers.

Objetivo:
- Instalar el sistema en openSUSE MicroOS.
- Dejarlo funcionando offline con RAG.
- Entender el por que de cada paso.

---

## 1) Que necesitas antes de empezar

1. Laptop con openSUSE MicroOS instalado.
   - Por que: los scripts usan `transactional-update` (propio de MicroOS).
2. ZIP del proyecto en USB o repo clonado.
   - Por que: el instalador USB trabaja desde `.zip`.
3. Conexion a internet al inicio.
   - Por que: descargar paquetes/dependencias.
4. Modelos locales (`.gguf`, `.onnx`) descargados por separado.
   - Por que: no se guardan en Git por peso.

---

## 2) Mapa rapido del proyecto

```bash
/root/codex
├── docker-compose.yml
├── gateway-mqtt/
├── services/
│   ├── cognitive-core/
│   ├── audio-interface/
│   ├── vision-cortex/
│   ├── rag-core/
│   └── iot-gateway/
├── dashboard/
├── ops/
├── config/runtime_profiles/
├── docs/
└── tests/
```

Scripts mas importantes:
- `ops/install_from_usb.sh`
- `ops/microos_bootstrap.sh`
- `ops/deploy_microos.sh`
- `ops/preflight_host_check.sh`
- `ops/test_by_module.sh`

---

## 3) Instalacion recomendada desde USB (2 etapas)

### Etapa 1: preparar host

```bash
cd /ruta/del/proyecto
./ops/install_from_usb.sh --prepare --zip /run/media/$USER/TU_USB/Maximun_V5.1_USB_Installer_3620e93.zip
```

Que hace:
- Instala base del host con `transactional-update`.
- Guarda estado para continuar luego del reinicio.

### Reinicia el sistema

Por que:
- MicroOS aplica cambios tras reinicio.

### Etapa 2: desplegar

Opcion A (recomendada, clave MQTT manual):

```bash
./ops/install_from_usb.sh --resume --mqtt-password 'TuClaveMuyLargaSegura_123456'
```

Opcion B (automatica):

```bash
./ops/install_from_usb.sh --resume
```

Si no pasas clave:
- El script genera una clave fuerte automaticamente.
- La guarda en:
  - `/opt/maximun/Maximun_V5.1/.mqtt_credentials.local`

---

## 4) Como cambiar la clave MQTT manualmente

Si prefieres hacerlo a mano:

1. Crear `.env`:

```bash
cp .env.example .env
```

2. Editar:

```bash
nano .env
```

3. Ajustar:
- `MQTT_PASSWORD=<clave fuerte de 16+ caracteres>`
- `MQTT_ENFORCE_STRONG_PASSWORD=true`
- (opcional avanzado) usuarios por rol MQTT:
  - `MQTT_CORE_USERNAME`, `MQTT_AUDIO_USERNAME`, `MQTT_VISION_USERNAME`, `MQTT_RAG_USERNAME`, `MQTT_IOT_USERNAME`, `MQTT_DASHBOARD_USERNAME`, `MQTT_OPS_USERNAME`
  - por defecto todos usan la misma clave segura que `MQTT_PASSWORD`

4. Validar:

```bash
./ops/preflight_host_check.sh
```

Si falla:
- revisa warnings y corrige.

---

## 5) Estructura de almacenamiento y modelos

Crear rutas base:

```bash
sudo mkdir -p /opt/maximun/data/{models_cache,projects,rag_store}
sudo mkdir -p /opt/maximun/data/rag_store/{docs,logs,models,chroma}
```

Copiar modelos a:
- `/opt/maximun/data/models_cache`

Modelos esperados:
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

---

## 6) Despliegue manual (si no usas instalador USB)

```bash
cp .env.example .env
./ops/apply_runtime_profile.sh lenovo330s_stable
./ops/storage_tier_setup.sh
./ops/check_system_consistency.sh || true
./ops/preflight_host_check.sh
./ops/deploy_microos.sh --profile lenovo330s_stable
```

---

## 7) Verificacion despues del despliegue

1. Estado contenedores:

```bash
podman compose ps
```

2. Pruebas:

```bash
./ops/self_test.sh
./ops/mqtt_smoke_test.sh
./ops/test_by_module.sh
```

3. Dashboard (si `ENABLE_UI=true`):
- `http://localhost:5173`

---

## 8) Seguridad implementada (resumen simple)

1. RAG restringe rutas: solo indexa dentro de `RAG_DOCS_PATH`.
2. Dashboard usa autenticacion MQTT (usuario/clave).
3. Broker MQTT usa ACL por rol (`MQTT_ENABLE_ACL=true`) para minimo privilegio.
4. Broker puede bloquear claves debiles con `MQTT_ENFORCE_STRONG_PASSWORD=true`.
5. Preflight detecta clave MQTT por defecto y falla para evitar despliegue inseguro.

---

## 9) Dependencias y enlaces oficiales

1. openSUSE MicroOS:
   - https://microos.opensuse.org/
2. Podman:
   - https://podman.io/docs
3. Mosquitto MQTT:
   - https://mosquitto.org/documentation/
4. paho-mqtt:
   - https://github.com/eclipse-paho/paho.mqtt.python
5. llama-cpp-python:
   - https://github.com/abetlen/llama-cpp-python
6. faster-whisper:
   - https://github.com/SYSTRAN/faster-whisper
7. Piper:
   - https://github.com/rhasspy/piper
8. ChromaDB:
   - https://docs.trychroma.com/
9. sentence-transformers:
   - https://www.sbert.net/
10. Bleak:
    - https://bleak.readthedocs.io/
11. pySerial:
    - https://pyserial.readthedocs.io/
12. MinimalModbus:
    - https://minimalmodbus.readthedocs.io/
13. python-opcua:
    - https://github.com/FreeOpcUa/python-opcua
14. python-can:
    - https://python-can.readthedocs.io/

---

## 10) Checklist final (ultra corto)

1. Instalar host.
2. Configurar `.env` y clave MQTT fuerte.
3. Preparar storage.
4. Copiar modelos.
5. Ejecutar preflight.
6. Desplegar.
7. Probar modulos.

Si falla algo:
- `./ops/preflight_host_check.sh`
- `./ops/check_system_consistency.sh`
- `./ops/module_control.sh logs <servicio>`
