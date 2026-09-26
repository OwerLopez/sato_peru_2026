# MASTER TECHNICAL & RESEARCH PLAN — SATO-AQP

**Detección temprana del riesgo de atraso significativo en obras públicas de Arequipa mediante integración de datos
abiertos oficiales, aprendizaje automático y NLP sobre el cuaderno de obra digital.**

Corte de datos: **25-09-2026** (asientos hasta **31-08-2026**). Todas las cifras de este documento se obtuvieron
ejecutando el código del repositorio sobre los archivos oficiales descargados (linaje con SHA-256 en
`data/raw/manifest.jsonl`). Niveles de certeza: **[VERIFICADO]** evidencia directa · **[PROBABLE]** evidencia suficiente,
falta validación adicional · **[HIPÓTESIS]** por comprobar · **[BLOQUEO]** sin información suficiente.

---

## 1. Veredicto de viabilidad

**La tesis es viable, con un alcance distinto al planteado inicialmente.** [VERIFICADO]

* Existe información pública, histórica, temporal e integrable para estudiar la **detección temprana** del atraso
  significativo en obras **contratadas con cuaderno de obra digital (COD)**: 2,73 M de asientos fechados a nivel nacional
  (104 297 en Arequipa), con un evento de atraso definido por la normativa y anotado en el propio cuaderno.
* **No es viable** restringirse a un solo sector en Arequipa (Saneamiento tendría 9 casos positivos), ni reconstruir
  series largas (2017–2023) con avance mensual, ni enlazar todas las fuentes por CUI de forma directa.
* El diseño viable: **unidad obra-mes**, **entrenamiento nacional (12 369 obras) y evaluación en Arequipa**, evento
  normativo (RLCE art. 203 / RLGCP art. 207), horizonte operativo de 60 días, comparación A (estructurado) vs B (+ texto).
* Resultado: el modelo detecta señal real pero **moderada** (ROC-AUC ≈ 0,72–0,78; PR-AUC ≈ 2–3 veces la prevalencia),
  útil para **priorizar** la supervisión, no para decidir automáticamente. La información documental (NLP) aporta una mejora
  pequeña pero estadísticamente significativa a nivel nacional en los tres horizontes; en el subconjunto de Arequipa la mejora
  tiene el mismo signo pero no alcanza significancia por el tamaño muestral (§17).

## 2. Evidencia encontrada (resumen)

| Hallazgo | Evidencia | Certeza |
|---|---|---|
| Asientos COD abiertos solo desde 2024-06 (27 archivos mensuales) | `EVIDENCE_LOG` E1 | VERIFICADO |
| Cuadernos/asientos/valorizaciones/contratos no contienen CUI | diccionarios y archivos | VERIFICADO |
| CUI recuperable: regex 61 %, TF-IDF calibrado prec. 99,1 % → 90,2 % de cuadernos de Arequipa enlazados | E4 | VERIFICADO |
| Evento normativo de atraso existe como tipo de asiento, con fecha | E1, E5, E8 | VERIFICADO |
| Regla del 80 % vigente en ambos regímenes (Ley 30225 y Ley 32069) | DS 344-2018-EF art. 203; DS 009-2025-EF art. 207 | VERIFICADO |
| Valorizaciones OECE: solo 54 contratos en Arequipa | E1 | VERIFICADO |
| Serie mensual MEF programado/ejecutado densa solo 2019–2021 | E2 | VERIFICADO |
| INFOBRAS y Banco de Inversiones = fotos sin historia | E2, E3 | VERIFICADO |
| PIM del SIAF no fechado | E6 | VERIFICADO |
| Fuentes volátiles (archivo reescrito con menos filas el mismo día) | E7 | VERIFICADO |
| Validez externa: atraso ×3,3 probabilidad de figurar luego como paralizada (Contraloría) | E8 | VERIFICADO (nacional); BLOQUEO en Arequipa (7 casos) |

## 3. Fuentes oficiales verificadas

| Institución | Dataset | Acceso real | Formato | Periodo | Actualización | Uso |
|---|---|---|---|---|---|---|
| OECE | Asientos del cuaderno de obra digital | API Confluence de la wiki de datos abiertos (enlazada en datosabiertos.gob.pe) | CSV `|` cp1252 | 2024-06 → 2026-08 | mensual | eventos, features, texto |
| OECE | Cuadernos de obra digital | idem | CSV | cuadernos creados 2024–2026 | mensual | obra, ubicación, contrato, RUC |
| OECE | Valorizaciones de obra | idem | CSV | 2024–2026 | mensual | validación del extractor NLP |
| OECE (CONOSCE) | Contratos | `conosce.osce.gob.pe/.../CONOSCE_CONTRATOSAAAA_0.xlsx` | XLSX | 2018–2026 | regenerado | monto y vigencia originales |
| MEF | Detalle / Cierre / Desactivadas (Banco de Inversiones) | `fs.datosabiertos.mef.gob.pe/datastorefiles` | CSV UTF-8 | 2001–2026 | diaria | universo de CUI, sector, montos viables |
| MEF | Estado situacional (F12B) | idem | CSV | 2019–2026 | diaria | problemas registrados fechados |
| MEF | Presupuesto y ejecución de gasto (SIAF) | idem, zip anual | CSV 7–10 GB | 2020–2026 usado | mensual/diaria | devengado mensual por CUI |
| Contraloría | INFOBRAS – DataSet Obras Públicas | `infobras.contraloria.gob.pe/InfobrasWeb/DataSets` | XLSX | foto | diaria | plazo/monto originales, contexto |
| Contraloría | Reportes de obras paralizadas | colección gob.pe 18230 | XLSX trimestral | 2023-09 → 2026-06 (13 cortes) | trimestral | validación externa, contexto |

Diccionarios y metadatos oficiales en `data/raw/*/docs/`.

## 4. Auditoría de datasets

Ver `EVIDENCE_LOG.md` (E1–E9) y reportes de calidad `data/staging/*.quality.json`. Resumen:

* **Parseo OECE:** 2 732 593 asientos; 1 308 reparados (separador en texto libre, anclas validadas), 1 rechazado;
  un mes con dialecto distinto; 94 duplicados por (cuaderno, número).
* **Nulos relevantes (panel):** contrato SEACE ausente en 66 % de filas; seguimiento F12B ausente en 63 %; devengado SIAF
  ausente en 11 % (obras sin CUI o sin ejecución presupuestal); plazo INFOBRAS disponible en 62 %.
* **Decimales y fechas:** INFOBRAS exporta decimales con espacio; SIAF/OECE con coma; fechas `aaaammdd`, `dd/mm/aaaa`
  e ISO según fuente → normalizadas en staging.
* **Catálogos cambiantes:** tipos de asiento cambian en 2025-05 y 2026-04 → armonización (`TIPO_MAP`).
* **Granularidad:** una obra (contrato) <-> un cuaderno; una inversión (CUI) puede tener varios contratos/cuadernos
  (en Arequipa 32 CUI con 2 cuadernos, 8 con 3).

## 5. Comparación real de sectores (Arequipa)

Fuente: `docs/research/sector_comparison.md` (script `research/sector_comparison.py`).

| Criterio | Saneamiento | Transporte | Educación | Salud | Agropecuaria | Otros | Sin CUI | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Inversiones MEF (activas + cerradas) | 951 | 2 837 | 1 601 | 642 | 896 | 4 161 | – | 11 088 |
| Obras INFOBRAS | 702 | 2 441 | 982 | 253 | 512 | 2 351 | 2 690 | 9 931 |
| Obras INFOBRAS con CUI en MEF | 702 | 2 441 | 982 | 253 | 512 | 2 346 | – | 7 236 |
| Obras por contrata con RUC | 365 | 1 204 | 414 | 60 | 191 | 962 | 861 | 4 057 |
| Con avance INFOBRAS | 567 | 2 003 | 801 | 202 | 407 | 1 908 | 2 098 | 7 986 |
| Con informes de control | 236 | 735 | 330 | 81 | 130 | 535 | 657 | 2 704 |
| Con paralización (INFOBRAS) | 69 | 104 | 42 | 17 | 19 | 132 | 48 | 431 |
| En panel Contraloría de paralizadas | 52 | 57 | 19 | 11 | 16 | 65 | 26 | 246 |
| Con devengado SIAF 2020–2026 | 385 | 1 750 | 580 | 202 | 337 | 1 636 | – | 4 890 |
| Cuadernos de obra digital | 47 | 216 | 77 | 16 | 43 | 229 | 68 | 696 |
| Cuadernos con asientos | 42 | 196 | 71 | 15 | 40 | 213 | 52 | 629 |
| Con valorizaciones OECE | 7 | 8 | 1 | 2 | 6 | 27 | 4 | 55 |
| Historia completa y ≥ 3 meses | 29 | 156 | 52 | 11 | 31 | 171 | 40 | 490 |
| Con evento de atraso normativo | 14 | 42 | 18 | 3 | 4 | 42 | 12 | 135 |
| Con suspensión del plazo | 24 | 90 | 48 | 4 | 18 | 113 | 17 | 314 |
| Integrables (CUI + MEF + INFOBRAS) | 40 | 206 | 76 | 16 | 38 | 217 | – | 593 |
| **Utilizables para ML (con evento)** | **29 (9)** | **156 (38)** | **52 (13)** | **11 (3)** | **31 (4)** | **171 (36)** | **40 (10)** | **490 (113)** |

**DECISIÓN (sector).** *Evidencia:* tabla anterior. *Alternativas:* Saneamiento; Transporte (el más grande); los 4 sectores
juntos; todas las obras. *Razón:* ningún sector alcanza un número de casos positivos que permita entrenar y evaluar con
potencia; el conjunto completo sí (y el entrenamiento nacional lo multiplica por ~14). *Riesgo:* heterogeneidad entre
sectores. *Contingencia:* el sector es una variable del modelo y los resultados se estratifican por sector en la plataforma;
con más meses de datos se podrá entrenar por sector (Transporte primero). [VERIFICADO]

## 6. Interoperabilidad

| Enlace | Llave | Método | Tasa (Arequipa / nacional) | Error medido |
|---|---|---|---|---|
| Asiento → cuaderno | `ID_CUADERNO` = `NRO_CORRELATIVO…` (anonimizado) | exacto | 629/696 cuadernos con asientos; 2 081 cuadernos nacionales con asientos sin metadatos (creados antes de 2024) | — |
| Cuaderno → CUI | CUI/SNIP citado en la denominación | regex validado contra 584 k inversiones | 53 % / 61 % | falsos: 37 ambiguos nacionales (se descartan) |
| Cuaderno → CUI (resto) | nombre de obra vs nombre de inversión, bloqueo por departamento | TF-IDF char 3–5, score ≥ 0,60, margen ≥ 0,05 | +37 % / +30 % | **precisión 0,991** sobre 10 075 pares con verdad de referencia |
| Total cuaderno → CUI | | cascada | **90,2 % / 91,3 %** | |
| Cuaderno → INFOBRAS | CUI + RUC ejecutor = RUC contratista o consorciado (único) | determinístico | 254/507 (50 %) + CUI con obra única | ambiguos (9 en Arequipa) sin enlazar |
| Cuaderno → SEACE | id de contrato = `N_COD_CONTRATO` | exacto | 48 % / 28 % (cobertura de CONOSCE) | — |
| CUI → SIAF, F12B, Banco de Inversiones | CUI | exacto | 89 % de filas del panel con SIAF | — |
| CUI / código INFOBRAS → Contraloría | exacto | exacto | 7 obras de Arequipa con cuaderno | — |

No se aplica fuzzy matching cuando existe un identificador confiable. [VERIFICADO]

## 7. Dataset investigable

| | Nacional | Arequipa |
|---|---:|---:|
| Cuadernos con historia completa (asiento N°1 observado) | 12 802 | 552 |
| Obras en el panel (con actividad) | 12 369 | 519 |
| Filas obra-mes (cortes 2024-06 … 2026-08) | 58 509 | 2 272 (H=30, elegibles observables) |
| Obras con evento de atraso normativo | 1 586 | 114 |
| Positivos H=30 / 60 / 90 (filas) | 1 465 / 2 669 / 3 403 | 109 / 196 / 256 |
| Prevalencia H=30 / 60 / 90 | 3,0 % / 5,8 % / 7,8 % | 4,8 % / 9,1 % / 12,5 % |

Construcción: `sato/features/panel.py`. Elegibilidad: obra iniciada, sin evento previo (predicción del *onset*), no
culminada/recepcionada/resuelta, con al menos un asiento en los 90 días previos.

## 8. Variable objetivo

**DECISIÓN (label).** `y_H(T) = 1` si el **primer** asiento del cuaderno de tipo «Valorización acumulada ejecutada menor
al 80 % del monto acumulado programado» o «Calendario acelerado de obra» ocurre en (T, T+H].
*Evidencia:* texto oficial de RLCE art. 203.1 y RLGCP art. 207.1 (ambos exigen anotar el hecho en el cuaderno); lectura de
muestras (E8). *Alternativas:* paralización (rara, tardía, fotos sin historia); días de retraso sobre plazo (plazo y fin real
solo como foto); ampliaciones de plazo (357/696 obras: demasiado frecuentes y muchas justificadas por lluvias).
*Razón:* definición legal, fechada, reproducible y observable en tiempo real. *Riesgo:* sub-registro (supervisores que anotan
el hecho como "Otras ocurrencias"). *Contingencia:* análisis de sensibilidad con el evento ampliado *disrupción* y ablación de
menciones libres; el sub-registro sesga a la baja la precisión medida (los "falsos positivos" pueden ser atrasos no tipificados).
[VERIFICADO]

## 9. Definición de retraso significativo

**Retraso significativo = atraso injustificado según la regla normativa del 80 %**: el monto de la valorización acumulada
ejecutada es menor al 80 % del programado (o, desde la Ley 32069, existe atraso en la ruta crítica), constatado por el
supervisor/inspector y anotado en el cuaderno. Es medible (porcentaje), verificable (asiento fechado y público), temporal
(fecha del asiento) y defendible (norma vigente en todo el periodo de datos: Ley 30225 hasta el 21-04-2025 y Ley 32069
desde el 22-04-2025). [VERIFICADO]

## 10. Horizonte

Se evaluaron H ∈ {30, 60, 90} días. **H operativo = 60 días** (pre-registrado: dos ciclos de valorización mensual, margen
para exigir medidas antes del disparador formal). Con H mayor aumenta la prevalencia y el PR-AUC pero se pierde precisión
temporal; con H = 30 los positivos son escasos (≈ 43 obras en el test de Arequipa). [VERIFICADO]

## 11. Data leakage

Política formal y auditoría feature por feature: `docs/methodology/LEAKAGE_POLICY.md`. Puntos clave:
* Asientos ≤ T; SIAF con rezago de un mes; PIM del año en curso excluido; F12B por fecha de registro.
* Fotos sin fecha (INFOBRAS, Banco de Inversiones, SEACE) solo para atributos fijados al inicio; ablación `A_sin_ib`.
* Vocabulario/IDF/SVD/PCA ajustados solo con el periodo de entrenamiento; scores de texto apilados *as-of* (forward chaining).
* Partición temporal con purga de H días; umbrales e hiperparámetros solo en validación.
* `tests/test_no_leakage.py` verifica estas reglas sobre los datos reales. [VERIFICADO]

## 12. Metodología

* **Tipo de investigación:** aplicada, cuantitativa, diseño observacional retrospectivo con simulación de despliegue (backtesting).
* **Validación principal:** holdout temporal ciego — train 2024-06 → 2025-05/08 (según H), valid 3 meses, test 2025-12 → 2026-07 (H=30),
  2026-06 (H=60), 2026-05 (H=90); purga de H días entre bloques.
* **Validación de estabilidad:** rolling-origin con 4 orígenes trimestrales (2025-06, 09, 12; 2026-03) y test de 3 meses.
* **Métricas:** PR-AUC (principal, clases desbalanceadas; Saito & Rehmsmeier 2015), ROC-AUC, Brier, precisión/recall/F1/F2 en el
  umbral de validación, precisión@k (capacidad de revisión), matriz de confusión, anticipación (días entre la primera alerta y el evento).
* **Inferencia:** bootstrap por obra (clusters, 1 000 remuestreos) para IC 95 % y p-valor de las diferencias A vs B (pareadas).
* **Baselines:** prevalencia (azar), regla heurística experta (suspensiones, penalidades, ampliaciones, adicionales, consultas
  pendientes), regresión logística, Random Forest, XGBoost, LightGBM.

## 13. Modelo A (estructurado)

84 variables sin texto libre: conteos por tipo de asiento (acumulados y 90 días), actividad y ritmo, días desde el último asiento,
proporción de asientos del supervisor, consultas pendientes, régimen legal, atributos de la inversión (sector, nivel, tipo, monto
viable), tipo de entidad, consorcio, historial de atrasos previos del contratista y de la entidad (fechado), SIAF (devengado acumulado,
3 meses, año, meses sin devengado, PIA), F12B fechado, plazo/monto originales INFOBRAS y SEACE. Features temporales: ventanas
(30/90 días), ratios de ritmo, tendencias de devengado. Implementación: `sato/features/structured.py`.

Resultado (test temporal, entrenamiento nacional, LightGBM):

| H | PR-AUC Arequipa | ROC-AUC Arequipa | PR-AUC nacional | ROC-AUC nacional | Prevalencia test Arequipa / nacional | Filas test Arequipa / nacional | Obras con evento en test Arequipa / nacional |
|---|---:|---:|---:|---:|---:|---:|---:|
| 30 | 0,122 | 0,692 | 0,081 | 0,750 | 0,052 / 0,026 | 808 / 19 538 | 43 / 542 |
| 60 | 0,196 | 0,704 | 0,139 | 0,742 | 0,091 / 0,050 | 693 / 16 756 | 42 / 534 |
| 90 | 0,228 | 0,693 | 0,182 | 0,740 | 0,127 / 0,069 | 577 / 14 085 | 39 / 508 |

Fuente: `artifacts/experiments/atraso_H*_A_train-nacional/resultados.json`.

## 14. Modelo B (estructurado + documental)

Se añadieron, sobre A: (i) léxico de 16 categorías de causas de atraso (literatura + terminología peruana), (ii) LSA (TF-IDF 1–2 gramas,
60 k términos, SVD 64), (iii) embeddings Sentence-BERT multilingüe (paraphrase-multilingual-MiniLM-L12-v2) promediados en la ventana y
reducidos con PCA 32, (iv) scores supervisados *as-of* sobre TF-IDF y embeddings, (v) extracción de avances reportados.
Volumen textual verificado: 2,11 M asientos de obras del panel, mediana 789 caracteres por asiento, redactados en español, 39 tipos de asiento, 5 roles de registrante.

| H | PR-AUC Arequipa A → B_full | ROC Arequipa A → B_full | PR-AUC nacional A → B_full | ROC nacional A → B_full |
|---|---|---|---|---|
| 30 | 0,122 → 0,135 | 0,692 → 0,707 | 0,081 → 0,101 | 0,750 → 0,788 |
| 60 | 0,196 → 0,216 | 0,704 → 0,719 | 0,139 → 0,158 | 0,742 → 0,774 |
| 90 | 0,228 → 0,265 | 0,693 → 0,722 | 0,182 → 0,196 | 0,740 → 0,758 |

## 15. NLP

| Representación | Qué resuelve | Aporte medido (nacional, H=60, PR-AUC; A = 0,139) |
|---|---|---|
| Léxico de causas (16 categorías) | señales interpretables (clima, pagos, expediente, personal, incumplimiento…) | 0,147 (sin proxy: 0,153) |
| LSA (TF-IDF + SVD) | tópicos latentes | 0,139 |
| Embeddings Sentence-BERT + PCA | semántica | 0,141 |
| Score TF-IDF *as-of* | vocabulario discriminante supervisado | 0,152 |
| Score embeddings *as-of* | semántica supervisada | 0,148 |
| Extracción de avances | valor ejecutado/programado reportado | 0,134 (cobertura 12 %) |
| **Todo (B_full)** | | **0,158** (sin proxy: 0,163) |

Conclusión: el NLP aporta (significativo a nivel nacional, §17); **el transformer no fue superior** a TF-IDF supervisado ni al léxico de dominio (Reimers & Gurevych 2020
sin ajuste fino al dominio). El modelo final usa la combinación. Importancia global TreeSHAP en test (B_full, H=60): contenido de
asientos 46 %, registros del cuaderno 28 %, características de la obra 11 %, SIAF 7 %, INFOBRAS-inicio 6 %, historial de actores
1,5 % (`docs/research/importancia_grupos.csv`). La categoría `proxy_80` no está entre las 20 variables más importantes.

## 16. XAI

* **Global:** TreeSHAP medio absoluto por variable y por grupo (`research/global_importance.py`).
* **Local:** para cada predicción, las 8 contribuciones TreeSHAP exactas (Lundberg et al. 2020) en log-odds, con descripción en
  español generada a partir del **valor real** de la variable (sin narrativa libre).
* **Evidencia:** cada contribución positiva se enlaza a registros reales: asientos del tipo o categoría que activó la variable
  (N° de asiento, fecha, rol, archivo mensual OECE), asientos más relevantes según el modelo de texto, meses SIAF (enlace SSI del MEF),
  registros F12B, obras previas del contratista con atraso. Cadena: **ALERTA → feature → registro → asiento → archivo oficial**.

## 17. Aporte científico y experimento central (A vs B)

Bootstrap pareado por obra (1 000 remuestreos de obras completas) sobre las mismas filas del test temporal ciego; LightGBM entrenado con datos nacionales en ambos modelos.

| H | Test | Métrica | Variante | A (media bootstrap) | B | B − A | IC 95 % | p (una cola) | Obras |
|---|---|---|---|---:|---:|---:|---|---:|---:|
| 30 | arequipa | PR-AUC | B_full | 0,136 | 0,145 | 0,010 | [-0,043; 0,063] | 0,364 | 253 |
| 30 | arequipa | ROC-AUC | B_full | 0,691 | 0,705 | 0,013 | [-0,047; 0,078] | 0,326 | 253 |
| 30 | arequipa | PR-AUC | B_full_sinproxy | 0,136 | 0,173 | 0,038 | [-0,028; 0,122] | 0,144 | 253 |
| 30 | arequipa | ROC-AUC | B_full_sinproxy | 0,691 | 0,706 | 0,015 | [-0,045; 0,080] | 0,324 | 253 |
| 30 | nacional | PR-AUC | B_full | 0,082 | 0,103 | 0,021 (*) | [0,008; 0,034] | 0,000 | 5734 |
| 30 | nacional | ROC-AUC | B_full | 0,750 | 0,788 | 0,038 (*) | [0,023; 0,054] | 0,000 | 5734 |
| 30 | nacional | PR-AUC | B_full_sinproxy | 0,082 | 0,099 | 0,017 (*) | [0,004; 0,031] | 0,002 | 5734 |
| 30 | nacional | ROC-AUC | B_full_sinproxy | 0,750 | 0,778 | 0,028 (*) | [0,011; 0,044] | 0,000 | 5734 |
| 60 | arequipa | PR-AUC | B_full | 0,209 | 0,230 | 0,021 | [-0,038; 0,083] | 0,250 | 233 |
| 60 | arequipa | ROC-AUC | B_full | 0,704 | 0,719 | 0,015 | [-0,037; 0,068] | 0,288 | 233 |
| 60 | arequipa | PR-AUC | B_full_sinproxy | 0,209 | 0,220 | 0,011 | [-0,050; 0,078] | 0,375 | 233 |
| 60 | arequipa | ROC-AUC | B_full_sinproxy | 0,704 | 0,705 | 0,001 | [-0,054; 0,057] | 0,496 | 233 |
| 60 | nacional | PR-AUC | B_full | 0,141 | 0,159 | 0,018 (*) | [0,005; 0,032] | 0,006 | 5158 |
| 60 | nacional | ROC-AUC | B_full | 0,742 | 0,774 | 0,032 (*) | [0,019; 0,045] | 0,000 | 5158 |
| 60 | nacional | PR-AUC | B_full_sinproxy | 0,141 | 0,164 | 0,024 (*) | [0,008; 0,039] | 0,002 | 5158 |
| 60 | nacional | ROC-AUC | B_full_sinproxy | 0,742 | 0,776 | 0,034 (*) | [0,021; 0,047] | 0,000 | 5158 |
| 90 | arequipa | PR-AUC | B_full | 0,241 | 0,281 | 0,040 | [-0,020; 0,112] | 0,092 | 196 |
| 90 | arequipa | ROC-AUC | B_full | 0,693 | 0,721 | 0,028 | [-0,029; 0,096] | 0,172 | 196 |
| 90 | arequipa | PR-AUC | B_full_sinproxy | 0,241 | 0,294 | 0,053 | [-0,008; 0,123] | 0,045 | 196 |
| 90 | arequipa | ROC-AUC | B_full_sinproxy | 0,693 | 0,716 | 0,023 | [-0,031; 0,082] | 0,217 | 196 |
| 90 | nacional | PR-AUC | B_full | 0,183 | 0,198 | 0,015 (*) | [0,000; 0,031] | 0,025 | 4535 |
| 90 | nacional | ROC-AUC | B_full | 0,740 | 0,758 | 0,018 (*) | [0,004; 0,033] | 0,003 | 4535 |
| 90 | nacional | PR-AUC | B_full_sinproxy | 0,183 | 0,206 | 0,024 (*) | [0,008; 0,039] | 0,001 | 4535 |
| 90 | nacional | ROC-AUC | B_full_sinproxy | 0,740 | 0,764 | 0,024 (*) | [0,012; 0,035] | 0,000 | 4535 |

(*) = el IC 95 % de la mejora excluye el cero. Tabla completa (todas las variantes y el objetivo *disrupción*):
`artifacts/experiments/comparacion_A_vs_B.csv`.

**Conclusiones del experimento central** [VERIFICADO]:

1. **A nivel nacional (≈ 4 500–5 700 obras en test) el Modelo B es mejor que el A en los tres horizontes**, con diferencias
   estadísticamente distinguibles de cero tanto en PR-AUC (+0,015 a +0,021) como en ROC-AUC (+0,018 a +0,038).
2. **La mejora no se explica por menciones informales del propio evento**: la variante `B_full_sinproxy` (sin la categoría léxica de la
   regla del 80 % ni la extracción de avances) mantiene mejoras significativas (+0,017 a +0,024 en PR-AUC).
3. **En Arequipa (≈ 200–250 obras, ≈ 40 con evento en el periodo de test) la mejora es positiva en todos los horizontes pero no
   significativa**: los intervalos incluyen el cero. Es un problema de potencia estadística del subconjunto regional, no una
   contradicción: el modelo se entrena con datos nacionales y el efecto medido a nivel nacional es el estimador más preciso.
4. **Evaluación rolling-origin (4 orígenes):** B_full supera a A en promedio (H=60: PR-AUC Arequipa 0,167 → 0,206; nacional
   0,134 → 0,150), aunque no en todos los orígenes (en el origen 2026-03 empatan) → la ganancia es real pero pequeña y variable.
5. **Magnitud práctica:** la mejora es modesta. El texto convierte un sistema que ordena obras con ROC ≈ 0,74 en uno con ≈ 0,77
   (nacional, H=60). La complejidad adicional de NLP se justifica porque además provee la **evidencia legible** (los asientos que
   sustentan cada alerta), que es el requisito central de explicabilidad; el costo computacional es bajo salvo los embeddings (GPU opcional).
6. **Estabilidad por semilla (5 semillas de LightGBM, H=60, `artifacts/experiments/estabilidad_semillas.csv`):** nacional
   PR-AUC A = 0,138 ± 0,002 vs B_full = 0,162 ± 0,004; ROC-AUC 0,742 ± 0,003 vs 0,772 ± 0,003 → la brecha (~0,024) es unas seis veces la
   desviación típica: la mejora no depende de la aleatoriedad del entrenamiento. Arequipa: 0,193 ± 0,011 vs 0,213 ± 0,021 (solapadas).
7. **Sensibilidad (evento ampliado *disrupción*: atraso, suspensión o resolución):** B también mejora a nivel nacional
   (PR-AUC +0,028 a +0,035, IC excluye cero).

**Aportes de la tesis** (novedad según búsqueda en ALICIA/CONCYTEC y literatura verificada, 25-09-2026):
1. Primer uso documentado de los **asientos abiertos del cuaderno de obra digital** (2,7 M registros) para alerta temprana.
2. **Etiqueta normativa** reproducible (regla del 80 %) en lugar de definiciones ad hoc de "retraso".
3. **Integración medida** de cinco fuentes oficiales con resolución de entidades de precisión conocida.
4. Evaluación **libre de fuga** (as-of, purga, auditoría automática) con **backtesting** del despliegue.
5. Cuantificación del **valor incremental del texto** con ablaciones que separan anticipación genuina de proxy.

Trabajos relacionados: predicción de atrasos con ML en construcción (Gondia et al. 2020; Egwim et al. 2021; Sanni-Anibire et al. 2020),
causas de atraso (Assaf & Al-Hejji 2006; Sambasivan & Soon 2007), alerta temprana en contratación pública (Gallego et al. 2021),
NLP en construcción (Tixier et al. 2016; Zhang et al. 2019). La diferencia: datos longitudinales oficiales de todo un país, evento
legal, predicción *as-of* y evidencia documental enlazada.

## 17-bis. Cartera nacional INFOBRAS: riesgo de retraso significativo al término

**Motivación.** El modelo de alerta (§8-§17) solo cubre contratos con cuaderno de obra digital (desde junio de 2024). Para
cubrir la cartera completa (todas las modalidades, incluida administración directa, y todos los sectores) se construyó un
segundo problema sobre el dataset abierto de INFOBRAS a escala nacional (139 159 obras).

* **Etiqueta** `y_30`: fin real posterior al fin programado en más del 30 % del plazo original. Solo se etiquetan obras con
  evidencia de término (fecha de finalización real); las obras abandonadas o sin registro se excluyen de la etiqueta.
  Sensibilidad: umbrales de 10 %, 50 % y 100 %.
* **Variables** (44): atributos fijados al inicio (modalidad, tipo de obra, nivel de gobierno, plazo, costo, supervisión,
  entrega de terreno, antigüedad del expediente, código de inversión), historial *as-of* de la entidad, del contratista y de la
  provincia, y una puntuación TF-IDF del nombre de la obra calculada fuera de muestra. Modelo de seguimiento (53 variables):
  añade el devengado SIAF mensual acumulado respecto del costo, meses sin devengado y brecha de ritmo (con un mes de rezago).
* **Particiones** por fecha de inicio (inicio): train 2012-01-01 a 2020-06-22 (72 551), valid 2020-07 a 2021-12 (13 965),
  test 2022-01-01 a 2024-06-30 (26 025). Seguimiento por fecha de corte mensual: train 2017-07 a 2022-11 (83 419 filas,
  41 443 obras), valid 2023 (10 661), test 2024-01 a 2025-12 (25 063 filas, 13 161 obras). Bootstrap por entidad (300).

| Objetivo (test) | Modelo | ROC-AUC nacional | PR-AUC nacional | ROC-AUC Arequipa | PR-AUC Arequipa | Prevalencia nacional |
|---|---|---|---|---|---|---|
| y_30 inicio | Regla (tasa histórica de la entidad) | 0,658 | 0,690 | 0,661 | 0,764 | 0,524 |
| y_30 inicio | Regresión logística | 0,718 | 0,742 | 0,730 | 0,802 | 0,524 |
| y_30 inicio | Bosque aleatorio | 0,741 | 0,767 | 0,734 | 0,804 | 0,524 |
| y_30 inicio | LightGBM | 0,733 | 0,759 | 0,742 | 0,815 | 0,524 |
| y_30 inicio | XGBoost | 0,701 | 0,729 | 0,699 | 0,778 | 0,524 |
| y_30 seguimiento | LightGBM inicio (misma muestra) | 0,723 | 0,831 | 0,736 | 0,883 | 0,649 |
| y_30 seguimiento | LightGBM seguimiento (+ SIAF mensual) | 0,753 | 0,855 | 0,763 | 0,900 | 0,649 |

* LightGBM supera a la regla de historial de la entidad: +0,075 ROC-AUC (IC 95 % [0,063; 0,086]) y +0,069 PR-AUC
  ([0,049; 0,088]) a nivel nacional; en Arequipa +0,084 ROC-AUC ([0,035; 0,145]).
* El seguimiento con SIAF mejora al modelo de inicio en la misma muestra: +0,030 ROC-AUC ([0,026; 0,033]) y +0,024 PR-AUC
  ([0,020; 0,028]) nacional; en Arequipa +0,025 ROC-AUC ([0,004; 0,046]).
* **Sensibilidad del umbral de la etiqueta** (LightGBM, test nacional): 10 % → ROC 0,762 / PR 0,834 (prevalencia 0,614);
  30 % → 0,733 / 0,759 (0,524); 50 % → 0,721 / 0,698 (0,449); 100 % → 0,705 / 0,587 (0,334). En todos los umbrales la mejora
  sobre la regla tiene IC que excluye el cero (ROC +0,041 a +0,103). Archivos `artifacts/exante/resultados_y_{10,30,50,100}.json`.
* **Ablación del texto del nombre** (`resultados_y_30_sintexto.json`): ROC 0,732 vs 0,733 con texto; el nombre de la obra no
  aporta señal medible. Se mantiene por costo nulo, pero no se reporta como contribución.
* **Operación**: reentrenamiento anual *as-of* (inicio 2016-2026, seguimiento 2019-2026). Niveles por cuantiles de predicciones
  fuera de tiempo anteriores al test (ALTO = 20 % superior, MEDIO = 30 % siguiente). Tasa de retraso observada por nivel en el
  periodo de prueba: inicio ALTO 78,3 % / MEDIO 54,4 % / BAJO 32,7 % (base 52,8 %); seguimiento ALTO 91,6 % / MEDIO 69,7 % /
  BAJO 44,4 % (base 65,3 %). Obras activas evaluadas al corte: 2 014 (74 en Arequipa). Archivo `artifacts/cartera/cartera_card.json`.
* **Limitación**: la etiqueta depende del registro de la fecha de finalización real en INFOBRAS; la prevalencia alta (52-65 %)
  refleja que el retraso significativo es la norma, no la excepción, en la cartera con término registrado.

## 18. Arquitectura

`docs/architecture/ARCHITECTURE.md`. Pipeline Python (DuckDB/Parquet) → PostgreSQL 16 → FastAPI → React/nginx; Docker Compose.

**DECISIÓN (arquitectura/stack/infraestructura).** *Alternativas:* Supabase, Prefect/Airflow, pgvector, Next.js, Kubernetes.
*Razón:* volumen (~10 GB brutos, mensual), costo cero, 5 estudiantes; ninguno de esos componentes resuelve un problema presente.
*Riesgo:* crecimiento a nivel nacional. *Contingencia:* la BD ya soporta todo el país (esquema idéntico); el pipeline es
paralelizable por departamento.

## 19. Modelo de datos

`db/migrations/001_schema.sql` — 20 tablas (§3 de ARCHITECTURE.md): linaje, dominio, series, ML (modelo, predicción,
explicación, evidencia), investigación, usuarios/revisiones/auditoría. Índices por provincia, sector, CUI, (obra, fecha), GIN de
texto completo en español y trigramas.

## 20. Pipeline

`python -m sato.pipeline all`: ingest → staging → integration → features → embeddings → experiments → release → load.
Idempotente, versionado por SHA-256, reintentos, reportes de calidad, carga transaccional.

## 21. Stack

Python 3.12, pandas 3, DuckDB 1.5, scikit-learn 1.9, LightGBM 4.7, XGBoost 3.4, sentence-transformers 6.1 (PyTorch 2.11, CUDA
opcional), FastAPI 0.141, SQLAlchemy 2.1, psycopg 3.3, PostgreSQL 16, React 19 + TypeScript + Vite 8 + Tailwind 4 + Leaflet +
Recharts, nginx 1.27, Docker Compose. Versiones fijadas en `requirements*.txt` y `web/package-lock.json`.

## 22. MVP

* **MVP científico (cumplido):** dataset obra-mes nacional, evento normativo, modelos A/B, test temporal, bootstrap, ablaciones.
* **MVP funcional (cumplido):** plataforma con panel, mapa, alertas priorizadas, detalle de obra, explicación y evidencia, búsqueda
  en asientos, revisiones de analistas, transparencia del modelo y de las fuentes.
* **Sistema final de tesis:** lo anterior + despliegue público (requiere cuenta de hosting/dominio, §23) + actualización mensual.
* **Evolución futura:** modelos por sector cuando haya más meses; ajuste fino de un modelo de lenguaje con etiquetas por asiento;
  obras por administración directa (sin COD); ampliación nacional de la plataforma; alertas por correo a entidades.

## 23. Producción

* **Local (entregado y probado):** `docker compose up` → http://localhost:8080 (PostgreSQL, API, web; health checks; contenedores sin root).
* **Público:** guía paso a paso en `docs/DEPLOYMENT.md` (VM + Caddy con HTTPS automático, `deploy/docker-compose.prod.yml`,
  respaldo `scripts/backup_db.sh`). Requiere una cuenta de hosting o un túnel. Lo que **el equipo debe hacer**: crear la cuenta (p. ej. VM con Docker o
  Render/Fly/Cloud Run + PostgreSQL gestionado), registrar dominio (opcional), definir secretos en el proveedor y ejecutar el
  cargador contra la BD remota. CI en `.github/workflows/ci.yml` (lint, pruebas, build de imágenes).

## 24. Costos

Mínimo: US$ 0 (local) o ~US$ 5–12/mes (VM pequeña + Caddy HTTPS). Recomendado: ~US$ 15–30/mes (CDN + contenedor + PostgreSQL
gestionado con backups). El pipeline pesado corre en un PC del equipo (GPU opcional; sin GPU los embeddings tardan varias horas).

**Monitoreo implementado:** `python -m sato.models.monitor` (PSI de features, cobertura mensual, tipos de asiento sin armonizar,
desempeño realizado). En el corte actual detecta drift real en el volumen de registros F12B (fuerte aumento en 2026) y en la
composición de obras activas → justifica el reentrenamiento trimestral previsto.

## 25. Seguridad

Secretos por entorno, bcrypt, JWT con expiración, roles, consultas parametrizadas (prueba de inyección), validación Pydantic, CSP
estricta, CORS restringido, rate limiting, cabeceras de seguridad, auditoría de accesos y revisiones, contenedores sin root, BD
expuesta solo en 127.0.0.1. Lectura pública justificada (datos de origen públicos).

## 26. Testing

`pytest`: 17 pruebas unitarias (parseo OECE, números INFOBRAS, regex CUI, extracción, métricas, bootstrap, anticipación,
descripciones), 11 de no-fuga sobre datos reales, 9 de integración de API (salud, cabeceras, filtros, validación, inyección SQL,
detalle/explicación, 404, autorización, flujo de login y revisión con auditoría). Frontend: verificación de tipos (`tsc`) y build.
Prueba manual de la interfaz en navegador (panel, mapa, alertas, detalle con SHAP y evidencia).

## 27. Distribución entre integrantes

| Integrante | Responsabilidad principal | Entregables |
|---|---|---|
| 1 – Data Engineering | ingest/staging/integración, calidad, linaje, actualización mensual | `sato/ingest`, `sato/staging`, `sato/integration`, reportes de calidad |
| 2 – ML/NLP | panel, features, experimentos, NLP, XAI, análisis estadístico | `sato/features`, `sato/models`, capítulo de resultados |
| 3 – Backend | API, BD, seguridad, carga, rendimiento | `sato/api`, `db/`, `sato/serving/load_db.py` |
| 4 – Frontend/UX | plataforma web, validación con usuarios (supervisores/OCI) | `web/` |
| 5 – DevOps/QA/Integración | Docker, CI, despliegue, pruebas, documentación, normativa | `docker/`, `.github/`, `tests/`, `docs/` |

Todos deben dominar: problema, evento normativo, política anti-fuga, resultados y limitaciones.

## 28. Riesgos

| Riesgo | Prob. | Impacto | Mitigación |
|---|---|---|---|
| Cambios de formato/catálogo en OECE | alta | medio | parser con anclas y reportes de calidad; armonización de tipos |
| Sub-registro del evento (anotado como "otras ocurrencias") | media | medio | sensibilidad; revisión humana de alertas |
| Pocos positivos en Arequipa (IC amplios) | alta | medio | entrenamiento nacional; bootstrap; más meses de datos |
| Drift por nueva normativa (DS 001-2026-EF) | media | medio | monitoreo PSI y desempeño; reentrenamiento trimestral |
| Fuentes que se reescriben | media | bajo | SHA-256 y corte congelado |
| Uso indebido de alertas como acusaciones | media | alto | avisos en la plataforma; explicaciones y evidencia; revisión humana |

## 29. Planes alternativos

* Si la señal documental no fuera significativa: publicar Modelo A (más simple) y reportar el resultado negativo de B.
* Si OECE dejara de publicar asientos: el modelo A-sin-texto con SIAF/F12B/INFOBRAS sigue operando (degradado).
* Para obras sin cuaderno digital: línea de trabajo con F12B + SIAF + INFOBRAS (evento: problema "Atrasos y/o paralizaciones" del F12B).

## 30. Definition of Done (estado)

| Área | Criterio | Estado |
|---|---|---|
| Datos | fuentes verificadas, ingesta, integración, calidad, histórico | **Cumplido** |
| Investigación | dataset, metodología, baselines, experimentos, resultados, A/B | **Cumplido** |
| ML | entrenamiento, validación temporal, métricas, explicabilidad, versionado | **Cumplido** |
| NLP | evaluado contra baselines; se usa porque aporta (ver §17) | **Cumplido** |
| Software | frontend, backend, BD, API, seguridad | **Cumplido** |
| Producción | Docker, CI, monitoreo (health/ready), backups (procedimiento) | **Cumplido en local**; dominio/HTTPS público **BLOQUEADO** por cuenta de hosting |
| Tesis | resultados reproducibles, tablas, metodología, limitaciones | **Cumplido** (este documento + código) |

## Matriz de estado del proyecto

| Elemento | Estado | Evidencia | Riesgo | Próxima decisión |
|---|---|---|---|---|
| Fuente MEF | VERIFICADO | E2, E6 | archivos diarios | congelar corte por release |
| SEACE | PARCIALMENTE VERIFICADO | cobertura 28 %/48 % | incompleto desde 2021 | reemplazar por buscador SEACE si se habilita API |
| INFOBRAS | VERIFICADO | E3 | foto sin historia | archivar fotos mensuales propias |
| CCOD (cuaderno digital) | VERIFICADO | E1 | formato cambiante | — |
| Contraloría | VERIFICADO | 13 cortes | trimestral | validación externa al crecer la muestra |
| Integración | VERIFICADO | E4, §6 | enlaces ambiguos | revisión manual de ambiguos |
| Sector | DECIDIDO | §5 | heterogeneidad | modelos por sector con más datos |
| Label | DECIDIDO | §8–9, E8 | sub-registro | auditoría con usuarios expertos |
| Dataset | VERIFICADO | §7 | pocos positivos en Arequipa | actualizar mensualmente |
| ML | DECIDIDO | §13, §17 | desempeño moderado | reentrenamiento trimestral |
| NLP | DECIDIDO | §15, §17 | costo de embeddings | — |
| Arquitectura | DECIDIDO | ARCHITECTURE.md | — | — |
| Producción | local: VERIFICADO · pública: BLOQUEADO | Docker probado | requiere cuenta | elegir proveedor (§23) |
