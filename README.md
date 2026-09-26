# SATO-AQP — Sistema de Alerta Temprana de Obras públicas (Arequipa)

Detección temprana del **riesgo de atraso significativo** en obras públicas de las 8 provincias de Arequipa,
integrando **exclusivamente datos abiertos oficiales** del Estado peruano, con aprendizaje automático
validado temporalmente, NLP sobre los asientos del cuaderno de obra digital, explicaciones por predicción
(TreeSHAP) y evidencia documental trazable.

Tesis de Ingeniería de Sistemas — Universidad Nacional de San Agustín de Arequipa.

## Qué hace

1. **Integra** cinco fuentes oficiales: OECE (cuadernos y asientos de obra digital, valorizaciones, contratos SEACE/CONOSCE),
   MEF (Banco de Inversiones/Invierte.pe, seguimiento F12B, ejecución presupuestal SIAF) y Contraloría (INFOBRAS y reportes
   trimestrales de obras paralizadas), con resolución de entidades medida (precisión 99,1 % en el enlace cuaderno → CUI).
2. **Construye la línea temporal** de cada obra (unidad obra-mes) usando solo información disponible en cada fecha.
3. **Predice** si la obra registrará en los próximos 60 días un **atraso significativo normativo**: el primer asiento que
   aplica la regla del 80 % (valorización acumulada ejecutada < 80 % de la programada) del RLCE art. 203 / RLGCP art. 207.
4. **Explica** cada alerta (factores TreeSHAP) y **muestra la evidencia**: asientos reales del cuaderno, meses SIAF,
   registros F12B, historial del contratista, con enlaces a las fuentes oficiales.
5. **Compara científicamente** un Modelo A (solo datos estructurados) con un Modelo B (estructurado + documental/NLP)
   mediante un test temporal ciego y bootstrap por obra.

Resultados, metodología y decisiones: [`docs/MASTER_TECHNICAL_RESEARCH_PLAN.md`](docs/MASTER_TECHNICAL_RESEARCH_PLAN.md).

## Ejecutar la plataforma en local (Docker)

Requisitos: Docker Desktop. Los datos procesados (`data/`) y el modelo (`artifacts/release/`) se generan con el pipeline
(sección siguiente) o se copian de un equipo que ya lo ejecutó.

```bash
cp .env.example .env          # y reemplazar las claves por valores aleatorios
docker compose up -d --build db api web
docker compose --profile carga run --rm cargador    # carga/actualiza la base de datos
```

Abrir <http://localhost:8080>. API y documentación OpenAPI: <http://localhost:8080/api/docs>.
El usuario administrador (opcional) se crea con `SATO_ADMIN_EMAIL` / `SATO_ADMIN_PASSWORD` del `.env`.

## Reproducir la investigación (fuente → dataset → experimento → modelo → resultado)

```bash
python -m venv .venv && .venv/Scripts/activate      # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements-dev.txt -r requirements-nlp.txt   # torch: ver requirements-nlp.txt
python -m sato.pipeline all          # ingest → staging → integration → features → embeddings → experiments → release → load
python -m pytest                      # pruebas unitarias, de no-fuga temporal y de API (esta última requiere la BD)
```

| Paso | Comando | Salida | Tiempo aprox. |
|---|---|---|---|
| Descarga de fuentes oficiales | `python -m sato.pipeline ingest` | `data/raw/` + `manifest.jsonl` (SHA-256) | 10 min (≈ 10 GB) |
| Normalización | `python -m sato.pipeline staging` | `data/staging/*.parquet` | 10 min |
| Integración / resolución de entidades | `python -m sato.pipeline integration` | `data/curated/` | 2 min |
| Features (panel, texto, extracción) | `python -m sato.pipeline features` | `data/features/` | 15 min |
| Embeddings Sentence-BERT | `python -m sato.pipeline embeddings` | `data/features/asiento_embeddings.npy` | 30 min con GPU |
| Experimentos | `python -m sato.pipeline experiments` | `artifacts/experiments/` | 90 min |
| Modelo operativo | `python -m sato.pipeline release` | `artifacts/release/` | 5 min |
| Base de datos | `DATABASE_URL=... python -m sato.pipeline load` | PostgreSQL | 2 min |

**Corte de datos de la tesis:** 25-09-2026 (asientos hasta 31-08-2026). Las fuentes se regeneran periódicamente
(incluso con filas eliminadas); el manifiesto `data/raw/manifest.jsonl` registra URL, tamaño y SHA-256 de cada archivo
usado, de modo que los resultados son verificables contra ese corte exacto.

## Estructura

```
sato/
  ingest/        descarga idempotente y catálogo de fuentes
  staging/       parsers por fuente (OECE, MEF, SIAF, INFOBRAS, Contraloría, SEACE)
  integration/   resolución de entidades y tablas curadas
  labels/        definición del evento objetivo
  features/      panel obra-mes, features estructuradas, texto (léxico, LSA, embeddings), extracción
  models/        experimentos temporales, evaluación, grilla, comparación A/B
  serving/       modelo operativo, SHAP, evidencia, carga de BD
  api/           FastAPI
  pipeline.py    orquestador
web/             frontend React + TypeScript (Vite)
db/migrations/   esquema PostgreSQL
docker/          Dockerfiles y nginx
tests/           pruebas
research/        scripts de investigación exploratoria (reproducibles)
docs/            plan maestro, evidencia, metodología, arquitectura, decisiones
```

## Documentación

* [Plan maestro técnico y de investigación](docs/MASTER_TECHNICAL_RESEARCH_PLAN.md) — veredicto, evidencia, metodología, resultados, arquitectura, riesgos, DoD.
* [Registro de evidencia](docs/research/EVIDENCE_LOG.md) — cada hallazgo verificado con su fuente.
* [Registro de decisiones](docs/DECISIONS.md) — decisiones cambiadas respecto del planteamiento inicial.
* [Política anti-fuga temporal](docs/methodology/LEAKAGE_POLICY.md) — auditoría feature por feature.
* [Arquitectura](docs/architecture/ARCHITECTURE.md) — datos, API, seguridad, despliegue, costos, drift.

## Licencia de los datos

Datos abiertos del Estado peruano (Plataforma Nacional de Datos Abiertos, portales de OECE, MEF y Contraloría).
Los resultados del modelo son estimaciones probabilísticas para priorizar la supervisión y no constituyen
determinación de responsabilidad de ninguna entidad o contratista.
