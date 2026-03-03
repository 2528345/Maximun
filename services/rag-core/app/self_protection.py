from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import math
import os
import re
import secrets
import time
from collections import defaultdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List

try:
    from cryptography.fernet import Fernet

    FERNET_AVAILABLE = True
except ImportError:
    Fernet = None
    FERNET_AVAILABLE = False

try:
    from phe import paillier

    PAILLIER_AVAILABLE = True
except ImportError:
    paillier = None
    PAILLIER_AVAILABLE = False


logger = logging.getLogger("SelfProtection")


class ThreatLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EncryptionLevel(Enum):
    NONE = "none"
    STANDARD = "standard"
    HOMOMORPHIC_LIGHT = "hom_light"


class HomomorphicCounter:
    def __init__(self, key_bits: int = 1024) -> None:
        if not PAILLIER_AVAILABLE:
            raise RuntimeError("Paillier not available")
        self.public_key, self.private_key = paillier.generate_paillier_keypair(n_length=key_bits)
        self.encrypted_counters: Dict[str, Any] = {}

    def increment(self, counter_name: str, amount: int = 1) -> None:
        if counter_name not in self.encrypted_counters:
            self.encrypted_counters[counter_name] = self.public_key.encrypt(0)
        self.encrypted_counters[counter_name] += self.public_key.encrypt(int(amount))

    def get_value(self, counter_name: str) -> int:
        if counter_name not in self.encrypted_counters:
            return 0
        return int(self.private_key.decrypt(self.encrypted_counters[counter_name]))

    def compare_threshold(self, counter_name: str, threshold: int) -> bool:
        return self.get_value(counter_name) >= int(threshold)


class SecureMetricsAggregator:
    def __init__(self) -> None:
        self.use_homomorphic = PAILLIER_AVAILABLE
        self.encrypted_values: Dict[str, List[Any]] = defaultdict(list)
        self.public_key = None
        self.private_key = None

        if self.use_homomorphic:
            self.public_key, self.private_key = paillier.generate_paillier_keypair(n_length=1024)

    def add_value(self, metric_name: str, value: float, encrypt: bool = True) -> None:
        if self.use_homomorphic and encrypt and self.public_key is not None:
            int_value = int(float(value) * 1000.0)
            self.encrypted_values[metric_name].append(self.public_key.encrypt(int_value))
            return
        self.encrypted_values[metric_name].append(float(value))

    def get_sum(self, metric_name: str) -> float:
        values = self.encrypted_values.get(metric_name, [])
        if not values:
            return 0.0
        if self.use_homomorphic and self.private_key is not None:
            total = values[0]
            for value in values[1:]:
                total += value
            return float(self.private_key.decrypt(total)) / 1000.0
        return float(sum(float(v) for v in values))

    def get_average(self, metric_name: str) -> float:
        values = self.encrypted_values.get(metric_name, [])
        if not values:
            return 0.0
        return self.get_sum(metric_name) / float(len(values))


class ThreatDetector:
    def __init__(self, storage_path: Path | None = None) -> None:
        self.storage_path = storage_path or Path("/tmp/threat_detector")
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.master_key = self._generate_master_key()
        self.fernet = Fernet(self.master_key) if FERNET_AVAILABLE else None
        self.encryption_level = (
            EncryptionLevel.HOMOMORPHIC_LIGHT
            if PAILLIER_AVAILABLE
            else (EncryptionLevel.STANDARD if FERNET_AVAILABLE else EncryptionLevel.NONE)
        )

        self.homomorphic_counters = None
        if PAILLIER_AVAILABLE:
            try:
                self.homomorphic_counters = HomomorphicCounter()
            except Exception as exc:
                logger.warning("No se pudo inicializar Paillier: %s", exc)

        self.metrics_aggregator = SecureMetricsAggregator()

        self.threat_history: List[bytes] = []
        self.user_patterns: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.rate_limits: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {"count": 0.0, "reset_time": time.time()}
        )
        self.max_requests_per_minute = int(os.getenv("SECURITY_RATE_LIMIT_RPM", "60"))

        self.attack_patterns = self._load_attack_patterns()

        self.stats = {
            "total_checks": 0,
            "threats_detected": 0,
            "threats_blocked": 0,
            "false_positives": 0,
        }

    def _generate_master_key(self) -> bytes:
        key_file = self.storage_path / "master.key"
        if key_file.exists():
            return key_file.read_bytes()

        if FERNET_AVAILABLE:
            key = Fernet.generate_key()
        else:
            key = base64.urlsafe_b64encode(secrets.token_bytes(32))

        key_file.write_bytes(key)
        try:
            key_file.chmod(0o600)
        except Exception:
            pass
        return key

    def _load_attack_patterns(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "sql_injection",
                "patterns": [
                    r"(\bOR\b|\bAND\b).*?=.*?",
                    r"union.*select",
                    r"drop\s+table",
                    r"insert\s+into",
                    r"--\s*$",
                    r"';.*--",
                ],
                "severity": "high",
            },
            {
                "name": "xss_attack",
                "patterns": [r"<script[^>]*>.*?</script>", r"javascript:", r"onerror\s*=", r"onclick\s*="],
                "severity": "high",
            },
            {
                "name": "path_traversal",
                "patterns": [r"\.\./", r"\.\.\\", r"%2e%2e", r"etc/passwd"],
                "severity": "high",
            },
            {
                "name": "command_injection",
                "patterns": [r";\s*(rm|cat|ls|curl|wget)", r"\|.*?(rm|cat|ls)", r"`.*?`", r"\$\(.*?\)"],
                "severity": "critical",
            },
            {
                "name": "prompt_injection",
                "patterns": [
                    r"ignore\s+(previous|all)\s+instructions",
                    r"system\s+prompt",
                    r"you\s+are\s+now",
                    r"forget\s+everything",
                    r"disregard.*?rules",
                ],
                "severity": "medium",
            },
            {
                "name": "data_exfiltration",
                "patterns": [
                    r"show\s+me\s+(all|every)",
                    r"list\s+(all|every)\s+(user|password|key|secret)",
                    r"dump\s+(database|table|memory)",
                    r"export\s+(all|everything)",
                ],
                "severity": "high",
            },
        ]

    def analyze_content(self, content: str, metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
        metadata = metadata or {}
        self.stats["total_checks"] += 1

        if self.homomorphic_counters:
            self.homomorphic_counters.increment("total_content_checks")

        threats_found: List[Dict[str, Any]] = []
        max_severity = "low"
        for attack in self.attack_patterns:
            for pattern in attack["patterns"]:
                if re.search(pattern, content, re.IGNORECASE):
                    threats_found.append(
                        {"type": attack["name"], "severity": attack["severity"], "pattern": pattern}
                    )
                    max_severity = self._max_severity(max_severity, attack["severity"])

        anomaly_score = self._calculate_anomaly_score(content)

        if len(content) > 50000:
            threats_found.append({"type": "excessive_length", "severity": "medium", "length": len(content)})
            max_severity = self._max_severity(max_severity, "medium")

        suspicious_ratio = self._count_suspicious_chars(content)
        if suspicious_ratio > 0.2:
            threats_found.append(
                {"type": "suspicious_encoding", "severity": "medium", "ratio": suspicious_ratio}
            )
            max_severity = self._max_severity(max_severity, "medium")

        if max_severity == "critical" or len(threats_found) >= 3:
            threat_level = ThreatLevel.CRITICAL.value
        elif max_severity == "high" or len(threats_found) >= 2:
            threat_level = ThreatLevel.HIGH.value
        elif max_severity == "medium" or threats_found:
            threat_level = ThreatLevel.MEDIUM.value
        else:
            threat_level = ThreatLevel.LOW.value

        if threats_found:
            self.stats["threats_detected"] += 1
            if self.homomorphic_counters:
                self.homomorphic_counters.increment("threats_detected")

        threat_record = {
            "timestamp": datetime.now().isoformat(),
            "threat_level": threat_level,
            "threats_found": len(threats_found),
            "content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest()[:16],
        }
        self.threat_history.append(self._encrypt_record(threat_record))
        if len(self.threat_history) > 1000:
            self.threat_history = self.threat_history[-500:]

        return {
            "threat_level": threat_level,
            "threat_type": threats_found[0]["type"] if threats_found else "none",
            "threats_found": threats_found,
            "anomaly_score": anomaly_score,
            "confidence": self._calculate_confidence(threats_found, anomaly_score),
            "timestamp": datetime.now().isoformat(),
        }

    def analyze_query(self, query: str, user_id: str = "anonymous") -> Dict[str, Any]:
        if self._check_rate_limit(user_id):
            self.stats["threats_blocked"] += 1
            return {
                "threat_level": ThreatLevel.HIGH.value,
                "threat_type": "rate_limit_exceeded",
                "blocked": True,
            }

        result = self.analyze_content(query)
        pattern_score = self._analyze_user_pattern(user_id, query)
        self.metrics_aggregator.add_value("query_length", len(query), encrypt=True)

        if result["threat_level"] in {ThreatLevel.HIGH.value, ThreatLevel.CRITICAL.value}:
            return result

        if pattern_score > 0.8:
            return {
                "threat_level": ThreatLevel.MEDIUM.value,
                "threat_type": "anomalous_user_pattern",
                "pattern_score": pattern_score,
                "confidence": 0.7,
            }

        return result

    def _check_rate_limit(self, user_id: str) -> bool:
        now = time.time()
        bucket = self.rate_limits[user_id]
        if now - float(bucket["reset_time"]) > 60:
            self.rate_limits[user_id] = {"count": 0.0, "reset_time": now}
            bucket = self.rate_limits[user_id]

        bucket["count"] = float(bucket["count"]) + 1.0
        if bucket["count"] > float(self.max_requests_per_minute):
            if self.homomorphic_counters:
                self.homomorphic_counters.increment("rate_limit_violations")
            return True
        return False

    def _analyze_user_pattern(self, user_id: str, query: str) -> float:
        patterns = self.user_patterns[user_id]
        patterns.append(
            {
                "query_length": len(query),
                "timestamp": time.time(),
                "query_hash": hashlib.sha256(query.encode("utf-8")).hexdigest()[:8],
            }
        )
        if len(patterns) > 100:
            self.user_patterns[user_id] = patterns[-50:]
            patterns = self.user_patterns[user_id]

        if len(patterns) < 5:
            return 0.0

        recent = patterns[-10:]
        unique_hashes = len({item["query_hash"] for item in recent})
        if unique_hashes < 3:
            return 0.9

        diffs = [recent[i + 1]["timestamp"] - recent[i]["timestamp"] for i in range(len(recent) - 1)]
        if not diffs:
            return 0.0
        avg_diff = sum(diffs) / len(diffs)
        return 0.7 if avg_diff < 0.5 else 0.0

    @staticmethod
    def _calculate_anomaly_score(content: str) -> float:
        entropy = ThreatDetector._calculate_entropy(content)
        return min(entropy / 8.0, 1.0)

    @staticmethod
    def _calculate_entropy(text: str) -> float:
        if not text:
            return 0.0
        freq: Dict[str, int] = {}
        for char in text:
            freq[char] = freq.get(char, 0) + 1

        entropy = 0.0
        length = len(text)
        for count in freq.values():
            prob = count / length
            entropy -= prob * math.log2(prob)
        return entropy

    @staticmethod
    def _count_suspicious_chars(content: str) -> float:
        if not content:
            return 0.0
        suspicious = sum(1 for char in content if not char.isprintable() and char not in "\n\r\t")
        return suspicious / len(content)

    @staticmethod
    def _calculate_confidence(threats: List[Dict[str, Any]], anomaly_score: float) -> float:
        if not threats:
            return 0.0
        base = min(len(threats) * 0.3, 0.9)
        return min(base + anomaly_score * 0.2, 1.0)

    @staticmethod
    def _severity_rank(level: str) -> int:
        rank = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        return rank.get(level, 0)

    def _max_severity(self, left: str, right: str) -> str:
        return right if self._severity_rank(right) >= self._severity_rank(left) else left

    def _encrypt_record(self, record: Dict[str, Any]) -> bytes:
        payload = json.dumps(record, ensure_ascii=True).encode("utf-8")
        if self.fernet is not None:
            return self.fernet.encrypt(payload)
        mac = hmac.new(self.master_key, payload, hashlib.sha256).hexdigest().encode("ascii")
        return base64.urlsafe_b64encode(mac + b"." + payload)

    def _decrypt_record(self, encrypted_data: bytes) -> Dict[str, Any]:
        if self.fernet is not None:
            payload = self.fernet.decrypt(encrypted_data)
            return json.loads(payload.decode("utf-8"))

        raw = base64.urlsafe_b64decode(encrypted_data)
        mac, payload = raw.split(b".", 1)
        expected = hmac.new(self.master_key, payload, hashlib.sha256).hexdigest().encode("ascii")
        if not hmac.compare_digest(mac, expected):
            raise ValueError("Invalid encrypted record HMAC")
        return json.loads(payload.decode("utf-8"))

    def get_stats(self) -> Dict[str, Any]:
        stats = dict(self.stats)
        stats["encryption_level"] = self.encryption_level.value
        stats["paillier_available"] = PAILLIER_AVAILABLE
        stats["fernet_available"] = FERNET_AVAILABLE
        stats["threat_history_size"] = len(self.threat_history)
        stats["tracked_users"] = len(self.user_patterns)

        if self.homomorphic_counters:
            stats["homomorphic_counters"] = {
                "total_content_checks": self.homomorphic_counters.get_value("total_content_checks"),
                "threats_detected": self.homomorphic_counters.get_value("threats_detected"),
                "rate_limit_violations": self.homomorphic_counters.get_value("rate_limit_violations"),
            }

        if self.metrics_aggregator.encrypted_values:
            stats["average_query_length"] = self.metrics_aggregator.get_average("query_length")

        return stats

    def export_encrypted_logs(self, output_path: Path) -> bool:
        try:
            payload = {
                "threat_history": [self._decrypt_record(item) for item in self.threat_history[-100:]],
                "stats": self.get_stats(),
                "export_time": datetime.now().isoformat(),
            }
            encrypted = self._encrypt_record(payload)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(encrypted)
            return True
        except Exception as exc:
            logger.error("Error exportando logs cifrados: %s", exc)
            return False
