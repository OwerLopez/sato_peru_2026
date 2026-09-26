# SATO — Sistema de Alerta Temprana de Obras Públicas del Perú

Plataforma de analítica predictiva que estima, con datos abiertos oficiales del Estado peruano, el riesgo de que una
obra pública **en ejecución** incurra en atraso significativo, explica cada estimación con los factores que la originan
y muestra la evidencia documental (asientos del cuaderno de obra digital, ejecución presupuestal SIAF, registros de
INFOBRAS y de Invierte.pe) para que el supervisor pueda verificarla.

Tesis de Ingeniería de Sistemas — Universidad Nacional de San Agustín de Arequipa (UNSA).

---

## 1. Resumen ejecutivo

| Aspecto | Descripción |
|---|---|
| Problema | Las obras públicas peruanas acumulan atrasos y paralizaciones que se detectan cuando el daño ya está hecho (ampliaciones de plazo, adicionales, resoluciones de contrato, obras paralizadas). |
| Propuesta | Un sistema de alerta temprana que ordena la cartera **activa** por riesgo a futuro, con explicación por obra y evidencia trazable a la fuente oficial. |
| Datos | Exclusivamente datos abiertos oficiales: OECE (cuaderno de obra digital, valorizaciones, SEACE/CONOSCE), MEF (Invierte.pe, Formato 12-B, SIAF), Contraloría (INFOBRAS, reportes de obras paralizadas). Sin datos sintéticos. |
| Modelos | (1) Alerta a 60 días de la causal del 80 % (contratos con cuaderno de obra digital); (2) riesgo de retraso significativo al término, al inicio y en seguimiento mensual (toda la cartera INFOBRAS, cualquier modalidad). |
| Validación | Particiones temporales con purga, conjunto de prueba ciego posterior al entrenamiento, evaluación *rolling-origin*, bootstrap por obra, estabilidad por semilla y calibración por nivel de riesgo. |
| Explicabilidad | TreeSHAP por predicción, traducido a lenguaje del dominio y enlazado a los registros que lo sustentan. |
| Alcance | Nacional (25 departamentos) con selector de ámbito; Arequipa como caso de estudio principal. |
| Producto | API REST (FastAPI), interfaz web (React), informe técnico en PDF por obra, suscripción a resumen semanal por correo, sincronización mensual automática. |

Resultados principales (corte de datos 25-09-2026; detalle y cifras completas en
[`docs/MASTER_TECHNICAL_RESEARCH_PLAN.md`](docs/MASTER_TECHNICAL_RESEARCH_PLAN.md)):

* **Alerta a 60 días (cuaderno de obra digital, prueba temporal ciega, nacional):** ROC-AUC 0,742 con datos estructurados
  (Modelo A) y 0,774 al añadir el texto de los asientos (Modelo B); PR-AUC 0,141 → 0,159 con prevalencia cercana al 5 %.
  La mejora del texto es estadísticamente distinta de cero (IC 95 % por bootstrap de obras [0,019; 0,045] en ROC-AUC) y se
  mantiene en la evaluación *rolling-origin* y entre semillas. En Arequipa la dirección es la misma pero el tamaño de muestra
  no permite distinguirla de cero.
* **Riesgo de retraso significativo al término (cartera INFOBRAS nacional):** ROC-AUC 0,733 al inicio de la obra y 0,753 con
  el seguimiento mensual de la ejecución SIAF (prueba 2024-2025, 25 063 observaciones de 13 161 obras). En prueba, el nivel
  ALTO del modelo de seguimiento agrupa obras con 91,6 % de retraso observado frente a 44,4 % en el nivel BAJO.
* La señal es real pero moderada: el sistema sirve para **priorizar la supervisión**, no para determinar responsabilidades.

## 2. Problema nacional

La ejecución de obras públicas es uno de los principales destinos del gasto de inversión del Estado y, al mismo tiempo,
una fuente recurrente de sobrecostos, ampliaciones de plazo y paralizaciones que la Contraloría General de la República
reporta trimestralmente. La información para anticipar estos problemas existe y es pública, pero está dispersa en portales
distintos, sin identificadores comunes y en formatos heterogéneos (el cuaderno de obra digital no registra el código único
de inversión, INFOBRAS publica solo una foto actual, SIAF publica el gasto por mes en archivos anuales de cientos de MB).
SATO integra esas fuentes, reconstruye la historia de cada obra sin usar información futura y la convierte en una
priorización accionable.

## 3. Marco normativo del evento que se predice

| Norma | Disposición utilizada |
|---|---|
| Reglamento de la Ley de Contrataciones del Estado (RLCE, D.S. 344-2018-EF), art. 203 | En caso de retraso injustificado, cuando la valorización acumulada ejecutada es menor al 80 % de la programada, el inspector o supervisor ordena al contratista presentar un calendario acelerado; si el retraso persiste respecto del nuevo calendario, lo anota en el cuaderno de obra e informa a la entidad, y puede ser causal de resolución del contrato o de intervención económica de la obra (art. 203.5). |
| Ley N.° 32069, Ley General de Contrataciones Públicas, y su Reglamento (RLGCP), art. 207 | Art. 207.1: si la valorización acumulada ejecutada es menor al 80 % de la programada o existe atraso en la ruta crítica, el supervisor ordena un nuevo programa de ejecución acelerado y anota el hecho en el cuaderno de incidencias. Rige para los contratos del nuevo régimen (vigente desde el 22-04-2025). |
| Directivas del cuaderno de obra digital (OECE) | Los asientos del inspector o supervisor son registros oficiales, fechados y firmados, publicados como datos abiertos. |

El evento objetivo del modelo de alerta es el **primer asiento** que aplica esa causal (valorización menor al 80 % o
exigencia de calendario acelerado). Es un hito formal, fechado y verificable, no una interpretación del modelo.
Para la cartera INFOBRAS el evento es *retraso significativo*: fecha de finalización real posterior a la programada en más
del 30 % del plazo original (análisis de sensibilidad con 10 %, 50 % y 100 %).

## 4. Arquitectura

```
 Fuentes oficiales                Pipeline (Python, DuckDB)                     Servicio
 -----------------                -------------------------                     --------
 OECE  cuadernos, asientos  --->  ingest    descarga idempotente + SHA-256
 OECE  valorizaciones             staging   parsers por fuente -> Parquet
 SEACE / CONOSCE contratos        integration resolución de entidades (CUI, RUC)   PostgreSQL 16
 MEF   Invierte.pe, F12-B, SIAF   features  panel obra-mes as-of, texto, NLP  ---> (tsvector, pg_trgm)
 Contraloría INFOBRAS,            models    experimentos temporales, A vs B          |
             obras paralizadas    release   modelo operativo, SHAP, evidencia        v
                                  cartera   modelos INFOBRAS inicio/seguimiento    FastAPI  --->  React + Leaflet
                                  load      carga a PostgreSQL                     (/api/v1)      (nginx, :8080)
                                                                                     ^
                                  cron_runner (worker): sincronización mensual y resumen semanal
```

* **Pipeline reproducible** (`python -m sato.pipeline <paso>`): cada paso lee solo salidas del anterior.
* **Base de datos**: esquema `sato` con obras, inversiones, asientos (búsqueda de texto completo en español), predicciones,
  explicaciones, evidencia, simulaciones, cartera nacional, suscripciones, sincronizaciones y auditoría.
* **API**: FastAPI con validación de entrada, límites de tasa, cabeceras de seguridad (CSP, X-Frame-Options), JWT para
  acciones de revisión y registro de auditoría. Documentación OpenAPI en `/api/docs`.
* **Frontend**: React 19 + TypeScript + Vite + Tailwind; radar de obras activas, mapa, ficha por obra con explicación,
  simulador de sensibilidad y modo auditoría de asientos, comparador regional, laboratorio de validación histórica.
* **Despliegue**: Docker Compose (db, api, web, cargador, worker) y superposición de producción con Caddy (HTTPS automático)
  en [`deploy/`](deploy/). Guía en [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

## 5. Metodología de aprendizaje automático

### 5.1 Unidad de análisis y prevención de fuga temporal

* Unidad: **obra-mes**. En cada fecha de corte *T* solo se usan datos con fecha menor o igual a *T* (asientos, valorizaciones,
  devengados SIAF con un mes de rezago, historial de la entidad y del contratista calculado *as-of*).
* Se excluyen campos que solo se conocen al final (avance, fecha real de término, estado actual de INFOBRAS) y el PIM del año
  en curso, que SIAF no publica fechado.
* Particiones: entrenamiento, validación y prueba **consecutivas en el tiempo**, con purga de observaciones cuya ventana
  de etiqueta cruza el límite de la partición. La prueba es ciega: los hiperparámetros y umbrales se fijan en validación.
* Pruebas automáticas de no-fuga en [`tests/test_no_leakage.py`](tests/test_no_leakage.py); auditoría variable por variable
  en [`docs/methodology/LEAKAGE_POLICY.md`](docs/methodology/LEAKAGE_POLICY.md).

### 5.2 Validación

* **Holdout temporal** con horizonte H ∈ {30, 60, 90} días (H = 60 operativo).
* **Rolling-origin**: cuatro orígenes trimestrales (2025-06-30 a 2026-03-31), reentrenando en cada uno.
* **Bootstrap por obra** (remuestreo de obras, no de filas) para intervalos de confianza de la diferencia A vs B.
* **Estabilidad**: cinco semillas por configuración.
* **Operación simulada (backtest)**: precisión y exhaustividad de los niveles de alerta a lo largo de los cortes mensuales.
* Métrica principal PR-AUC (clase minoritaria); complementarias ROC-AUC, Brier, precisión/recall en el top-k y calibración.

### 5.3 Modelos

* **Modelo A (estructurado)**: LightGBM sobre variables del cuaderno (conteos por tipo de asiento, recencia, rol del autor),
  valorizaciones, SIAF, Invierte.pe, contrato SEACE e historial de actores.
* **Modelo B (estructurado + documental)**: añade léxico del dominio, extracción de información de los asientos
  (porcentajes de avance, causales), y puntuaciones de texto apiladas (TF-IDF y Sentence-BERT) calculadas fuera de muestra.
* **Cartera INFOBRAS**: LightGBM al inicio de la obra y en seguimiento mensual (ejecución SIAF acumulada), comparado con una
  regla basada en el historial de la entidad, regresión logística, bosque aleatorio y XGBoost.
* Niveles de riesgo: ALTO / MEDIO / BAJO por umbrales fijados en validación (modelo de alerta) o por cuantiles de
  predicciones fuera de tiempo anteriores al periodo de prueba (cartera), con su tasa observada publicada en la interfaz.

### 5.4 Procesamiento de lenguaje natural

* Representación semántica con **Sentence-BERT** (`paraphrase-multilingual-MiniLM-L12-v2`, Reimers y Gurevych, 2019) sobre
  el texto de cada asiento; agregación por ventana temporal de la obra.
* Línea base léxica TF-IDF de n-gramas de caracteres y LSA; léxico del dominio validado manualmente.
* Las puntuaciones de texto se obtienen con validación cruzada por grupos de obra y se apilan en el modelo tabular, de modo
  que la contribución del texto es medible y ablacionable.

### 5.5 Explicabilidad

* **TreeSHAP** (Lundberg et al., 2020) por predicción; cada factor se describe en lenguaje del dominio y se vincula con la
  evidencia que lo sustenta (asientos citados, meses SIAF, registros F12-B, historial del contratista).
* **Simulador de sensibilidad**: recalcula la probabilidad cambiando una sola señal (por ejemplo, consultas pendientes en
  cero). Muestra de qué depende la estimación; no es una estimación causal del efecto de una intervención.

## 6. Ejecución local con Docker (3 pasos)

Requisitos: Docker Desktop y los datos procesados (`data/`, `artifacts/`) generados con el pipeline (sección 7).

```bash
cp .env.example .env
```

Editar `.env` y reemplazar las claves por valores aleatorios (`POSTGRES_PASSWORD`, `SATO_JWT_SECRET`).

```bash
docker compose up -d --build db api web
```

```bash
docker compose --profile carga run --rm cargador
```

Abrir <http://localhost:8080>. La API y su documentación OpenAPI están en <http://localhost:8080/api/docs>.
Opcional: `docker compose --profile worker up -d worker` activa la sincronización mensual y el resumen semanal por correo
(sin SMTP configurado los correos se guardan como archivos `.eml` en `artifacts/outbox`).

## 7. Reproducir la investigación

```bash
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements-dev.txt -r requirements-nlp.txt
python -m sato.pipeline all
python -m pytest
```

En Linux/macOS la activación es `source .venv/bin/activate`.

| Paso | Comando | Salida |
|---|---|---|
| Descarga de fuentes oficiales | `python -m sato.pipeline ingest` | `data/raw/` y `manifest.jsonl` (URL, tamaño, SHA-256) |
| Normalización | `python -m sato.pipeline staging` | `data/staging/*.parquet` |
| Integración y resolución de entidades | `python -m sato.pipeline integration` | `data/curated/` |
| Variables (panel, texto, extracción) | `python -m sato.pipeline features` | `data/features/` |
| Embeddings Sentence-BERT (GPU recomendada) | `python -m sato.pipeline embeddings` | `data/features/asiento_embeddings.npy` |
| Experimentos del modelo de alerta | `python -m sato.pipeline experiments` | `artifacts/experiments/` |
| Modelo operativo de alerta | `python -m sato.pipeline release` | `artifacts/release/` |
| Experimentos de la cartera INFOBRAS | `python -m sato.pipeline cartera_experimentos` | `artifacts/exante/` |
| Modelos operativos de la cartera | `python -m sato.pipeline cartera` | `artifacts/cartera/` |
| Monitoreo de deriva | `python -m sato.pipeline monitor` | `artifacts/monitoring/` |
| Base de datos | `python -m sato.pipeline load` | PostgreSQL (variable `DATABASE_URL`) |

**Corte de datos de la tesis:** 25-09-2026 (asientos del cuaderno de obra digital hasta 31-08-2026; registros INFOBRAS
efectivos hasta 31-03-2026). Los portales regeneran sus archivos periódicamente; el manifiesto registra la huella SHA-256 de
cada archivo usado para que los resultados sean verificables contra ese corte exacto.

## 8. Estructura modular y linaje de datos

```
sato/
  ingest/        catálogo de fuentes y descarga idempotente           data/raw/ + manifest.jsonl
  staging/       parsers por fuente (OECE, MEF, SIAF, INFOBRAS,       data/staging/
                 Contraloría, SEACE)
  integration/   resolución de entidades cuaderno -> CUI -> INFOBRAS  data/curated/
  labels/        definición del evento objetivo (art. 203 / 207)
  features/      panel obra-mes as-of, variables estructuradas,       data/features/
                 léxico, LSA, embeddings, extracción de información
  models/        experimentos temporales, grilla, rolling-origin,     artifacts/experiments/
                 comparación A vs B, monitoreo
  exante/        cartera INFOBRAS: dataset, entrenamiento,            artifacts/exante/, artifacts/cartera/
                 seguimiento SIAF, servicio
  serving/       modelo operativo, SHAP, evidencia, simulaciones,     artifacts/release/
                 carga de base de datos
  services/      correo, resumen semanal, calendario de sincronización
  api/           FastAPI (rutas, seguridad, auditoría)
  pipeline.py    orquestador de pasos
  cron_runner.py worker de sincronización
web/             interfaz React + TypeScript
db/migrations/   esquema PostgreSQL
docker/          Dockerfiles y configuración de nginx
deploy/          superposición de producción (Caddy, HTTPS)
tests/           pruebas unitarias, de no-fuga temporal y de API
research/        scripts de investigación exploratoria reproducibles
docs/            plan maestro, evidencia, metodología, arquitectura, decisiones, despliegue
```

Linaje: cada predicción almacenada conserva la versión del modelo, la fecha de corte y las variables usadas; cada factor
explicativo apunta a registros de evidencia con su fuente y URL oficial; cada archivo fuente conserva URL, fecha de
modificación declarada por el servidor, fecha de descarga y SHA-256 (consultables en la página *Datos y sistema*).

## 9. Limitaciones

* El cuaderno de obra digital solo está publicado desde junio de 2024; el modelo de alerta cubre contratos con cuaderno.
* INFOBRAS publica una foto actual por obra; solo se usan sus campos fijados al inicio (plazo, monto) para predecir.
* La mejora del texto es estadísticamente significativa a escala nacional pero modesta en magnitud.
* El simulador mide sensibilidad del modelo, no efectos causales.
* El informe PDF es un documento técnico de apoyo; no es un documento oficial de ninguna entidad.

## 10. Documentación

* [Plan maestro técnico y de investigación](docs/MASTER_TECHNICAL_RESEARCH_PLAN.md)
* [Registro de evidencia](docs/research/EVIDENCE_LOG.md)
* [Registro de decisiones](docs/DECISIONS.md)
* [Política anti-fuga temporal](docs/methodology/LEAKAGE_POLICY.md)
* [Arquitectura](docs/architecture/ARCHITECTURE.md)
* [Despliegue](docs/DEPLOYMENT.md)

## 11. Licencia de los datos y uso responsable

Datos abiertos del Estado peruano (Plataforma Nacional de Datos Abiertos y portales de OECE, MEF y Contraloría). Las
estimaciones del sistema son probabilísticas y sirven para priorizar la supervisión; no constituyen determinación de
responsabilidad de ninguna entidad, funcionario o contratista.
