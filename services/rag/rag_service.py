#!/usr/bin/env python3
"""
SERVICIO RAG - BASE DE DATOS VECTORIAL CON CHROMADB
Memoria semántica para recuperación de información relevante
"""

import asyncio
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import paho.mqtt.client as mqtt

logger = logging.getLogger("RAGService")

class RAGService:
    """Servicio RAG con ChromaDB para memoria semántica"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Inicializar servicio RAG
        
        Args:
            config: Configuración del servicio
        """
        self.config = config
        self.mqtt_client = None
        self.chroma_client = None
        self.collection = None
        self.is_running = False
        self.documents_count = 0
        
        logger.info("📚 Inicializando servicio RAG...")
    
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
            client.subscribe("vr/rag/query")
            client.subscribe("vr/rag/document/add")
            client.subscribe("vr/rag/document/delete")
        else:
            logger.error(f"❌ Error MQTT: código {rc}")
    
    def _on_mqtt_message(self, client, userdata, msg):
        """Callback: mensaje MQTT recibido"""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())
            
            if topic == "vr/rag/query":
                asyncio.create_task(self.search_documents(payload))
            elif topic == "vr/rag/document/add":
                asyncio.create_task(self.add_document(payload))
            elif topic == "vr/rag/document/delete":
                asyncio.create_task(self.delete_document(payload))
        except Exception as e:
            logger.error(f"❌ Error procesando mensaje: {e}")
    
    async def search_documents(self, payload: Dict[str, Any]) -> None:
        """
        Buscar documentos similares
        
        Args:
            payload: Consulta de búsqueda
        """
        try:
            query = payload.get("query", "")
            top_k = payload.get("top_k", 3)
            
            logger.info(f"🔍 Buscando documentos similares a: {query}")
            
            # Aquí iría la lógica de ChromaDB
            # results = self.collection.query(query_texts=[query], n_results=top_k)
            
            results = {
                "timestamp": datetime.now().isoformat(),
                "query": query,
                "results": [],
                "similarities": []
            }
            
            self.mqtt_client.publish(
                "vr/rag/search/results",
                json.dumps(results)
            )
            logger.info(f"✅ Búsqueda completada: {len(results['results'])} resultados")
        except Exception as e:
            logger.error(f"❌ Error buscando documentos: {e}")
    
    async def add_document(self, payload: Dict[str, Any]) -> None:
        """
        Agregar documento a la base de datos
        
        Args:
            payload: Documento a agregar
        """
        try:
            doc_id = payload.get("id", "")
            content = payload.get("content", "")
            metadata = payload.get("metadata", {})
            
            logger.info(f"📄 Agregando documento: {doc_id}")
            
            # Aquí iría la lógica de ChromaDB
            # self.collection.add(
            #     ids=[doc_id],
            #     documents=[content],
            #     metadatas=[metadata]
            # )
            
            self.documents_count += 1
            
            result = {
                "timestamp": datetime.now().isoformat(),
                "document_id": doc_id,
                "status": "added",
                "total_documents": self.documents_count
            }
            
            self.mqtt_client.publish(
                "vr/rag/index/status",
                json.dumps(result)
            )
            logger.info(f"✅ Documento agregado: {doc_id}")
        except Exception as e:
            logger.error(f"❌ Error agregando documento: {e}")
    
    async def delete_document(self, payload: Dict[str, Any]) -> None:
        """
        Eliminar documento de la base de datos
        
        Args:
            payload: ID del documento a eliminar
        """
        try:
            doc_id = payload.get("id", "")
            
            logger.info(f"🗑️ Eliminando documento: {doc_id}")
            
            # Aquí iría la lógica de ChromaDB
            # self.collection.delete(ids=[doc_id])
            
            if self.documents_count > 0:
                self.documents_count -= 1
            
            result = {
                "timestamp": datetime.now().isoformat(),
                "document_id": doc_id,
                "status": "deleted",
                "total_documents": self.documents_count
            }
            
            self.mqtt_client.publish(
                "vr/rag/index/status",
                json.dumps(result)
            )
            logger.info(f"✅ Documento eliminado: {doc_id}")
        except Exception as e:
            logger.error(f"❌ Error eliminando documento: {e}")
    
    async def rebuild_index(self) -> None:
        """Reconstruir índice"""
        try:
            logger.info("🔨 Reconstruyendo índice...")
            
            # Aquí iría la lógica de reconstrucción
            
            result = {
                "timestamp": datetime.now().isoformat(),
                "status": "rebuilt",
                "documents": self.documents_count
            }
            
            self.mqtt_client.publish(
                "vr/rag/index/status",
                json.dumps(result)
            )
            logger.info("✅ Índice reconstruido")
        except Exception as e:
            logger.error(f"❌ Error reconstruyendo índice: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Verificar salud del servicio"""
        return {
            "status": "healthy" if self.is_running else "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "mqtt_connected": self.mqtt_client is not None,
            "documents_in_db": self.documents_count
        }
    
    async def start(self) -> None:
        """Iniciar servicio"""
        try:
            logger.info("🚀 Iniciando servicio RAG...")
            
            if not self.connect_mqtt():
                raise Exception("No se pudo conectar a MQTT")
            
            # Aquí iría la inicialización de ChromaDB
            # self.chroma_client = chromadb.Client()
            # self.collection = self.chroma_client.get_or_create_collection(
            #     name=self.config.get("collection_name", "vr_assistant")
            # )
            
            self.is_running = True
            logger.info("✅ Servicio RAG iniciado")
            
            while self.is_running:
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"❌ Error iniciando servicio: {e}")
            self.is_running = False
    
    async def stop(self) -> None:
        """Detener servicio"""
        logger.info("🛑 Deteniendo servicio RAG...")
        self.is_running = False
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        logger.info("✅ Servicio RAG detenido")

async def main():
    """Punto de entrada"""
    config = {
        "mqtt_host": "localhost",
        "mqtt_port": 1883,
        "collection_name": "vr_assistant_documents"
    }
    
    service = RAGService(config)
    try:
        await service.start()
    except KeyboardInterrupt:
        await service.stop()

if __name__ == "__main__":
    asyncio.run(main())
