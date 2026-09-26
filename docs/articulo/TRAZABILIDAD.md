# Trazabilidad del artículo: afirmación, evidencia y forma de reproducirla

Cada cifra del artículo `Articulo_Cientifico_Final.docx` proviene de un artefacto del repositorio o de una medición registrada.
El documento se genera con `node docs/articulo/fuente/construir.js` (contenido en `fuente/contenido.js`); las mediciones del
prototipo se insertan desde `evaluacion/metricas_prototipo.json` y la construcción se detiene si una cita, figura, tabla o
métrica no existe.

## Datos y diagnóstico

| Afirmación | Evidencia | Reproducción |
|---|---|---|
| 2 262 obras paralizadas al corte 2026-06-30; 68,2 % gobiernos locales; causales 27,6 % y 26,2 % | `data/staging/contraloria_paralizadas.parquet` (13 cortes, 30 369 filas) | `python -m sato.pipeline staging` y conteo por `fecha_corte` |
| 139 159 obras INFOBRAS; 128 417 con resultado; 51,2 % con retraso > 30 %; mediana del sobreplazo 21,1 % | `artifacts/cartera/obras.parquet` (`y_30`, `sobreplazo`) | `python -m sato.pipeline cartera` |
| 2 732 593 asientos; 1 308 reparados; 1 rechazado | `data/staging/*.quality.json`; `docs/research/EVIDENCE_LOG.md` (E1) | `python -m sato.pipeline staging` |
| 12 802 cuadernos con historia completa; 12 369 obras; 58 509 obra-mes; 1 586 obras con evento | `docs/MASTER_TECHNICAL_RESEARCH_PLAN.md` §7; `sato/features/panel.py` | `python -m sato.pipeline features` |
| Precisión de enlace 99,1 % (10 075 pares); 90,2 % de cuadernos de Arequipa enlazados | `EVIDENCE_LOG.md` (E4) | `python -m sato.pipeline integration` |
| Validez externa 3,3 % vs 1,0 %; 45 de 53 casos | `EVIDENCE_LOG.md` (E8) | `research/` |
| Extracción de avances: 70,9 % con error ≤ 1 pp; cobertura 11,9 % | `EVIDENCE_LOG.md` (E9); `docs/research/validacion_extraccion.json` | `research/validate_extraction.py` |
| Normativa: RLCE art. 203.1 y 203.5; RLGCP art. 207.1; Ley 31589 | `docs/normativa/*.txt` (textos oficiales) | — |

## Modelo de alerta a 60 días

| Afirmación | Evidencia |
|---|---|
| Test nacional H = 60: 16 756 filas, 5 158 obras, 842 positivos, prevalencia 0,050 | `artifacts/experiments/atraso_H60_*_train-nacional/predicciones_test.parquet`; `docs/articulo/generar_figuras.py` (imprime los conteos) |
| ROC-AUC 0,742 → 0,774; PR-AUC 0,139 → 0,158 (puntual); Brier 0,045 | `artifacts/experiments/atraso_H60_{A,B_full}_train-nacional/resultados.json`; API `/api/v1/modelo` |
| Diferencias bootstrap (Tabla 5) | `artifacts/experiments/comparacion_A_vs_B.csv` |
| Rolling-origin (Fig. 7) | `artifacts/experiments/rolling_resultados.csv` |
| Semillas: 0,138 ± 0,002 vs 0,162 ± 0,004; 0,742 ± 0,003 vs 0,772 ± 0,003 | `artifacts/experiments/estabilidad_semillas.csv` |
| Representaciones de texto (0,147; 0,152; 0,148; 0,141; 0,158) | `docs/MASTER_TECHNICAL_RESEARCH_PLAN.md` §15; `artifacts/experiments/grid_resultados.csv` |
| Importancia por grupo (46,0 %, 28,5 %, 7,1 %) | `docs/research/importancia_grupos.csv` |
| Backtest (Tabla 8) | `artifacts/release/modelo_card.json` (`operacion_backtest_nacional`, `operacion_backtest_arequipa`) |
| Arequipa: 36 de 42 obras anticipadas, mediana 40,5 días | API `/api/v1/modelo` → `metricas.arequipa` |
| Partición: entrenamiento 2024-06-30 a 2025-05-31; validación 2025-08-31 a 2025-10-31; prueba 2025-12-31 a 2026-06-30 | API `/api/v1/modelo` → `metricas.periodos` |

## Modelos de la cartera INFOBRAS

| Afirmación | Evidencia |
|---|---|
| Tabla 6 (ROC/PR por modelo, prevalencias, Arequipa) | `artifacts/exante/resultados_y_30.json`, `artifacts/exante/resultados_seguimiento.json` |
| Diferencias bootstrap (+0,075 [0,063; 0,086]; +0,030 [0,026; 0,033]) | mismos archivos, claves `bootstrap_nacional` |
| Sensibilidad 10/30/50/100 % y ablación del nombre | `artifacts/exante/resultados_y_{10,30,50,100}.json`, `resultados_y_30_sintexto.json` |
| Calibración por nivel (Fig. 8) | `artifacts/cartera/cartera_card.json` (`umbrales`) |
| 2 014 obras activas; 1 166 en nivel alto | tabla `sato.cartera_obra` / `cartera_riesgo` (API `/api/v1/cartera?estado=ACTIVA`) |

## Prototipo

| Afirmación | Evidencia | Reproducción |
|---|---|---|
| Latencias, throughput y errores (1, 20, 50 usuarios) | `evaluacion/k6_vus{1,20,50}.json` | `k6 run evaluacion/k6_carga.js` con `evaluacion/docker-compose.eval.yml` |
| 10 de 10 casos de seguridad | `evaluacion/seguridad_resultados.json` | `python docs/articulo/evaluacion/pruebas_seguridad.py` |
| Primera ejecución de seguridad 9 de 10 (límite de tasa no efectivo por contador por worker) | registro de la sesión de evaluación; corrección en `docker/nginx.conf` | — |
| Lighthouse 100/100/100 accesibilidad; 88/100/95 desempeño | `evaluacion/lighthouse_{radar,ficha,cartera}.json` | `npx lighthouse` (preset escritorio) |
| Primera medición de accesibilidad 96/89/95 | registro de la sesión de evaluación; correcciones de contraste y etiquetas en `web/src` | — |
| 43 pruebas aprobadas; 28 tablas; 6 662 MB; 32 endpoints; 14 rutas; carga en 557 s | `evaluacion/metricas_prototipo.json` | `python docs/articulo/evaluacion/consolidar_metricas.py` |
| Operación: 2 970 obras con cuaderno evaluadas, 190 ALTO, 461 MEDIO, 4 698 activas distintas | API `/api/v1/resumen` (`cuaderno`, `consolidado`) | — |

## Referencias

`verificar_referencias.py` resuelve cada DOI en Crossref y guarda los metadatos en `referencias_verificadas.json`;
`fuente/generar_referencias.py` produce las entradas IEEE a partir de esos metadatos. Las 13 fuentes sin DOI (actas NeurIPS,
JMLR, normas, conjuntos de datos, ISO/IEC 25010 y OWASP) se verificaron por su URL oficial. Los resúmenes se leyeron con
`resumenes_openalex.py` antes de citar.
