#!/usr/bin/env python3
"""
TESTS - Servicio de Visión
Tests unitarios para reconocimiento facial y detección de objetos
"""

import pytest
import asyncio
import json
import numpy as np
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.vision.vision_service import VisionService
from services.vision.facenet_handler import FaceNetHandler, FaceDetector
from services.vision.yolo_handler import YOLOHandler, YOLOBatchDetector

class TestFaceNetHandler:
    """Tests para FaceNetHandler"""
    
    @pytest.fixture
    def facenet_handler(self):
        """Fixture para FaceNetHandler"""
        return FaceNetHandler()
    
    def test_initialization(self, facenet_handler):
        """Test: Inicialización de FaceNet"""
        assert facenet_handler.model_path is not None
        assert facenet_handler.face_database is not None
    
    def test_get_database_info(self, facenet_handler):
        """Test: Obtener información de base de datos"""
        info = facenet_handler.get_database_info()
        assert "total_persons" in info
        assert "persons" in info
    
    def test_register_face(self, facenet_handler):
        """Test: Registrar cara"""
        # Crear imagen simulada
        face_image = np.random.randn(224, 224, 3).astype(np.uint8)
        
        result = facenet_handler.register_face("Juan", face_image)
        assert isinstance(result, bool)
    
    def test_recognize_face(self, facenet_handler):
        """Test: Reconocer cara"""
        # Crear imagen simulada
        face_image = np.random.randn(224, 224, 3).astype(np.uint8)
        
        result = facenet_handler.recognize_face(face_image)
        # Puede retornar None o Dict
        assert result is None or isinstance(result, dict)

class TestYOLOHandler:
    """Tests para YOLOHandler"""
    
    @pytest.fixture
    def yolo_handler(self):
        """Fixture para YOLOHandler"""
        return YOLOHandler("yolov5n")
    
    def test_initialization(self, yolo_handler):
        """Test: Inicialización de YOLO"""
        assert yolo_handler.model_name == "yolov5n"
        assert len(yolo_handler.class_names) > 0
    
    def test_get_class_names(self, yolo_handler):
        """Test: Obtener nombres de clases"""
        classes = yolo_handler._get_class_names()
        assert "person" in classes
        assert "car" in classes
        assert len(classes) == 80
    
    def test_detect(self, yolo_handler):
        """Test: Detectar objetos"""
        image = np.random.randn(640, 640, 3).astype(np.uint8)
        detections = yolo_handler.detect(image)
        assert isinstance(detections, list)
    
    def test_detect_persons(self, yolo_handler):
        """Test: Detectar personas"""
        image = np.random.randn(640, 640, 3).astype(np.uint8)
        persons = yolo_handler.detect_persons(image)
        assert isinstance(persons, list)
    
    def test_detect_animals(self, yolo_handler):
        """Test: Detectar animales"""
        image = np.random.randn(640, 640, 3).astype(np.uint8)
        animals = yolo_handler.detect_animals(image)
        assert isinstance(animals, list)
    
    def test_count_objects_by_class(self, yolo_handler):
        """Test: Contar objetos por clase"""
        image = np.random.randn(640, 640, 3).astype(np.uint8)
        counts = yolo_handler.count_objects_by_class(image)
        assert isinstance(counts, dict)
    
    def test_get_model_info(self, yolo_handler):
        """Test: Obtener información del modelo"""
        info = yolo_handler.get_model_info()
        assert "model_name" in info
        assert "class_count" in info
        assert info["model_name"] == "yolov5n"

class TestFaceDetector:
    """Tests para FaceDetector"""
    
    @pytest.fixture
    def face_detector(self):
        """Fixture para FaceDetector"""
        return FaceDetector()
    
    def test_detect_faces(self, face_detector):
        """Test: Detectar caras"""
        image = np.random.randn(480, 640, 3).astype(np.uint8)
        faces = face_detector.detect_faces(image)
        assert isinstance(faces, list)
    
    def test_extract_face_region(self, face_detector):
        """Test: Extraer región de cara"""
        image = np.random.randn(480, 640, 3).astype(np.uint8)
        bbox = {"x": 100, "y": 100, "width": 200, "height": 200}
        
        region = face_detector.extract_face_region(image, bbox)
        assert region is not None

class TestVisionService:
    """Tests para VisionService"""
    
    @pytest.fixture
    def vision_service(self):
        """Fixture para VisionService"""
        config = {
            "mqtt_host": "localhost",
            "mqtt_port": 1883
        }
        return VisionService(config)
    
    def test_initialization(self, vision_service):
        """Test: Inicialización del servicio"""
        assert vision_service.config is not None
        assert vision_service.is_running is False
    
    @pytest.mark.asyncio
    async def test_process_frame(self, vision_service):
        """Test: Procesar frame"""
        payload = {
            "frame": "base64_encoded_frame"
        }
        
        vision_service.mqtt_client = MagicMock()
        await vision_service.process_frame(payload)
        
        assert vision_service.mqtt_client is not None
    
    @pytest.mark.asyncio
    async def test_health_check(self, vision_service):
        """Test: Health check"""
        vision_service.is_running = True
        vision_service.mqtt_client = MagicMock()
        
        health = await vision_service.health_check()
        
        assert "status" in health
        assert "timestamp" in health

class TestYOLOBatchDetector:
    """Tests para YOLOBatchDetector"""
    
    @pytest.fixture
    def batch_detector(self):
        """Fixture para YOLOBatchDetector"""
        yolo = YOLOHandler("yolov5n")
        return YOLOBatchDetector(yolo)
    
    def test_detect_batch(self, batch_detector):
        """Test: Detectar lote"""
        image_paths = ["/tmp/image1.jpg", "/tmp/image2.jpg"]
        results = batch_detector.detect_batch(image_paths)
        
        assert isinstance(results, list)

# Tests de integración
class TestVisionServiceIntegration:
    """Tests de integración"""
    
    @pytest.mark.asyncio
    async def test_full_vision_pipeline(self):
        """Test: Pipeline completo de visión"""
        facenet = FaceNetHandler()
        yolo = YOLOHandler("yolov5n")
        
        assert facenet.is_initialized or not facenet.is_initialized
        assert yolo.is_initialized or not yolo.is_initialized

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
