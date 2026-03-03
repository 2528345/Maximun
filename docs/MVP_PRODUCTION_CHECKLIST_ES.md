# MAXIMUN V5.1 - Checklist MVP Producción

## Ya listo en el repo

- Arquitectura modular (`cognitive`, `audio`, `vision`, `rag`, `iot`, `gateway`, `dashboard`)
- Deploy automatizado en MicroOS (`ops/deploy_microos.sh`)
- Perfiles runtime para 8GB
- Integridad por firmas + checksums de modelos
- MQTT endurecido con usuario/clave y TLS opcional
- Tests de contrato + CI en GitHub Actions

## Plantilla recomendada (MVP prod)

Usa este perfil:

- `config/runtime_profiles/lenovo330s_mvp_production.env`

Aplicar:

```bash
cp .env.example .env
./ops/apply_runtime_profile.sh lenovo330s_mvp_production
./ops/generate_mqtt_tls_certs.sh
./ops/generate_model_checksums.sh
./ops/deploy_microos.sh --profile lenovo330s_mvp_production
```

Nota:
- Este perfil usa `RAG_EMBED_BACKEND=sentence`, por lo que `rag-core` necesita `sentence-transformers`.
- Si operarás 100% offline, precarga el modelo `all-MiniLM-L6-v2` antes del despliegue final.

## Lo que falta para considerarlo MVP producción real

1. Secretos reales y rotación
- Cambiar `MQTT_PASSWORD` y `MASTER_HASH` por valores únicos.
- No dejar secretos en texto plano en git ni capturas.

2. TLS activo de extremo a extremo
- Mantener `MQTT_TLS_ENABLE=true` y `MQTT_CLIENT_TLS_ENABLE=true`.
- Definir política de renovación de certificados (por ejemplo cada 90-180 días).

3. Backups y recuperación probada
- Backup periódico de `/opt/maximun/data`.
- Probar restore completo (RAG + proyectos + firmas) al menos una vez por mes.

4. Monitoreo operativo
- Alertas para: RAM >90%, fallo de contenedor, pérdida de broker MQTT.
- Retención de logs con rotación (evitar llenar SSD).

5. Endurecimiento del host
- Firewall activo, puertos externos mínimos.
- Usuario sin privilegios para operación diaria.
- Actualizaciones transaccionales periódicas de MicroOS.

6. Seguridad de dashboard
- Publicar UI solo en red local o detrás de reverse proxy con autenticación.
- Evitar exponer 5173 a Internet sin control de acceso.

7. Pruebas de integración periódicas
- Ejecutar `ops/test_by_module.sh` después de cada cambio.
- Agregar test de “arranque limpio” con `.env` de producción.
- Mantener activo `ops/autocheck_modules.sh --daemon` o su servicio systemd usuario.

## Criterio mínimo de salida a producción (MVP)

- CI verde en `master`.
- `preflight_host_check.sh` sin fallos críticos.
- `check_system_consistency.sh` consistente (advertencias controladas por perfil).
- `self_test.sh` y `test_by_module.sh` pasando.
- Secretos y TLS activos.
