# Arquitectura de SATO

Documento técnico de referencia. La visión general, los diagramas y la guía de uso están en el [README](../../README.md);
las decisiones con su evidencia, en [DECISIONS.md](../DECISIONS.md).

## 1. Componentes

| Componente | Tecnología | Responsabilidad | Código |
|---|---|---|---|
| Pipeline de datos y ML | Python 3.12, DuckDB, pandas, LightGBM, SHAP | Descarga, normalización, integración, variables, entrenamiento, explicaciones, monitoreo y carga | `sato/` (salvo `api/`) |
| Base de datos | PostgreSQL 16 (`pg_trgm`, `unaccent`, texto completo en español) | Datos servidos, historial de cargas, usuarios, revisiones, suscripciones y auditoría | `db/migrations/` |
| API | FastAPI, SQLAlchemy Core, slowapi, PyJWT, bcrypt, ReportLab | Lectura pública, revisión autenticada, informes PDF, estado y monitoreo | `sato/api/` |
| Interfaz | React 19, TypeScript, Vite, Tailwind, Radix UI, Recharts, Leaflet, TanStack Query | Panorama, alertas, cartera, fichas, validación, fuentes, estado del sistema | `web/src/` |
| Proxy web | nginx 1.27 | Archivos estáticos, proxy `/api`, límites de tasa, cabeceras de seguridad | `docker/nginx.conf` |
| Worker | Python (`sato.cron_runner`) | Sincronización mensual autocontrolada y resumen semanal por correo | `sato/cron_runner.py` |
| HTTPS (producción) | Caddy 2 | Certificados automáticos y HSTS | `deploy/` |

## 2. Decisiones de arquitectura

| Decisión | Alternativas evaluadas | Razón |
|---|---|---|
| **DuckDB + Parquet** para el procesamiento analítico | Spark, pandas puro, PostgreSQL como data lake | ~3 GB brutos; los CSV anuales de SIAF (7–10 GB) se agregan en un minuto en un solo equipo, sin servidor |
| **PostgreSQL 16** para servir la plataforma | Supabase, MongoDB, SQLite | Integridad relacional, búsqueda de texto completo en español, trigramas, MVCC para recargas sin cortar la lectura |
| **Sin orquestador externo** (Airflow, Prefect, Dagster) | Orquestadores | Un flujo lineal y mensual; el worker propio aporta candado, reintentos, latido y avisos con menos componentes |
| **LightGBM + TreeSHAP** | Regresión logística, bosque aleatorio, XGBoost, redes neuronales | Mejor o igual PR-AUC en validación, nulos nativos y explicaciones exactas; el volumen tabular no justifica aprendizaje profundo |
| **Sentence-BERT preentrenado** (sin ajuste fino) | BETO ajustado, modelos generativos | No hay etiquetas por asiento para ajustar; el aporte del texto se mide por ablación |
| **FastAPI** | Django, Node | Mismo lenguaje que el pipeline, validación con Pydantic, OpenAPI automático |
| **SPA estática + nginx** | Next.js | No requiere render en servidor; un solo origen permite una CSP estricta |
| **Docker Compose** | Kubernetes | 3 servicios, 1 trabajo y 1 worker: Kubernetes sería sobreingeniería |
| **Vistas materializadas del riesgo vigente** | `LATERAL ... LIMIT 1` por fila | El listado de la cartera bajó de ~0,8 s a menos de 0,1 s (se refrescan en cada carga) |
| **Caché en memoria por versión de datos** | Redis | Los datos cambian una vez al mes; la caché se invalida sola al cambiar `corte_datos` y no agrega un servicio |

## 3. Modelo de datos (esquema `sato`)

| Grupo | Tablas | Se recarga en cada versión |
|---|---|---|
| Linaje | `fuente_archivo`, `corte_datos` | Sí |
| Dominio | `entidad`, `contratista`, `inversion`, `obra`, `asiento`, `siaf_mensual`, `infobras_obra`, `contraloria_paralizada`, `mef_seguimiento` | Sí |
| Cartera nacional | `cartera_obra`, `cartera_riesgo`, `cartera_explicacion` | Sí |
| Modelo y explicaciones | `modelo`, `prediccion`, `explicacion`, `evidencia`, `simulacion`, `configuracion` | Sí |
| Investigación | `experimento_resultado`, `comparacion_ab` | Sí |
| Vistas derivadas | `obra_prediccion_vigente`, `cartera_riesgo_vigente` (materializadas) | Se refrescan |
| Operación | `carga_datos`, `sincronizacion`, `servicio_latido`, `envio_correo` | No |
| Personas | `usuario`, `revision_alerta`, `auditoria`, `suscripcion` | No |

Las revisiones humanas se guardan por clave natural (obra, corte y versión del modelo), no por el identificador de la
predicción, para que sobrevivan a cada recarga. Migraciones: `001_schema.sql`, `002_cartera_nacional.sql`, `003_operacion.sql`
(historial de cargas, latido, vistas materializadas, vencimiento de enlaces y unicidad de suscripciones con `NULLS NOT DISTINCT`).

## 4. Carga de datos y compuerta de integridad

1. Migraciones pendientes (`public.schema_migrations`).
2. Validación de entradas: archivos presentes, columnas requeridas, claves sin nulos ni repetidos.
3. Transacción única: `DELETE` de las tablas de datos (los lectores siguen viendo la versión vigente por MVCC) y `COPY` de
   la nueva versión.
4. Conciliación por tabla: filas de origen, cargadas y descartadas, con el motivo del descarte.
5. `REFRESH MATERIALIZED VIEW CONCURRENTLY`, reporte de monitoreo y auditoría de calidad (`sato/serving/calidad.py`).
6. Compuerta: se rechaza si algún chequeo CRÍTICO tiene hallazgos o si una tabla clave cae más de `SATO_CARGA_CAIDA_MAX`.
7. `COMMIT` (o `ROLLBACK`) y registro del intento en `carga_datos`; después, `VACUUM (ANALYZE)`.

## 5. API (`/api/v1`)

| Método | Ruta | Descripción | Acceso |
|---|---|---|---|
| GET | `/api/health`, `/api/ready` | Proceso vivo; base con modelo activo y datos cargados | público |
| GET | `/resumen`, `/comparador`, `/ambitos`, `/filtros` | Panorama por ámbito, comparación territorial y sectorial, valores de filtros | público |
| GET | `/radar/cuaderno`, `/radar/cartera` | Obras activas ordenadas por riesgo con sus 3 factores principales | público |
| GET | `/obras`, `/obras/mapa`, `/obras/{id}`, `/obras/{id}/riesgo`, `/obras/{id}/asientos`, `/obras/{id}/informe-pdf` | Contratos con cuaderno de obra digital | público |
| GET | `/cartera`, `/cartera/mapa`, `/cartera/{codigo}` | Cartera nacional INFOBRAS | público |
| GET | `/alertas`, `/predicciones/{id}`, `/predicciones/{id}/simulacion` | Alertas del corte, explicación con evidencia, sensibilidad | público |
| GET | `/modelo`, `/modelo/cartera`, `/modelo/calibracion`, `/investigacion/*`, `/estadisticas/resumen`, `/fuentes` | Transparencia del modelo y de los datos | público |
| GET | `/sistema/estado`, `/sistema/monitoreo`, `/sistema/cargas`, `/sistema/calidad`, `/sistema/sincronizacion` | Semáforo operativo, deriva, historial de cargas, calidad, fuentes | público |
| POST | `/suscripciones` · GET `/suscripciones/confirmar`, `/suscripciones/baja` | Resumen semanal con doble confirmación | público |
| POST | `/auth/login` · GET `/auth/me` | Sesión con JWT | público |
| GET/POST | `/alertas/{obra}/{corte}/revisiones` | Revisión humana de alertas | analista, admin |
| GET | `/admin/auditoria`, `/admin/sincronizaciones` | Auditoría y errores completos de operación | admin |

Errores: 401/403/404/422/429 con `detail`; 503 con `Retry-After` si la base no responde; 500 genérico sin detalles internos.

## 6. Seguridad (defensa en profundidad)

| Capa | Control | Verificación |
|---|---|---|
| Red | La API no publica puertos; la web escucha en `127.0.0.1` salvo `WEB_BIND`; en producción solo Caddy (80/443) | `docker-compose.yml`, `deploy/` |
| Proxy | Límite por IP (5 r/s, ráfaga 60) y estricto en ingreso y suscripción (10 r/min); `X-Forwarded-For` aceptado solo desde la IP fija de Caddy (`SATO_PROXY_CONFIABLE`) y reemplazado hacia la API; CSP, `X-Frame-Options`, `nosniff` | `docs/articulo/evaluacion/pruebas_seguridad.py` |
| API | Validación Pydantic (tipos, longitudes, enumeraciones, UUID); consultas parametrizadas; `statement_timeout` y `lock_timeout`; límite de intentos de ingreso por cuenta e IP; `Cache-Control: no-store` en respuestas privadas | `tests/test_seguridad.py` |
| Sesión | JWT HS256 con emisor, `nbf`, `exp` y campos obligatorios; rol leído de la base en cada solicitud; secreto ≥ 32 caracteres obligatorio en producción; token en `sessionStorage` enviado por cabecera (sin cookies, sin CSRF) | `tests/test_seguridad.py`, `web/src/api.test.ts` |
| Datos personales | Contraseñas bcrypt; respuestas de ingreso y suscripción que no revelan cuentas; auditoría de ingresos, bloqueos, revisiones e informes | `tests/test_seguridad.py` |
| Interfaz | React escapa el contenido; enlaces externos solo http(s) con `rel="noopener noreferrer"`; CSP `script-src 'self'` | `web/src/api.test.ts` |
| Dependencias | `pip-audit` y `npm audit` en CI | `.github/workflows/ci.yml` |
| Contenedores | Usuarios sin privilegios (uid 10001), imágenes `slim`/`alpine`, `HEALTHCHECK` | `docker/*.Dockerfile` |

## 7. Operación autocontrolada

| Mecanismo | Implementación |
|---|---|
| Sincronización mensual | `cron_runner.bucle`: día `SATO_SYNC_DIA` (acotado a 1–28) |
| Exclusión mutua | `pg_try_advisory_lock`: una segunda sincronización se omite |
| Reintentos | Por paso con espera exponencial (`SATO_PASO_REINTENTOS`); por mes, hasta `SATO_SYNC_MAX_INTENTOS` con espera de 2, 4, 8 h |
| Recuperación | Las sincronizaciones `EN_CURSO` huérfanas se marcan como interrumpidas al iniciar la siguiente |
| Latido | `servicio_latido`: `/sistema/estado` avisa si el worker no reporta en 3 h |
| Avisos | Correo a `SATO_ALERTAS_EMAIL` ante fallo, rechazo, intentos agotados o alertas del monitoreo |
| Semáforo | `/sistema/estado`: OPERATIVO, CON_AVISOS o DEGRADADO, con motivos calculados a partir del estado real |

## 8. Monitoreo del modelo

| Qué se monitorea | Cómo | Acción |
|---|---|---|
| Cobertura de la fuente | Asientos por mes frente al promedio de 6 meses | Aviso si cae más de 20 % |
| Catálogo de asientos | Tipos sin armonizar (`tipo_std = OTRO`) | Actualizar el mapeo de tipos |
| Deriva de variables | PSI del último corte frente al periodo de entrenamiento | Aviso si PSI > 0,25: evaluar reentrenamiento (decisión humana) |
| Desempeño realizado | PR-AUC y proporción de atrasos anticipados cuando vence el horizonte de 60 días | Revisar si cae de forma sostenida |
| Proporción de nivel alto | Puntaje z robusto del corte vigente frente a los cortes del backtest | Aviso si \|z\| > 3,5: revisar fuentes antes de difundir |

Implementación: `sato/models/monitor.py` (paso `monitor`) → `artifacts/monitoring/reporte.json` → configuración
`monitoreo_modelo` → `/api/v1/sistema/monitoreo` → pantalla «Estado y monitoreo».
