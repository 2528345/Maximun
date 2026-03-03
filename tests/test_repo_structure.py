from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "docker-compose.yml",
    "README.md",
    "ops/preflight_host_check.sh",
    "ops/check_system_consistency.sh",
    "ops/apply_runtime_profile.sh",
    "ops/storage_tier_setup.sh",
    "ops/generate_model_checksums.sh",
    "ops/test_by_module.sh",
    "ops/microos_bootstrap.sh",
    "ops/deploy_microos.sh",
    "ops/module_control.sh",
    "config/runtime_profiles/lenovo330s_stable.env",
    "config/runtime_profiles/lenovo330s_engineering.env",
    "services/cognitive-core/app/main.py",
    "services/audio-interface/app/main.py",
    "services/vision-cortex/app/main.py",
    "services/rag-core/app/main.py",
    "services/rag-core/app/self_protection.py",
    "gateway-mqtt/mosquitto.conf",
]


def test_required_files_exist() -> None:
    missing = [p for p in REQUIRED_FILES if not (ROOT / p).exists()]
    assert not missing, f"Missing files: {missing}"
