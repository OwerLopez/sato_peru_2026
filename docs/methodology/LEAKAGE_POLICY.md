# Política de prevención de fuga temporal de información (data leakage)

**Regla general.** Para una predicción en el corte **T** (último día del mes), el modelo solo puede usar
información que **existía y era consultable en T**. Todo lo registrado, publicado o actualizado después de T
está prohibido, aunque hoy esté en los archivos descargados.

```
Disponible hasta T (fecha del registro <= T y publicado)  -> PERMITIDO
Registrado/actualizado después de T, o foto actual sin fecha  -> PROHIBIDO
```

## 1. Fechas relevantes por fuente

| Fuente | Fecha que gobierna la disponibilidad | Rezago de publicación | Regla aplicada |
|---|---|---|---|
| Asientos del cuaderno de obra digital (OECE) | `FECHA_REGISTRO_ASIENTO` (fecha de publicación del asiento en el sistema) | El COD publica en tiempo real; el dataset abierto se actualiza mensualmente (día 1) | Asientos con fecha ≤ T. En operación, el corte de fin de mes se procesa con el archivo publicado el día 1 del mes siguiente |
| Estado de los asientos | `ESTADO_ASIENTO` = DEFINITIVO en el 100 % de registros (verificado) | — | No hay versiones borrador que puedan cambiar |
| SIAF – devengado mensual (MEF) | `ANO_EJE`, `MES_EJE` | El mes m se consolida en los días siguientes al cierre | Solo meses **anteriores** al mes de T (rezago conservador de 1 mes) |
| SIAF – PIA / PIM | Registrados en `MES_EJE = 0` **sin fecha** | — | PIA del año de T: permitido (aprobado antes del 1 de enero). **PIM del año en curso: prohibido** (incluye modificaciones posteriores a T) |
| Estado situacional F12B (MEF) | `FECHA_REGISTRO` | — | Registros con `fecha_registro ≤ T` (no se usa `PERIODO`, que puede registrarse tarde) |
| Banco de Inversiones (MEF) | Foto diaria sin historia | — | Solo atributos fijados antes de la ejecución: función, nivel de gobierno, tipo de inversión, marco, monto viable. **Prohibidos:** estado, costo actualizado, avance físico, devengado acumulado, fechas de F12B |
| INFOBRAS (Contraloría) | Foto a la fecha de consulta | — | Solo atributos fijados al inicio: plazo original, monto del contrato, fecha de inicio. **Prohibidos:** avance, paralización, modificaciones, fin reprogramado/real, adicionales. Se evalúa con ablación (`A_sin_ib`) |
| Contratos SEACE (CONOSCE) | Foto; archivos regenerados | — | Solo monto contratado y vigencia **originales**. **Prohibidos:** monto adicional, fin de vigencia actualizado, indicador de resolución |
| Contraloría – obras paralizadas | `fecha_corte` trimestral | ~2 meses | **No se usa como feature**; solo validación externa y contexto en la plataforma |

## 2. Auditoría feature por feature

| Grupo / feature | Cálculo | Disponible en T | Riesgo residual |
|---|---|---|---|
| `asi_n_total`, `asi_n_30d`, `asi_n_90d`, `asi_dias_activos_30d` | Conteos de asientos con fecha ≤ T | Sí | Ninguno |
| `asi_dias_desde_ultimo`, `asi_dias_desde_primero`, `asi_dias_desde_inicio_plazo` | Diferencias con fechas ≤ T | Sí (test automático: nunca negativos) | Ninguno |
| `asi_cum_<tipo>`, `asi_90d_<tipo>` | Conteo por tipo armonizado de asiento con fecha ≤ T | Sí | El tipo es asignado por quien registra: puede haber errores de clasificación (no es fuga) |
| `asi_frac_supervision_90d`, `asi_consultas_pendientes`, `asi_ritmo_30d_vs_90d` | Derivadas de lo anterior | Sí | Ninguno |
| `est_regimen_ley32069` | Tipo del asiento de apertura (≤ T) | Sí | Ninguno |
| `est_sector`, `est_nivel_gobierno`, `est_tipo_inversion`, `est_marco`, `est_log_monto_viable` | Banco de Inversiones (atributos de formulación) | Sí (fijados antes del contrato) | Bajo: el sector se asigna vía el CUI enlazado (error de enlace ~1 %) |
| `est_tipo_entidad`, `est_es_consorcio`, `est_n_miembros_consorcio`, `est_dep_code` | Metadatos del cuaderno | Sí | Ninguno |
| `est_log_monto_contratado`, `est_plazo_vigencia_dias` | SEACE original | Sí (fijados a la firma) | Bajo: cobertura parcial |
| `ib_plazo_original_dias`, `ib_log_monto_contrato`, `ib_frac_plazo_transcurrido`, `ib_dias_para_fin_programado` | INFOBRAS original + T | Valor fijado al inicio | **Medio**: la foto es posterior a T; se asume que no se reescriben. Ablación `A_sin_ib` |
| `actor_contratista_*`, `actor_entidad_*` | Obras previas del mismo RUC con inicio < T y atraso con fecha < T (nacional) | Sí | Ninguno (solo eventos fechados antes de T) |
| `siaf_dev_acum`, `siaf_dev_3m`, `siaf_dev_ytd`, `siaf_meses_desde_ultimo_dev`, ratios | Meses < mes(T) | Sí | Bajo: correcciones retroactivas del SIAF (poco frecuentes) |
| `siaf_pia_anio` | PIA del año de T | Sí | Ninguno |
| `mefseg_*` | Registros F12B con fecha_registro ≤ T | Sí | Ninguno |
| `tmp_mes`, `tmp_vigencia_ley32069` | Calendario | Sí | Ninguno |
| `txt_lx_*`, `txt_n_asientos_60d`, `txt_len_media_60d` | Texto de asientos en (T-60, T] | Sí | Ninguno |
| `txt_lx_proxy_80` | Menciones informales de la regla del 80 % | Sí | **No es fuga**, pero puede ser el mismo hecho anotado en otro tipo de asiento: se mide con la ablación `*_sinproxy` |
| `ie_*` | Avances extraídos del texto de asientos ≤ T | Sí | Igual que `proxy_80` (se excluye en `B_full_sinproxy`) |
| `txt_lsa_*` | TF-IDF + SVD: vocabulario, IDF y SVD ajustados **solo con asientos ≤ 2025-10-31** (periodo de entrenamiento) | Sí | Ninguno respecto del test |
| `txt_emb_*` | Sentence-BERT preentrenado (sin ajuste) + PCA ajustado con filas de entrenamiento | Sí | Ninguno respecto del test |
| `txt_stack_tfidf`, `txt_stack_emb` | Regresión logística **as-of**: el score del mes m usa un modelo entrenado solo con filas T' tales que T' + H ≤ m; en test, congelado en el inicio del test | Sí | Ninguno (forward chaining) |

## 3. Etiquetas y partición

* Etiqueta `y_H(T) = 1` si el **primer** asiento de atraso normativo ocurre en (T, T+H].
* Solo son elegibles las filas donde el evento aún **no** ocurrió y la obra no terminó (predicción del *onset*).
* Una etiqueta solo se usa si `T + H ≤ fin de datos`; las demás son filas de inferencia.
* Partición temporal con **purga de H días**: `max(T_train) + H ≤ min(T_valid)` y `max(T_trainval) + H ≤ min(T_test)`.
* Umbral de alerta e hiperparámetros se eligen **solo** con validación; el test se evalúa una vez.

## 4. Verificación automática

`tests/test_no_leakage.py` recalcula, de forma independiente al código de features y sobre los datos
reales, las etiquetas, los conteos de asientos, el devengado SIAF con rezago y la partición con purga.
Cualquier violación hace fallar la suite de pruebas.
