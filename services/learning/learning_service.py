#!/usr/bin/env python3
"""
SERVICIO DE APRENDIZAJE - MOTOR CON AUTO-CONCIENCIA
Análisis de errores, mejora continua y auto-reflexión
"""

import asyncio
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import paho.mqtt.client as mqtt
import sqlite3
from pathlib import Path

logger = logging.getLogger("LearningService")

class LearningService:
    """Servicio de aprendizaje con auto-conciencia"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Inicializar servicio de aprendizaje
        
        Args:
            config: Configuración del servicio
        """
        self.config = config
        self.mqtt_client = None
        self.db_path = config.get("db_path", "/app/learning_db/learning.db")
        self.is_running = False
        self.experiences = []
        self.error_patterns = {}
        self.improvement_metrics = {}
        
        logger.info("🤖 Inicializando servicio de aprendizaje...")
        self._init_database()
    
    def _init_database(self) -> None:
        """Inicializar base de datos de aprendizaje"""
        try:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Tabla de experiencias
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS experiences (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT,
                    action TEXT,
                    result TEXT,
                    feedback REAL,
                    learned BOOLEAN
                )
            """)
            
            # Tabla de errores
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS errors (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT,
                    error_type TEXT,
                    frequency INTEGER,
                    pattern TEXT
                )
            """)
            
            # Tabla de mejoras
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS improvements (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT,
                    metric_name TEXT,
                    old_value REAL,
                    new_value REAL,
                    improvement_percentage REAL
                )
            """)
            
            conn.commit()
            conn.close()
            
            logger.info("✅ Base de datos de aprendizaje inicializada")
        except Exception as e:
            logger.error(f"❌ Error inicializando base de datos: {e}")
    
    def connect_mqtt(self) -> bool:
        """Conectar con MQTT broker"""
        try:
            self.mqtt_client = mqtt.Client()
            self.mqtt_client.on_connect = self._on_mqtt_connect
            self.mqtt_client.on_message = self._on_mqtt_message
            
            host = self.config.get("mqtt_host", "localhost")
            port = self.config.get("mqtt_port", 1883)
            
            self.mqtt_client.connect(host, port, keepalive=60)
            self.mqtt_client.loop_start()
            
            logger.info(f"✅ Conectado a MQTT: {host}:{port}")
            return True
        except Exception as e:
            logger.error(f"❌ Error conectando a MQTT: {e}")
            return False
    
    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """Callback: conexión MQTT establecida"""
        if rc == 0:
            logger.info("✅ MQTT conectado")
            client.subscribe("vr/learning/experience")
            client.subscribe("vr/learning/feedback")
            client.subscribe("vr/learning/error")
        else:
            logger.error(f"❌ Error MQTT: código {rc}")
    
    def _on_mqtt_message(self, client, userdata, msg):
        """Callback: mensaje MQTT recibido"""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())
            
            if topic == "vr/learning/experience":
                asyncio.create_task(self.learn_from_experience(payload))
            elif topic == "vr/learning/feedback":
                asyncio.create_task(self.process_feedback(payload))
            elif topic == "vr/learning/error":
                asyncio.create_task(self.analyze_error(payload))
        except Exception as e:
            logger.error(f"❌ Error procesando mensaje: {e}")
    
    async def learn_from_experience(self, payload: Dict[str, Any]) -> None:
        """
        Aprender de una nueva experiencia
        
        Args:
            payload: Datos de la experiencia
        """
        try:
            action = payload.get("action", "")
            result = payload.get("result", "")
            
            logger.info(f"📖 Aprendiendo de experiencia: {action}")
            
            experience = {
                "timestamp": datetime.now().isoformat(),
                "action": action,
                "result": result,
                "learned": False
            }
            
            self.experiences.append(experience)
            
            # Guardar en base de datos
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO experiences (timestamp, action, result, learned)
                VALUES (?, ?, ?, ?)
            """, (experience["timestamp"], action, result, False))
            conn.commit()
            conn.close()
            
            self.mqtt_client.publish(
                "vr/learning/analysis/pattern",
                json.dumps(experience)
            )
            logger.info("✅ Experiencia registrada")
        except Exception as e:
            logger.error(f"❌ Error aprendiendo de experiencia: {e}")
    
    async def process_feedback(self, payload: Dict[str, Any]) -> None:
        """
        Procesar feedback del usuario
        
        Args:
            payload: Feedback recibido
        """
        try:
            feedback_score = payload.get("score", 0.5)
            action_id = payload.get("action_id", "")
            
            logger.info(f"👍 Feedback recibido: {feedback_score}")
            
            # Actualizar experiencia con feedback
            if self.experiences:
                self.experiences[-1]["feedback"] = feedback_score
                self.experiences[-1]["learned"] = feedback_score > 0.7
            
            result = {
                "timestamp": datetime.now().isoformat(),
                "feedback_score": feedback_score,
                "action_id": action_id,
                "status": "processed"
            }
            
            self.mqtt_client.publish(
                "vr/learning/model/update",
                json.dumps(result)
            )
            logger.info("✅ Feedback procesado")
        except Exception as e:
            logger.error(f"❌ Error procesando feedback: {e}")
    
    async def analyze_error(self, payload: Dict[str, Any]) -> None:
        """
        Analizar error y detectar patrones
        
        Args:
            payload: Datos del error
        """
        try:
            error_type = payload.get("error_type", "unknown")
            error_context = payload.get("context", "")
            
            logger.info(f"🔍 Analizando error: {error_type}")
            
            # Contar frecuencia de errores
            if error_type not in self.error_patterns:
                self.error_patterns[error_type] = 0
            self.error_patterns[error_type] += 1
            
            # Guardar en base de datos
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO errors (timestamp, error_type, frequency, pattern)
                VALUES (?, ?, ?, ?)
            """, (datetime.now().isoformat(), error_type, 
                  self.error_patterns[error_type], error_context))
            conn.commit()
            conn.close()
            
            analysis = {
                "timestamp": datetime.now().isoformat(),
                "error_type": error_type,
                "frequency": self.error_patterns[error_type],
                "pattern_detected": self.error_patterns[error_type] > 3
            }
            
            self.mqtt_client.publish(
                "vr/learning/analysis/error",
                json.dumps(analysis)
            )
            
            logger.info(f"✅ Error analizado: {error_type} (frecuencia: {self.error_patterns[error_type]})")
        except Exception as e:
            logger.error(f"❌ Error analizando error: {e}")
    
    async def self_awareness_check(self) -> Dict[str, Any]:
        """
        Auto-conciencia: reflexión sobre el aprendizaje
        
        Returns:
            Datos de auto-conciencia
        """
        logger.info("🤔 Realizando auto-reflexión...")
        
        total_experiences = len(self.experiences)
        learned_experiences = sum(1 for e in self.experiences if e.get("learned", False))
        learning_rate = (learned_experiences / total_experiences * 100) if total_experiences > 0 else 0
        
        awareness = {
            "timestamp": datetime.now().isoformat(),
            "total_experiences": total_experiences,
            "learned_experiences": learned_experiences,
            "learning_rate": f"{learning_rate:.2f}%",
            "error_patterns": self.error_patterns,
            "self_assessment": "improving" if learning_rate > 50 else "learning"
        }
        
        self.mqtt_client.publish(
            "vr/learning/self/awareness",
            json.dumps(awareness)
        )
        
        logger.info(f"✅ Auto-reflexión completada: {learning_rate:.2f}% aprendido")
        return awareness
    
    async def health_check(self) -> Dict[str, Any]:
        """Verificar salud del servicio"""
        return {
            "status": "healthy" if self.is_running else "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "mqtt_connected": self.mqtt_client is not None,
            "experiences_count": len(self.experiences),
            "error_patterns": len(self.error_patterns)
        }
    
    async def start(self) -> None:
        """Iniciar servicio"""
        try:
            logger.info("🚀 Iniciando servicio de aprendizaje...")
            
            if not self.connect_mqtt():
                raise Exception("No se pudo conectar a MQTT")
            
            self.is_running = True
            logger.info("✅ Servicio de aprendizaje iniciado")
            
            # Realizar auto-reflexión cada 60 segundos
            while self.is_running:
                await asyncio.sleep(60)
                await self.self_awareness_check()
        except Exception as e:
            logger.error(f"❌ Error iniciando servicio: {e}")
            self.is_running = False
    
    async def stop(self) -> None:
        """Detener servicio"""
        logger.info("🛑 Deteniendo servicio de aprendizaje...")
        self.is_running = False
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        logger.info("✅ Servicio de aprendizaje detenido")

async def main():
    """Punto de entrada"""
    config = {
        "mqtt_host": "localhost",
        "mqtt_port": 1883,
        "db_path": "/app/learning_db/learning.db"
    }
    
    service = LearningService(config)
    try:
        await service.start()
    except KeyboardInterrupt:
        await service.stop()

if __name__ == "__main__":
    asyncio.run(main())
