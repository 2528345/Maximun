#!/usr/bin/env python3
"""
DEFINICIÓN DE TÓPICOS MQTT
Centraliza todos los canales de comunicación entre servicios
"""

from typing import Dict, List
from dataclasses import dataclass

# ============================================================================
# TÓPICOS DE AUDIO
# ============================================================================

@dataclass
class AudioTopics:
    """Tópicos para el servicio de audio"""
    # Entrada de audio
    INPUT_RAW: str = "vr/audio/input/raw"  # Audio crudo del micrófono
    INPUT_PROCESSED: str = "vr/audio/input/processed"  # Audio procesado
    
    # Salida de audio
    OUTPUT_TEXT: str = "vr/audio/output/text"  # Texto reconocido
    OUTPUT_CONFIDENCE: str = "vr/audio/output/confidence"  # Confianza del reconocimiento
    OUTPUT_LANGUAGE: str = "vr/audio/output/language"  # Idioma detectado
    
    # Síntesis de voz
    SYNTHESIZE_REQUEST: str = "vr/audio/synthesize/request"  # Solicitud de síntesis
    SYNTHESIZE_RESPONSE: str = "vr/audio/synthesize/response"  # Respuesta de síntesis
    
    # Estado
    STATUS: str = "vr/audio/status"  # Estado del servicio
    HEALTH: str = "vr/audio/health"  # Health check
    
    @classmethod
    def get_all(cls) -> List[str]:
        """Obtener todos los tópicos de audio"""
        return [
            cls.INPUT_RAW,
            cls.INPUT_PROCESSED,
            cls.OUTPUT_TEXT,
            cls.OUTPUT_CONFIDENCE,
            cls.OUTPUT_LANGUAGE,
            cls.SYNTHESIZE_REQUEST,
            cls.SYNTHESIZE_RESPONSE,
            cls.STATUS,
            cls.HEALTH
        ]

# ============================================================================
# TÓPICOS DE VISIÓN
# ============================================================================

@dataclass
class VisionTopics:
    """Tópicos para el servicio de visión"""
    # Entrada de video
    INPUT_FRAME: str = "vr/vision/input/frame"  # Frame de cámara
    INPUT_IMAGE: str = "vr/vision/input/image"  # Imagen estática
    
    # Detección de caras
    FACE_DETECTED: str = "vr/vision/face/detected"  # Cara detectada
    FACE_RECOGNIZED: str = "vr/vision/face/recognized"  # Cara reconocida
    FACE_CONFIDENCE: str = "vr/vision/face/confidence"  # Confianza del reconocimiento
    
    # Detección de objetos
    OBJECTS_DETECTED: str = "vr/vision/objects/detected"  # Objetos detectados
    OBJECTS_DATA: str = "vr/vision/objects/data"  # Datos de objetos
    
    # Estado
    STATUS: str = "vr/vision/status"  # Estado del servicio
    HEALTH: str = "vr/vision/health"  # Health check
    
    @classmethod
    def get_all(cls) -> List[str]:
        """Obtener todos los tópicos de visión"""
        return [
            cls.INPUT_FRAME,
            cls.INPUT_IMAGE,
            cls.FACE_DETECTED,
            cls.FACE_RECOGNIZED,
            cls.FACE_CONFIDENCE,
            cls.OBJECTS_DETECTED,
            cls.OBJECTS_DATA,
            cls.STATUS,
            cls.HEALTH
        ]

# ============================================================================
# TÓPICOS DE FILTRO (TINYLLAMA)
# ============================================================================

@dataclass
class FilterTopics:
    """Tópicos para el servicio de filtro"""
    # Entrada
    INPUT_TEXT: str = "vr/filter/input/text"  # Texto a procesar
    INPUT_CONTEXT: str = "vr/filter/input/context"  # Contexto
    
    # Salida
    OUTPUT_FILTERED: str = "vr/filter/output/filtered"  # Texto filtrado
    OUTPUT_INTENT: str = "vr/filter/output/intent"  # Intención detectada
    OUTPUT_ENTITIES: str = "vr/filter/output/entities"  # Entidades extraídas
    
    # Cache
    CACHE_HIT: str = "vr/filter/cache/hit"  # Acierto de caché
    CACHE_MISS: str = "vr/filter/cache/miss"  # Fallo de caché
    
    # Estado
    STATUS: str = "vr/filter/status"  # Estado del servicio
    HEALTH: str = "vr/filter/health"  # Health check
    
    @classmethod
    def get_all(cls) -> List[str]:
        """Obtener todos los tópicos de filtro"""
        return [
            cls.INPUT_TEXT,
            cls.INPUT_CONTEXT,
            cls.OUTPUT_FILTERED,
            cls.OUTPUT_INTENT,
            cls.OUTPUT_ENTITIES,
            cls.CACHE_HIT,
            cls.CACHE_MISS,
            cls.STATUS,
            cls.HEALTH
        ]

# ============================================================================
# TÓPICOS DE RAZONAMIENTO (PHI-3)
# ============================================================================

@dataclass
class ReasoningTopics:
    """Tópicos para el servicio de razonamiento"""
    # Entrada
    INPUT_QUERY: str = "vr/reasoning/input/query"  # Consulta
    INPUT_CONTEXT: str = "vr/reasoning/input/context"  # Contexto
    INPUT_KNOWLEDGE: str = "vr/reasoning/input/knowledge"  # Conocimiento
    
    # Salida
    OUTPUT_DECISION: str = "vr/reasoning/output/decision"  # Decisión
    OUTPUT_REASONING: str = "vr/reasoning/output/reasoning"  # Razonamiento
    OUTPUT_CONFIDENCE: str = "vr/reasoning/output/confidence"  # Confianza
    
    # HMR-ACT
    HMRACT_PERCEPTION: str = "vr/reasoning/hmract/perception"  # Nivel 1
    HMRACT_ANALYSIS: str = "vr/reasoning/hmract/analysis"  # Nivel 2
    HMRACT_REASONING: str = "vr/reasoning/hmract/reasoning"  # Nivel 3
    HMRACT_DECISION: str = "vr/reasoning/hmract/decision"  # Nivel 4
    HMRACT_ACTION: str = "vr/reasoning/hmract/action"  # Nivel 5
    
    # Estado
    STATUS: str = "vr/reasoning/status"  # Estado del servicio
    HEALTH: str = "vr/reasoning/health"  # Health check
    
    @classmethod
    def get_all(cls) -> List[str]:
        """Obtener todos los tópicos de razonamiento"""
        return [
            cls.INPUT_QUERY,
            cls.INPUT_CONTEXT,
            cls.INPUT_KNOWLEDGE,
            cls.OUTPUT_DECISION,
            cls.OUTPUT_REASONING,
            cls.OUTPUT_CONFIDENCE,
            cls.HMRACT_PERCEPTION,
            cls.HMRACT_ANALYSIS,
            cls.HMRACT_REASONING,
            cls.HMRACT_DECISION,
            cls.HMRACT_ACTION,
            cls.STATUS,
            cls.HEALTH
        ]

# ============================================================================
# TÓPICOS DE RAG
# ============================================================================

@dataclass
class RAGTopics:
    """Tópicos para el servicio RAG"""
    # Entrada
    QUERY: str = "vr/rag/query"  # Consulta
    DOCUMENT_ADD: str = "vr/rag/document/add"  # Agregar documento
    DOCUMENT_DELETE: str = "vr/rag/document/delete"  # Eliminar documento
    
    # Salida
    SEARCH_RESULTS: str = "vr/rag/search/results"  # Resultados de búsqueda
    SIMILARITY_SCORE: str = "vr/rag/search/similarity"  # Puntuación de similitud
    
    # Mantenimiento
    INDEX_REBUILD: str = "vr/rag/index/rebuild"  # Reconstruir índice
    INDEX_STATUS: str = "vr/rag/index/status"  # Estado del índice
    
    # Estado
    STATUS: str = "vr/rag/status"  # Estado del servicio
    HEALTH: str = "vr/rag/health"  # Health check
    
    @classmethod
    def get_all(cls) -> List[str]:
        """Obtener todos los tópicos de RAG"""
        return [
            cls.QUERY,
            cls.DOCUMENT_ADD,
            cls.DOCUMENT_DELETE,
            cls.SEARCH_RESULTS,
            cls.SIMILARITY_SCORE,
            cls.INDEX_REBUILD,
            cls.INDEX_STATUS,
            cls.STATUS,
            cls.HEALTH
        ]

# ============================================================================
# TÓPICOS DE HARDWARE
# ============================================================================

@dataclass
class HardwareTopics:
    """Tópicos para el servicio de hardware"""
    # Control GPIO
    GPIO_SET: str = "vr/hardware/gpio/set"  # Establecer pin
    GPIO_GET: str = "vr/hardware/gpio/get"  # Leer pin
    GPIO_STATUS: str = "vr/hardware/gpio/status"  # Estado de pin
    
    # Control Serial
    SERIAL_SEND: str = "vr/hardware/serial/send"  # Enviar datos
    SERIAL_RECEIVE: str = "vr/hardware/serial/receive"  # Recibir datos
    
    # Control Bluetooth
    BT_CONNECT: str = "vr/hardware/bluetooth/connect"  # Conectar
    BT_DISCONNECT: str = "vr/hardware/bluetooth/disconnect"  # Desconectar
    BT_SEND: str = "vr/hardware/bluetooth/send"  # Enviar datos
    
    # Control Zigbee
    ZIGBEE_DISCOVER: str = "vr/hardware/zigbee/discover"  # Descubrir dispositivos
    ZIGBEE_CONTROL: str = "vr/hardware/zigbee/control"  # Controlar dispositivo
    
    # Control MQTT
    MQTT_RELAY: str = "vr/hardware/mqtt/relay"  # Relé MQTT
    
    # Control ESP32
    ESP32_COMMAND: str = "vr/hardware/esp32/command"  # Comando ESP32
    ESP32_RESPONSE: str = "vr/hardware/esp32/response"  # Respuesta ESP32
    
    # Estado
    STATUS: str = "vr/hardware/status"  # Estado del servicio
    HEALTH: str = "vr/hardware/health"  # Health check
    
    @classmethod
    def get_all(cls) -> List[str]:
        """Obtener todos los tópicos de hardware"""
        return [
            cls.GPIO_SET,
            cls.GPIO_GET,
            cls.GPIO_STATUS,
            cls.SERIAL_SEND,
            cls.SERIAL_RECEIVE,
            cls.BT_CONNECT,
            cls.BT_DISCONNECT,
            cls.BT_SEND,
            cls.ZIGBEE_DISCOVER,
            cls.ZIGBEE_CONTROL,
            cls.MQTT_RELAY,
            cls.ESP32_COMMAND,
            cls.ESP32_RESPONSE,
            cls.STATUS,
            cls.HEALTH
        ]

# ============================================================================
# TÓPICOS DE APRENDIZAJE
# ============================================================================

@dataclass
class LearningTopics:
    """Tópicos para el servicio de aprendizaje"""
    # Entrada
    EXPERIENCE: str = "vr/learning/experience"  # Nueva experiencia
    FEEDBACK: str = "vr/learning/feedback"  # Feedback del usuario
    ERROR: str = "vr/learning/error"  # Error detectado
    
    # Análisis
    ERROR_ANALYSIS: str = "vr/learning/analysis/error"  # Análisis de error
    PATTERN_DETECTED: str = "vr/learning/analysis/pattern"  # Patrón detectado
    
    # Mejora
    MODEL_UPDATE: str = "vr/learning/model/update"  # Actualizar modelo
    IMPROVEMENT_METRIC: str = "vr/learning/improvement/metric"  # Métrica de mejora
    
    # Auto-conciencia
    SELF_AWARENESS: str = "vr/learning/self/awareness"  # Auto-conciencia
    SELF_REFLECTION: str = "vr/learning/self/reflection"  # Auto-reflexión
    
    # Estado
    STATUS: str = "vr/learning/status"  # Estado del servicio
    HEALTH: str = "vr/learning/health"  # Health check
    
    @classmethod
    def get_all(cls) -> List[str]:
        """Obtener todos los tópicos de aprendizaje"""
        return [
            cls.EXPERIENCE,
            cls.FEEDBACK,
            cls.ERROR,
            cls.ERROR_ANALYSIS,
            cls.PATTERN_DETECTED,
            cls.MODEL_UPDATE,
            cls.IMPROVEMENT_METRIC,
            cls.SELF_AWARENESS,
            cls.SELF_REFLECTION,
            cls.STATUS,
            cls.HEALTH
        ]

# ============================================================================
# TÓPICOS GLOBALES
# ============================================================================

@dataclass
class GlobalTopics:
    """Tópicos globales del sistema"""
    # Sistema
    SYSTEM_STATUS: str = "vr/system/status"  # Estado del sistema
    SYSTEM_HEALTH: str = "vr/system/health"  # Health check global
    SYSTEM_SHUTDOWN: str = "vr/system/shutdown"  # Apagar sistema
    SYSTEM_RESTART: str = "vr/system/restart"  # Reiniciar sistema
    
    # Monitoreo
    METRICS: str = "vr/metrics"  # Métricas del sistema
    PERFORMANCE: str = "vr/performance"  # Rendimiento
    ERRORS: str = "vr/errors"  # Errores globales
    
    # Logs
    LOGS: str = "vr/logs"  # Logs del sistema
    
    @classmethod
    def get_all(cls) -> List[str]:
        """Obtener todos los tópicos globales"""
        return [
            cls.SYSTEM_STATUS,
            cls.SYSTEM_HEALTH,
            cls.SYSTEM_SHUTDOWN,
            cls.SYSTEM_RESTART,
            cls.METRICS,
            cls.PERFORMANCE,
            cls.ERRORS,
            cls.LOGS
        ]

# ============================================================================
# COLECCIÓN DE TODOS LOS TÓPICOS
# ============================================================================

class AllTopics:
    """Colección de todos los tópicos MQTT"""
    
    audio = AudioTopics()
    vision = VisionTopics()
    filter = FilterTopics()
    reasoning = ReasoningTopics()
    rag = RAGTopics()
    hardware = HardwareTopics()
    learning = LearningTopics()
    global_topics = GlobalTopics()
    
    @classmethod
    def get_all_topics(cls) -> List[str]:
        """Obtener todos los tópicos del sistema"""
        topics = []
        topics.extend(AudioTopics.get_all())
        topics.extend(VisionTopics.get_all())
        topics.extend(FilterTopics.get_all())
        topics.extend(ReasoningTopics.get_all())
        topics.extend(RAGTopics.get_all())
        topics.extend(HardwareTopics.get_all())
        topics.extend(LearningTopics.get_all())
        topics.extend(GlobalTopics.get_all())
        return topics
    
    @classmethod
    def get_topics_summary(cls) -> Dict[str, int]:
        """Obtener resumen de tópicos por categoría"""
        return {
            "audio": len(AudioTopics.get_all()),
            "vision": len(VisionTopics.get_all()),
            "filter": len(FilterTopics.get_all()),
            "reasoning": len(ReasoningTopics.get_all()),
            "rag": len(RAGTopics.get_all()),
            "hardware": len(HardwareTopics.get_all()),
            "learning": len(LearningTopics.get_all()),
            "global": len(GlobalTopics.get_all()),
            "total": len(cls.get_all_topics())
        }

if __name__ == "__main__":
    print("📡 Resumen de tópicos MQTT:")
    import json
    print(json.dumps(AllTopics.get_topics_summary(), indent=2))
