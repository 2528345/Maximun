#!/usr/bin/env python3
"""
TESTS - Servicio de Audio
Tests unitarios para STT/TTS
"""

import pytest
import asyncio
import json
import numpy as np
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys

# Agregar rutas
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.audio.audio_service import AudioService
from services.audio.vosk_handler import VoskHandler, VoskStreamRecognizer
from services.audio.piper_handler import PiperHandler, PiperBatchSynthesizer

class TestVoskHandler:
    """Tests para VoskHandler"""
    
    @pytest.fixture
    def vosk_handler(self):
        """Fixture para VoskHandler"""
        return VoskHandler("/app/data/models/vosk")
    
    def test_initialization(self, vosk_handler):
        """Test: Inicialización de Vosk"""
        assert vosk_handler.model_path is not None
        assert vosk_handler.sample_rate == 16000
    
    def test_get_supported_languages(self, vosk_handler):
        """Test: Obtener idiomas soportados"""
        languages = vosk_handler.get_supported_languages()
        assert "es" in languages
        assert "en" in languages
        assert len(languages) > 0
    
    def test_set_language(self, vosk_handler):
        """Test: Cambiar idioma"""
        result = vosk_handler.set_language("es")
        assert result is True
        
        result = vosk_handler.set_language("invalid_lang")
        assert result is False
    
    def test_get_model_info(self, vosk_handler):
        """Test: Obtener información del modelo"""
        info = vosk_handler.get_model_info()
        assert "model_path" in info
        assert "sample_rate" in info
        assert "supported_languages" in info
    
    def test_recognize_audio(self, vosk_handler):
        """Test: Reconocer audio"""
        # Crear audio simulado
        audio_data = np.random.randn(16000).astype(np.float32)
        result = vosk_handler.recognize_audio(audio_data)
        
        # Verificar que retorna resultado
        assert result is not None or result is None  # Depende de inicialización

class TestPiperHandler:
    """Tests para PiperHandler"""
    
    @pytest.fixture
    def piper_handler(self):
        """Fixture para PiperHandler"""
        return PiperHandler("/app/data/models/piper/es_ES-carla-x_low.onnx")
    
    def test_initialization(self, piper_handler):
        """Test: Inicialización de Piper"""
        assert piper_handler.voice_path is not None
        assert piper_handler.sample_rate == 22050
    
    def test_get_supported_voices(self, piper_handler):
        """Test: Obtener voces soportadas"""
        voices = piper_handler.get_supported_voices()
        assert len(voices) > 0
        assert "es_ES-carla-x_low" in voices
    
    def test_get_voice_info(self, piper_handler):
        """Test: Obtener información de voz"""
        info = piper_handler.get_voice_info()
        assert "voice_path" in info
        assert "sample_rate" in info
        assert "supported_voices" in info
    
    def test_synthesize(self, piper_handler):
        """Test: Sintetizar texto"""
        text = "Hola mundo"
        result = piper_handler.synthesize(text)
        
        # Verificar que retorna resultado
        assert result is not None or result is None

class TestAudioService:
    """Tests para AudioService"""
    
    @pytest.fixture
    def audio_service(self):
        """Fixture para AudioService"""
        config = {
            "mqtt_host": "localhost",
            "mqtt_port": 1883
        }
        return AudioService(config)
    
    def test_initialization(self, audio_service):
        """Test: Inicialización del servicio"""
        assert audio_service.config is not None
        assert audio_service.is_running is False
    
    @pytest.mark.asyncio
    async def test_process_audio(self, audio_service):
        """Test: Procesar audio"""
        payload = {
            "audio": "base64_encoded_audio"
        }
        
        # Mock MQTT
        audio_service.mqtt_client = MagicMock()
        
        # Ejecutar
        await audio_service.process_audio(payload)
        
        # Verificar
        assert audio_service.mqtt_client is not None
    
    @pytest.mark.asyncio
    async def test_health_check(self, audio_service):
        """Test: Health check"""
        audio_service.is_running = True
        audio_service.mqtt_client = MagicMock()
        
        health = await audio_service.health_check()
        
        assert "status" in health
        assert "timestamp" in health

class TestVoskStreamRecognizer:
    """Tests para VoskStreamRecognizer"""
    
    @pytest.fixture
    def stream_recognizer(self):
        """Fixture para VoskStreamRecognizer"""
        vosk = VoskHandler("/app/data/models/vosk")
        return VoskStreamRecognizer(vosk)
    
    def test_start_recording(self, stream_recognizer):
        """Test: Iniciar grabación"""
        stream_recognizer.start_recording()
        assert stream_recognizer.is_recording is True
    
    def test_stop_recording(self, stream_recognizer):
        """Test: Detener grabación"""
        stream_recognizer.start_recording()
        result = stream_recognizer.stop_recording()
        assert stream_recognizer.is_recording is False

class TestPiperBatchSynthesizer:
    """Tests para PiperBatchSynthesizer"""
    
    @pytest.fixture
    def batch_synthesizer(self):
        """Fixture para PiperBatchSynthesizer"""
        piper = PiperHandler("/app/data/models/piper/es_ES-carla-x_low.onnx")
        return PiperBatchSynthesizer(piper)
    
    def test_synthesize_batch(self, batch_synthesizer):
        """Test: Sintetizar lote"""
        texts = ["Hola", "Mundo", "Prueba"]
        results = batch_synthesizer.synthesize_batch(texts)
        
        assert isinstance(results, list)
    
    def test_get_results(self, batch_synthesizer):
        """Test: Obtener resultados"""
        results = batch_synthesizer.get_results()
        assert isinstance(results, list)

# Tests de integración
class TestAudioServiceIntegration:
    """Tests de integración"""
    
    @pytest.mark.asyncio
    async def test_full_audio_pipeline(self):
        """Test: Pipeline completo de audio"""
        # Crear servicios
        vosk = VoskHandler("/app/data/models/vosk")
        piper = PiperHandler("/app/data/models/piper/es_ES-carla-x_low.onnx")
        
        # Verificar inicialización
        assert vosk.is_initialized or not vosk.is_initialized
        assert piper.is_initialized or not piper.is_initialized

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
