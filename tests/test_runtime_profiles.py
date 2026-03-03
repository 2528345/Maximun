from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILES = [
    ROOT / "config/runtime_profiles/lenovo330s_stable.env",
    ROOT / "config/runtime_profiles/lenovo330s_engineering.env",
]

REQUIRED_KEYS = {
    "MAXIMUN_RUNTIME_PROFILE",
    "MAXIMUN_DATA_ROOT",
    "ENABLE_UI",
    "ENABLE_VISION",
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
    "MOONDREAM_ENABLED",
    "FASTER_WHISPER_MODEL",
    "STT_CPU_THREADS",
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
