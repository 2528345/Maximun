#!/usr/bin/env python3
"""
SERVICIO DE VISIÓN - RECONOCIMIENTO FACIAL Y DETECCIÓN DE OBJETOS
Usa FaceNet para reconocimiento facial y YOLO para detección de objetos
"""

import asyncio
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import paho.mqtt.client as mqtt
import cv2
import numpy as np

logger = logging.getLogger("VisionService")

class VisionService:
    """Servicio de visión para reconocimiento facial y detección de objetos"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Inicializar servicio de visión
        
        Args:
            config: Configuración del servicio
        """
        self.config = config
        self.mqtt_client = None
        self.facenet_model = None
        self.yolo_model = None
        self.face_database = {}
        self.is_running = False
        
        logger.info("👁️ Inicializando servicio de visión...")
    
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
            client.subscribe("vr/vision/input/frame")
            client.subscribe("vr/vision/input/image")
        else:
            logger.error(f"❌ Error MQTT: código {rc}")
    
    def _on_mqtt_message(self, client, userdata, msg):
        """Callback: mensaje MQTT recibido"""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())
            
            if topic == "vr/vision/input/frame":
                asyncio.create_task(self.process_frame(payload))
            elif topic == "vr/vision/input/image":
                asyncio.create_task(self.process_image(payload))
        except Exception as e:
            logger.error(f"❌ Error procesando mensaje: {e}")
    
    async def process_frame(self, payload: Dict[str, Any]) -> None:
        """
        Procesar frame de cámara
        
        Args:
            payload: Datos del frame
        """
        try:
            logger.info("📹 Procesando frame...")
            
            # Aquí iría la lógica de detección
            # faces = self.facenet_model.detect_faces(frame)
            # objects = self.yolo_model.detect(frame)
            
            result = {
                "timestamp": datetime.now().isoformat(),
                "faces_detected": 0,
                "objects_detected": 0,
                "recognized_faces": []
            }
            
            self.mqtt_client.publish(
                "vr/vision/face/detected",
                json.dumps(result)
            )
            logger.info("✅ Frame procesado")
        except Exception as e:
            logger.error(f"❌ Error procesando frame: {e}")
    
    async def process_image(self, payload: Dict[str, Any]) -> None:
        """
        Procesar imagen estática
        
        Args:
            payload: Datos de imagen
        """
        try:
            logger.info("🖼️ Procesando imagen...")
            
            result = {
                "timestamp": datetime.now().isoformat(),
                "faces": [],
                "objects": []
            }
            
            self.mqtt_client.publish(
                "vr/vision/objects/detected",
                json.dumps(result)
            )
            logger.info("✅ Imagen procesada")
        except Exception as e:
            logger.error(f"❌ Error procesando imagen: {e}")
    
    def recognize_face(self, face_embedding: np.ndarray) -> Optional[Dict[str, Any]]:
        """
        Reconocer cara comparando con base de datos
        
        Args:
            face_embedding: Embedding de FaceNet
        
        Returns:
            Información de la cara reconocida
        """
        best_match = None
        best_distance = float('inf')
        threshold = 0.6
        
        for person_name, stored_embedding in self.face_database.items():
            # Calcular distancia euclidiana
            distance = np.linalg.norm(face_embedding - stored_embedding)
            
            if distance < best_distance:
                best_distance = distance
                best_match = person_name
        
        if best_distance < threshold:
            return {
                "name": best_match,
                "confidence": 1 - (best_distance / threshold),
                "distance": float(best_distance)
            }
        
        return None
    
    def detect_objects(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detectar objetos en frame
        
        Args:
            frame: Frame de video
        
        Returns:
            Lista de objetos detectados
        """
        # Aquí iría la lógica de YOLO
        return []
    
    async def health_check(self) -> Dict[str, Any]:
        """Verificar salud del servicio"""
        return {
            "status": "healthy" if self.is_running else "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "mqtt_connected": self.mqtt_client is not None,
            "faces_in_database": len(self.face_database)
        }
    
    async def start(self) -> None:
        """Iniciar servicio"""
        try:
            logger.info("🚀 Iniciando servicio de visión...")
            
            if not self.connect_mqtt():
                raise Exception("No se pudo conectar a MQTT")
            
            self.is_running = True
            logger.info("✅ Servicio de visión iniciado")
            
            while self.is_running:
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"❌ Error iniciando servicio: {e}")
            self.is_running = False
    
    async def stop(self) -> None:
        """Detener servicio"""
        logger.info("🛑 Deteniendo servicio de visión...")
        self.is_running = False
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        logger.info("✅ Servicio de visión detenido")

async def main():
    """Punto de entrada"""
    config = {
        "mqtt_host": "localhost",
        "mqtt_port": 1883,
        "facenet_model": "facenet",
        "yolo_model": "yolov5n"
    }
    
    service = VisionService(config)
    try:
        await service.start()
    except KeyboardInterrupt:
        await service.stop()

if __name__ == "__main__":
    asyncio.run(main())
