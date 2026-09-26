CONTEXTO DE TESIS GRUPAL – INGENIERÍA DE SISTEMAS – UNSA

Somos un grupo de 5 estudiantes de Ingeniería de Sistemas de la UNSA y estamos buscando desarrollar una tesis aplicada, viable y con impacto real, basada en datos públicos oficiales del Estado peruano.

PROBLEMA GENERAL IDENTIFICADO

Las obras públicas pueden presentar retrasos significativos, ampliaciones de plazo, adicionales de obra, problemas técnicos, problemas contractuales, bajo avance físico/financiero y finalmente paralización. El problema no es únicamente que existan obras paralizadas, sino que muchas señales del deterioro de una obra aparecen progresivamente durante su ejecución y están distribuidas en diferentes fuentes de información pública.

Actualmente la información está fragmentada entre diferentes sistemas y entidades. Un investigador o funcionario tendría que revisar manualmente información financiera, contractual, valorizaciones, avances, cuadernos de obra, asientos y documentos de control para comprender la evolución de una obra.

Nuestra hipótesis de trabajo es que, mediante integración de datos + análisis temporal + Machine Learning/NLP, podría ser posible detectar tempranamente patrones asociados con un retraso significativo antes de que el problema sea evidente o termine en paralización.

IMPORTANTE:
NO queremos hacer simplemente "un sistema que predice obras paralizadas".
Queremos investigar la DETECCIÓN TEMPRANA DEL DETERIORO/RIESGO DE RETRASO durante la ejecución de una obra.

ÁMBITO GEOGRÁFICO

Departamento de Arequipa, Perú.

Consideraremos sus 8 provincias:

- Arequipa
- Camaná
- Caravelí
- Castilla
- Caylloma
- Condesuyos
- Islay
- La Unión

No queremos limitarnos únicamente a la ciudad de Arequipa ni únicamente al Gobierno Regional. El interés es considerar obras ejecutadas por los diferentes niveles de gobierno cuando los datos permitan su integración:

- Gobierno Nacional
- Gobierno Regional
- Gobiernos Locales

FUENTES DE DATOS OFICIALES IDENTIFICADAS

1. MEF / Invierte.pe / Datos Abiertos
   Puede aportar información de inversiones, CUI, presupuesto, PIM, ejecución, fechas, ubicación, entidad, etc.

2. OECE / SEACE
   Se identificaron datasets públicos de:

- contratos
- valorizaciones de obras
- cuadernos de obra digitales
- asientos de cuadernos de obra digitales
- proveedores/consorcios y otros datos relacionados

Los datasets de valorizaciones, cuadernos y asientos están publicados en la Plataforma Nacional de Datos Abiertos y tienen recursos CSV/XLSX/diccionarios de datos.

3. INFOBRAS / Contraloría
   Puede aportar información relacionada con seguimiento de obras, avance físico/financiero y estado de ejecución.

4. CONTRALORÍA
   Publica informes y bases de obras paralizadas, incluyendo información por departamento y servicios de control. Existen reportes hasta marzo de 2026.

POSIBLE INTEGRACIÓN

La arquitectura conceptual de datos sería:

MEF
 ↓
CUI / identificación de inversión
 ↓
INFOBRAS
 ↓
OECE/SEACE
 ↓
Contrato
 ↓
Valorizaciones
 ↓
Cuaderno de obra
 ↓
Asientos
 ↓
Contraloría
 ↓
Evento real: retraso significativo / paralización / etc.

Esto todavía debe VALIDARSE EXPERIMENTALMENTE. No debemos asumir que todas las obras podrán enlazarse entre todas las fuentes.

SECTORES QUE DECIDIMOS EVALUAR

Reducimos inicialmente el universo a 4 sectores:

1. SANEAMIENTO
      Agua potable, alcantarillado, tratamiento de aguas residuales, etc.

2. TRANSPORTE / VIAL
      Carreteras, caminos, puentes y obras relacionadas.

3. EDUCACIÓN
      Infraestructura educativa/colegios.

4. SALUD
      Hospitales y establecimientos de salud.

Agricultura/riego queda como sector secundario que podría reincorporarse si el análisis de datos demuestra que tiene mejor cobertura.

Actualmente SANEAMIENTO es el candidato principal, pero NO está cerrado definitivamente.

La selección definitiva debe hacerse con datos reales, no por intuición.

CRITERIOS PARA ELEGIR EL SECTOR DEFINITIVO

Debemos comparar los 4 sectores utilizando:

- número total de obras;
- número de obras con CUI;
- número con información MEF;
- número con contrato/SEACE;
- número con valorizaciones;
- número con cuaderno de obra;
- número con asientos;
- número con información de avance;
- número con información de Contraloría;
- número de obras con historial temporal suficiente;
- número de obras con retrasos/paralizaciones;
- cantidad de casos normales vs casos problemáticos;
- posibilidad real de cruzar las fuentes;
- calidad y consistencia de los datos.

La comparación debería terminar en una tabla similar a:

Sector | Obras | CUI | Contratos | Valorizaciones | Cuadernos | Asientos | Casos problemáticos | Obras utilizables

Solo después de esa evaluación se debe cerrar el sector.

PROBLEMA ESPECÍFICO QUE QUEREMOS INVESTIGAR

Una formulación provisional sería:

"¿Es posible detectar tempranamente el riesgo de retraso significativo en la ejecución de obras públicas mediante el análisis temporal de indicadores de ejecución y registros documentales disponibles en fuentes públicas oficiales?"

La definición exacta de "retraso significativo" todavía debe establecerse y justificarse.

También falta definir:

- cuántos días o qué porcentaje constituye retraso significativo;
- horizonte de anticipación (30, 60, 90 días, etc.);
- momento exacto desde el cual se considera válida una predicción;
- qué evento será la variable objetivo/label.

PROPUESTA DE SOLUCIÓN

Desarrollar una plataforma de apoyo a la supervisión de obras públicas que:

1. Integre información de diferentes fuentes oficiales.
2. Construya una línea temporal de cada obra.
3. Calcule indicadores de evolución:
      - avance físico;
      - avance financiero;
      - desviación respecto al cronograma;
      - presupuesto;
      - valorizaciones;
      - ampliaciones;
      - adicionales;
      - frecuencia de incidencias;
      - etc.
4. Analice información documental de cuadernos/asientos cuando exista.
5. Utilice Machine Learning para detectar patrones asociados al deterioro/riesgo de retraso.
6. Genere alertas tempranas.
7. Explique por qué una obra fue considerada de riesgo.
8. Muestre las evidencias/documentos que sustentan la alerta.

NO queremos una "caja negra" que simplemente diga:
"Riesgo = 87%".

Queremos algo como:

"Riesgo elevado debido a:

- desviación creciente del avance físico respecto al programado;
- reducción/irregularidad de valorizaciones;
- ampliación reciente del plazo;
- incidencias técnicas recurrentes;
- determinados patrones encontrados en registros documentales."

Y permitir consultar la evidencia correspondiente.

PROPUESTA DE INVESTIGACIÓN MÁS INTERESANTE

Comparar dos escenarios:

MODELO A:
Solo datos estructurados:

- presupuesto
- avance
- cronograma
- valorizaciones
- ampliaciones
- adicionales
- ejecución financiera
- etc.

MODELO B:
Datos estructurados + información documental:

- cuadernos de obra
- asientos
- texto disponible en registros

La investigación podría determinar si incorporar información documental permite detectar el deterioro con mayor anticipación o mejorar el desempeño respecto al modelo estructurado.

Esto sería más interesante científicamente que simplemente construir una aplicación de predicción.

VALIDACIÓN

Queremos utilizar información histórica.

La idea es simular el paso del tiempo:

Ejemplo:
En enero de 2023, ¿qué habría detectado el sistema?
En febrero, ¿el riesgo aumentó?
En marzo, ¿habría generado una alerta?
Posteriormente, ¿la obra realmente presentó un retraso significativo?

Esto permitiría medir:

- precisión;
- recall;
- F1;
- PR-AUC/ROC-AUC cuando corresponda;
- falsos positivos;
- falsos negativos;
- anticipación promedio de la alerta;
- desempeño según horizonte temporal.

MUY IMPORTANTE: EVITAR DATA LEAKAGE

Si queremos detectar un problema en el momento T, el modelo solamente puede utilizar información disponible hasta T.

NO podemos utilizar información posterior al evento para predecirlo.

Por ejemplo:
Si una obra se paralizó en agosto, no podemos utilizar un informe de septiembre que ya dice que la obra fue paralizada para generar la predicción de julio.

RESTRICCIONES Y REALISMO

Somos 5 estudiantes universitarios.

Queremos una tesis:

- técnicamente ambiciosa pero realizable;
- basada principalmente en datos públicos;
- con costos bajos;
- sin depender de acceso privilegiado al Estado;
- sin inventar datos;
- sin datos simulados como fuente principal;
- sin limitarla únicamente a Arequipa ciudad;
- con posibilidad de reproducir la metodología.

No queremos:

- un proyecto excesivamente grande que pretenda solucionar toda la gestión de obras públicas del Perú;
- una IA genérica que simplemente "prediga";
- un sistema basado únicamente en un chatbot;
- depender de una API privada costosa;
- afirmar que algo funciona antes de comprobar la disponibilidad y calidad de los datos.

LO QUE YA TENEMOS IDENTIFICADO

- Problema general: retrasos/deterioro/paralización de obras públicas.
- Enfoque: detección temprana, no solamente predicción de paralización.
- Área geográfica: departamento de Arequipa.
- Cobertura: las 8 provincias.
- Posibles fuentes: MEF, OECE/SEACE, INFOBRAS y Contraloría.
- Posibles sectores: Saneamiento, Transporte, Educación y Salud.
- Candidato actual: Saneamiento.
- Idea de integración de fuentes.
- Idea de línea temporal por obra.
- Idea de ML con datos estructurados.
- Posible incorporación de NLP sobre registros documentales.
- Comparación modelo estructurado vs estructurado + documentos.
- Necesidad de explicabilidad.
- Necesidad de validación temporal y prevención de data leakage.

LO QUE TODAVÍA FALTA IDENTIFICAR

1. ¿Cuál de los 4 sectores realmente tiene mayor cantidad de datos utilizables?
2. ¿Cuántas obras de cada sector existen en las 8 provincias?
3. ¿Cuántas pueden cruzarse entre MEF, OECE, INFOBRAS y Contraloría?
4. ¿Qué periodo histórico ofrece mayor cobertura?
5. ¿Qué variables concretas están disponibles en cada fuente?
6. ¿Cuál será exactamente la variable objetivo?
7. ¿Qué significa "retraso significativo"?
8. ¿Cuál será el horizonte de predicción?
9. ¿Cuántos casos positivos/negativos tenemos?
10. ¿Qué algoritmo/modelos son apropiados después de conocer los datos?
11. ¿Realmente los textos de cuadernos/asientos tienen suficiente cobertura y calidad para NLP?
12. ¿Qué novedad científica concreta tendrá el trabajo frente a sistemas existentes de seguimiento/riesgo de obras?
13. ¿Cuál será el alcance exacto del MVP?
14. ¿Qué métricas utilizará la evaluación?
15. ¿Qué metodología de investigación y validación utilizaremos?

CONSIDERACIONES PARA EL EQUIPO DE INVESTIGACIÓN

No den por hecho que Saneamiento es definitivamente el mejor sector.

Primero analicen la disponibilidad REAL de datos oficiales para Arequipa y sus 8 provincias.

Tampoco den por hecho que habrá "miles de obras útiles" ni que todas las fuentes se pueden cruzar automáticamente.

Queremos que la IA nos ayude a comprobar:
DATOS → PROBLEMA → VARIABLE OBJETIVO → MODELO → VALIDACIÓN → SISTEMA.

La prioridad actual NO es programar.
La prioridad es validar que existe suficiente información para que la tesis sea científicamente viable.

OBJETIVO FINAL

Construir y evaluar un sistema basado en datos que permita identificar tempranamente señales de riesgo de retraso significativo en obras públicas de un sector específico del departamento de Arequipa, utilizando información histórica oficial y, si los datos lo permiten, combinando variables estructuradas con información documental.
