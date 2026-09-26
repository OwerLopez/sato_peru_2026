# Registro de evidencia (Evidence Log)

Registro cronológico de hallazgos verificados directamente (descarga, lectura o
ejecución de código). Fecha de las verificaciones: 2026-09-25.
Cada afirmación indica la fuente primaria y cómo se verificó.

## E1. Fuentes OECE (ex OSCE) — Cuaderno de Obra Digital y Valorizaciones

| Dataset | Dónde está el archivo real | Formato | Periodo | Actualización |
|---|---|---|---|---|
| Asientos del cuaderno de obra digital | Adjuntos de la wiki OECE `osce-gob-pe.atlassian.net/wiki` (página 106889263), enlazada desde datosabiertos.gob.pe | CSV mensual `cod-asientosAAAAMM.csv`, cp1252, `|`, CRLF | 2024-06 → 2026-08 (27 archivos) | mensual (último: 01/09/2026) |
| Cuadernos de obra digital | idem (página 106889274) | CSV anual `cod-cuadernosAAAA.csv` | 2024, 2025, 2026 | mensual |
| Valorizaciones de obras (SEACE) | idem (página 106889259) | CSV anual | 2024–2026 | mensual |

Verificado por código (`sato/staging/oece.py`, `research/q_oece_profile.py`):

- Cada archivo mensual de asientos contiene **solo** asientos publicados en ese mes
  (FECHA_REGISTRO_ASIENTO ∈ mes del archivo). No existen asientos abiertos anteriores a 2024-06.
- 2 732 593 asientos nacionales; 1 308 registros reparados (separador `|` dentro del texto) y 1 rechazado.
  El archivo 2024-11 usa un dialecto distinto (todos los campos entre comillas).
- 17 100 cuadernos nacionales (31 586 filas: una por miembro de consorcio); **696 en Arequipa** (UBIGEO 04xxxx).
  629 cuadernos de Arequipa tienen asientos → **104 299 asientos en Arequipa**.
- 2 081 cuadernos con asientos no tienen metadatos en los archivos de cuadernos (creados antes de 2024: sin ubicación).
- Los cuadernos **no contienen CUI**; sí IDENTIFICADOR_DEL_CONTRATO/EXPEDIENTE (SEACE), RUC contratista/entidad, UBIGEO y denominación.
- Valorizaciones: 10 010 registros nacionales, 1 009 contratos; **solo 54 contratos en Arequipa** → insuficiente para ML.
- El catálogo de TIPO_ASIENTO cambia en 2025-05 (entrada en vigencia Ley 32069) y 2026-04 (DS 001-2026-EF).

## E2. Fuentes MEF (Invierte.pe / SIAF)

API interna del portal `datosabiertos.mef.gob.pe` (POST `/Rest/PortalWebDatasetDetalle/v1.0/getDatasetDetalle`);
archivos en `fs.datosabiertos.mef.gob.pe/datastorefiles/`, **regenerados a diario** (Last-Modified = 2026-09-25).

| Archivo | Tamaño | Granularidad | Uso |
|---|---:|---|---|
| DETALLE_INVERSIONES.csv | 239 MB | 1 fila por inversión ACTIVA (150 518) | universo, atributos estáticos |
| CIERRE_INVERSIONES.csv | 117 MB | inversiones cerradas (119 311) | universo, fechas de cierre |
| INVERSIONES_DESACTIVADAS.csv | 280 MB | desactivadas (355 854) | universo para validación de CUI |
| FORMATO_12B.csv | 181 MB | foto actual F12B (año vigente) | solo contexto (sin historia) |
| ESTADO_SITUACIONAL.csv | 210 MB | registros fechados de situación/problema/riesgo (1.4 M) | eventos y texto con fecha |
| PROCESO_SELECCION.csv ("Componentes") | 1.2 GB | CUI × componente × periodo × etapa | series programado/ejecutado (F12B antiguo) |
| AAAA-Gasto(.zip) | 0.5–0.7 GB zip (7–10 GB CSV) | año-mes × ejecutora × meta × clasificador | devengado mensual por CUI |

- Arequipa: 7 226 inversiones activas + 3 862 cerradas; presentes las 8 provincias.
- ESTADO_SITUACIONAL en Arequipa: 41 442 registros, 7 188 CUI, 2019-02 → 2026-09, con tipos
  "PROBLEMA (Atrasos y/o paralizaciones)", "PROBLEMA (Paralización)", "PROBLEMA (Resolución de contrato)", etc.
  Muy concentrado en 2026 (17 118 registros).
- PROCESO_SELECCION: la serie mensual CONTRACTUAL (programado) vs EJECUCION (real) existe con densidad
  solo en 2019–2021 (571 CUI de Arequipa con ambas). **No sirve como columna temporal reciente.**

## E3. INFOBRAS (Contraloría)

- Dataset oficial: `infobras.contraloria.gob.pe/InfobrasWeb/DataSets` → XLSX "DataSet-Obras-Publicas dd-mm-aaaa" (57 MB, generado el día de la consulta).
- 191 180 obras nacionales, 97 campos, **1 fila por obra (foto a la fecha de consulta)**. Arequipa: 9 931 obras.
- Incluye CUI, RUC de ejecutor, fechas de inicio / fin programado / fin reprogramado / fin real, días de ampliación,
  adicionales, paralización (fecha, causal, días), último avance programado vs real.
- Decimales exportados con espacio ("1205287 56") → requiere limpieza.
- No contiene la historia mensual de avances (solo el último registro).

## E4. Resolución de entidades cuaderno → CUI (medida)

`research/q_cui_regex.py`, `research/q_cui_fuzzy.py`:

1. Regex de CUI/SNIP en la denominación, validado contra el universo MEF (626 k registros): 61% nacional, 53% Arequipa.
2. TF-IDF de n-gramas de caracteres (3–5) contra NOMBRE_INVERSION, bloqueado por departamento.
   Evaluado contra 10 075 pares con CUI explícito (verdad de referencia): umbral 0.6 y margen ≥ 0.05 →
   **precisión 99.1 %, cobertura 90.6 %**.
3. Resultado combinado: **90.2 % de cuadernos de Arequipa (628/696)** y 91.3 % nacional enlazados a un CUI.

## E5. Normativa verificada en texto oficial

- **DS 344-2018-EF (RLCE, Ley 30225), art. 203.1** (texto con modificaciones al 25-04-2023, gob.pe):
  si la valorización acumulada ejecutada es < 80% de la programada → el supervisor ordena calendario
  acelerado y "anota tal hecho en el cuaderno de obra". 203.5: si persiste < 80% del nuevo calendario → causal de
  intervención económica o resolución.
- **DS 009-2025-EF (Reglamento Ley 32069), art. 207.1** (versión actualizada al 09-01-2026, gob.pe/OECE):
  misma regla del 80% (+ "o exista atraso en la ruta crítica"), anotación en el "cuaderno de incidencias";
  modificado por DS 001-2026-EF (publicado 08-01-2026).
- Ley 32069 entra en vigencia 90 días calendario después de publicado su reglamento (22-01-2025) → 22-04-2025
  (texto de la colección oficial OECE en gob.pe).
- **Ley 31589, art. 2** (El Peruano, 22-10-2022): obra pública paralizada = avance físico ≥ 40% (contrata) con
  ≥ 6 meses sin ejecución física o contrato resuelto/nulo; administración directa: ≥ 50% y > 6 meses.
  (Un resumen secundario consultado indicaba 50% para todos los casos: incorrecto.)

## E6. SIAF (Consulta Amigable, MEF)

- Archivos anuales `AAAA-Gasto(.zip)` de 0,5–0,7 GB (7–10 GB descomprimidos); agregados a proyecto × año × mes con DuckDB
  (`sato/staging/siaf.py`): 2020–2026, 53–69 mil CUI por año.
- Semántica verificada: `MES_EJE` 1–12 contienen flujos (devengado, girado); **PIA y PIM solo aparecen en `MES_EJE = 0`**
  con su valor anual no fechado → el PIM del año en curso es inutilizable como feature (fuga).

## E7. Volatilidad y calidad de las fuentes

- El archivo CONOSCE de contratos 2024 cambió de 10 988 a 9 666 filas (y el tamaño del XLSX de 2,78 MB a 2,43 MB) entre dos descargas
  el mismo día 25-09-2026. Las columnas alternan mayúsculas/minúsculas entre versiones.
- MEF regenera sus archivos a diario (Last-Modified = día de consulta).
- OECE publica un mes (2024-11) con un dialecto CSV distinto (comillas).
- 94 asientos repetidos (mismo cuaderno y número), 14 idénticos incluso en fecha-hora: se deduplican al cargar la BD.
- El certificado TLS de `datosabiertos.mef.gob.pe` falló la validación de `urllib` (Python) pero no la de `requests/certifi` ni curl.

## E8. Etiqueta: auditoría de calidad

- Lectura de muestras aleatorias: los asientos tipificados como «Valorización acumulada … menor al 80 %» y «Calendario acelerado»
  describen efectivamente la aplicación del art. 203/207 (citan porcentajes ejecutado/programado u ordenan el calendario acelerado).
- Búsqueda por texto (regex de 80 %/calendario acelerado/retraso injustificado) en otros tipos: 3 426 cuadernos vs 2 047 con el tipo
  estructurado; las menciones libres mezclan casos reales con falsos positivos («no es de aplicación el art. 203») → la etiqueta usa
  el tipo estructurado; el texto libre se analiza como sensibilidad/ablación.
- Validez externa (nacional, `research/` + panel de Contraloría): P(aparecer luego en el reporte de obras paralizadas | atraso) = 3,3 %
  vs 1,0 % sin atraso (razón 3,3); en 45 de 53 obras (85 %) el atraso normativo precede a su aparición en el reporte.

## E9. Extracción de avances desde el texto (NLP basado en reglas)

- Validada contra valorizaciones oficiales OECE (`research/validate_extraction.py`): exactitud del avance ejecutado 70,9 % y programado
  72,1 % con error ≤ 1 punto porcentual (error absoluto mediano 0,0); cobertura baja: 11,9 % de las valorizaciones tiene un reporte
  numérico extraíble del texto.

## E10. Literatura verificada (Crossref, DOI)

`docs/research/references_crossref.json` — 24 referencias verificadas por DOI (Gondia et al. 2020; Egwim et al. 2021; Assaf & Al-Hejji
2006; Sambasivan & Soon 2007; Gallego, Rivero & Martínez 2021; Decarolis et al.; Bajari, Houghton & Tadelis; Flyvbjerg 2014; Kaufman et
al. 2012; Saito & Rehmsmeier 2015; Lundberg et al. 2020; Reimers & Gurevych 2019, 2020; Zhang et al. 2019; Tixier et al. 2016; Cerqueira
et al. 2020; Fazekas & Kocsis 2017/2020; Niculescu-Mizil & Caruana 2005; Chen & Guestrin 2016; Roberts et al. 2017; Sanni-Anibire et al.
2020). Búsqueda en ALICIA (CONCYTEC, 2026-09-25): las tesis peruanas sobre el cuaderno de obra digital son estudios de gestión con
encuestas; 0 resultados para "obras paralizadas aprendizaje automático".
