#!/usr/bin/env python3
"""
SERVICIO DE AUDIO - STT/TTS OFFLINE
Reconocimiento y síntesis de voz usando Vosk y Piper
"""

import asyncio
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime
import paho.mqtt.client as mqtt
from pathlib import Path

logger = logging.getLogger("AudioService")

class AudioService:
    """Servicio de audio para STT/TTS"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Inicializar servicio de audio
        
        Args:
            config: Configuración del servicio
        """
        self.config = config
        self.mqtt_client = None
        self.vosk_handler = None
        self.piper_handler = None
        self.is_running = False
        
        logger.info("🎤 Inicializando servicio de audio...")
    
    def connect_mqtt(self) -> bool:
        """Conectar con MQTT broker"""
        try:
            self.mqtt_client = mqtt.Client()
            self.mqtt_client.on_connect = self._on_mqtt_connect
            self.mqtt_client.on_message = self._on_mqtt_message
            self.mqtt_client.on_disconnect = self._on_mqtt_disconnect
            
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
            # Suscribirse a tópicos
            client.subscribe("vr/audio/input/raw")
            client.subscribe("vr/audio/synthesize/request")
        else:
            logger.error(f"❌ Error MQTT: código {rc}")
    
    def _on_mqtt_message(self, client, userdata, msg):
        """Callback: mensaje MQTT recibido"""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())
            
            if topic == "vr/audio/input/raw":
                asyncio.create_task(self.process_audio(payload))
            elif topic == "vr/audio/synthesize/request":
                asyncio.create_task(self.synthesize_audio(payload))
        except Exception as e:
            logger.error(f"❌ Error procesando mensaje: {e}")
    
    def _on_mqtt_disconnect(self, client, userdata, rc):
        """Callback: desconexión MQTT"""
        if rc != 0:
            logger.warning(f"⚠️ Desconexión inesperada: código {rc}")
        else:
            logger.info("✅ Desconectado de MQTT")
    
    async def process_audio(self, payload: Dict[str, Any]) -> None:
        """
        Procesar audio y convertir a texto
        
        Args:
            payload: Datos de audio
        """
        try:
            logger.info("🎤 Procesando audio...")
            
            # Aquí iría la lógica de Vosk
            # text = self.vosk_handler.recognize(audio_data)
            
            # Publicar resultado
            result = {
                "timestamp": datetime.now().isoformat(),
                "text": "Texto reconocido",
                "confidence": 0.95,
                "language": "es"
            }
            
            self.mqtt_client.publish(
                "vr/audio/output/text",
                json.dumps(result)
            )
            logger.info(f"✅ Audio procesado: {result['text']}")
        except Exception as e:
            logger.error(f"❌ Error procesando audio: {e}")
    
    async def synthesize_audio(self, payload: Dict[str, Any]) -> None:
        """
        Sintetizar texto a voz
        
        Args:
            payload: Texto a sintetizar
        """
        try:
            text = payload.get("text", "")
            logger.info(f"🗣️ Sintetizando: {text}")
            
            # Aquí iría la lógica de Piper
            # audio_data = self.piper_handler.synthesize(text)
            
            result = {
                "timestamp": datetime.now().isoformat(),
                "text": text,
                "status": "success"
            }
            
            self.mqtt_client.publish(
                "vr/audio/synthesize/response",
                json.dumps(result)
            )
            logger.info("✅ Audio sintetizado")
        except Exception as e:
            logger.error(f"❌ Error sintetizando audio: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Verificar salud del servicio"""
        return {
            "status": "healthy" if self.is_running else "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "mqtt_connected": self.mqtt_client is not None
        }
    
    async def start(self) -> None:
        """Iniciar servicio"""
        try:
            logger.info("🚀 Iniciando servicio de audio...")
            
            if not self.connect_mqtt():
                raise Exception("No se pudo conectar a MQTT")
            
            self.is_running = True
            logger.info("✅ Servicio de audio iniciado")
            
            # Mantener servicio activo
            while self.is_running:
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"❌ Error iniciando servicio: {e}")
            self.is_running = False
    
    async def stop(self) -> None:
        """Detener servicio"""
        logger.info("🛑 Deteniendo servicio de audio...")
        self.is_running = False
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        logger.info("✅ Servicio de audio detenido")

async def main():
    """Punto de entrada"""
    config = {
        "mqtt_host": "localhost",
        "mqtt_port": 1883,
        "vosk_model": "vosk-model-es-0.42",
        "piper_voice": "es_ES-carla-x_low"
    }
    
    service = AudioService(config)
    try:
        await service.start()
    except KeyboardInterrupt:
        await service.stop()

if __name__ == "__main__":
    asyncio.run(main())
