from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILES = [
    ROOT / "config/runtime_profiles/lenovo330s_stable.env",
    ROOT / "config/runtime_profiles/lenovo330s_engineering.env",
    ROOT / "config/runtime_profiles/lenovo330s_mvp_production.env",
]

REQUIRED_KEYS = {
    "MAXIMUN_RUNTIME_PROFILE",
    "MAXIMUN_DATA_ROOT",
    "MQTT_PORT",
    "MQTT_WS_PORT",
    "MQTT_TLS_PORT",
    "MQTT_USERNAME",
    "MQTT_PASSWORD",
    "MQTT_ALLOW_ANONYMOUS",
    "MQTT_WS_ALLOW_ANONYMOUS",
    "MQTT_TLS_ENABLE",
    "MQTT_TLS_ALLOW_ANONYMOUS",
    "MQTT_TLS_CA_FILE",
    "MQTT_TLS_CERT_FILE",
    "MQTT_TLS_KEY_FILE",
    "MQTT_CLIENT_TLS_ENABLE",
    "MQTT_TLS_CA_CERT",
    "MQTT_TLS_CLIENT_CERT",
    "MQTT_TLS_CLIENT_KEY",
    "MQTT_TLS_INSECURE",
    "AUTOCHECK_INTERVAL_SEC",
    "AUTOCHECK_AUTOSTART",
    "ENABLE_UI",
    "ENABLE_VISION",
    "ENABLE_IOT",
    "RAM_BUDGET_MB",
    "RESERVE_RAM_MB",
    "LLM_THREADS",
    "LLM_BATCH",
    "GLM_CTX",
    "GLM_MAX_TOKENS",
    "RAG_ENABLED",
    "RAG_STORAGE_ROOT",
    "RAG_DOCS_PATH",
    "RAG_RAM_CACHE_PATH",
    "RAG_SSD_BUDGET_GB",
    "RAG_EMBED_BACKEND",
    "RAG_QUERY_CACHE_TTL_SEC",
    "IOT_SIMULATION",
    "IOT_ENABLE_BLUETOOTH",
    "IOT_ENABLE_ZIGBEE",
    "IOT_ENABLE_INDUSTRIAL",
    "IOT_STATUS_INTERVAL_SEC",
    "IOT_ZIGBEE_SERIAL_PORT",
    "IOT_MODBUS_SERIAL_PORT",
    "IOT_CAN_CHANNEL",
    "MOONDREAM_ENABLED",
    "FASTER_WHISPER_MODEL",
    "STT_CPU_THREADS",
    "SIGNATURE_ENFORCEMENT",
    "MODEL_CHECKSUM_FILE",
    "FAILSAFE_EXEC_MODE",
    "FAILSAFE_PODMAN_SERVICES",
    "SMART_CHECK_INTERVAL_SEC",
    "ENGINEERING_FEEDBACK_LOG",
    "REWARD_MEMORY_PATH",
}


def _parse_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip()
    return out


def test_profiles_exist() -> None:
    for profile in PROFILES:
        assert profile.exists(), f"Missing profile: {profile}"


def test_profiles_have_required_keys() -> None:
    for profile in PROFILES:
        content = _parse_env_file(profile)
        missing = sorted(REQUIRED_KEYS - set(content.keys()))
        assert not missing, f"{profile.name} missing keys: {missing}"
