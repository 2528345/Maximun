#!/usr/bin/env python3
"""
SERVICIO DE FILTRO - TINYLLAMA 1.1B
Procesamiento rápido de consultas con caché inteligente
"""

import asyncio
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime
import paho.mqtt.client as mqtt
from functools import lru_cache
import hashlib

logger = logging.getLogger("FilterService")

class FilterService:
    """Servicio de filtro usando TinyLlama 1.1B"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Inicializar servicio de filtro
        
        Args:
            config: Configuración del servicio
        """
        self.config = config
        self.mqtt_client = None
        self.tinyllama_model = None
        self.cache = {}
        self.cache_hits = 0
        self.cache_misses = 0
        self.is_running = False
        
        logger.info("🧠 Inicializando servicio de filtro...")
    
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
            client.subscribe("vr/filter/input/text")
        else:
            logger.error(f"❌ Error MQTT: código {rc}")
    
    def _on_mqtt_message(self, client, userdata, msg):
        """Callback: mensaje MQTT recibido"""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())
            
            if topic == "vr/filter/input/text":
                asyncio.create_task(self.process_text(payload))
        except Exception as e:
            logger.error(f"❌ Error procesando mensaje: {e}")
    
    def _get_cache_key(self, text: str) -> str:
        """Generar clave de caché"""
        return hashlib.md5(text.encode()).hexdigest()
    
    def _check_cache(self, text: str) -> Optional[Dict[str, Any]]:
        """Verificar si está en caché"""
        key = self._get_cache_key(text)
        if key in self.cache:
            self.cache_hits += 1
            logger.info(f"✅ Caché hit: {text[:50]}...")
            return self.cache[key]
        self.cache_misses += 1
        return None
    
    def _store_cache(self, text: str, result: Dict[str, Any]) -> None:
        """Guardar en caché"""
        key = self._get_cache_key(text)
        self.cache[key] = result
        
        # Limitar tamaño de caché
        if len(self.cache) > 1000:
            # Eliminar entrada más antigua
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
    
    async def process_text(self, payload: Dict[str, Any]) -> None:
        """
        Procesar texto con TinyLlama
        
        Args:
            payload: Texto a procesar
        """
        try:
            text = payload.get("text", "")
            logger.info(f"📝 Procesando: {text[:50]}...")
            
            # Verificar caché
            cached_result = self._check_cache(text)
            if cached_result:
                self.mqtt_client.publish(
                    "vr/filter/cache/hit",
                    json.dumps(cached_result)
                )
                return
            
            # Aquí iría la lógica de TinyLlama
            # filtered_text = self.tinyllama_model.process(text)
            
            result = {
                "timestamp": datetime.now().isoformat(),
                "original": text,
                "filtered": text,
                "intent": "unknown",
                "entities": [],
                "confidence": 0.85
            }
            
            # Guardar en caché
            self._store_cache(text, result)
            
            self.mqtt_client.publish(
                "vr/filter/output/filtered",
                json.dumps(result)
            )
            logger.info("✅ Texto procesado")
        except Exception as e:
            logger.error(f"❌ Error procesando texto: {e}")
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas de caché"""
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "cache_size": len(self.cache),
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": f"{hit_rate:.2f}%",
            "total_requests": total_requests
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Verificar salud del servicio"""
        stats = await self.get_cache_stats()
        return {
            "status": "healthy" if self.is_running else "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "mqtt_connected": self.mqtt_client is not None,
            **stats
        }
    
    async def start(self) -> None:
        """Iniciar servicio"""
        try:
            logger.info("🚀 Iniciando servicio de filtro...")
            
            if not self.connect_mqtt():
                raise Exception("No se pudo conectar a MQTT")
            
            self.is_running = True
            logger.info("✅ Servicio de filtro iniciado")
            
            while self.is_running:
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"❌ Error iniciando servicio: {e}")
            self.is_running = False
    
    async def stop(self) -> None:
        """Detener servicio"""
        logger.info("🛑 Deteniendo servicio de filtro...")
        self.is_running = False
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        logger.info("✅ Servicio de filtro detenido")

async def main():
    """Punto de entrada"""
    config = {
        "mqtt_host": "localhost",
        "mqtt_port": 1883,
        "tinyllama_model": "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
    }
    
    service = FilterService(config)
    try:
        await service.start()
    except KeyboardInterrupt:
        await service.stop()

if __name__ == "__main__":
    asyncio.run(main())
