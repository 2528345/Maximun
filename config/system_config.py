#!/usr/bin/env python3
"""
CONFIGURACIÓN CENTRALIZADA DEL SISTEMA VR ASSISTANT
Carga variables de entorno de forma segura
"""

import os
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
from dotenv import load_dotenv
import logging

# Cargar variables de entorno desde .env
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

logger = logging.getLogger("SystemConfig")

# ============================================================================
# VALIDACIÓN DE VARIABLES DE ENTORNO
# ============================================================================

def validate_env_var(var_name: str, default: Optional[str] = None, required: bool = False) -> str:
    """
    Validar y obtener variable de entorno de forma segura
    
    Args:
        var_name: Nombre de la variable
        default: Valor por defecto si no existe
        required: Si es requerida
    
    Returns:
        Valor de la variable
    
    Raises:
        ValueError: Si es requerida y no existe
    """
    value = os.getenv(var_name, default)
    
    if required and not value:
        raise ValueError(f"Variable de entorno requerida no configurada: {var_name}")
    
    if value:
        logger.info(f"✅ Variable {var_name} cargada correctamente")
    else:
        logger.warning(f"⚠️ Variable {var_name} no configurada, usando default: {default}")
    
    return value or ""

# ============================================================================
# CONFIGURACIÓN MQTT
# ============================================================================

@dataclass
class MQTTConfig:
    """Configuración MQTT segura"""
    BROKER_HOST: str = validate_env_var("MQTT_BROKER_HOST", "localhost", required=True)
    BROKER_PORT: int = int(validate_env_var("MQTT_BROKER_PORT", "1883"))
    USERNAME: str = validate_env_var("MQTT_USERNAME", required=True)
    PASSWORD: str = validate_env_var("MQTT_PASSWORD", required=True)
    KEEPALIVE: int = int(validate_env_var("MQTT_KEEPALIVE", "60"))
    CLIENT_ID: str = validate_env_var("MQTT_CLIENT_ID", "vr-assistant")
    QOS: int = int(validate_env_var("MQTT_QOS", "1"))
    RECONNECT_DELAY: int = int(validate_env_var("MQTT_RECONNECT_DELAY", "5"))
    MAX_RECONNECT_ATTEMPTS: int = int(validate_env_var("MQTT_MAX_RECONNECT_ATTEMPTS", "10"))
    
    def validate(self):
        """Validar configuración MQTT"""
        if not self.BROKER_HOST:
            raise ValueError("MQTT_BROKER_HOST es requerido")
        if not self.USERNAME or not self.PASSWORD:
            raise ValueError("MQTT_USERNAME y MQTT_PASSWORD son requeridos")
        if not (1 <= self.BROKER_PORT <= 65535):
            raise ValueError(f"MQTT_BROKER_PORT debe estar entre 1 y 65535, recibido: {self.BROKER_PORT}")
        if self.QOS not in [0, 1, 2]:
            raise ValueError(f"MQTT_QOS debe ser 0, 1 o 2, recibido: {self.QOS}")
        logger.info("✅ Configuración MQTT validada correctamente")

# ============================================================================
# CONFIGURACIÓN DE MODELOS DE IA
# ============================================================================

@dataclass
class ModelsConfig:
    """Configuración de modelos de IA"""
    # Modelos de lenguaje
    REASONING_MODEL: str = validate_env_var("REASONING_MODEL", "microsoft/phi-3-mini-4k-instruct")
    FILTER_MODEL: str = validate_env_var("FILTER_MODEL", "TinyLlama/TinyLlama-1.1B-Chat-v1.0")
    EMBEDDING_MODEL: str = validate_env_var("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    
    # Modelos de visión
    FACE_RECOGNITION_MODEL: str = validate_env_var("FACE_RECOGNITION_MODEL", "facenet")
    OBJECT_DETECTION_MODEL: str = validate_env_var("OBJECT_DETECTION_MODEL", "yolov5n")
    
    # Modelos de audio
    STT_MODEL: str = validate_env_var("STT_MODEL", "vosk")
    TTS_ENGINE: str = validate_env_var("TTS_ENGINE", "piper")
    
    # Rutas de modelos
    MODELS_PATH: str = validate_env_var("MODELS_PATH", "/app/shared_models")
    FACE_DATABASE_PATH: str = validate_env_var("FACE_DATABASE_PATH", "/app/shared_models/face_database.json")
    
    # Configuración de rendimiento
    MODEL_DEVICE: str = validate_env_var("MODEL_DEVICE", "cpu")  # cpu o cuda
    MODEL_PRECISION: str = validate_env_var("MODEL_PRECISION", "float32")  # float32 o float16
    
    def validate(self):
        """Validar configuración de modelos"""
        if self.MODEL_DEVICE not in ["cpu", "cuda"]:
            raise ValueError(f"MODEL_DEVICE debe ser 'cpu' o 'cuda', recibido: {self.MODEL_DEVICE}")
        if self.MODEL_PRECISION not in ["float32", "float16"]:
            raise ValueError(f"MODEL_PRECISION debe ser 'float32' o 'float16', recibido: {self.MODEL_PRECISION}")
        logger.info("✅ Configuración de modelos validada correctamente")

# ============================================================================
# CONFIGURACIÓN DE RAG
# ============================================================================

@dataclass
class RAGConfig:
    """Configuración de base de datos vectorial RAG"""
    PERSIST_DIRECTORY: str = validate_env_var("RAG_PERSIST_DIRECTORY", "/app/rag_storage")
    COLLECTION_NAME: str = validate_env_var("RAG_COLLECTION_NAME", "vr_assistant_documents")
    CHUNK_SIZE: int = int(validate_env_var("RAG_CHUNK_SIZE", "1000"))
    CHUNK_OVERLAP: int = int(validate_env_var("RAG_CHUNK_OVERLAP", "200"))
    MAX_RESULTS: int = int(validate_env_var("RAG_MAX_RESULTS", "5"))
    SIMILARITY_THRESHOLD: float = float(validate_env_var("RAG_SIMILARITY_THRESHOLD", "0.7"))
    SUPPORTED_FORMATS: List[str] = [".pdf", ".docx", ".xlsx", ".txt", ".jpg", ".png", ".mp3", ".wav"]
    
    def validate(self):
        """Validar configuración RAG"""
        if self.CHUNK_SIZE < 100:
            raise ValueError(f"RAG_CHUNK_SIZE debe ser >= 100, recibido: {self.CHUNK_SIZE}")
        if self.CHUNK_OVERLAP >= self.CHUNK_SIZE:
            raise ValueError(f"RAG_CHUNK_OVERLAP debe ser < CHUNK_SIZE")
        if not (0 <= self.SIMILARITY_THRESHOLD <= 1):
            raise ValueError(f"RAG_SIMILARITY_THRESHOLD debe estar entre 0 y 1, recibido: {self.SIMILARITY_THRESHOLD}")
        logger.info("✅ Configuración RAG validada correctamente")

# ============================================================================
# CONFIGURACIÓN DE HARDWARE
# ============================================================================

@dataclass
class HardwareConfig:
    """Configuración de interfaz de hardware"""
    GPIO_MODE: str = validate_env_var("GPIO_MODE", "BCM")  # BCM o BOARD
    SERIAL_TIMEOUT: float = float(validate_env_var("SERIAL_TIMEOUT", "1.0"))
    BLUETOOTH_TIMEOUT: float = float(validate_env_var("BLUETOOTH_TIMEOUT", "10.0"))
    I2C_BUS: int = int(validate_env_var("I2C_BUS", "1"))
    MODBUS_TIMEOUT: float = float(validate_env_var("MODBUS_TIMEOUT", "5.0"))
    
    # Puertos seriales
    SERIAL_PORTS: Dict[str, str] = {
        "default": validate_env_var("SERIAL_PORT_DEFAULT", "/dev/ttyUSB0"),
        "modbus": validate_env_var("SERIAL_PORT_MODBUS", "/dev/ttyUSB1"),
    }
    
    def validate(self):
        """Validar configuración de hardware"""
        if self.GPIO_MODE not in ["BCM", "BOARD"]:
            raise ValueError(f"GPIO_MODE debe ser 'BCM' o 'BOARD', recibido: {self.GPIO_MODE}")
        if self.SERIAL_TIMEOUT <= 0:
            raise ValueError(f"SERIAL_TIMEOUT debe ser > 0, recibido: {self.SERIAL_TIMEOUT}")
        logger.info("✅ Configuración de hardware validada correctamente")

# ============================================================================
# CONFIGURACIÓN DE LOGGING
# ============================================================================

@dataclass
class LoggingConfig:
    """Configuración de logging"""
    LOG_LEVEL: str = validate_env_var("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE: str = validate_env_var("LOG_FILE", "/app/logs/vr_assistant.log")
    LOG_MAX_BYTES: int = int(validate_env_var("LOG_MAX_BYTES", "10485760"))  # 10MB
    LOG_BACKUP_COUNT: int = int(validate_env_var("LOG_BACKUP_COUNT", "5"))
    
    def validate(self):
        """Validar configuración de logging"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.LOG_LEVEL not in valid_levels:
            raise ValueError(f"LOG_LEVEL debe ser uno de {valid_levels}, recibido: {self.LOG_LEVEL}")
        logger.info("✅ Configuración de logging validada correctamente")

# ============================================================================
# CONFIGURACIÓN DE SEGURIDAD
# ============================================================================

@dataclass
class SecurityConfig:
    """Configuración de seguridad"""
    # Límites de recursos
    MAX_QUEUE_SIZE: int = int(validate_env_var("MAX_QUEUE_SIZE", "1000"))
    MAX_TEXT_LENGTH: int = int(validate_env_var("MAX_TEXT_LENGTH", "10000"))
    MAX_FILE_SIZE: int = int(validate_env_var("MAX_FILE_SIZE", "104857600"))  # 100MB
    
    # Timeouts
    PROCESSING_TIMEOUT: int = int(validate_env_var("PROCESSING_TIMEOUT", "30"))
    OCR_TIMEOUT: int = int(validate_env_var("OCR_TIMEOUT", "60"))
    AUDIO_PROCESSING_TIMEOUT: int = int(validate_env_var("AUDIO_PROCESSING_TIMEOUT", "120"))
    
    # Rate limiting
    RATE_LIMIT_ENABLED: bool = validate_env_var("RATE_LIMIT_ENABLED", "true").lower() == "true"
    RATE_LIMIT_REQUESTS: int = int(validate_env_var("RATE_LIMIT_REQUESTS", "100"))
    RATE_LIMIT_WINDOW: int = int(validate_env_var("RATE_LIMIT_WINDOW", "60"))
    
    # Validación de datos
    VALIDATE_INPUT: bool = validate_env_var("VALIDATE_INPUT", "true").lower() == "true"
    SANITIZE_INPUT: bool = validate_env_var("SANITIZE_INPUT", "true").lower() == "true"
    
    def validate(self):
        """Validar configuración de seguridad"""
        if self.MAX_QUEUE_SIZE <= 0:
            raise ValueError(f"MAX_QUEUE_SIZE debe ser > 0, recibido: {self.MAX_QUEUE_SIZE}")
        if self.MAX_TEXT_LENGTH <= 0:
            raise ValueError(f"MAX_TEXT_LENGTH debe ser > 0, recibido: {self.MAX_TEXT_LENGTH}")
        if self.PROCESSING_TIMEOUT <= 0:
            raise ValueError(f"PROCESSING_TIMEOUT debe ser > 0, recibido: {self.PROCESSING_TIMEOUT}")
        logger.info("✅ Configuración de seguridad validada correctamente")

# ============================================================================
# CONFIGURACIÓN GLOBAL
# ============================================================================

class SystemConfig:
    """Configuración global del sistema"""
    
    def __init__(self):
        """Inicializar configuración"""
        self.mqtt = MQTTConfig()
        self.models = ModelsConfig()
        self.rag = RAGConfig()
        self.hardware = HardwareConfig()
        self.logging = LoggingConfig()
        self.security = SecurityConfig()
    
    def validate_all(self):
        """Validar todas las configuraciones"""
        logger.info("🔍 Validando configuración del sistema...")
        self.mqtt.validate()
        self.models.validate()
        self.rag.validate()
        self.hardware.validate()
        self.logging.validate()
        self.security.validate()
        logger.info("✅ Todas las configuraciones validadas correctamente")
    
    def get_config_summary(self) -> Dict:
        """Obtener resumen de configuración"""
        return {
            "mqtt": {
                "host": self.mqtt.BROKER_HOST,
                "port": self.mqtt.BROKER_PORT,
                "client_id": self.mqtt.CLIENT_ID
            },
            "models": {
                "reasoning": self.models.REASONING_MODEL,
                "filter": self.models.FILTER_MODEL,
                "device": self.models.MODEL_DEVICE
            },
            "rag": {
                "collection": self.rag.COLLECTION_NAME,
                "chunk_size": self.rag.CHUNK_SIZE
            },
            "logging": {
                "level": self.logging.LOG_LEVEL,
                "file": self.logging.LOG_FILE
            }
        }

# ============================================================================
# INSTANCIA GLOBAL
# ============================================================================

# Crear instancia global de configuración
config = SystemConfig()

# Validar al importar
try:
    config.validate_all()
except ValueError as e:
    logger.error(f"❌ Error en configuración: {e}")
    raise

if __name__ == "__main__":
    print("📋 Resumen de configuración:")
    import json
    print(json.dumps(config.get_config_summary(), indent=2))
