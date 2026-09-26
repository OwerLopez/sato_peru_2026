# Arquitectura de SATO-AQP

## 1. Vista general

```
 FUENTES OFICIALES (datos abiertos)
 ├─ OECE  : asientos y cuadernos de obra digital, valorizaciones, contratos CONOSCE
 ├─ MEF   : Banco de Inversiones (Invierte.pe), estado situacional F12B, SIAF (devengado mensual)
 └─ CGR   : INFOBRAS (foto de obras), reportes trimestrales de obras paralizadas
        │  sato.ingest.download  (idempotente, reintentos, SHA-256 -> data/raw/manifest.jsonl)
        ▼
 data/raw  ──►  sato.staging.*   (parseo robusto, tipos, cp1252, reparación de separadores) ──► data/staging (Parquet)
        ▼
 sato.integration.*  (resolución de entidades cuaderno→CUI→INFOBRAS; SEACE por id de contrato) ──► data/curated
        ▼
 sato.features.*  (panel obra-mes, features estructuradas, léxico, LSA, embeddings, extracción) ──► data/features
        ▼
 sato.models.*    (grilla temporal, rolling-origin, comparación A/B con bootstrap) ──► artifacts/experiments
        ▼
 sato.serving.release  (modelo operativo, backtest as-of, TreeSHAP, evidencia) ──► artifacts/release
        ▼
 sato.serving.load_db  (migraciones + carga transaccional) ──► PostgreSQL 16
        ▼
 FastAPI (sato.api)  ◄──►  nginx (SPA React + proxy /api)  ◄── navegador
```

## 2. Decisiones de arquitectura

| Decisión | Alternativas evaluadas | Razón |
|---|---|---|
| **DuckDB + Parquet** para el procesamiento analítico | Spark, Pandas puro, PostgreSQL como data lake | Volumen de ~3 GB brutos (CSV de 7–10 GB por año de SIAF se agregan en ~1 min con DuckDB en un solo equipo). Sin servidor, reproducible, gratuito |
| **PostgreSQL 16** para servir la plataforma | Supabase, MongoDB, SQLite | Relacional con integridad, búsqueda de texto completo en español (`tsvector` + `unaccent`), trigramas; gratuito y portable. Supabase no aporta nada que la tesis necesite y añade dependencia de un proveedor |
| **Sin pgvector** | pgvector para búsqueda semántica | Los embeddings se usan fuera de línea como features; la plataforma no requiere búsqueda vectorial en línea |
| **Sin Airflow/Prefect/Dagster** | Orquestadores | Actualización mensual y un único flujo lineal: `python -m sato.pipeline all` programado (cron / tarea programada / GitHub Actions) basta. Menos componentes que mantener |
| **LightGBM + TreeSHAP** | Regresión logística, Random Forest, XGBoost, redes neuronales | Mejor o igual PR-AUC en validación, manejo nativo de nulos y categóricas, explicaciones exactas y rápidas. Deep learning no se justifica con ~50 mil filas tabulares |
| **Sentence-BERT multilingüe preentrenado** (sin ajuste fino) | BETO ajustado, LLMs | Ajuste fino requeriría etiquetas por asiento que no existen; el preentrenado + TF-IDF + léxico permite medir el aporte del texto con costo bajo |
| **FastAPI** | Django, Node/Express | Mismo lenguaje que el pipeline, validación con Pydantic, OpenAPI automático |
| **React + Vite (SPA estática) + nginx** | Next.js | No se necesita renderizado en servidor; build estático servido por nginx, que además hace de proxy de la API (un solo origen, CSP estricta) |
| **Docker Compose** | Kubernetes | 3 servicios + 1 job; Kubernetes sería sobreingeniería |

## 3. Modelo de datos (PostgreSQL, esquema `sato`)

`db/migrations/001_schema.sql`

* **Linaje**: `fuente_archivo` (URL, SHA-256, fechas), `corte_datos`.
* **Dominio**: `entidad`, `contratista`, `inversion` (CUI), `obra` (contrato con cuaderno digital; PK = id del cuaderno),
  `asiento` (con `tsvector` generado e índice GIN), `siaf_mensual`, `infobras_obra` (foto), `contraloria_paralizada`, `mef_seguimiento`.
* **ML**: `modelo` (versión, métricas de test, features, SHA-256, activo), `prediccion` (obra × corte; `backtest` o `vigente`;
  `y_observado` cuando el horizonte ya transcurrió), `explicacion` (top-8 TreeSHAP), `evidencia` (asiento / SIAF / F12B / historial).
* **Investigación**: `experimento_resultado`, `comparacion_ab`.
* **Seguridad**: `usuario` (bcrypt), `revision_alerta` (clave natural obra+corte+versión, sobrevive recargas), `auditoria`.

Relaciones: `obra.cui → inversion`, `obra.entidad_ruc → entidad`, `obra.contratista_ruc → contratista`,
`asiento.cuaderno_id → obra`, `prediccion → modelo, obra`, `explicacion/evidencia → prediccion`, `evidencia.asiento_id → asiento`.

## 4. Pipeline de datos: propiedades

| Propiedad | Implementación |
|---|---|
| Idempotencia | Cada paso sobrescribe su salida; la carga a BD es una transacción `truncate + copy` |
| Versionado | `manifest.jsonl` (SHA-256 por archivo), versión del modelo = objetivo-H-features-fecha de corte, git para código |
| Logs | `logging` estándar con marca de tiempo en cada paso; request-id en la API |
| Reintentos | Descargas con backoff exponencial (5 intentos) |
| Calidad de datos | Estado de parseo por registro (`ok/repaired/rejected`) y reportes `*.quality.json`; pruebas de no-fuga |
| Linaje | Cada evidencia apunta al registro fuente (asiento N°, archivo mensual OECE, mes SIAF, URL oficial) |
| Incremental | Las fuentes publican archivos completos (no deltas); se recalcula todo mensualmente (~1 h, dominada por embeddings) |
| Fallos | Un paso fallido detiene el pipeline; la BD solo se reemplaza si la carga completa termina (rollback automático) |

## 5. API (`/api/v1`)

| Método | Ruta | Descripción | Auth |
|---|---|---|---|
| GET | `/api/health`, `/api/ready` | Salud y disponibilidad (BD + modelo activo) | — |
| GET | `/obras` | Listado con filtros (provincia, sector, estado, nivel, texto) y paginación | — |
| GET | `/obras/mapa` | Obras con coordenadas y último nivel | — |
| GET | `/obras/{id}` | Detalle integrado + enlaces a fuentes oficiales | — |
| GET | `/obras/{id}/riesgo` | Serie de predicciones, actividad mensual, SIAF, hitos | — |
| GET | `/obras/{id}/asientos` | Asientos con búsqueda de texto completo | — |
| GET | `/alertas` | Alertas del corte con sus 3 factores principales | — |
| GET | `/predicciones/{id}` | Explicación TreeSHAP + evidencia documental | — |
| GET | `/estadisticas/resumen` | KPI, provincias, sectores, histórico de backtest | — |
| GET | `/modelo`, `/investigacion/experimentos`, `/investigacion/comparacion`, `/fuentes` | Transparencia del modelo y de los datos | — |
| POST | `/auth/login` · GET `/auth/me` | JWT (HS256) | — |
| GET/POST | `/alertas/{obra}/{corte}/revisiones` | Revisión humana de alertas | analista, admin |
| GET | `/admin/auditoria` | Registro de auditoría | admin |

Errores: 401/403/404/422 con `detail`; 500 genérico sin filtrar detalles internos. Documentación OpenAPI en `/api/docs`.

## 6. Seguridad

* **Secretos** solo por variables de entorno (`.env` fuera de git; `SATO_JWT_SECRET` ≥ 32 caracteres obligatorio en producción).
* **Contraseñas** con bcrypt; sin usuarios por defecto (el administrador se crea desde variables de entorno).
* **Autorización** por rol (`analista`, `admin`); la lectura es pública porque los datos de origen son públicos.
* **Inyección SQL**: solo consultas parametrizadas (SQLAlchemy `text()` con parámetros enlazados); prueba automática.
* **Validación** de entrada con Pydantic/FastAPI (longitudes, enumeraciones, UUID, rangos de paginación).
* **XSS**: React escapa por defecto; CSP estricta en nginx (`script-src 'self'`), sin HTML crudo del usuario.
* **CORS** restringido a orígenes configurados; **rate limiting** (slowapi) por IP.
* **Cabeceras**: `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, CSP.
* **Auditoría** de inicios de sesión (exitosos y fallidos) y revisiones.
* **HTTPS**: terminado en el proxy/plataforma de despliegue (ver §7). Contenedores sin root.

## 7. Despliegue y costos

| Opción | Componentes | Costo aproximado | Comentario |
|---|---|---|---|
| **Local (entregado)** | `docker compose up` | 0 | Reproducible en cualquier PC con Docker |
| **Costo mínimo** | VM pequeña (1–2 vCPU, 2 GB) con Docker Compose + Caddy para HTTPS automático | ~US$ 5–12/mes (o créditos académicos) | La BD de Arequipa ocupa < 500 MB; el pipeline mensual puede correr en el equipo del equipo de tesis y cargar la BD remota |
| **Recomendada** | Frontend estático en CDN (Cloudflare Pages), API en contenedor gestionado (Render/Fly/Cloud Run), PostgreSQL gestionado con backups | ~US$ 15–30/mes | Backups automáticos, HTTPS y dominios gestionados |

El pipeline pesado (SIAF ~5 GB comprimidos, embeddings con GPU) **no** necesita correr en la nube: produce
`artifacts/release` y la carga a la BD remota se hace con `DATABASE_URL`.

**Backups y recuperación**: `pg_dump` diario del esquema `sato` (la BD se puede reconstruir íntegramente desde el
pipeline; las únicas tablas no reproducibles son `usuario`, `revision_alerta` y `auditoria`).

**Monitoreo**: `/api/ready` para health checks; logs estructurados con request-id; métricas de drift (§8).

## 8. Drift y reentrenamiento

| Qué se monitorea | Cómo | Acción |
|---|---|---|
| Cobertura de fuentes | nº de asientos/cuadernos por mes, % enlazado a CUI | alerta si cae > 20 % frente al promedio de 6 meses |
| Cambio de catálogo de asientos | tipos nuevos sin armonizar (`tipo_std = OTRO`) | actualizar `TIPO_MAP` (ya ocurrió en 2025-05 y 2026-04) |
| Drift de features | PSI mensual de las 20 features más importantes vs. entrenamiento | PSI > 0.25 → reentrenar |
| Desempeño | cuando el horizonte H se cumple, `y_observado` permite calcular PR-AUC/recall del mes | caída > 30 % en 3 cortes → recalibrar umbral / reentrenar |
| Normativa | cambios de reglamento (p.ej. DS 001-2026-EF) | revisar definición del evento y tipos de asiento |

Reentrenamiento programado: trimestral con ventana expansiva (el backtest de la plataforma ya simula esta política).
