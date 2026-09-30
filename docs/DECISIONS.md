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


## D15. Explicaciones en lenguaje claro y confiabilidad observada en lugar de puntajes técnicos

* **Motivo:** los factores se mostraban como descripciones técnicas («Riesgo inferido del vocabulario... (modelo TF-IDF)»,
  «código INEI: 04», «Días para el fin programado: -45») y la probabilidad sola invitaba a leerla como certeza.
* **Adoptada:** `sato/serving/lenguaje.py` traduce cada variable y su valor real a una frase; la interfaz acompaña cada
  estimación con su nivel, las veces que supera la tasa promedio, su posición relativa en el corte y la tasa de eventos
  observada para ese nivel en el backtest (`/modelo/calibracion`). El valor SHAP queda disponible bajo demanda.
* **Evidencia:** las probabilidades del modelo de alerta están calibradas (deciles 1,5 % → 1,1 % y 20,0 % → 17,7 %), por lo
  que mostrar la tasa observada no distorsiona la estimación.

## D16. Auditoría de calidad de datos automática y sin corrección silenciosa

* **Motivo:** los hallazgos de calidad estaban dispersos en reportes por fuente y no eran visibles para el usuario.
* **Adoptada:** `sato/serving/calidad.py` ejecuta 29 chequeos sobre la base después de cada carga y los publica en
  «Datos y fuentes». Los hallazgos se informan tal como están en las fuentes; no se imputan ni se ocultan.
* **Resultado:** detectó un defecto real (1 800 obras activas sin explicación del riesgo de seguimiento), corregido con prueba de regresión.

## D17. Compuerta de integridad antes de publicar cada carga

* **Motivo:** la carga reemplazaba todos los datos sin comprobar que la nueva versión fuera completa; un archivo oficial
  truncado o un paso previo fallido habría publicado una base incompleta.
* **Adoptada:** `load_db.load` valida las entradas (archivos, columnas, claves sin nulos ni repetidos), concilia filas de origen,
  cargadas y descartadas con su motivo, y antes del `COMMIT` exige que los chequeos críticos de `calidad` estén en cero y que
  ninguna tabla clave caiga más de `SATO_CARGA_CAIDA_MAX` (20 %) frente a la carga vigente. Si falla, la transacción se revierte.
  Cada intento queda en `carga_datos` (OK, RECHAZADA o ERROR) y se publica en «Estado y monitoreo».
* **Verificación:** pruebas de reversión sobre una base temporal (`tests/test_bd.py`) y unitarias de la compuerta (`tests/test_operacion.py`).

## D18. Recarga sin interrumpir la lectura (DELETE en lugar de TRUNCATE)

* **Evidencia:** durante una recarga real, `/api/v1/resumen` y `/api/v1/obras` no respondieron en 30 s: `TRUNCATE` toma un
  bloqueo exclusivo que se mantiene toda la transacción (unos 10 minutos).
* **Adoptada:** la transacción borra con `DELETE` y refresca las vistas con `REFRESH MATERIALIZED VIEW CONCURRENTLY`; por MVCC
  la API sigue leyendo la versión vigente hasta el `COMMIT`. Después se ejecuta `VACUUM (ANALYZE)`. La API usa además
  `lock_timeout` (5 s) y `statement_timeout` (20 s) para responder 503 en lugar de quedar colgada ante cualquier bloqueo.
* **Costo medido:** la carga pasa de unos 10 a 22 minutos (más 4 minutos de `VACUUM`), y las consultas son más lentas mientras
  dura (mediana de 2,1 s); a cambio, la API respondió 417 de 417 solicitudes durante la recarga.
* **Hallazgos al implementarlo:** el borrado quedó detenido porque `evidencia.asiento_id` no tenía índice (cada asiento borrado
  recorría la tabla hija); se indexaron las seis claves foráneas que no lo tenían y se agregó una prueba que lo exige. El
  `VACUUM` posterior fallaba por la memoria compartida de 64 MB de Docker (`shm_size: 256mb`) y, al estar dentro de la carga,
  marcaba como ERROR una versión ya publicada; ahora corre después del registro y su falla solo genera un aviso.

## D19. Monitoreo del modelo visible y detección de anomalías

* **Motivo:** el paso `monitor` calculaba deriva (PSI) y desempeño realizado, pero el reporte no llegaba a la plataforma.
* **Adoptada:** el reporte se carga con cada versión de datos y se publica en `/sistema/monitoreo` y en la pantalla «Estado y
  monitoreo», con nombres de variables en lenguaje claro. Se agregó la detección de una proporción atípica de obras en nivel
  alto en el corte vigente (puntaje z robusto con mediana y MAD, umbral 3,5; Iglewicz y Hoaglin, 1993).
* **No adoptado:** reentrenamiento automático. El PSI alto puede reflejar un cambio real de la cartera y no un deterioro; el
  reentrenamiento exige revisar el desempeño realizado y repetir la validación temporal, por lo que queda como decisión humana.

## D20. Worker autocontrolado

* **Adoptada:** candado de base de datos (`pg_try_advisory_lock`) para que nunca haya dos sincronizaciones simultáneas;
  reintentos por paso con espera exponencial (los rechazos de la compuerta no se reintentan); tope de intentos por mes con
  espera creciente; recuperación de sincronizaciones interrumpidas; latido en `servicio_latido`; avisos por correo a
  `SATO_ALERTAS_EMAIL` ante fallos, rechazos o alertas del monitoreo.

## D21. Endurecimiento de seguridad verificado con pruebas

* Límite de intentos de ingreso por cuenta y por IP en la API (además de nginx) y verificación bcrypt aun cuando la cuenta no
  existe (sin diferencia de tiempo que revele cuentas).
* JWT con emisor, `nbf` y campos obligatorios; el rol efectivo se lee de la base en cada solicitud.
* Suscripciones con respuesta uniforme (no revelan suscriptores), enlace de confirmación con vencimiento, validación del
  ámbito contra los datos y enlaces armados con `SATO_BASE_URL` (nunca con la cabecera `Host`). Se corrigió la restricción
  única que, por tratar `NULL` como distinto, permitía duplicar suscripciones a «todo el Perú».
* IP del cliente: nginx confiaba en `X-Forwarded-For` de toda la red privada, y un cliente que llegaba por la puerta de
  enlace de Docker podía declarar cualquier IP y evadir los límites de tasa (lo detectó `tests/e2e/test_despliegue.py`: 20
  intentos de ingreso sin un solo 429). Ahora solo se confía en la IP fija de Caddy (`SATO_PROXY_CONFIABLE`, plantilla de
  nginx) y nginx reemplaza la cabecera hacia la API; la web se publica solo en `127.0.0.1` salvo que se indique `WEB_BIND`.
* `Cache-Control: no-store` en respuestas autenticadas y de acciones; `X-Request-ID` solo si es un identificador simple.
* Enlaces a fuentes externas solo con esquema http(s) en la interfaz.
