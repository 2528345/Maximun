# openSUSE MicroOS Runbook (Lenovo 330s, 8GB RAM)

## Scope

This runbook is tuned for:

- Host OS: openSUSE MicroOS
- CPU: Intel i5 with AVX2
- RAM: 8GB
- Goal: offline runtime with strict memory limits

## 1) Bootstrap host

```bash
cd /root/codex
./ops/microos_bootstrap.sh
# Optional auto-apply (requires sudo)
# ./ops/microos_bootstrap.sh --apply
```

After `transactional-update`, reboot host.

## 2) Host permissions and data layout

```bash
./ops/host_permissions.sh
sudo mkdir -p /opt/maximun/data/models_cache
sudo mkdir -p /opt/maximun/data/projects
sudo mkdir -p /opt/maximun/data/rag_store
sudo mkdir -p /opt/maximun/data/rag_store/docs
```

## 3) Copy required models

Place these files in `/opt/maximun/data/models_cache`:

- `qwen-2.5-1.5b-instruct.gguf`
- `deepseek-r1-distill-qwen-1.5b.gguf`
- `glm-4-9b-chat-iq4_xs.gguf`
- `yolov8n.onnx`
- `moondream2-text-model-f16.gguf`
- `moondream2-mmproj-f16.gguf`
- `es_ES-sharvard-medium.onnx`

## 4) Deploy

```bash
cp .env.example .env
./ops/apply_runtime_profile.sh lenovo330s_stable
./ops/storage_tier_setup.sh
./ops/check_system_consistency.sh || true
./ops/deploy_microos.sh
```

Default deploy in 8GB mode starts only core services.
To enable optional modules edit `.env`:

- `ENABLE_UI=true`
- `ENABLE_VISION=true`

For heavier coding sessions:

```bash
./ops/apply_runtime_profile.sh lenovo330s_engineering
./ops/storage_tier_setup.sh
./ops/deploy_microos.sh --profile lenovo330s_engineering
```

## 4.1) RAG document ingestion path

- Put project knowledge files here:
  - `/opt/maximun/data/rag_store/docs`
- Supported formats:
  - `pdf`, `md`, `markdown`, `txt`, `rst`
- Trigger ingestion via MQTT topic:
  - `cognition/rag/ingest_path`

## 5) Validate module workflow

```bash
./ops/test_by_module.sh
```

## 6) Resource safety model

- Qwen stays resident as L1.
- DeepSeek and GLM are hot-swapped.
- Moondream deliberate analysis is blocked under RAM interlock when GLM is active and free RAM is below threshold.
- Audio STT pauses during engineering mode (`system/resource/pause`).

## 7) Module operations

```bash
./ops/module_control.sh status all
./ops/module_control.sh logs cognitive-core
./ops/module_control.sh restart audio-interface
```

## 8) Known constraints on 8GB

- GLM engineering passes are CPU-bound and can be slow.
- Keep swap enabled on SSD.
- Avoid running extra desktop-heavy workloads while engineering mode is active.
