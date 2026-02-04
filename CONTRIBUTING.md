# 🤝 Guía de Contribución

¡Gracias por tu interés en contribuir a VR Assistant Mejorado!

## 📋 Código de conducta

Por favor, sé respetuoso y constructivo en todas las interacciones.

## 🚀 Cómo contribuir

### 1. Fork el proyecto
```bash
# Haz clic en "Fork" en GitHub
```

### 2. Clona tu fork
```bash
git clone https://github.com/tu-usuario/vr-assistant-mejorado.git
cd vr-assistant-mejorado
```

### 3. Crea una rama para tu feature
```bash
git checkout -b feature/nombre-del-feature
```

### 4. Haz tus cambios
- Sigue el estilo de código existente
- Agrega tests para nuevas funcionalidades
- Actualiza la documentación

### 5. Ejecuta tests
```bash
pytest tests/ --cov=services
```

### 6. Commit tus cambios
```bash
git commit -m "Descripción clara del cambio"
```

### 7. Push a tu rama
```bash
git push origin feature/nombre-del-feature
```

### 8. Abre un Pull Request
- Describe claramente qué cambios hiciste
- Referencia cualquier issue relacionado

## 📝 Estilo de código

- Usa **Black** para formateo
- Sigue **PEP 8**
- Agrega docstrings a funciones
- Usa type hints

```python
def process_audio(audio_data: bytes, language: str = "es") -> str:
    """
    Procesar audio y retornar texto.
    
    Args:
        audio_data: Datos de audio en bytes
        language: Código de idioma (default: "es")
    
    Returns:
        Texto reconocido
    """
    pass
```

## 🧪 Testing

- Escribe tests para nuevas funcionalidades
- Mantén cobertura > 80%
- Usa pytest

```bash
# Ejecutar tests
pytest tests/

# Con cobertura
pytest --cov=services tests/

# Tests específicos
pytest tests/test_audio.py -v
```

## 📚 Documentación

- Actualiza README.md si es necesario
- Agrega docstrings a código nuevo
- Actualiza docs/ si cambias arquitectura

## 🐛 Reportar bugs

Abre un Issue con:
- Descripción clara del problema
- Pasos para reproducir
- Comportamiento esperado
- Comportamiento actual
- Sistema operativo y versión

## 💡 Sugerir mejoras

Abre un Issue con:
- Descripción de la mejora
- Caso de uso
- Beneficios

## 📞 Preguntas

- Abre un Discussion en GitHub
- Revisa la documentación existente

---

¡Gracias por contribuir! 🎉
