#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MAXIMUN - Configuración Central del Sistema v2.0
Autor: Manus (basado en propuesta v2.0)
Fecha: 2026-02-18
"""
import os
from pathlib import Path

# ============================================
# PATHS BASE
# ============================================
BASE_DIR = Path("/opt/maximun")
MODELS_DIR = BASE_DIR / "models"
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
HDD_DIR = Path("/mnt/hdd")

# ============================================
# MODELOS CPU-ONLY
# ============================================
MODELS = {
    "vision": {
        "name": "qwen2-vl-2b-q2k",
        "path": MODELS_DIR / "qwen2-vl-2b-q2k",
        "max_memory": "1500MB",
        "device": "cpu"
    },
    "multimodal": {
        "name": "minicpm-v-2.0-q2k",
        "path": MODELS_DIR / "minicpm-v-2.0-q2k",
        "max_memory": "1800MB",
        "device": "cpu"
    },
    "audio": {
        "name": "whisper-ct2-int8",
        "path": MODELS_DIR / "whisper-ct2-int8",
        "max_memory": "400MB",
        "device": "cpu"
    },
    "embeddings": {
        "name": "all-MiniLM-L6-v2",
        "path": MODELS_DIR / "embeddings",
        "max_memory": "200MB",
        "device": "cpu"
    }
}

# ============================================
# MQTT (HMR-ACT)
# ============================================
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPICS = {
    "reasoning_input": "reasoning/input",
    "hmr_act_output": "reasoning/hmr_act/output",
    "final_output": "reasoning/final/output",
    "hardware_commands": "hardware/commands",
    "feedback": "system/feedback",
    "health": "system/health"
}

# ============================================
# REDIS / POSTGRESQL
# ============================================
REDIS_HOST = "localhost"
REDIS_PORT = 6379
POSTGRES_HOST = "localhost"
POSTGRES_PORT = 5432
POSTGRES_DB = "maximun"
POSTGRES_USER = "maximun"
POSTGRES_PASS = "kimi_secure_pass_2025"

# ============================================
# SSD/HDD UMBRALES
# ============================================
SSD_THRESHOLD = 85  # % máximo uso
HDD_THRESHOLD = 95  # % máximo uso
SSD_CHECK_INTERVAL = 30  # segundos

# ============================================
# RAG CHROMADB
# ============================================
RAG_PATH = HDD_DIR / "rag" / "chromadb"
RAG_BACKUP = HDD_DIR / "rag" / "backups"
RAG_COLLECTION = "maximun_knowledge"

# ============================================
# FEEDBACK & AUTO-APRENDIZAJE
# ============================================
FEEDBACK_FILE = DATA_DIR / "feedback.jsonl"
COGNITIVE_MEMORY = DATA_DIR / "cognitive_memory.json"
POLICY_HISTORY = DATA_DIR / "policy_history"

REWARD_GOOD = 1
REWARD_NEUTRAL = 0
REWARD_BAD = -1
REWARD_THRESHOLD = 0.65

if __name__ == "__main__":
    print("✅ MAXIMUN - Configuración cargada")
