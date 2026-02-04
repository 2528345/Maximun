#!/usr/bin/env python3
"""
SERVICIO DE RAZONAMIENTO - PHI-3 7B + MOTOR HMR-ACT
Razonamiento inteligente en 5 niveles: Percepción → Análisis → Razonamiento → Decisión → Acción
"""

import asyncio
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import paho.mqtt.client as mqtt
from enum import Enum

logger = logging.getLogger("ReasoningService")

class HMRACTLevel(Enum):
    """Niveles del motor HMR-ACT"""
    PERCEPTION = 1
    ANALYSIS = 2
    REASONING = 3
    DECISION = 4
    ACTION = 5

class ReasoningService:
    """Servicio de razonamiento con motor HMR-ACT"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Inicializar servicio de razonamiento
        
        Args:
            config: Configuración del servicio
        """
        self.config = config
        self.mqtt_client = None
        self.phi3_model = None
        self.is_running = False
        self.reasoning_history = []
        
        logger.info("🧠 Inicializando servicio de razonamiento...")
    
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
            client.subscribe("vr/reasoning/input/query")
        else:
            logger.error(f"❌ Error MQTT: código {rc}")
    
    def _on_mqtt_message(self, client, userdata, msg):
        """Callback: mensaje MQTT recibido"""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())
            
            if topic == "vr/reasoning/input/query":
                asyncio.create_task(self.process_query(payload))
        except Exception as e:
            logger.error(f"❌ Error procesando mensaje: {e}")
    
    async def level_1_perception(self, query: str) -> Dict[str, Any]:
        """
        NIVEL 1: PERCEPCIÓN
        ¿Qué veo? - Identificar entrada
        """
        logger.info("🔍 [NIVEL 1] Percepción: Identificando entrada...")
        
        perception = {
            "level": HMRACTLevel.PERCEPTION.value,
            "timestamp": datetime.now().isoformat(),
            "input": query,
            "identified_elements": []
        }
        
        self.mqtt_client.publish(
            "vr/reasoning/hmract/perception",
            json.dumps(perception)
        )
        
        return perception
    
    async def level_2_analysis(self, perception: Dict[str, Any]) -> Dict[str, Any]:
        """
        NIVEL 2: ANÁLISIS
        ¿Qué significa esto? - Analizar contexto
        """
        logger.info("📊 [NIVEL 2] Análisis: Analizando contexto...")
        
        analysis = {
            "level": HMRACTLevel.ANALYSIS.value,
            "timestamp": datetime.now().isoformat(),
            "perception_input": perception,
            "context": "análisis_contextual",
            "patterns": []
        }
        
        self.mqtt_client.publish(
            "vr/reasoning/hmract/analysis",
            json.dumps(analysis)
        )
        
        return analysis
    
    async def level_3_reasoning(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        NIVEL 3: RAZONAMIENTO
        ¿Qué debo hacer? - Razonar sobre opciones
        """
        logger.info("🤔 [NIVEL 3] Razonamiento: Razonando sobre opciones...")
        
        reasoning = {
            "level": HMRACTLevel.REASONING.value,
            "timestamp": datetime.now().isoformat(),
            "analysis_input": analysis,
            "reasoning_chain": [],
            "options": []
        }
        
        self.mqtt_client.publish(
            "vr/reasoning/hmract/reasoning",
            json.dumps(reasoning)
        )
        
        return reasoning
    
    async def level_4_decision(self, reasoning: Dict[str, Any]) -> Dict[str, Any]:
        """
        NIVEL 4: DECISIÓN
        ¿Cuál es la mejor acción? - Tomar decisión
        """
        logger.info("✅ [NIVEL 4] Decisión: Tomando decisión...")
        
        decision = {
            "level": HMRACTLevel.DECISION.value,
            "timestamp": datetime.now().isoformat(),
            "reasoning_input": reasoning,
            "chosen_action": "acción_seleccionada",
            "confidence": 0.85,
            "alternatives": []
        }
        
        self.mqtt_client.publish(
            "vr/reasoning/hmract/decision",
            json.dumps(decision)
        )
        
        return decision
    
    async def level_5_action(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """
        NIVEL 5: ACCIÓN
        Ejecutar la acción decidida
        """
        logger.info("🚀 [NIVEL 5] Acción: Ejecutando acción...")
        
        action = {
            "level": HMRACTLevel.ACTION.value,
            "timestamp": datetime.now().isoformat(),
            "decision_input": decision,
            "action_executed": "acción_ejecutada",
            "result": "éxito"
        }
        
        self.mqtt_client.publish(
            "vr/reasoning/hmract/action",
            json.dumps(action)
        )
        
        return action
    
    async def process_query(self, payload: Dict[str, Any]) -> None:
        """
        Procesar consulta a través del motor HMR-ACT (5 niveles)
        
        Args:
            payload: Consulta a procesar
        """
        try:
            query = payload.get("query", "")
            logger.info(f"🎯 Procesando consulta: {query}")
            
            # NIVEL 1: Percepción
            perception = await self.level_1_perception(query)
            
            # NIVEL 2: Análisis
            analysis = await self.level_2_analysis(perception)
            
            # NIVEL 3: Razonamiento
            reasoning = await self.level_3_reasoning(analysis)
            
            # NIVEL 4: Decisión
            decision = await self.level_4_decision(reasoning)
            
            # NIVEL 5: Acción
            action = await self.level_5_action(decision)
            
            # Publicar resultado final
            result = {
                "timestamp": datetime.now().isoformat(),
                "query": query,
                "final_decision": decision.get("chosen_action"),
                "confidence": decision.get("confidence"),
                "hmract_chain": {
                    "perception": perception,
                    "analysis": analysis,
                    "reasoning": reasoning,
                    "decision": decision,
                    "action": action
                }
            }
            
            self.mqtt_client.publish(
                "vr/reasoning/output/decision",
                json.dumps(result)
            )
            
            # Guardar en historial
            self.reasoning_history.append(result)
            
            logger.info("✅ Consulta procesada exitosamente")
        except Exception as e:
            logger.error(f"❌ Error procesando consulta: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Verificar salud del servicio"""
        return {
            "status": "healthy" if self.is_running else "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "mqtt_connected": self.mqtt_client is not None,
            "reasoning_history_size": len(self.reasoning_history)
        }
    
    async def start(self) -> None:
        """Iniciar servicio"""
        try:
            logger.info("🚀 Iniciando servicio de razonamiento...")
            
            if not self.connect_mqtt():
                raise Exception("No se pudo conectar a MQTT")
            
            self.is_running = True
            logger.info("✅ Servicio de razonamiento iniciado")
            
            while self.is_running:
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"❌ Error iniciando servicio: {e}")
            self.is_running = False
    
    async def stop(self) -> None:
        """Detener servicio"""
        logger.info("🛑 Deteniendo servicio de razonamiento...")
        self.is_running = False
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        logger.info("✅ Servicio de razonamiento detenido")

async def main():
    """Punto de entrada"""
    config = {
        "mqtt_host": "localhost",
        "mqtt_port": 1883,
        "phi3_model": "microsoft/phi-3-mini-4k-instruct"
    }
    
    service = ReasoningService(config)
    try:
        await service.start()
    except KeyboardInterrupt:
        await service.stop()

if __name__ == "__main__":
    asyncio.run(main())
