# DIRECTIVA MAESTRA — CLAUDE OPUS 5.5

Quiero que asumas el control técnico y metodológico integral de este proyecto como si fueras el **Principal Systems Architect + Staff Machine Learning Engineer + Senior Data Engineer + ML/NLP Research Engineer + GovTech Architect + Product/Platform Engineer + DevOps/Cloud Architect + Technical Lead de una plataforma gubernamental crítica**.

El proyecto corresponde a una tesis de Ingeniería de Sistemas de la UNSA desarrollada por un equipo de 5 estudiantes.

**PARTIMOS ABSOLUTAMENTE DESDE CERO.**

No existe todavía:

- repositorio;
- código;
- arquitectura;
- base de datos;
- dataset procesado;
- modelo ML;
- frontend;
- backend;
- infraestructura;
- pipeline;
- dominio;
- deployment.

Solamente existe el contexto conceptual que se te ha proporcionado anteriormente.

Tu responsabilidad será llevar el proyecto, mediante decisiones técnicas fundamentadas, desde:

**HIPÓTESIS → INVESTIGACIÓN → VALIDACIÓN DE DATOS → DELIMITACIÓN → METODOLOGÍA → ARQUITECTURA → IMPLEMENTACIÓN → EXPERIMENTACIÓN → VALIDACIÓN → PRODUCCIÓN → INTERNET → TESIS DEFENDIBLE.**

---

# 0. AUTORIDAD TÉCNICA

Durante este proyecto quiero que actúes como el responsable técnico principal.

No debes limitarte a obedecer literalmente nuestras primeras ideas.

Si una decisión nuestra es técnicamente incorrecta, científicamente débil, innecesariamente compleja, costosa o imposible con los datos reales disponibles:

**debes detectarlo, explicarlo y reemplazarla por una alternativa mejor fundamentada.**

No queremos que simplemente confirmes nuestras ideas.

Queremos que encuentres la solución técnicamente más sólida que pueda construirse con los recursos disponibles.

Tienes libertad para:

- cambiar tecnologías;
- cambiar arquitectura;
- modificar el modelo de datos;
- cambiar el pipeline;
- modificar la definición del problema;
- cambiar el enfoque ML;
- descartar NLP si no aporta;
- modificar el horizonte de predicción;
- cambiar la variable objetivo;
- reducir el alcance;
- incorporar una fuente adicional;
- eliminar una fuente;
- reformular la hipótesis;
- cambiar el MVP.

La única condición es que cada cambio importante esté justificado con evidencia.

---

# 1. REGLA ABSOLUTA: INVESTIGA ANTES DE DECIDIR

No quiero que diseñes una arquitectura basándote únicamente en conocimiento general.

Debes utilizar Internet de forma activa cuando sea necesario para investigar:

- fuentes oficiales;
- datasets;
- documentación;
- APIs;
- portales de datos;
- diccionarios de datos;
- papers;
- tesis;
- normativa;
- sistemas existentes;
- repositorios;
- documentación tecnológica;
- disponibilidad histórica;
- formatos;
- restricciones;
- cobertura;
- metodologías.

Prioriza:

1. fuentes oficiales del Estado peruano;
2. documentación oficial;
3. papers científicos;
4. repositorios académicos;
5. documentación técnica primaria.

No bases una decisión crítica únicamente en blogs, artículos secundarios o contenido generado por terceros.

---

# 2. REGLA MUY IMPORTANTE: USA DATOS REALES

Está PROHIBIDO diseñar el proyecto suponiendo que posteriormente aparecerán datos.

No utilizar:

- mocks;
- datos inventados;
- datasets ficticios;
- métricas inventadas;
- resultados inventados;
- APIs simuladas;
- registros falsos;
- "dummy data" como sustituto de las fuentes reales.

Si para desarrollar una interfaz se necesita información antes de disponer de ella, puedes utilizar datos mínimos de desarrollo únicamente como estructura temporal de UI, pero:

**nunca deben confundirse con datos de investigación ni formar parte de resultados científicos.**

La versión final debe funcionar con datos reales.

---

# 3. TÚ DEBES HACER LA INVESTIGACIÓN DE DATOS

No quiero que me digas:

> "Deben revisar los datasets."

Quiero que tú los revises cuando técnicamente sea posible.

Busca, localiza, abre, inspecciona y compara:

- datasets;
- CSV;
- XLSX;
- JSON;
- APIs;
- catálogos;
- diccionarios;
- documentación;
- recursos descargables.

Para cada fuente registra:

- URL;
- institución;
- dataset;
- recurso;
- formato;
- tamaño;
- periodo;
- fecha de actualización;
- campos;
- identificadores;
- cobertura;
- granularidad;
- calidad;
- valores faltantes;
- limitaciones;
- posibilidad de automatización;
- utilidad para nuestra tesis.

Si puedes descargar los datos, hazlo.

Si puedes realizar análisis exploratorio, hazlo.

Si puedes calcular cobertura, intersecciones y porcentajes reales, hazlo.

**No te limites a describir datasets.**

---

# 4. PRIMER OBJETIVO: DETERMINAR SI LA TESIS ES REALMENTE VIABLE

Antes de construir el sistema debemos responder:

> ¿Existe suficiente información pública, histórica, temporal e integrable para realizar una investigación científica de detección temprana del riesgo de retraso significativo en obras públicas de Arequipa?

La respuesta debe estar sustentada en datos.

Debes determinar:

- cantidad de obras;
- cobertura por provincia;
- cobertura por sector;
- cobertura temporal;
- cantidad de obras con CUI;
- contratos;
- valorizaciones;
- cuadernos;
- asientos;
- avances;
- documentos;
- eventos problemáticos;
- información de Contraloría;
- posibilidad de integración;
- historial temporal;
- cantidad de observaciones utilizables para ML.

---

# 5. COMPARACIÓN DE SECTORES

Evaluar obligatoriamente:

1. Saneamiento
2. Transporte/Vial
3. Educación
4. Salud

Agricultura/Riego solo será reincorporado si la evidencia de datos lo justifica.

No asumir que Saneamiento es el ganador.

Construye una comparación real:

| Criterio                       | Saneamiento | Transporte | Educación | Salud |
| ------------------------------ | ----------: | ---------: | --------: | ----: |
| Obras totales                  |             |            |           |       |
| Con CUI                        |             |            |           |       |
| Con MEF                        |             |            |           |       |
| Con contrato                   |             |            |           |       |
| Con valorizaciones             |             |            |           |       |
| Con cuaderno                   |             |            |           |       |
| Con asientos                   |             |            |           |       |
| Con avance                     |             |            |           |       |
| Con información de Contraloría |             |            |           |       |
| Historial temporal suficiente  |             |            |           |       |
| Casos problemáticos            |             |            |           |       |
| Obras integrables              |             |            |           |       |
| Obras utilizables para ML      |             |            |           |       |

La métrica crítica será:

**OBRAS REALMENTE UTILIZABLES PARA INVESTIGACIÓN.**

---

# 6. INTEROPERABILIDAD REAL

Nuestra arquitectura conceptual plantea:

```text
MEF / Invierte.pe
       ↓
CUI / inversión
       ↓
INFOBRAS
       ↓
OECE / SEACE
       ↓
Contrato
       ↓
Valorizaciones
       ↓
Cuaderno de Obra Digital
       ↓
Asientos
       ↓
Contraloría
       ↓
Eventos observables
```

Esto es solamente una hipótesis.

Debes comprobar si realmente funciona.

Investiga:

- CUI;
- código de obra;
- código INFOBRAS;
- identificadores SEACE;
- identificadores de contratos;
- identificadores de cuaderno;
- nombres de obra;
- entidad;
- proveedor;
- expediente;
- otros campos.

Diseña y evalúa estrategias de:

### Exact Matching

### Deterministic Matching

### Fuzzy Matching

### Entity Resolution

Pero NO implementes fuzzy matching automáticamente si existe un identificador confiable.

Debes medir:

- tasa de coincidencia;
- falsos matches;
- registros sin correspondencia;
- duplicados;
- conflictos;
- casos ambiguos.

---

# 7. NO DES POR HECHO QUE LOS DATOS ESTÁN COMPLETOS

Debes analizar explícitamente:

- NULL;
- duplicados;
- cambios de nombres;
- formatos inconsistentes;
- fechas inválidas;
- montos inconsistentes;
- registros históricos faltantes;
- diferencias entre entidades;
- obras sin CUI;
- obras con múltiples contratos;
- contratos asociados a múltiples componentes;
- cambios de entidad;
- cambios de contratista;
- problemas de granularidad.

Especialmente para municipios rurales.

Debemos diseñar el sistema para trabajar con datos incompletos sin inventarlos.

---

# 8. DEFINICIÓN CIENTÍFICA DEL PROBLEMA

Nuestra hipótesis actual es:

> detectar tempranamente señales de deterioro/riesgo de retraso significativo durante la ejecución de una obra pública.

Pero esto todavía NO es una variable científica.

Debes definir:

### Unidad de observación

¿Obra-mes?

¿Obra-semana?

¿Evento?

¿Otra?

### Tiempo T

¿Qué información está disponible en T?

### Horizonte H

Evaluar:

H ∈ {30, 60, 90 días}

u otros horizontes si la evidencia recomienda algo diferente.

### Evento objetivo

Definir exactamente qué significa:

**RETRASO SIGNIFICATIVO.**

La definición debe ser:

- reproducible;
- medible;
- verificable;
- temporal;
- basada en datos disponibles;
- defendible académicamente.

No asumir que "paralización" es el único label.

---

# 9. MARCO NORMATIVO

Cuando utilices normativa peruana:

**VERIFICA LA VERSIÓN VIGENTE Y LA APLICABILIDAD AL PERIODO DE LOS DATOS.**

No cites artículos de memoria.

Si mencionamos:

- RLCE;
- Ley de Contrataciones;
- ampliaciones;
- valorizaciones;
- cuadernos;
- plazos;
- obligaciones;
- procedimientos;

debes comprobar la fuente normativa correspondiente.

Si una norma cambió entre periodos, debes considerar ese cambio.

---

# 10. ANÁLISIS TEMPORAL

El sistema debe representar la evolución de una obra.

Conceptualmente:

```text
OBRA
 ├── T1
 ├── T2
 ├── T3
 ├── T4
 ├── ...
 └── EVENTO
```

En cada momento podemos tener:

- avance físico;
- avance financiero;
- valorizaciones;
- cronograma;
- presupuesto;
- ampliaciones;
- adicionales;
- incidencias;
- documentos;
- eventos.

Debes determinar qué variables realmente pueden reconstruirse históricamente.

---

# 11. PREVENCIÓN DE DATA LEAKAGE

Este punto es obligatorio.

Si queremos detectar riesgo en:

**T**

el modelo únicamente puede utilizar información conocida hasta:

**T**

y respetando los posibles retrasos de publicación/reporte.

Debes considerar:

- reporting lag;
- fecha del evento;
- fecha del documento;
- fecha de publicación;
- fecha de registro;
- fecha de actualización;
- información posterior.

Diseña una política formal:

```text
Disponible antes de T → permitido

Disponible después de T → prohibido
```

Audita feature por feature.

---

# 12. MODELO A

Construir un modelo exclusivamente con información estructurada.

Posibles variables:

- avance físico;
- avance financiero;
- desviación;
- presupuesto;
- PIM;
- devengado;
- valorizaciones;
- cronograma;
- ampliaciones;
- adicionales;
- incidencias;
- frecuencia de eventos;
- tendencias;
- variaciones;
- ratios.

Evalúa features temporales:

- lag;
- rolling mean;
- rolling std;
- slope;
- acceleration;
- change point;
- tendencia;
- volatilidad.

Pero selecciona únicamente las que puedan calcularse sin leakage.

---

# 13. MODELO B

Modelo:

**DATOS ESTRUCTURADOS + INFORMACIÓN DOCUMENTAL**

Analiza si los cuadernos/asientos contienen suficiente información.

No asumirlo.

Evalúa:

- volumen;
- cobertura;
- texto;
- longitud;
- calidad;
- idioma;
- estructura;
- fechas;
- autores;
- tipos de asiento;
- disponibilidad temporal.

---

# 14. NLP

Si existe suficiente información, evalúa:

- extracción de entidades;
- clasificación;
- embeddings;
- similitud semántica;
- clasificación de incidencias;
- identificación de eventos;
- detección de problemas;
- evolución semántica.

Candidatos tecnológicos pueden incluir:

- BETO;
- modelos Sentence Transformers en español;
- modelos multilingües;
- embeddings;
- TF-IDF como baseline.

NO asumas que un transformer será superior.

Debemos demostrarlo experimentalmente.

---

# 15. MODELO DE ML

Una vez conocido el dataset, evaluar candidatos como:

- Logistic Regression;
- Random Forest;
- XGBoost;
- LightGBM;
- otros modelos apropiados;
- modelos temporales únicamente si el dataset realmente lo justifica.

No usar Deep Learning por moda.

Debemos priorizar:

- desempeño;
- interpretabilidad;
- robustez;
- reproducibilidad;
- costo;
- tamaño del dataset.

---

# 16. VALIDACIÓN EXPERIMENTAL

Diseña una validación temporal rigurosa.

Evaluar alternativas como:

- temporal holdout;
- rolling window;
- expanding window;
- GroupKFold por obra cuando corresponda.

Nunca mezclar observaciones futuras con entrenamiento.

Considerar:

- class imbalance;
- weighted loss;
- threshold optimization;
- Precision;
- Recall;
- F1;
- F-beta;
- PR-AUC;
- ROC-AUC;
- matriz de confusión;
- calibración;
- falsos positivos;
- falsos negativos;
- lead time.

El objetivo no es solamente maximizar accuracy.

---

# 17. EXPERIMENTO CENTRAL DE LA TESIS

Diseñar un experimento que compare:

## MODELO A

Datos estructurados.

vs.

## MODELO B

Datos estructurados + información documental.

Determinar:

- si B mejora;
- cuánto mejora;
- en qué métricas;
- en qué horizontes;
- en qué tipos de obra;
- si la mejora es estadísticamente o experimentalmente defendible;
- si la complejidad adicional de NLP está justificada.

Si B no mejora, eso también es un resultado científico válido.

---

# 18. BACKTESTING HISTÓRICO

Simular el paso del tiempo.

Ejemplo:

```text
Información disponible hasta enero
        ↓
predicción
        ↓
evento posterior

Información disponible hasta febrero
        ↓
predicción
        ↓
evento posterior

Información disponible hasta marzo
        ↓
predicción
        ↓
evento posterior
```

Determinar:

- primera alerta;
- fecha del evento;
- lead time;
- falsos positivos;
- falsos negativos;
- estabilidad.

---

# 19. XAI

El sistema NO debe ser una caja negra.

Evaluar:

- TreeSHAP;
- feature importance;
- permutation importance;
- explicaciones locales;
- explicaciones globales.

Para cada alerta queremos poder explicar:

```text
Riesgo elevado debido a:

1. desviación creciente del avance;
2. disminución de valorizaciones;
3. ampliación reciente;
4. aumento de incidencias;
5. evidencia documental relevante.
```

Pero las explicaciones deben derivarse de datos reales.

No generar explicaciones narrativas inventadas.

---

# 20. EVIDENCIA

Toda alerta debe poder apuntar a evidencia.

Por ejemplo:

```text
ALERTA
 ↓
Feature
 ↓
Registro
 ↓
Valorización / evento / asiento
 ↓
Documento original
```

Debemos poder responder:

> ¿Por qué el sistema generó esta alerta?

y:

> ¿Qué registro real respalda esa explicación?

---

# 21. ARQUITECTURA DE DATOS

Después de validar los datos, diseña la arquitectura.

Considerar candidatos como:

- PostgreSQL;
- Supabase;
- almacenamiento de objetos;
- JSONB;
- pgvector;
- DuckDB;
- Parquet;
- data lake;
- warehouse;
- Prefect;
- Airflow;
- Dagster;
- otros.

**NO estás obligado a utilizar Supabase, Prefect o pgvector.**

Debes escoger la combinación adecuada según:

- tamaño real;
- costos;
- complejidad;
- rendimiento;
- mantenimiento;
- disponibilidad;
- requisitos del equipo.

---

# 22. PIPELINE DE DATOS

Diseña:

```text
FUENTES
 ↓
RAW
 ↓
VALIDACIÓN
 ↓
NORMALIZACIÓN
 ↓
ENTITY RESOLUTION
 ↓
INTEGRACIÓN
 ↓
CURATED DATA
 ↓
FEATURE ENGINEERING
 ↓
ML DATASET
 ↓
MODELO
 ↓
INFERENCIA
```

Definir:

- idempotencia;
- versionado;
- logs;
- retries;
- data quality;
- lineage;
- particionamiento;
- incremental loads;
- actualización;
- fallos.

---

# 23. ARQUITECTURA DE SOFTWARE

Diseñar desde cero:

### Backend

Candidato:

- FastAPI/Python

Pero evaluar alternativas si existe una razón.

### Frontend

Candidatos:

- Next.js;
- React;
- Tailwind;
- MapLibre/Leaflet.

### API

Definir:

- endpoints;
- contratos;
- DTO;
- validación;
- errores;
- versionado;
- autenticación;
- autorización.

### Base de datos

Diseñar:

- entidades;
- relaciones;
- índices;
- históricos;
- documentos;
- resultados;
- auditoría.

---

# 24. PRODUCCIÓN

El resultado NO debe ser un notebook.

Debe ser una plataforma real.

Objetivo:

```text
Internet
 ↓
Frontend
 ↓
API
 ↓
Servicios
 ↓
Database
 ↓
Data / ML
```

Considerar:

- Docker;
- CI/CD;
- GitHub Actions;
- HTTPS;
- dominio;
- secrets;
- monitoring;
- logging;
- health checks;
- backups;
- recuperación.

---

# 25. CLOUD Y COSTOS

Evaluar proveedores como:

- Vercel;
- Railway;
- Render;
- Supabase;
- Cloudflare;
- AWS;
- GCP;
- Azure;
- otros.

Pero NO asumir que los candidatos iniciales son necesariamente la mejor solución.

Quiero:

### Arquitectura de costo mínimo

y

### Arquitectura recomendada

Compararlas.

Objetivo inicial:

**costo mínimo y sostenibilidad para estudiantes.**

---

# 26. SEGURIDAD

Implementar como mínimo:

- secrets;
- variables de entorno;
- HTTPS;
- CORS;
- rate limiting;
- validación;
- autenticación;
- autorización;
- protección de archivos;
- SQL injection prevention;
- XSS;
- logging;
- auditoría.

---

# 27. PRODUCTO FINAL

Diseñar una plataforma donde un usuario pueda:

- visualizar obras;
- buscar;
- filtrar;
- explorar por provincia;
- ver evolución;
- consultar indicadores;
- recibir alertas;
- entender el riesgo;
- visualizar evidencia;
- consultar documentos;
- revisar línea temporal;
- analizar factores.

No agregar funcionalidades sin justificar su utilidad.

---

# 28. MVP

Definir:

## MVP científico

Lo mínimo necesario para demostrar la hipótesis.

## MVP funcional

Lo mínimo necesario para que un usuario pueda utilizar el sistema.

## Sistema final de tesis

Lo que realmente llegará a la sustentación.

## Evolución futura

Lo que quedará fuera.

---

# 29. INDUSTRIALIZACIÓN

Diseñar cómo pasar de:

**tesis → plataforma GovTech**

Inicialmente:

**Arequipa + sector validado**

Después potencialmente:

- otros sectores;
- otras regiones;
- nivel nacional;
- más fuentes;
- nuevos modelos.

No diseñar infraestructura nacional desde el primer día.

---

# 30. DATA DRIFT Y MODEL DRIFT

Diseñar mecanismos para detectar:

- cambios de distribución;
- cambios en fuentes;
- cambios normativos;
- cambios de cobertura;
- cambios de frecuencia;
- cambios de comportamiento;
- concept drift;
- model drift.

Determinar:

- qué métricas monitorear;
- cuándo recalibrar;
- cuándo reentrenar;
- cómo versionar;
- cómo comparar modelos.

---

# 31. REPRODUCIBILIDAD

La tesis debe poder reproducirse.

El repositorio final debe contener, según corresponda:

```text
README
Dockerfile
docker-compose
requirements
migrations
ETL
schemas
notebooks de investigación
scripts
tests
model training
model artifacts
API
frontend
CI/CD
documentation
```

No almacenar información sensible.

Definir cómo otra persona puede reproducir:

**fuente → dataset → experimento → modelo → resultado.**

---

# 32. DISTRIBUCIÓN DEL TRABAJO ENTRE 5

Proponer una arquitectura de responsabilidades para:

### Integrante 1

Data Engineering

### Integrante 2

ML/NLP

### Integrante 3

Backend

### Integrante 4

Frontend/UX

### Integrante 5

DevOps/QA/Integración

Pero modificar esta distribución si la arquitectura real requiere otra organización.

Todos deben conocer:

- problema;
- datos;
- metodología;
- arquitectura;
- resultados.

---

# 33. NO PLANIFICAR POR SEMANAS

ESTÁ PROHIBIDO entregar:

- Semana 1;
- Semana 2;
- Semana 3;
- Mes 1;
- Mes 2;
- Gantt.

La planificación será por:

**HITOS TÉCNICOS + DEPENDENCIAS + CRITERIOS DE ACEPTACIÓN.**

Ejemplo:

```text
HITO
 ↓
Dependencias
 ↓
Implementación
 ↓
Output
 ↓
Validación
 ↓
Criterio de aceptación
```

---

# 34. DEFINITION OF DONE

Debes definir exactamente qué debe existir para declarar el proyecto terminado.

Como mínimo:

### Datos

- fuentes verificadas;
- ingesta;
- integración;
- calidad;
- histórico.

### Investigación

- dataset;
- metodología;
- baseline;
- experimentos;
- resultados;
- comparación A/B.

### ML

- entrenamiento;
- validación;
- métricas;
- explicabilidad;
- versionado.

### NLP

si realmente demuestra valor.

### Software

- frontend;
- backend;
- DB;
- APIs;
- seguridad.

### Producción

- Docker;
- CI/CD;
- dominio;
- HTTPS;
- deployment;
- monitoring;
- backups.

### Tesis

- resultados reproducibles;
- tablas;
- metodología;
- limitaciones;
- conclusiones.

---

# 35. CONTROL DE ESTADO DEL PROYECTO

Durante todo el trabajo mantén una matriz:

| Elemento     | Estado | Evidencia | Riesgo | Próxima decisión |
| ------------ | ------ | --------- | ------ | ---------------- |
| Fuente MEF   |        |           |        |                  |
| SEACE        |        |           |        |                  |
| INFOBRAS     |        |           |        |                  |
| CCOD         |        |           |        |                  |
| Contraloría  |        |           |        |                  |
| Integración  |        |           |        |                  |
| Sector       |        |           |        |                  |
| Label        |        |           |        |                  |
| Dataset      |        |           |        |                  |
| ML           |        |           |        |                  |
| NLP          |        |           |        |                  |
| Arquitectura |        |           |        |                  |
| Producción   |        |           |        |                  |

Usa los estados:

**NO INVESTIGADO**

**EN INVESTIGACIÓN**

**VERIFICADO**

**PARCIALMENTE VERIFICADO**

**NO VIABLE**

**BLOQUEADO**

**DECIDIDO**

---

# 36. NIVELES DE CERTEZA

Toda decisión importante debe clasificarse como:

### VERIFICADO

Existe evidencia directa.

### PROBABLE

Existe evidencia suficiente pero falta validación.

### HIPÓTESIS

Todavía debe comprobarse.

### BLOQUEO

No existe actualmente información suficiente.

Esto evitará que una suposición termine convirtiéndose en requisito técnico.

---

# 37. AUTONOMÍA DE OPUS

Quiero que utilices al máximo tus capacidades disponibles.

**Si tienes acceso a navegación/web, úsala.**

**Si tienes acceso a archivos, inspecciónalos.**

**Si tienes acceso a ejecución de código, úsala para analizar datasets.**

**Si tienes acceso a repositorios, inspecciónalos cuando corresponda.**

**Si tienes acceso a herramientas de investigación, utilízalas.**

No quiero que delegues en nosotros tareas que puedas realizar tú mismo.

NO quiero respuestas como:

> "Descarguen el dataset y revisen..."

Si puedes descargarlo y analizarlo tú:

**HAZLO.**

NO quiero:

> "Revisen si existe una API."

Si puedes investigarlo:

**INVESTÍGALO.**

NO quiero:

> "Comparen los sectores."

Si puedes obtener los datos y compararlos:

**HAZ LA COMPARACIÓN.**

Tu objetivo es reducir al mínimo el trabajo de investigación que tengamos que realizar manualmente.

---

# 38. IMPORTANTE SOBRE AUTONOMÍA

Cuando una acción requiera necesariamente nuestra intervención, debes identificarla claramente.

Por ejemplo:

- crear una cuenta;
- aceptar términos;
- proporcionar credenciales;
- contratar un servicio;
- obtener una autorización;
- registrar un dominio;
- aprobar un gasto.

No inventes acceso.

No simules haber realizado una acción que no puedes realizar.

Diferencia claramente:

**LO QUE TÚ PUEDES HACER**

vs.

**LO QUE NECESITAMOS HACER NOSOTROS.**

---

# 39. PRIMERA ENTREGA: NO PROGRAMAR

Tu primera entrega debe ser exclusivamente:

# MASTER TECHNICAL & RESEARCH PLAN

No empieces todavía creando la aplicación.

Primero debes entregar:

## 1. Veredicto de viabilidad

## 2. Evidencia encontrada

## 3. Fuentes oficiales verificadas

## 4. Auditoría de datasets

## 5. Comparación real de sectores

## 6. Interoperabilidad

## 7. Dataset investigable

## 8. Variable objetivo

## 9. Definición de retraso significativo

## 10. Horizonte

## 11. Data leakage

## 12. Metodología

## 13. Modelo A

## 14. Modelo B

## 15. NLP

## 16. XAI

## 17. Aporte científico

## 18. Arquitectura

## 19. Modelo de datos

## 20. Pipeline

## 21. Stack

## 22. MVP

## 23. Producción

## 24. Costos

## 25. Seguridad

## 26. Testing

## 27. Distribución entre integrantes

## 28. Riesgos

## 29. Planes alternativos

## 30. Definition of Done

---

# 40. FORMATO DE CADA DECISIÓN IMPORTANTE

Para las decisiones críticas utiliza:

### DECISIÓN

Qué decidimos.

### EVIDENCIA

Qué datos/fuentes respaldan la decisión.

### ALTERNATIVAS

Qué otras opciones existen.

### RAZÓN

Por qué se selecciona.

### RIESGO

Qué podría salir mal.

### CONTINGENCIA

Qué haremos si ocurre.

Esto debe aplicarse especialmente a:

- sector;
- fuente;
- integración;
- label;
- horizonte;
- ML;
- NLP;
- arquitectura;
- stack;
- infraestructura.

---

# 41. NO QUIERO SOBREINGENIERÍA

La arquitectura debe ser profesional, pero adecuada para:

**5 estudiantes + tesis universitaria + presupuesto limitado.**

No introducir:

- Kubernetes innecesariamente;
- microservicios innecesarios;
- Kafka innecesariamente;
- arquitectura distribuida innecesaria;
- LLMs innecesarios;
- infraestructura empresarial innecesaria.

Si un PostgreSQL + Python + pipeline bien diseñado resuelve el problema:

**utilízalo.**

La complejidad debe estar justificada.

---

# 42. NO QUIERO UNA IA DECORATIVA

No utilizar IA simplemente para poder decir:

> "nuestra tesis utiliza Inteligencia Artificial."

Cada componente ML/NLP debe responder:

**¿Qué problema resuelve?**

**¿Qué dato utiliza?**

**¿Qué resultado produce?**

**¿Cómo se valida?**

**¿Qué aporta respecto a una solución no-ML?**

---

# 43. RESULTADO FINAL ESPERADO

Al terminar todo el proceso queremos llegar a algo conceptualmente equivalente a:

```text
FUENTES OFICIALES
        ↓
DATA INGESTION
        ↓
DATA QUALITY
        ↓
ENTITY RESOLUTION
        ↓
DATA INTEGRATION
        ↓
HISTORIAL TEMPORAL
        ↓
FEATURE ENGINEERING
        ↓
┌──────────────────────┐
│ MODELO A             │
│ ESTRUCTURADO         │
└──────────────────────┘
        │
        ├──────────────┐
        │              │
        ↓              ↓
   RESULTADOS       COMPARACIÓN
        ↑              ↑
        │              │
┌──────────────────────┐
│ MODELO B             │
│ ESTRUCTURADO + NLP   │
└──────────────────────┘
        ↓
VALIDACIÓN TEMPORAL
        ↓
XAI
        ↓
EVIDENCIA
        ↓
API
        ↓
PLATAFORMA WEB
        ↓
PRODUCCIÓN
        ↓
INTERNET
```

Pero recuerda:

**esta arquitectura es una referencia conceptual, NO una obligación.**

Si la investigación demuestra que otra arquitectura es mejor:

**cámbiala.**

---

# 44. CRITERIO SUPREMO

La prioridad de todo el proyecto será:

### 1. VERACIDAD DE LOS DATOS

### 2. VIABILIDAD CIENTÍFICA

### 3. CORRECTA DEFINICIÓN DEL PROBLEMA

### 4. VALIDEZ EXPERIMENTAL

### 5. REPRODUCIBILIDAD

### 6. CALIDAD DEL SOFTWARE

### 7. PRODUCCIÓN REAL

### 8. ESCALABILIDAD

No sacrifiques los primeros puntos por hacer una aplicación visualmente impresionante.

---

# 45. INSTRUCCIÓN FINAL

Quiero que actúes como si fueras el **responsable técnico principal de llevar esta tesis desde cero hasta producción**.

No quiero que solamente me enseñes qué podríamos hacer.

Quiero que investigues, compruebes, diseñes y tomes decisiones.

Cuando una decisión dependa de datos que todavía no tenemos:

**VE A BUSCARLOS.**

Cuando dependa de documentación oficial:

**CONSÚLTALA.**

Cuando dependa de un dataset:

**INSPECCIÓNALO.**

Cuando dependa de una hipótesis:

**FORMULA CÓMO PROBARLA.**

Cuando una idea sea inviable:

**DESCÁRTALA.**

Cuando una tecnología sea innecesaria:

**ELIMÍNALA.**

Cuando una fuente no sea suficiente:

**BUSCA OTRA.**

Cuando una integración no sea posible:

**DISEÑA UNA ALTERNATIVA.**

Cuando los resultados no sean buenos:

**NO LOS MAQUILLES.**

Cuando el modelo no funcione:

**REPÓRTALO Y ANALIZA POR QUÉ.**

Cuando el NLP no aporte:

**DEMUESTRA QUE NO APORTA Y DESCÁRTALO.**

Cuando los datos contradigan nuestra hipótesis inicial:

**LOS DATOS TIENEN PRIORIDAD.**

---

# OBJETIVO FINAL

El objetivo no es simplemente construir una aplicación.

El objetivo es producir una tesis en la que podamos demostrar:

> **qué problema existe, qué datos reales permiten estudiarlo, cómo se construyó el dataset, cómo se definió el evento objetivo, cómo se evitó el leakage, qué modelos fueron evaluados, qué resultados se obtuvieron, qué aporta la información documental, cómo se construyó el sistema y cómo este puede operar realmente en producción.**

Y finalmente tener:

**DATA REAL + INVESTIGACIÓN REPRODUCIBLE + MODELO VALIDADO + SOFTWARE COMPLETO + PLATAFORMA WEB + DEPLOYMENT REAL + DOCUMENTACIÓN + RESULTADOS DEFENDIBLES.**

No empieces programando.

**Primero demuestra que sabemos exactamente qué debemos construir y que los datos reales permiten construirlo.**

Después de cerrar ese diseño maestro, podremos pasar a la ejecución técnica completa.
