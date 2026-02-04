#!/bin/bash

# SCRIPT DE INSTALACIÓN - VR Assistant Mejorado
# Configura todo el entorno

set -e

echo "🚀 Iniciando instalación de VR Assistant Mejorado..."

# Colores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

# Verificar Python
echo -e "${BLUE}📦 Verificando Python...${NC}"
python3 --version

# Crear directorios
echo -e "${BLUE}📁 Creando directorios...${NC}"
mkdir -p data/models
mkdir -p data/logs
mkdir -p data/rag_db
mkdir -p learning_db
mkdir -p config/grafana/provisioning

# Instalar dependencias
echo -e "${BLUE}📚 Instalando dependencias Python...${NC}"
pip install --upgrade pip
pip install -r requirements.txt

# Descargar modelos (opcional)
echo -e "${BLUE}🤖 Modelos (opcional)...${NC}"
echo "Para descargar modelos, ejecuta:"
echo "  python scripts/download_models.py"

# Docker (opcional)
if command -v docker &> /dev/null; then
    echo -e "${GREEN}✅ Docker instalado${NC}"
    echo "Para construir imágenes: docker-compose build"
    echo "Para iniciar servicios: docker-compose up -d"
else
    echo -e "${RED}⚠️  Docker no instalado${NC}"
    echo "Instala Docker desde: https://docs.docker.com/get-docker/"
fi

# Verificar estructura
echo -e "${BLUE}✓ Verificando estructura del proyecto...${NC}"
if [ -d "services" ] && [ -d "config" ] && [ -d "tests" ]; then
    echo -e "${GREEN}✅ Estructura correcta${NC}"
else
    echo -e "${RED}❌ Estructura incorrecta${NC}"
    exit 1
fi

# Tests
echo -e "${BLUE}🧪 Ejecutando tests...${NC}"
pytest tests/ -v --tb=short || echo "⚠️  Algunos tests fallaron"

echo -e "${GREEN}✅ Instalación completada${NC}"
echo ""
echo "Próximos pasos:"
echo "1. Configura variables de entorno: cp .env.example .env"
echo "2. Inicia MQTT: docker run -d -p 1883:1883 eclipse-mosquitto"
echo "3. Inicia servicios: docker-compose up -d"
echo "4. Verifica salud: curl http://localhost:8001/health"
