# Registro de decisiones (cambios respecto de THESIS_CONTEXT.md y MASTER_TECHNICAL_PLAN.md)

Formato: **decisión anterior → evidencia → motivo → alternativa adoptada → impacto**. Toda la evidencia citada
es reproducible con los scripts de `research/` y los módulos de `sato/` (ver `docs/research/EVIDENCE_LOG.md`).

---

## D1. Sector de estudio: Saneamiento → todas las obras con cuaderno digital (sector como variable)

* **Anterior:** Saneamiento como candidato principal; elegir un único sector.
* **Evidencia:** `docs/research/sector_comparison.md`. En Arequipa, las obras con historia completa y ≥ 3 meses de asientos
  son 29 (Saneamiento), 156 (Transporte), 52 (Educación), 11 (Salud), 31 (Agropecuaria); con evento de atraso normativo:
  **9, 38, 13, 3 y 4** respectivamente.
* **Motivo:** con 9 casos positivos (Saneamiento) o 3 (Salud) no es posible entrenar ni evaluar con un mínimo de potencia estadística;
  ningún sector aislado en Arequipa lo permite.
* **Adoptada:** universo = contratos de obra con cuaderno de obra digital en las 8 provincias (490 obras utilizables, 113 con evento),
  con el sector (función MEF) como variable del modelo y resultados reportados por sector en la plataforma.
* **Impacto:** la tesis gana tamaño muestral y sigue respondiendo a la pregunta por sector de forma descriptiva; se pierde
  la especialización sectorial (declarada como limitación y trabajo futuro).

## D2. Cadena de integración MEF → INFOBRAS → OECE → contrato → valorizaciones → cuaderno → asientos → Contraloría → nodo central en el cuaderno de obra digital

* **Anterior:** cadena lineal de enlaces por CUI a través de todas las fuentes.
* **Evidencia:** los datasets de cuadernos, asientos, valorizaciones y contratos de OECE **no contienen CUI**; SEACE tampoco.
  El id de contrato de los cuadernos coincide exactamente con `N_COD_CONTRATO` de CONOSCE (pero solo el 28 % nacional / 48 % Arequipa
  de los cuadernos tiene contrato publicado en CONOSCE). El CUI se recupera: regex (61 % nacional), TF-IDF calibrado (precisión 0,991).
* **Motivo:** la hipótesis de enlace universal por CUI es falsa con los datos abiertos actuales.
* **Adoptada:** grafo con el **cuaderno** como nodo central: cuaderno→CUI (regex + TF-IDF), CUI→MEF/SIAF/F12B (exacto),
  cuaderno→INFOBRAS (CUI + RUC del contratista/consorciado, determinístico), cuaderno→SEACE (id de contrato, exacto),
  CUI/código INFOBRAS→Contraloría (exacto). Cada enlace guarda método y puntaje.
* **Impacto:** 90,2 % de cuadernos de Arequipa enlazados a CUI; la integración es medible y auditable.

## D3. Variable objetivo: "retraso significativo" indefinido / paralización → atraso normativo art. 203/207

* **Anterior:** definir días o porcentaje de retraso; paralización como posible label.
* **Evidencia:** (a) RLCE art. 203.1 y RLGCP art. 207.1 definen el atraso relevante como valorización acumulada ejecutada < 80 % de la
  programada y obligan a anotarlo en el cuaderno; (b) los asientos tienen los tipos «Valorización acumulada ejecutada menor al 80 %…» y
  «Calendario acelerado de obra», verificados por lectura de muestras; (c) la paralización (Ley 31589: ≥ 6 meses sin ejecución) es rara,
  tardía y en INFOBRAS no tiene historia fechada fiable.
* **Motivo:** una definición legal, fechada, reproducible y observable en tiempo real es más defendible que un umbral arbitrario de días.
* **Adoptada:** evento = primer asiento de esos tipos; sensibilidad con un evento ampliado ("disrupción": + suspensión del plazo o resolución).
* **Impacto:** 1 586 obras con evento a nivel nacional y 135 en Arequipa (696 cuadernos), con fecha exacta.

## D4. Horizonte histórico largo → ventana 2024-06 a 2026-08

* **Anterior:** simulación desde años previos (p. ej. 2023) con varias fuentes.
* **Evidencia:** los asientos abiertos solo existen desde 2024-06 (un archivo mensual por mes); la serie mensual programado/ejecutado del MEF
  (PROCESO_SELECCION) solo es densa en 2019–2021; INFOBRAS no publica historia de avances.
* **Adoptada:** panel mensual 2024-06 → 2026-08; solo obras con asiento N° 1 observado (historia completa).
* **Impacto:** 27 cortes mensuales; sin sesgo de truncamiento; limita la antigüedad del análisis (declarado).

## D5. Valorizaciones OECE como fuente temporal principal → solo validación

* **Evidencia:** 10 010 registros nacionales, 1 009 contratos, **54 contratos en Arequipa**.
* **Adoptada:** se usan para validar el extractor NLP de avances (exactitud 71–72 % a ±1 pp) y no como fuente de features principal.

## D6. Entrenamiento solo con Arequipa → entrenamiento nacional, evaluación en Arequipa

* **Evidencia:** grilla experimental: con H = 60, PR-AUC en test de Arequipa 0,196 (entrenado nacional) vs 0,148 (solo Arequipa), LightGBM, Modelo A.
* **Adoptada:** entrenamiento con 12 369 obras nacionales, evaluación principal en Arequipa y secundaria nacional.

## D7. NLP con transformers por defecto → comparación de representaciones y ablaciones

* **Anterior:** candidatos BETO / Sentence Transformers; supuesto implícito de superioridad.
* **Adoptada:** léxico de dominio, TF-IDF+SVD, TF-IDF supervisado *as-of*, Sentence-BERT multilingüe (sin ajuste fino), extracción de
  avances; ablación "sin proxy" para separar anticipación genuina de la misma anotación en otro tipo de asiento.
* **Resultado:** ver `artifacts/experiments/comparacion_A_vs_B.csv` y §17 del plan maestro.

## D8. Horizonte H: {30, 60, 90} evaluados; H operativo = 60 días (pre-registrado)

* **Motivo:** las valorizaciones son mensuales; 60 días = dos ciclos, suficiente para que la entidad actúe antes del disparador formal.
  La elección no se basó en el test.

## D9. Arquitectura: Supabase / Prefect / pgvector / Next.js → PostgreSQL + DuckDB/Parquet + orquestador propio + React/Vite

* **Motivo:** volumen (~10 GB brutos, actualización mensual), costo cero, menos componentes; no se requiere búsqueda vectorial en línea ni SSR.
  Ver `docs/architecture/ARCHITECTURE.md` §2.

## D10. Uso restringido de fotos sin fecha (INFOBRAS, Banco de Inversiones, SEACE, PIM)

* **Evidencia:** INFOBRAS y el Banco de Inversiones publican el estado actual; el PIM del SIAF está en `MES_EJE = 0` sin fecha; un
  archivo CONOSCE cambió de 10 988 a 9 666 filas el mismo día.
* **Adoptada:** solo atributos fijados al inicio; ablación `A_sin_ib`; política en `docs/methodology/LEAKAGE_POLICY.md`.

## D11. Política de alerta: umbral F2 → alerta = nivel ALTO (umbral F1), MEDIO = vigilancia

* **Evidencia (backtest as-of Arequipa, 1 740 filas observables, prevalencia 8,4 %):** umbral F2 marca 53 % de obras (precisión 12 %,
  recall 78 %); umbral F1 marca 21 % (precisión 18 %, recall 47 %).
* **Motivo:** una alerta que marca la mitad de la cartera no sirve para priorizar la supervisión.
* **Adoptada:** alerta = ALTO; MEDIO = "en vigilancia". Ambos umbrales se eligen en validación.

## D12. Alcance: solo contratos con cuaderno digital → + cartera nacional INFOBRAS (todas las modalidades)

* **Evidencia:** el cuaderno de obra digital cubre solo contratos desde junio de 2024; INFOBRAS publica 139 159 obras de todas
  las modalidades y sectores con fechas programadas y reales de término.
* **Adoptada:** segundo problema (retraso significativo al término, umbral 30 % del plazo) con modelos de inicio y seguimiento
  SIAF, entrenados a nivel nacional con particiones temporales. El modelo de alerta a 60 días se mantiene como núcleo de la tesis.

## D13. Niveles de riesgo de la cartera por cuantiles fuera de tiempo (no por umbral F1/F0.5)

* **Evidencia:** con prevalencias de 52-65 %, el umbral F0.5 marcaba cerca del 47 % de las obras como ALTO.
* **Adoptada:** ALTO = percentil 80 y MEDIO = percentil 50 de predicciones fuera de tiempo anteriores al test; se publica la
  tasa observada por nivel en el periodo de prueba.

## D14. Alcance nacional con selector de ámbito

* **Motivo:** el entrenamiento ya era nacional; restringir la interfaz a Arequipa ocultaba 97 % de las obras evaluadas.
* **Adoptada:** carga nacional en la base de datos; Arequipa se conserva como caso de estudio y en todas las métricas separadas.

