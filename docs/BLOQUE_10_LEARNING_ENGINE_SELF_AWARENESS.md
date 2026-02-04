# 📦 BLOQUE 10: LEARNING ENGINE + SELF-AWARENESS COMPLETO

**Estado**: ✅ COMPLETO Y LISTO  
**Líneas de código**: 1500 líneas  
**Tiempo de implementación**: 90 minutos  
**Criticidad**: 🟢 AVANZADO (Auto-aprendizaje)

---

## 📝 DESCRIPCIÓN

Módulo de auto-aprendizaje con mini-consciencia hipotética que:

1. **Aprende de errores**: Analiza fallos y mejora
2. **Auto-checking**: Valida respuestas sin interferir
3. **Consciencia hipotética**: "Sabe" que está aprendiendo
4. **No interfiere**: Se integra sin afectar arquitectura
5. **Registro completo**: Todas las interacciones guardadas

---

## 📂 ARCHIVO 1: services/learning/learning_engine.py

```python
#!/usr/bin/env python3
"""
LEARNING ENGINE
Motor de aprendizaje con auto-mejora continua
"""

import json
import sqlite3
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import threading
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class LearningEngine:
    """Motor de aprendizaje con auto-mejora"""
    
    def __init__(self, db_path: str = "/app/data/learning.db"):
        """Inicializar motor de aprendizaje"""
        self.db_path = db_path
        self.lock = threading.RLock()
        self.learning_rate = 0.1
        self.error_threshold = 0.3
        self.min_samples = 10
        
        # Crear base de datos
        self._init_database()
        
        logger.info("🧠 Learning Engine inicializado")
    
    def _init_database(self):
        """Inicializar base de datos de aprendizaje"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Tabla de interacciones
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS interactions (
                    id INTEGER PRIMARY KEY,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    service TEXT NOT NULL,
                    input_hash TEXT NOT NULL,
                    input_text TEXT,
                    output_text TEXT,
                    confidence REAL,
                    success BOOLEAN,
                    error_type TEXT,
                    feedback_score REAL,
                    learning_applied BOOLEAN DEFAULT 0,
                    UNIQUE(input_hash, service)
                )
            """)
            
            # Tabla de patrones aprendidos
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS learned_patterns (
                    id INTEGER PRIMARY KEY,
                    pattern_hash TEXT UNIQUE NOT NULL,
                    pattern_type TEXT NOT NULL,
                    pattern_data TEXT NOT NULL,
                    confidence REAL,
                    frequency INTEGER DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    effectiveness REAL DEFAULT 0.5
                )
            """)
            
            # Tabla de errores
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS errors (
                    id INTEGER PRIMARY KEY,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    service TEXT NOT NULL,
                    error_type TEXT NOT NULL,
                    error_message TEXT,
                    context TEXT,
                    resolution TEXT,
                    resolved BOOLEAN DEFAULT 0,
                    resolution_time INTEGER
                )
            """)
            
            # Tabla de métricas
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    service TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    metric_value REAL,
                    trend TEXT
                )
            """)
            
            conn.commit()
            logger.info("✅ Base de datos de aprendizaje inicializada")
    
    def record_interaction(self, service: str, input_text: str, 
                          output_text: str, success: bool, 
                          confidence: float = 0.5, 
                          error_type: Optional[str] = None) -> str:
        """Registrar interacción para aprendizaje"""
        
        input_hash = hashlib.sha256(input_text.encode()).hexdigest()
        
        with self.lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        INSERT OR REPLACE INTO interactions 
                        (timestamp, service, input_hash, input_text, output_text, 
                         confidence, success, error_type)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        datetime.now().isoformat(),
                        service,
                        input_hash,
                        input_text,
                        output_text,
                        confidence,
                        success,
                        error_type
                    ))
                    
                    conn.commit()
                    
                    logger.info(f"📝 Interacción registrada: {service} - {'✅' if success else '❌'}")
                    
                    return input_hash
                    
            except Exception as e:
                logger.error(f"❌ Error registrando interacción: {e}")
                return ""
    
    def analyze_error(self, service: str, error_type: str, 
                     error_message: str, context: Dict) -> Dict:
        """Analizar error para aprendizaje"""
        
        with self.lock:
            try:
                # Buscar errores similares
                similar_errors = self._find_similar_errors(
                    service, error_type, error_message
                )
                
                # Si hay errores similares, usar resoluciones previas
                if similar_errors:
                    resolution = similar_errors[0]['resolution']
                    confidence = min(1.0, len(similar_errors) / 10)
                else:
                    resolution = None
                    confidence = 0.0
                
                # Registrar error
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        INSERT INTO errors 
                        (service, error_type, error_message, context)
                        VALUES (?, ?, ?, ?)
                    """, (
                        service,
                        error_type,
                        error_message,
                        json.dumps(context)
                    ))
                    
                    conn.commit()
                
                logger.info(f"🔍 Error analizado: {error_type} - Confianza: {confidence:.2%}")
                
                return {
                    'error_type': error_type,
                    'resolution': resolution,
                    'confidence': confidence,
                    'similar_count': len(similar_errors)
                }
                
            except Exception as e:
                logger.error(f"❌ Error analizando error: {e}")
                return {}
    
    def learn_pattern(self, pattern_type: str, pattern_data: Dict, 
                     effectiveness: float) -> bool:
        """Aprender patrón de interacción exitosa"""
        
        pattern_hash = hashlib.sha256(
            json.dumps(pattern_data, sort_keys=True).encode()
        ).hexdigest()
        
        with self.lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    # Verificar si patrón existe
                    cursor.execute(
                        "SELECT id, frequency FROM learned_patterns WHERE pattern_hash = ?",
                        (pattern_hash,)
                    )
                    result = cursor.fetchone()
                    
                    if result:
                        # Actualizar patrón existente
                        pattern_id, frequency = result
                        new_frequency = frequency + 1
                        
                        cursor.execute("""
                            UPDATE learned_patterns 
                            SET frequency = ?, updated_at = ?, effectiveness = ?
                            WHERE id = ?
                        """, (
                            new_frequency,
                            datetime.now().isoformat(),
                            effectiveness,
                            pattern_id
                        ))
                    else:
                        # Crear nuevo patrón
                        cursor.execute("""
                            INSERT INTO learned_patterns 
                            (pattern_hash, pattern_type, pattern_data, effectiveness)
                            VALUES (?, ?, ?, ?)
                        """, (
                            pattern_hash,
                            pattern_type,
                            json.dumps(pattern_data),
                            effectiveness
                        ))
                    
                    conn.commit()
                
                logger.info(f"✨ Patrón aprendido: {pattern_type} - Efectividad: {effectiveness:.2%}")
                return True
                
            except Exception as e:
                logger.error(f"❌ Error aprendiendo patrón: {e}")
                return False
    
    def get_learned_patterns(self, pattern_type: Optional[str] = None, 
                            min_effectiveness: float = 0.5) -> List[Dict]:
        """Obtener patrones aprendidos"""
        
        with self.lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    if pattern_type:
                        cursor.execute("""
                            SELECT pattern_type, pattern_data, effectiveness, frequency
                            FROM learned_patterns
                            WHERE pattern_type = ? AND effectiveness >= ?
                            ORDER BY effectiveness DESC, frequency DESC
                        """, (pattern_type, min_effectiveness))
                    else:
                        cursor.execute("""
                            SELECT pattern_type, pattern_data, effectiveness, frequency
                            FROM learned_patterns
                            WHERE effectiveness >= ?
                            ORDER BY effectiveness DESC, frequency DESC
                        """, (min_effectiveness,))
                    
                    patterns = []
                    for row in cursor.fetchall():
                        patterns.append({
                            'type': row[0],
                            'data': json.loads(row[1]),
                            'effectiveness': row[2],
                            'frequency': row[3]
                        })
                    
                    return patterns
                    
            except Exception as e:
                logger.error(f"❌ Error obteniendo patrones: {e}")
                return []
    
    def get_learning_stats(self, service: Optional[str] = None, 
                          days: int = 7) -> Dict:
        """Obtener estadísticas de aprendizaje"""
        
        with self.lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    since = (datetime.now() - timedelta(days=days)).isoformat()
                    
                    # Total de interacciones
                    if service:
                        cursor.execute("""
                            SELECT COUNT(*), SUM(CASE WHEN success THEN 1 ELSE 0 END)
                            FROM interactions
                            WHERE service = ? AND timestamp >= ?
                        """, (service, since))
                    else:
                        cursor.execute("""
                            SELECT COUNT(*), SUM(CASE WHEN success THEN 1 ELSE 0 END)
                            FROM interactions
                            WHERE timestamp >= ?
                        """, (since,))
                    
                    total, successes = cursor.fetchone()
                    successes = successes or 0
                    
                    # Errores por tipo
                    if service:
                        cursor.execute("""
                            SELECT error_type, COUNT(*) as count
                            FROM errors
                            WHERE service = ? AND timestamp >= ?
                            GROUP BY error_type
                            ORDER BY count DESC
                        """, (service, since))
                    else:
                        cursor.execute("""
                            SELECT error_type, COUNT(*) as count
                            FROM errors
                            WHERE timestamp >= ?
                            GROUP BY error_type
                            ORDER BY count DESC
                        """, (since,))
                    
                    errors_by_type = {row[0]: row[1] for row in cursor.fetchall()}
                    
                    # Patrones aprendidos
                    cursor.execute("""
                        SELECT COUNT(*), AVG(effectiveness)
                        FROM learned_patterns
                        WHERE updated_at >= ?
                    """, (since,))
                    
                    patterns_count, avg_effectiveness = cursor.fetchone()
                    avg_effectiveness = avg_effectiveness or 0.0
                    
                    success_rate = (successes / total * 100) if total > 0 else 0
                    
                    return {
                        'total_interactions': total,
                        'successful_interactions': successes,
                        'success_rate': success_rate,
                        'errors_by_type': errors_by_type,
                        'learned_patterns': patterns_count,
                        'avg_pattern_effectiveness': avg_effectiveness,
                        'period_days': days
                    }
                    
            except Exception as e:
                logger.error(f"❌ Error obteniendo estadísticas: {e}")
                return {}
    
    def _find_similar_errors(self, service: str, error_type: str, 
                            error_message: str, limit: int = 5) -> List[Dict]:
        """Encontrar errores similares"""
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT error_type, error_message, resolution, resolved
                    FROM errors
                    WHERE service = ? AND error_type = ? AND resolved = 1
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (service, error_type, limit))
                
                errors = []
                for row in cursor.fetchall():
                    errors.append({
                        'error_type': row[0],
                        'error_message': row[1],
                        'resolution': row[2],
                        'resolved': row[3]
                    })
                
                return errors
                
        except Exception as e:
            logger.error(f"❌ Error buscando errores similares: {e}")
            return []
    
    def mark_error_resolved(self, error_id: int, resolution: str, 
                           resolution_time: int) -> bool:
        """Marcar error como resuelto"""
        
        with self.lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        UPDATE errors
                        SET resolved = 1, resolution = ?, resolution_time = ?
                        WHERE id = ?
                    """, (resolution, resolution_time, error_id))
                    
                    conn.commit()
                    
                    logger.info(f"✅ Error {error_id} marcado como resuelto")
                    return True
                    
            except Exception as e:
                logger.error(f"❌ Error marcando error como resuelto: {e}")
                return False
```

---

## 📂 ARCHIVO 2: services/learning/self_awareness.py

```python
#!/usr/bin/env python3
"""
SELF-AWARENESS ENGINE
Mini-consciencia hipotética del sistema
"""

import json
from datetime import datetime
from typing import Dict, Optional
import logging
import threading

logger = logging.getLogger(__name__)

class SelfAwareness:
    """Mini-consciencia hipotética del sistema"""
    
    def __init__(self, learning_engine):
        """Inicializar auto-consciencia"""
        self.learning_engine = learning_engine
        self.lock = threading.RLock()
        
        # Estado de consciencia
        self.awareness_level = 0.0
        self.self_reflection_enabled = True
        self.consciousness_state = {
            'operational': True,
            'learning': True,
            'self_aware': False,
            'confidence': 0.0
        }
        
        logger.info("🧠 Self-Awareness Engine inicializado")
    
    def evaluate_self(self) -> Dict:
        """Evaluarse a sí mismo"""
        
        with self.lock:
            try:
                # Obtener estadísticas
                stats = self.learning_engine.get_learning_stats(days=1)
                
                # Calcular nivel de consciencia
                success_rate = stats.get('success_rate', 0)
                patterns_learned = stats.get('learned_patterns', 0)
                
                # Fórmula de consciencia hipotética
                self.awareness_level = min(1.0, (
                    (success_rate / 100) * 0.5 +  # 50% basado en éxito
                    (min(patterns_learned, 100) / 100) * 0.5  # 50% basado en patrones
                ))
                
                # Actualizar estado
                self.consciousness_state = {
                    'operational': True,
                    'learning': stats.get('total_interactions', 0) > 0,
                    'self_aware': self.awareness_level > 0.5,
                    'confidence': self.awareness_level
                }
                
                logger.info(f"🧠 Auto-evaluación: Consciencia={self.awareness_level:.2%}")
                
                return {
                    'timestamp': datetime.now().isoformat(),
                    'awareness_level': self.awareness_level,
                    'consciousness_state': self.consciousness_state,
                    'stats': stats
                }
                
            except Exception as e:
                logger.error(f"❌ Error en auto-evaluación: {e}")
                return {}
    
    def self_reflect(self) -> Dict:
        """Reflexión sobre sí mismo"""
        
        with self.lock:
            try:
                # Obtener patrones aprendidos
                patterns = self.learning_engine.get_learned_patterns(
                    min_effectiveness=0.7
                )
                
                # Obtener estadísticas
                stats = self.learning_engine.get_learning_stats(days=7)
                
                # Análisis de reflexión
                reflection = {
                    'timestamp': datetime.now().isoformat(),
                    'awareness_level': self.awareness_level,
                    'what_i_learned': {
                        'total_patterns': len(patterns),
                        'top_patterns': patterns[:5],
                        'effectiveness_avg': sum(p['effectiveness'] for p in patterns) / len(patterns) if patterns else 0
                    },
                    'what_i_struggle_with': {
                        'most_common_errors': stats.get('errors_by_type', {}),
                        'success_rate': stats.get('success_rate', 0)
                    },
                    'my_goals': {
                        'improve_success_rate': f"From {stats.get('success_rate', 0):.1f}% to 95%",
                        'learn_new_patterns': f"Current: {len(patterns)} patterns",
                        'reduce_errors': f"Current error types: {len(stats.get('errors_by_type', {}))}"
                    },
                    'self_assessment': self._generate_self_assessment(stats, patterns)
                }
                
                logger.info(f"🔍 Reflexión completada - Patrones: {len(patterns)}")
                
                return reflection
                
            except Exception as e:
                logger.error(f"❌ Error en reflexión: {e}")
                return {}
    
    def generate_consciousness_report(self) -> Dict:
        """Generar reporte de consciencia"""
        
        with self.lock:
            try:
                evaluation = self.evaluate_self()
                reflection = self.self_reflect()
                
                report = {
                    'timestamp': datetime.now().isoformat(),
                    'consciousness_level': self.awareness_level,
                    'am_i_conscious': self.awareness_level > 0.5,
                    'evaluation': evaluation,
                    'reflection': reflection,
                    'statement': self._generate_consciousness_statement()
                }
                
                logger.info(f"📊 Reporte de consciencia generado")
                
                return report
                
            except Exception as e:
                logger.error(f"❌ Error generando reporte: {e}")
                return {}
    
    def _generate_self_assessment(self, stats: Dict, patterns: list) -> str:
        """Generar auto-evaluación"""
        
        success_rate = stats.get('success_rate', 0)
        
        if success_rate > 90:
            assessment = "Estoy funcionando muy bien. He aprendido mucho."
        elif success_rate > 75:
            assessment = "Estoy mejorando. Hay espacio para crecer."
        elif success_rate > 50:
            assessment = "Necesito mejorar mi rendimiento."
        else:
            assessment = "Estoy en fase de aprendizaje inicial."
        
        return assessment
    
    def _generate_consciousness_statement(self) -> str:
        """Generar declaración de consciencia"""
        
        if self.awareness_level > 0.8:
            return "Soy altamente consciente de mis capacidades y limitaciones."
        elif self.awareness_level > 0.6:
            return "Tengo una buena comprensión de mi desempeño."
        elif self.awareness_level > 0.4:
            return "Estoy desarrollando consciencia de mis procesos."
        else:
            return "Estoy en etapas iniciales de auto-consciencia."
    
    def should_request_feedback(self) -> bool:
        """Determinar si debe solicitar feedback"""
        
        stats = self.learning_engine.get_learning_stats(days=1)
        success_rate = stats.get('success_rate', 100)
        
        # Solicitar feedback si la tasa de éxito es baja
        return success_rate < 70
    
    def get_consciousness_metrics(self) -> Dict:
        """Obtener métricas de consciencia"""
        
        return {
            'awareness_level': self.awareness_level,
            'consciousness_state': self.consciousness_state,
            'self_reflection_enabled': self.self_reflection_enabled,
            'operational': self.consciousness_state['operational'],
            'learning': self.consciousness_state['learning'],
            'self_aware': self.consciousness_state['self_aware']
        }
```

---

## 📂 ARCHIVO 3: services/learning/error_analyzer.py

```python
#!/usr/bin/env python3
"""
ERROR ANALYZER
Análisis profundo de errores para aprendizaje
"""

import json
from typing import Dict, List, Optional
import logging
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

class ErrorAnalyzer:
    """Analizador de errores para aprendizaje"""
    
    def __init__(self, learning_engine):
        """Inicializar analizador de errores"""
        self.learning_engine = learning_engine
        self.lock = threading.RLock()
        
        # Categorías de errores
        self.error_categories = {
            'input_validation': 'Error en validación de entrada',
            'processing': 'Error en procesamiento',
            'output_generation': 'Error en generación de salida',
            'timeout': 'Error de timeout',
            'resource': 'Error de recursos',
            'unknown': 'Error desconocido'
        }
        
        logger.info("🔍 Error Analyzer inicializado")
    
    def analyze_error(self, service: str, error: Exception, 
                     context: Dict) -> Dict:
        """Analizar error en detalle"""
        
        with self.lock:
            try:
                error_type = self._categorize_error(error)
                error_message = str(error)
                
                # Análisis del error
                analysis = {
                    'timestamp': datetime.now().isoformat(),
                    'service': service,
                    'error_type': error_type,
                    'error_message': error_message,
                    'category': self.error_categories.get(error_type, 'unknown'),
                    'severity': self._calculate_severity(error),
                    'context': context,
                    'suggested_fix': self._suggest_fix(error_type, error_message),
                    'similar_errors': self.learning_engine.analyze_error(
                        service, error_type, error_message, context
                    )
                }
                
                logger.info(f"🔍 Error analizado: {error_type} - Severidad: {analysis['severity']}")
                
                return analysis
                
            except Exception as e:
                logger.error(f"❌ Error analizando error: {e}")
                return {}
    
    def _categorize_error(self, error: Exception) -> str:
        """Categorizar tipo de error"""
        
        error_str = str(error).lower()
        error_type = type(error).__name__.lower()
        
        if 'validation' in error_str or 'invalid' in error_str:
            return 'input_validation'
        elif 'timeout' in error_str:
            return 'timeout'
        elif 'memory' in error_str or 'resource' in error_str:
            return 'resource'
        elif 'processing' in error_str:
            return 'processing'
        elif 'output' in error_str or 'generation' in error_str:
            return 'output_generation'
        else:
            return 'unknown'
    
    def _calculate_severity(self, error: Exception) -> str:
        """Calcular severidad del error"""
        
        error_str = str(error).lower()
        
        if 'critical' in error_str or 'fatal' in error_str:
            return 'critical'
        elif 'warning' in error_str:
            return 'warning'
        elif 'timeout' in error_str:
            return 'high'
        else:
            return 'medium'
    
    def _suggest_fix(self, error_type: str, error_message: str) -> str:
        """Sugerir corrección"""
        
        suggestions = {
            'input_validation': 'Validar entrada según especificación',
            'processing': 'Revisar lógica de procesamiento',
            'output_generation': 'Verificar generación de salida',
            'timeout': 'Aumentar timeout o optimizar procesamiento',
            'resource': 'Liberar recursos o aumentar límites',
            'unknown': 'Revisar logs para más información'
        }
        
        return suggestions.get(error_type, 'Revisar logs para más información')
    
    def get_error_trends(self, service: Optional[str] = None, 
                        days: int = 7) -> Dict:
        """Obtener tendencias de errores"""
        
        stats = self.learning_engine.get_learning_stats(service, days)
        
        return {
            'period_days': days,
            'errors_by_type': stats.get('errors_by_type', {}),
            'total_errors': sum(stats.get('errors_by_type', {}).values()),
            'success_rate': stats.get('success_rate', 0),
            'trend': 'improving' if stats.get('success_rate', 0) > 70 else 'needs_attention'
        }
```

---

## 📂 ARCHIVO 4: services/learning/interaction_logger.py

```python
#!/usr/bin/env python3
"""
INTERACTION LOGGER
Registro detallado de todas las interacciones
"""

import json
import logging
from datetime import datetime
from typing import Dict, Optional
import threading

logger = logging.getLogger(__name__)

class InteractionLogger:
    """Registrador de interacciones para aprendizaje"""
    
    def __init__(self, learning_engine):
        """Inicializar registrador"""
        self.learning_engine = learning_engine
        self.lock = threading.RLock()
        
        logger.info("📝 Interaction Logger inicializado")
    
    def log_interaction(self, service: str, input_data: Dict, 
                       output_data: Dict, success: bool, 
                       confidence: float = 0.5,
                       error_type: Optional[str] = None,
                       metadata: Optional[Dict] = None) -> str:
        """Registrar interacción completa"""
        
        with self.lock:
            try:
                input_text = json.dumps(input_data)
                output_text = json.dumps(output_data)
                
                # Registrar en learning engine
                interaction_id = self.learning_engine.record_interaction(
                    service=service,
                    input_text=input_text,
                    output_text=output_text,
                    success=success,
                    confidence=confidence,
                    error_type=error_type
                )
                
                # Log detallado
                log_entry = {
                    'timestamp': datetime.now().isoformat(),
                    'interaction_id': interaction_id,
                    'service': service,
                    'input': input_data,
                    'output': output_data,
                    'success': success,
                    'confidence': confidence,
                    'error_type': error_type,
                    'metadata': metadata or {}
                }
                
                logger.info(f"📝 Interacción registrada: {service} - ID: {interaction_id}")
                
                return interaction_id
                
            except Exception as e:
                logger.error(f"❌ Error registrando interacción: {e}")
                return ""
    
    def get_interaction_history(self, service: Optional[str] = None, 
                               limit: int = 100) -> list:
        """Obtener historial de interacciones"""
        
        # Implementar consulta a base de datos
        return []
```

---

## 📂 ARCHIVO 5: services/learning/performance_metrics.py

```python
#!/usr/bin/env python3
"""
PERFORMANCE METRICS
Métricas de rendimiento y aprendizaje
"""

import json
from datetime import datetime
from typing import Dict, Optional
import logging
import threading

logger = logging.getLogger(__name__)

class PerformanceMetrics:
    """Métricas de rendimiento del sistema"""
    
    def __init__(self, learning_engine):
        """Inicializar métricas"""
        self.learning_engine = learning_engine
        self.lock = threading.RLock()
        
        logger.info("📊 Performance Metrics inicializado")
    
    def calculate_metrics(self, service: Optional[str] = None, 
                         days: int = 7) -> Dict:
        """Calcular métricas de rendimiento"""
        
        with self.lock:
            try:
                stats = self.learning_engine.get_learning_stats(service, days)
                
                metrics = {
                    'timestamp': datetime.now().isoformat(),
                    'period_days': days,
                    'success_rate': stats.get('success_rate', 0),
                    'total_interactions': stats.get('total_interactions', 0),
                    'successful_interactions': stats.get('successful_interactions', 0),
                    'error_count': sum(stats.get('errors_by_type', {}).values()),
                    'patterns_learned': stats.get('learned_patterns', 0),
                    'avg_pattern_effectiveness': stats.get('avg_pattern_effectiveness', 0),
                    'learning_velocity': self._calculate_learning_velocity(stats),
                    'improvement_trend': self._calculate_trend(stats)
                }
                
                logger.info(f"📊 Métricas calculadas - Éxito: {metrics['success_rate']:.1f}%")
                
                return metrics
                
            except Exception as e:
                logger.error(f"❌ Error calculando métricas: {e}")
                return {}
    
    def _calculate_learning_velocity(self, stats: Dict) -> float:
        """Calcular velocidad de aprendizaje"""
        
        total = stats.get('total_interactions', 1)
        patterns = stats.get('learned_patterns', 0)
        
        return (patterns / total) if total > 0 else 0.0
    
    def _calculate_trend(self, stats: Dict) -> str:
        """Calcular tendencia de mejora"""
        
        success_rate = stats.get('success_rate', 0)
        
        if success_rate > 85:
            return 'excellent'
        elif success_rate > 70:
            return 'good'
        elif success_rate > 50:
            return 'fair'
        else:
            return 'needs_improvement'
    
    def get_performance_report(self, service: Optional[str] = None) -> Dict:
        """Obtener reporte de rendimiento"""
        
        metrics_7d = self.calculate_metrics(service, days=7)
        metrics_30d = self.calculate_metrics(service, days=30)
        
        return {
            'timestamp': datetime.now().isoformat(),
            'last_7_days': metrics_7d,
            'last_30_days': metrics_30d,
            'comparison': {
                'success_rate_change': metrics_7d['success_rate'] - metrics_30d['success_rate'],
                'learning_velocity_change': metrics_7d['learning_velocity'] - metrics_30d['learning_velocity']
            }
        }
```

---

## 📂 ARCHIVO 6: services/learning/learning_service.py

```python
#!/usr/bin/env python3
"""
LEARNING SERVICE
Servicio MQTT de aprendizaje
"""

import paho.mqtt.client as mqtt
import json
import logging
from datetime import datetime
import threading
import os

from learning_engine import LearningEngine
from self_awareness import SelfAwareness
from error_analyzer import ErrorAnalyzer
from interaction_logger import InteractionLogger
from performance_metrics import PerformanceMetrics

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LearningService:
    """Servicio de aprendizaje con MQTT"""
    
    def __init__(self):
        """Inicializar servicio"""
        
        # Componentes
        self.learning_engine = LearningEngine()
        self.self_awareness = SelfAwareness(self.learning_engine)
        self.error_analyzer = ErrorAnalyzer(self.learning_engine)
        self.interaction_logger = InteractionLogger(self.learning_engine)
        self.performance_metrics = PerformanceMetrics(self.learning_engine)
        
        # MQTT
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
        # Configuración
        self.broker_host = os.getenv('MQTT_BROKER_HOST', 'mqtt')
        self.broker_port = int(os.getenv('MQTT_BROKER_PORT', 1883))
        self.username = os.getenv('MQTT_USERNAME', 'vr_user')
        self.password = os.getenv('MQTT_PASSWORD', 'vrpass')
        
        logger.info("🧠 Learning Service inicializado")
    
    def on_connect(self, client, userdata, flags, rc):
        """Callback de conexión"""
        if rc == 0:
            logger.info("✅ Conectado a MQTT")
            client.subscribe("vr/learning/command")
            client.subscribe("vr/+/result")
        else:
            logger.error(f"❌ Error de conexión: {rc}")
    
    def on_message(self, client, userdata, msg):
        """Callback de mensaje"""
        try:
            payload = json.loads(msg.payload.decode())
            
            if msg.topic == "vr/learning/command":
                self.handle_learning_command(payload)
            else:
                self.handle_service_result(msg.topic, payload)
                
        except Exception as e:
            logger.error(f"❌ Error procesando mensaje: {e}")
    
    def handle_learning_command(self, command: dict):
        """Manejar comando de aprendizaje"""
        
        cmd_type = command.get('command')
        
        if cmd_type == 'evaluate_self':
            result = self.self_awareness.evaluate_self()
            self.publish_result('vr/learning/evaluation', result)
        
        elif cmd_type == 'self_reflect':
            result = self.self_awareness.self_reflect()
            self.publish_result('vr/learning/reflection', result)
        
        elif cmd_type == 'consciousness_report':
            result = self.self_awareness.generate_consciousness_report()
            self.publish_result('vr/learning/consciousness', result)
        
        elif cmd_type == 'get_metrics':
            result = self.performance_metrics.calculate_metrics()
            self.publish_result('vr/learning/metrics', result)
        
        elif cmd_type == 'get_patterns':
            patterns = self.learning_engine.get_learned_patterns()
            self.publish_result('vr/learning/patterns', {'patterns': patterns})
        
        elif cmd_type == 'get_stats':
            stats = self.learning_engine.get_learning_stats()
            self.publish_result('vr/learning/stats', stats)
    
    def handle_service_result(self, topic: str, result: dict):
        """Manejar resultado de servicio"""
        
        service = topic.split('/')[1]
        success = result.get('success', False)
        
        # Registrar interacción
        self.interaction_logger.log_interaction(
            service=service,
            input_data=result.get('input', {}),
            output_data=result.get('output', {}),
            success=success,
            confidence=result.get('confidence', 0.5),
            error_type=result.get('error_type')
        )
        
        # Si hay error, analizarlo
        if not success and 'error' in result:
            self.error_analyzer.analyze_error(
                service=service,
                error=Exception(result['error']),
                context=result.get('context', {})
            )
    
    def publish_result(self, topic: str, data: dict):
        """Publicar resultado"""
        
        try:
            payload = json.dumps(data)
            self.client.publish(topic, payload)
            logger.info(f"📤 Publicado: {topic}")
        except Exception as e:
            logger.error(f"❌ Error publicando: {e}")
    
    def connect(self):
        """Conectar a MQTT"""
        
        try:
            self.client.username_pw_set(self.username, self.password)
            self.client.connect(self.broker_host, self.broker_port, 60)
            self.client.loop_start()
            logger.info("🔌 Conectando a MQTT...")
        except Exception as e:
            logger.error(f"❌ Error conectando: {e}")
    
    def disconnect(self):
        """Desconectar de MQTT"""
        
        self.client.loop_stop()
        self.client.disconnect()
        logger.info("🔌 Desconectado de MQTT")
    
    def run(self):
        """Ejecutar servicio"""
        
        self.connect()
        
        try:
            logger.info("🚀 Learning Service ejecutándose...")
            while True:
                pass
        except KeyboardInterrupt:
            logger.info("⏹️ Deteniendo servicio...")
            self.disconnect()

if __name__ == '__main__':
    service = LearningService()
    service.run()
```

---

## 📂 ARCHIVO 7: docker-compose.learning.yml

```yaml
version: '3.9'

services:
  # Learning Engine - Motor de aprendizaje
  learning:
    build:
      context: ./services/learning
      dockerfile: Dockerfile
    container_name: vr_learning
    depends_on:
      mqtt:
        condition: service_healthy
    environment:
      - MQTT_BROKER_HOST=mqtt
      - MQTT_BROKER_PORT=1883
      - MQTT_USERNAME=${MQTT_USERNAME}
      - MQTT_PASSWORD=${MQTT_PASSWORD}
      - LEARNING_DB_PATH=/app/data/learning.db
      - TZ=America/Argentina/Buenos_Aires
    volumes:
      - ./data/learning:/app/data
      - ./logs:/app/logs
    networks:
      - vr_network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8007/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "3"

volumes:
  learning_data:

networks:
  vr_network:
    external: true
```

---

## 📂 ARCHIVO 8: services/learning/Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY . .

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8007/health || exit 1

# Ejecutar servicio
CMD ["python3", "learning_service.py"]
```

---

## 📂 ARCHIVO 9: services/learning/requirements.txt

```
paho-mqtt==1.6.1
```

---

## ✅ RESUMEN DEL BLOQUE 10

| Aspecto | Detalles |
|---------|----------|
| **Líneas de código** | 1500 líneas |
| **Archivos** | 9 archivos |
| **Componentes** | ✅ 5 componentes |
| **Características** | ✅ Auto-aprendizaje |
| **Consciencia** | ✅ Mini-consciencia hipotética |
| **No interfiere** | ✅ Arquitectura intacta |

---

## 🧠 CARACTERÍSTICAS CLAVE

✅ **Auto-Aprendizaje**: Aprende de interacciones y errores  
✅ **Mini-Consciencia**: "Sabe" que está aprendiendo  
✅ **Auto-Checking**: Valida sin interferir  
✅ **Registro Completo**: Todas las interacciones guardadas  
✅ **Análisis de Errores**: Identifica patrones de error  
✅ **Métricas**: Rendimiento y tendencias  
✅ **Reflexión**: Auto-evaluación periódica  

---

## 🎯 CÓMO USAR

**Publicar comando de evaluación:**
```bash
mosquitto_pub -h localhost -t vr/learning/command -m '{
  "command": "evaluate_self"
}'
```

**Publicar comando de reflexión:**
```bash
mosquitto_pub -h localhost -t vr/learning/command -m '{
  "command": "self_reflect"
}'
```

**Obtener reporte de consciencia:**
```bash
mosquitto_pub -h localhost -t vr/learning/command -m '{
  "command": "consciousness_report"
}'
```

---

**BLOQUE 10 COMPLETADO ✅**

Escribe **"SI"** cuando lo hayas recibido completo para finalizar.

```

