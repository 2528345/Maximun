from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = ROOT / "docker-compose.yml"


def _load_compose() -> dict:
    return yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))


def test_expected_services_present() -> None:
    compose = _load_compose()
    services = compose.get("services", {})
    expected = {
        "gateway-mqtt",
        "cognitive-core",
        "audio-interface",
        "vision-cortex",
        "rag-core",
        "iot-gateway",
        "dashboard",
    }
    assert expected.issubset(set(services.keys()))


def test_resource_limits_match_v51() -> None:
    compose = _load_compose()
    s = compose["services"]

    assert s["cognitive-core"]["mem_limit"] == "6500m"
    assert s["cognitive-core"]["cpus"] == "3.50"

    assert s["vision-cortex"]["mem_limit"] == "800m"
    assert s["vision-cortex"]["cpus"] == "0.50"

    assert s["audio-interface"]["mem_limit"] == "600m"
    assert s["audio-interface"]["cpus"] == "0.50"

    assert s["gateway-mqtt"]["mem_limit"] == "100m"
    assert s["gateway-mqtt"]["cpus"] == "0.10"

    assert s["iot-gateway"]["mem_limit"] == "220m"
    assert s["iot-gateway"]["cpus"] == "0.35"


def test_critical_mounts_exist() -> None:
    compose = _load_compose()
    s = compose["services"]

    cc_vols = "\n".join(s["cognitive-core"].get("volumes", []))
    assert "models_cache:/models_cache:ro" in cc_vols
    assert "projects:/output:rw" in cc_vols
    assert "rag_store:/rag_store:rw" in cc_vols
