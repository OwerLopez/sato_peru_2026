// Construye Guia_Exposicion_SATO.docx: guion de exposicion para cinco integrantes.
//   node docs/exposicion/construir_guia.js   (requiere el paquete docx; NODE_PATH o DOCX_MODULE)
// Todas las cifras provienen del articulo (docs/articulo) y de las mediciones del prototipo
// (docs/articulo/evaluacion/metricas_prototipo.json); no se escriben valores nuevos.
const fs = require('fs')
const path = require('path')
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, ShadingType, AlignmentType, HeadingLevel,
  Header, Footer, PageNumber, BorderStyle, LevelFormat, TableLayoutType, VerticalAlign, PageBreak, ExternalHyperlink,
} = require(process.env.DOCX_MODULE || 'docx')

const URL_PUBLICA = process.env.SATO_URL_PUBLICA || 'https://owerlopez.github.io/sato_peru_2026/'
const REPO = 'https://github.com/OwerLopez/sato_peru_2026'
const AZUL = '0A1C30'
const AZUL_T = '1F72B4'
const GRIS = '3E4A5B'
const FUENTE = 'Calibri'
const ANCHO = 12240 - 2 * 1300

function runs(texto, base = {}) {
  texto = texto.replace(/`/g, "")
  const out = []
  const rx = /(\*\*[^*]+\*\*|\*[^*\s][^*]*\*|https?:\/\/[^\s]+?(?=[.,;:]?(\s|$)))/g
  let last = 0
  let m
  while ((m = rx.exec(texto))) {
    if (m.index > last) out.push(new TextRun({ text: texto.slice(last, m.index), font: FUENTE, ...base }))
    const s = m[0]
    if (s.startsWith('**')) out.push(new TextRun({ text: s.slice(2, -2), bold: true, font: FUENTE, ...base }))
    else if (s.startsWith('*')) out.push(new TextRun({ text: s.slice(1, -1), italics: true, font: FUENTE, ...base }))
    else out.push(new ExternalHyperlink({ link: s, children: [new TextRun({ text: s, font: FUENTE, ...base, color: '0563C1', underline: {} })] }))
    last = m.index + s.length
  }
  if (last < texto.length) out.push(new TextRun({ text: texto.slice(last), font: FUENTE, ...base }))
  return out
}
const P = (t, o = {}) => new Paragraph({ alignment: o.align || AlignmentType.JUSTIFIED, spacing: { after: o.after ?? 110, line: 276 }, keepNext: o.keepNext, children: runs(t, { size: o.size || 22, color: o.color, italics: o.italics }) })
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: false, spacing: { before: 320, after: 140 }, keepNext: true, border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: AZUL_T, space: 4 } }, children: [new TextRun({ text: t, font: FUENTE, bold: true, size: 32, color: AZUL })] })
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 220, after: 90 }, keepNext: true, children: [new TextRun({ text: t, font: FUENTE, bold: true, size: 26, color: AZUL_T })] })
const H3 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_3, spacing: { before: 160, after: 60 }, keepNext: true, children: [new TextRun({ text: t, font: FUENTE, bold: true, size: 23, color: AZUL })] })
const V = (items) => items.map((t) => new Paragraph({ numbering: { reference: 'vinetas', level: 0 }, alignment: AlignmentType.LEFT, spacing: { after: 50, line: 264 }, children: runs(t, { size: 22 }) }))
const N = (items, ref) => items.map((t) => new Paragraph({ numbering: { reference: ref, level: 0 }, alignment: AlignmentType.LEFT, spacing: { after: 60, line: 264 }, children: runs(t, { size: 22 }) }))
const salto = () => new Paragraph({ children: [new PageBreak()] })

function celda(t, o = {}) {
  return new TableCell({
    width: { size: o.w, type: WidthType.DXA },
    shading: o.fill ? { type: ShadingType.CLEAR, fill: o.fill, color: 'auto' } : undefined,
    margins: { top: 70, bottom: 70, left: 110, right: 110 },
    verticalAlign: VerticalAlign.CENTER,
    children: String(t).split('\n').map((l) => new Paragraph({ alignment: o.align || AlignmentType.LEFT, spacing: { after: 30, line: 252 }, children: runs(l, { size: o.size || 20, bold: o.bold, color: o.color }) })),
  })
}
function tabla(cab, filas, anchos, o = {}) {
  const tot = anchos.reduce((a, b) => a + b, 0)
  const ws = anchos.map((x) => Math.floor((x / tot) * ANCHO))
  ws[ws.length - 1] += ANCHO - ws.reduce((a, b) => a + b, 0)
  const borde = { style: BorderStyle.SINGLE, size: 4, color: 'C9D3DF' }
  return new Table({
    width: { size: ANCHO, type: WidthType.DXA }, columnWidths: ws, layout: TableLayoutType.FIXED,
    borders: { top: borde, bottom: borde, left: borde, right: borde, insideHorizontal: borde, insideVertical: borde },
    rows: [
      new TableRow({ tableHeader: true, cantSplit: true, children: cab.map((c, i) => celda(c, { w: ws[i], fill: AZUL, bold: true, color: 'FFFFFF' })) }),
      ...filas.map((f, r) => new TableRow({ cantSplit: true, children: f.map((c, i) => celda(c, { w: ws[i], fill: r % 2 ? 'F4F6F9' : undefined, bold: o.primeraNegrita && i === 0 })) })),
    ],
  })
}
function caja(titulo, lineas, color = 'EFF6FC', borde = AZUL_T) {
  const b = { style: BorderStyle.SINGLE, size: 4, color: borde }
  const hijos = [new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: titulo, font: FUENTE, bold: true, size: 21, color: borde === AZUL_T ? AZUL : borde })] })]
  for (const l of lineas) hijos.push(new Paragraph({ alignment: AlignmentType.LEFT, spacing: { after: 60, line: 264 }, children: runs(l, { size: 21 }) }))
  return new Table({
    width: { size: ANCHO, type: WidthType.DXA }, columnWidths: [ANCHO], layout: TableLayoutType.FIXED,
    borders: { top: b, bottom: b, right: b, left: { style: BorderStyle.SINGLE, size: 24, color: borde }, insideHorizontal: b, insideVertical: b },
    rows: [new TableRow({ cantSplit: true, children: [new TableCell({ width: { size: ANCHO, type: WidthType.DXA }, shading: { type: ShadingType.CLEAR, fill: color, color: 'auto' }, margins: { top: 110, bottom: 110, left: 180, right: 160 }, children: hijos })] })],
  })
}
const guion = (lineas) => caja('Guion sugerido (dígalo con sus palabras)', lineas.map((l) => `«${l}»`), 'F7F7F7', '8A97A8')
const esp = (n = 120) => new Paragraph({ spacing: { after: n }, children: [] })

// ------------------------------------------------------------------ contenido
const hijos = []
hijos.push(new Paragraph({ alignment: AlignmentType.LEFT, spacing: { before: 600, after: 80 }, children: [new TextRun({ text: 'GUÍA DE EXPOSICIÓN', font: FUENTE, bold: true, size: 24, color: AZUL_T })] }))
hijos.push(new Paragraph({ alignment: AlignmentType.LEFT, spacing: { after: 120 }, children: [new TextRun({ text: 'SATO: Sistema de Alerta Temprana de Obras Públicas', font: FUENTE, bold: true, size: 44, color: AZUL })] }))
hijos.push(P('Alerta temprana del atraso en obras públicas del Perú mediante aprendizaje automático explicable y el cuaderno de obra digital', { size: 26, color: GRIS, align: AlignmentType.LEFT }))
hijos.push(esp(200))
hijos.push(tabla(['Dato', 'Valor'], [
  ['Sistema en línea', URL_PUBLICA + ' (copia pública permanente, de solo lectura, con los resultados reales del modelo)'],
  ['Código fuente', REPO],
  ['Integrantes', '5 (Integrante 1 a Integrante 5; reemplazar por los nombres del equipo)'],
  ['Duración sugerida', '20 minutos de exposición + preguntas (incluye una versión corta de 10 minutos)'],
  ['Curso', 'Gestión de Sistemas y Tecnologías de Información · Universidad Nacional de San Agustín de Arequipa'],
], [26, 74], { primeraNegrita: true }))
hijos.push(esp(160))
hijos.push(caja('El mensaje que el docente debe recordar', [
  'Construimos un sistema que **anticipa, con 60 días de ventaja, qué obras públicas del Perú tienen más riesgo de atrasarse**, usando solo datos abiertos del Estado y el texto del cuaderno de obra digital. Cada alerta se explica en lenguaje claro y se respalda con los documentos oficiales que la originan.',
  'No reemplaza al supervisor: le dice **dónde mirar primero**. Revisando el 10 % de obras con mayor riesgo se encuentra cerca de un tercio de los atrasos formales, con una precisión 3,2 veces mayor que revisar al azar.',
]))

hijos.push(H1('1. Cómo usar esta guía'))
hijos.push(...V([
  'Cada integrante tiene una sección con: **objetivo**, **guion en palabras simples**, **puntos técnicos** (para demostrar dominio como ingenieros de sistemas), **cifras exactas** que debe mencionar y la **transición** al siguiente integrante.',
  'Las cifras de esta guía son las del artículo y las medidas en el prototipo. **No redondeen hacia arriba ni agreguen datos**: si no recuerdan una cifra, digan la idea sin el número.',
  'Hablen primero en simple y luego añadan el detalle técnico. Regla práctica: **una idea, un dato, un ejemplo**.',
  'Si el tiempo se reduce, usen la versión de 10 minutos (sección 3) y lleven la demostración como parte central.',
]))

hijos.push(H1('2. Distribución de la exposición (20 minutos)'))
hijos.push(tabla(['Integrante', 'Tema', 'Tiempo', 'Apoyo visual'], [
  ['Integrante 1', 'El problema, la oportunidad y el objetivo', '3 min', 'Panorama del sistema en línea'],
  ['Integrante 2', 'Los datos: de dónde vienen y cómo se integraron', '3,5 min', 'Página «Datos y fuentes»'],
  ['Integrante 3', 'Inteligencia artificial: el modelo, el texto y los resultados', '4,5 min', 'Página «Validación del modelo»'],
  ['Integrante 4', 'Ingeniería del sistema: arquitectura, calidad, seguridad y operación', '4 min', 'Figura de arquitectura y página «Estado y monitoreo»'],
  ['Integrante 5', 'Demostración en vivo, conclusiones, limitaciones y futuro', '5 min', 'Sistema en línea y el informe PDF'],
], [16, 44, 12, 28], { primeraNegrita: true }))
hijos.push(esp())
hijos.push(P('**Orden lógico:** problema → datos → inteligencia artificial → ingeniería del sistema → demostración y cierre. Cada parte responde a una pregunta del docente: ¿por qué?, ¿con qué?, ¿cómo predice?, ¿cómo está construido? y ¿funciona de verdad?'))

hijos.push(H1('3. Versión corta (10 minutos)'))
hijos.push(tabla(['Integrante', 'Qué decir en 2 minutos'], [
  ['Integrante 1', 'Problema (2 262 obras paralizadas en junio de 2026; la supervisión se entera tarde) y objetivo (anticipar el atraso a 60 días con datos abiertos).'],
  ['Integrante 2', 'Integramos OECE, MEF y Contraloría: 2,73 millones de asientos del cuaderno digital y 139 159 obras de INFOBRAS; enlazamos fuentes sin identificador común con 99,1 % de precisión.'],
  ['Integrante 3', 'LightGBM con y sin el texto del cuaderno; el texto mejora el ROC-AUC de 0,742 a 0,774 de forma significativa; en la práctica el nivel ALTO acierta 3,2 veces más que el azar.'],
  ['Integrante 4', 'Arquitectura en contenedores, 41 servicios de API, 32 chequeos de calidad, 13 de 13 pruebas de seguridad, 192 pruebas automatizadas aprobadas y funcionamiento autónomo.'],
  ['Integrante 5', 'Demostración: panorama → ficha de una obra → factores y evidencia → informe PDF; cierre con limitaciones y futuro.'],
], [18, 82], { primeraNegrita: true }))

// ---------------------------------------------------------------- integrante 1
hijos.push(salto())
hijos.push(H1('4. Integrante 1: el problema, la oportunidad y el objetivo (3 min)'))
hijos.push(H3('Objetivo de su parte'))
hijos.push(P('Que el docente entienda por qué el problema importa, por qué nadie lo resolvía y qué se propuso el equipo.'))
hijos.push(guion([
  'En junio de 2026 la Contraloría reportó 2 262 obras paralizadas en el Perú; el 68,2 % está a cargo de gobiernos locales. Detrás de cada una hay un colegio, una posta o una pista que la población sigue esperando.',
  'El problema de fondo es que la supervisión es reactiva: una obra se declara paralizada cuando el daño ya ocurrió. La ley la califica así cuando acumula seis meses sin avance.',
  'Pero la información para anticiparlo ya existe y es pública. Desde junio de 2024, el cuaderno de obra digital registra cada día lo que pasa en la obra: penalidades, ausencias del residente, demoras. Nadie lo estaba usando para predecir.',
  'Nuestro objetivo fue construir un sistema que estime, con 60 días de anticipación, qué obras tienen más riesgo de registrar un atraso formal, usando solo datos abiertos, y medir si el texto del cuaderno mejora esa predicción.',
]))
hijos.push(H3('Puntos técnicos para demostrar dominio'))
hijos.push(...V([
  '**Evento a predecir definido por la norma, no inventado:** el primer asiento que aplica la regla del 80 % (valorización acumulada ejecutada menor al 80 % de la programada), según el RLCE art. 203 y el RLGCP art. 207 (reglamentos de las leyes de contrataciones del Estado, anterior y vigente). Es un hecho legal, fechado y verificable por cualquiera.',
  '**Relevancia del evento:** las obras que lo registran aparecen luego como paralizadas con una frecuencia de 3,3 % frente a 1,0 % de las demás, y en 45 de 53 casos el atraso precede a la paralización.',
  '**Magnitud:** de las 139 159 obras de INFOBRAS, el 51,2 % de las que tienen resultado conocido terminó con un retraso mayor al 30 % del plazo.',
  '**Pregunta de investigación:** ¿el texto del cuaderno mejora la anticipación respecto de los datos estructurados? **Hipótesis H1:** sí, y la mejora es estadísticamente distinta de cero.',
  '**Brecha:** los estudios previos usan encuestas a expertos o pocos proyectos y validan con particiones aleatorias (mezclando pasado y futuro); ninguno usa registros diarios de ejecución de todo un país con validación temporal. Los sistemas públicos similares de otros países (Brasil, Ucrania, Colombia) vigilan licitaciones y contratos, no la ejecución de la obra: ver la sección 9.',
]))
hijos.push(caja('Frase para impresionar', ['«No inventamos qué es un atraso: usamos la misma regla que aplica la ley, así cualquier auditor puede reproducir nuestra etiqueta con los archivos públicos».']))
hijos.push(P('**Transición:** «Para lograrlo, primero había que reunir datos que el Estado publica en portales distintos y que no conversan entre sí. Eso lo explica [Integrante 2]».', { italics: true }))

// ---------------------------------------------------------------- integrante 2
hijos.push(salto())
hijos.push(H1('5. Integrante 2: los datos y su integración (3,5 min)'))
hijos.push(H3('Objetivo de su parte'))
hijos.push(P('Mostrar que el mayor reto de ingeniería fue convertir datos públicos dispersos en una base confiable, sin fuga de información del futuro.'))
hijos.push(guion([
  'Trabajamos con datos abiertos oficiales de tres instituciones: el OECE, que publica el cuaderno de obra digital y los contratos; el MEF, con el banco de inversiones y la ejecución presupuestal mes a mes; y la Contraloría, con INFOBRAS y los reportes de obras paralizadas.',
  'Son 2,73 millones de asientos del cuaderno, 139 159 obras de INFOBRAS y archivos de gasto de hasta 680 MB comprimidos. No usamos ningún dato privado ni inventado.',
  'El reto: el cuaderno no trae el código único de inversión, así que no se puede unir directamente con el MEF. Lo resolvimos con técnicas de resolución de entidades (reconocer que dos registros de fuentes distintas son la misma obra) y logramos 99,1 % de precisión en 10 075 pares de prueba.',
  'Y cuidamos algo clave: en cada mes solo usamos información disponible hasta esa fecha. Si el modelo viera el futuro, sus resultados serían falsos en la práctica.',
]))
hijos.push(H3('Puntos técnicos'))
hijos.push(tabla(['Fuente', 'Institución', 'Uso en el sistema'], [
  ['Cuaderno de obra digital (asientos y valorizaciones)', 'OECE', 'Evento objetivo, variables del cuaderno y texto (2 732 593 asientos, jun. 2024 a ago. 2026)'],
  ['Contratos de obra (SEACE/CONOSCE)', 'OECE', 'Monto y plazo originales'],
  ['Banco de Inversiones (Invierte.pe) y Formato 12-B', 'MEF', 'Código único de inversión, sector, monto viable, problemas registrados'],
  ['Ejecución presupuestal SIAF', 'MEF', 'Gasto devengado mensual por inversión'],
  ['INFOBRAS', 'Contraloría', 'Cartera nacional de 139 159 obras de todas las modalidades'],
  ['Obras paralizadas (13 cortes trimestrales)', 'Contraloría', 'Diagnóstico y validez externa del evento'],
], [38, 16, 46]))
hijos.push(esp())
hijos.push(...V([
  '**Descarga reproducible:** cada archivo se registra con su URL, tamaño y huella **SHA-256** (huella digital única del archivo: si cambia un solo byte, cambia la huella); el corte de datos quedó congelado al 25 de septiembre de 2026. Detectamos que un archivo oficial cambió de 10 988 a 9 666 filas el mismo día: por eso la huella es indispensable.',
  '**Procesamiento:** Python 3.12, pandas y **DuckDB** (base de datos analítica que procesa archivos grandes directamente, sin instalar un servidor) para procesar archivos de hasta 10 GB sin un servidor de datos.',
  '**Resolución de entidades:** expresiones regulares + similitud **TF-IDF de n-gramas de caracteres** (compara nombres por fragmentos de letras para reconocer la misma obra escrita de forma distinta), bloqueada por departamento y calibrada con 10 075 pares con código explícito: **99,1 % de precisión**; enlazó el 90,2 % de los cuadernos de Arequipa.',
  '**Panel obra-mes «as-of»** (cada fila es una obra en un mes, calculada solo con lo que se sabía hasta ese mes)**:** 12 369 obras y 58 509 observaciones; en cada fin de mes solo se usan registros con fecha anterior, el SIAF hasta el mes previo y el historial de los actores calculado a esa fecha. Hay **pruebas automáticas de no fuga** que recalculan las variables sobre los datos reales.',
  '**Calidad de datos:** una auditoría automática de 32 chequeos (11 críticos, 11 de aviso y 10 informativos). En la base vigente: 17 sin hallazgos, 5 hallazgos propios de las fuentes y **0 fallas críticas**. Los hallazgos se muestran en la interfaz tal como están, sin maquillarlos.',
]))
hijos.push(caja('Frase para impresionar', ['«El 80 % del trabajo de un sistema de IA serio está en los datos: integramos cinco fuentes oficiales que no comparten identificadores y lo medimos, no lo supusimos: 99,1 % de precisión de enlace».']))
hijos.push(P('**Transición:** «Con los datos limpios y sin fuga, entrenamos los modelos de inteligencia artificial. [Integrante 3] explica cómo predicen y qué tan bien».', { italics: true }))

// ---------------------------------------------------------------- integrante 3
hijos.push(salto())
hijos.push(H1('6. Integrante 3: inteligencia artificial y resultados (4,5 min)'))
hijos.push(H3('Objetivo de su parte'))
hijos.push(P('Explicar el modelo de aprendizaje automático, el uso del lenguaje natural y demostrar con evidencia estadística que funciona, sin exagerar.'))
hijos.push(guion([
  'Comparamos dos modelos. El modelo A usa solo datos estructurados: cuántos asientos hay de cada tipo, el ritmo de registro, el gasto, el contrato. El modelo B agrega lo que dicen los asientos: el texto escrito por el residente y el supervisor.',
  'Para leer el texto usamos procesamiento de lenguaje natural: un diccionario de 16 categorías de causas de atraso, TF-IDF (técnica que pondera cuánto importa cada palabra en un texto) y un modelo de lenguaje multilingüe, Sentence-BERT, que convierte cada texto en un vector numérico.',
  'Lo evaluamos como se usaría en la vida real: entrenamos con el pasado y probamos en meses futuros que el modelo nunca vio. El texto mejoró el ROC-AUC (medida de 0,5 a 1 de qué tan bien ordena las obras por riesgo; 0,5 es azar) de 0,742 a 0,774, y esa mejora es estadísticamente significativa a nivel nacional.',
  'En la práctica: si un supervisor revisa solo el 10 % de obras que marcamos en riesgo alto, encuentra el 32 % de los atrasos, con una precisión de 17,6 % frente a 5,6 % si eligiera al azar. Es decir, 3,2 veces mejor.',
  'Y cada alerta se explica: con TreeSHAP mostramos qué datos de la obra subieron o bajaron el riesgo, en lenguaje claro y con el asiento oficial que lo respalda.',
]))
hijos.push(H3('Puntos técnicos'))
hijos.push(...V([
  '**Algoritmo:** **LightGBM** (algoritmo que combina cientos de árboles de decisión pequeños, cada uno corrigiendo los errores del anterior; técnica llamada *gradient boosting*), elegido por su desempeño con datos tabulares y valores faltantes. Se comparó con regresión logística, bosque aleatorio y XGBoost: con las mismas variables obtienen resultados similares, lo que prueba que la ganancia viene de la **información añadida** (el texto) y no del algoritmo.',
  '**Variables:** 84 estructuradas en el modelo A; el modelo B añade léxico de 16 categorías, LSA (análisis semántico latente: resume miles de palabras en pocos temas), embeddings (vectores numéricos que representan el significado de un texto) **Sentence-BERT** (paraphrase-multilingual-MiniLM-L12-v2), puntuaciones supervisadas de texto y extracción de avances reportados.',
  '**Validación temporal ciega:** entrenamiento de junio de 2024 a mayo de 2025, validación de agosto a octubre de 2025 y prueba de diciembre de 2025 a junio de 2026, con **purga de 60 días** (un espacio vacío entre bloques para que ningún evento se filtre de un periodo a otro) entre bloques. Además, **rolling-origin** (repetir la evaluación desde varios puntos de partida en el tiempo) con 4 orígenes, **5 semillas** y **bootstrap** (remuestrear los datos muchas veces para calcular intervalos de confianza) de 1 000 remuestreos por obra.',
  '**Métricas:** con eventos raros (prevalencia 5,0 %) la exactitud engaña; por eso usamos **PR-AUC** (mide qué tan bien encuentra los casos raros; es la métrica principal) y **ROC-AUC**.',
  '**Calibración** (que la probabilidad estimada coincida con lo que realmente ocurre)**:** las probabilidades se pueden leer literalmente. En el grupo de mayor riesgo el modelo estimó 20,0 % y ocurrió 17,7 %. Por nivel: ALTO 17,6 %, MEDIO 8,5 %, BAJO 3,1 %.',
  '**Explicabilidad:** **TreeSHAP** (método basado en teoría de juegos que reparte la predicción entre los datos de la obra para explicar cuánto aportó cada uno). El contenido de los asientos aporta el 46,0 % de la importancia del modelo B.',
  '**Segundo modelo (cartera INFOBRAS):** estima el riesgo de terminar con retraso mayor al 30 % del plazo para 139 159 obras de todas las modalidades: ROC-AUC 0,733 al inicio y 0,753 con el seguimiento mensual del gasto; en el nivel ALTO se atrasó el 91,6 % frente a 44,4 % en el nivel BAJO.',
]))
hijos.push(tabla(['Resultado (prueba temporal nacional, 16 756 observaciones)', 'Modelo A', 'Modelo B'], [
  ['ROC-AUC', '0,742', '0,774'],
  ['PR-AUC (prevalencia 5,0 %)', '0,139', '0,158'],
  ['Diferencia B − A en ROC-AUC (IC 95 %)', '', '+0,032 [0,019; 0,045]'],
  ['Diferencia B − A en PR-AUC (IC 95 %; p)', '', '+0,018 [0,005; 0,032]; p = 0,006'],
], [58, 18, 24]))
hijos.push(esp())
hijos.push(tabla(['Uso práctico (simulación mes a mes)', 'Resultado'], [
  ['Obras marcadas en nivel ALTO', '10,2 % de las obras'],
  ['Precisión del nivel ALTO', '17,6 % frente a 5,6 % al azar (3,2 veces)'],
  ['Atrasos formales capturados', '32,1 %'],
  ['Arequipa: obras con evento alertadas antes', '36 de 42, con mediana de 40,5 días de anticipación'],
], [55, 45]))
hijos.push(caja('Frase para impresionar', ['«No reportamos 95 % de exactitud porque con un evento de 5 % un modelo que nunca alerta tendría 95 %. Reportamos métricas honestas, con intervalos de confianza y validación en el futuro, y aun así el sistema triplica la eficacia de una revisión al azar».']))
hijos.push(P('**Transición:** «Un buen modelo no sirve si no está en un sistema confiable, seguro y que funcione solo. De eso habla [Integrante 4]».', { italics: true }))

// ---------------------------------------------------------------- integrante 4
hijos.push(salto())
hijos.push(H1('7. Integrante 4: ingeniería del sistema (4 min)'))
hijos.push(H3('Objetivo de su parte'))
hijos.push(P('Demostrar que SATO no es un notebook de ciencia de datos, sino un sistema de software completo, probado y preparado para producción.'))
hijos.push(guion([
  'SATO es un sistema web completo. Tiene un pipeline que descarga y procesa los datos, una base de datos PostgreSQL, una API REST (servicio web que entrega los datos a la interfaz en formato JSON) hecha con FastAPI y una interfaz web en React con TypeScript. Todo corre en contenedores Docker (paquetes que incluyen el programa y todo lo que necesita, para que funcione igual en cualquier equipo).',
  'Lo diseñamos como un sistema de producción: antes de publicar datos nuevos, una compuerta de integridad ejecuta 32 chequeos y rechaza la carga si algo crítico falla. Durante una recarga completa de 26,8 minutos, el sistema siguió respondiendo: 417 de 417 consultas sin error.',
  'Funciona solo: cada mes se sincroniza con las fuentes, reintenta si falla, avisa por correo y vigila si los datos nuevos se alejan de los de entrenamiento. Hoy detecta 8 variables con cambio grande y recomienda reentrenar: el sistema lo dice en lugar de ocultarlo.',
  'Y lo probamos: 192 pruebas automatizadas aprobadas, 13 de 13 pruebas de seguridad según OWASP y 100 de 100 en accesibilidad con Lighthouse.',
]))
hijos.push(H3('Tecnologías utilizadas'))
hijos.push(tabla(['Capa', 'Tecnologías', 'Por qué'], [
  ['Datos', 'Python 3.12, pandas, DuckDB, Parquet', 'Procesar archivos de gigabytes sin servidor de datos'],
  ['IA y ML', 'LightGBM, scikit-learn, XGBoost, Sentence-BERT, TF-IDF, LSA, TreeSHAP', 'Modelo tabular robusto, texto en español sin ajuste fino y explicaciones exactas'],
  ['Base de datos', 'PostgreSQL 16 con búsqueda de texto completo en español y vistas materializadas', 'Consultas rápidas sobre 2,4 millones de asientos'],
  ['Backend', 'FastAPI, SQLAlchemy Core, JWT, ReportLab (PDF)', '41 servicios REST documentados, seguros y con informe PDF'],
  ['Frontend', 'React 19, TypeScript, Vite, Tailwind CSS, Radix UI, Recharts, Leaflet, TanStack Query', 'Interfaz accesible, rápida y adaptable a teléfonos (15 pantallas)'],
  ['Infraestructura', 'Docker Compose, nginx, Caddy (HTTPS), túnel de Cloudflare, GitHub Actions', 'Despliegue reproducible e integración continua'],
  ['Calidad', 'pytest, Playwright, Vitest, k6, Lighthouse, ruff, oxlint, pip-audit, npm audit', 'Pruebas automáticas, carga, accesibilidad y dependencias'],
], [16, 46, 38]))
hijos.push(H3('Puntos técnicos'))
hijos.push(...V([
  '**Arquitectura por capas:** fuentes oficiales → pipeline (ingesta, normalización, integración, variables, modelos) → compuerta de integridad → PostgreSQL → API → nginx → interfaz. Un proceso programado (worker) cierra el ciclo.',
  '**Recarga sin cortes:** se reemplazan filas dentro de una transacción en vez de vaciar tablas, y las vistas materializadas (resultados de consultas guardados para responder más rápido) se refrescan de forma concurrente. Un error no deja datos a medias (reversión transaccional).',
  '**Operación autónoma:** candado de base de datos para impedir dos sincronizaciones a la vez, reintentos con espera exponencial, recuperación de ejecuciones interrumpidas, latido del servicio y avisos por correo.',
  '**Monitoreo del modelo (MLOps):** deriva de cada variable con **PSI** (índice de estabilidad poblacional: mide cuánto cambió cada variable respecto de los datos de entrenamiento) y detección de anomalías en la proporción de obras en riesgo alto con **puntuación z robusta** (mide qué tan lejos de lo normal está un valor usando la mediana, que no se deja arrastrar por casos extremos; umbral 3,5).',
  '**Seguridad en profundidad:** límites de tasa por IP en nginx, máximo de intentos de ingreso por cuenta (5) y por IP (20) en 15 minutos con tiempo de respuesta constante, JWT (credencial digital firmada que identifica al usuario en cada solicitud) con emisor y vigencia, rol leído de la base, cabeceras de seguridad (CSP, X-Frame-Options), errores sin trazas internas y tiempos máximos por consulta. **13 de 13 casos OWASP** (estándar internacional de los riesgos de seguridad web más importantes) aprobados.',
  '**Rendimiento:** con 20 usuarios concurrentes, p95 de 167,8 ms (el 95 % de las respuestas tardó menos de 167,8 milisegundos) y 266,4 solicitudes por segundo sin errores (medido con k6, herramienta de pruebas de carga).',
  '**Pruebas:** 192 pruebas del backend (unitarias, API, contratos, base de datos, seguridad, concurrencia y 36 de extremo a extremo en navegador, incluidas pantallas de teléfono de 375 px) y 12 de la interfaz, **todas aprobadas**.',
  '**Diseño accesible:** sistema de diseño institucional (tipografías Lexend y Source Sans 3, contraste AAA, colores de riesgo con ícono de forma distinta, paleta validada para daltonismo). Lighthouse: accesibilidad 100 en las páginas evaluadas; rendimiento 94, 99 y 100.',
]))
hijos.push(caja('Frase para impresionar', ['«El sistema se vigila a sí mismo: si los datos cambian y el modelo empieza a envejecer, lo detecta y lo muestra públicamente. Eso es MLOps (prácticas para operar y vigilar modelos de aprendizaje automático en producción) aplicado, no solo un modelo entrenado una vez».']))
hijos.push(P('**Transición:** «Ahora les mostramos que todo esto funciona en vivo. [Integrante 5] hace la demostración».', { italics: true }))

// ---------------------------------------------------------------- integrante 5
hijos.push(salto())
hijos.push(H1('8. Integrante 5: demostración en vivo y cierre (5 min)'))
hijos.push(H3('Objetivo de su parte'))
hijos.push(P('Mostrar el sistema funcionando con datos reales y cerrar con conclusiones, limitaciones honestas y visión de futuro.'))
hijos.push(H3('Recorrido de la demostración (3 minutos)'))
hijos.push(P(`Abrir ${URL_PUBLICA} antes de empezar la exposición. Es una copia de solo lectura: evite escribir en el buscador de la lista, porque solo están incluidas las consultas del recorrido.`))
hijos.push(...N([
  '**Panorama:** «Hoy el sistema monitorea 4 698 obras en ejecución. 190 obras del cuaderno digital están en riesgo alto de atraso formal en los próximos 60 días». Mostrar el mapa en grises con los puntos de riesgo y la línea de tendencia.',
  '**Alertas del cuaderno:** mostrar el resumen por nivel (que también filtra) y abrir la primera obra.',
  '**Ficha de la obra:** leer el nivel, la probabilidad, cuántas veces supera el promedio y la confiabilidad del nivel: «en la validación, 18 de cada 100 obras en nivel alto registraron el atraso».',
  '**Factores y evidencia:** abrir la pestaña de factores; mostrar un factor en lenguaje claro y pulsar «Ver evidencia» para abrir el asiento oficial del cuaderno que lo respalda.',
  '**Informe técnico PDF:** pulsar «Informe técnico PDF» y mostrar la portada, la escala de riesgo, los factores y la evidencia.',
  '**Validación del modelo:** mostrar que las probabilidades coinciden con lo que ocurrió (barras y línea casi juntas).',
  '**Estado y monitoreo:** mostrar que el sistema reporta su propia salud y la deriva de las variables.',
], 'demo'))
hijos.push(H3('Cierre (2 minutos)'))
hijos.push(guion([
  'Conclusión: sí se puede anticipar el atraso de obras públicas con datos abiertos. El texto del cuaderno de obra digital mejora la predicción de forma significativa a escala nacional, aunque la mejora es moderada.',
  'El valor práctico es priorizar: con capacidad limitada de supervisión, revisar primero las obras de mayor riesgo encuentra tres veces más atrasos que revisar al azar.',
  'Somos honestos con los límites: es una estimación para priorizar, no una acusación ni una decisión automática.',
]))
hijos.push(H3('Limitaciones (decirlas da credibilidad)'))
hijos.push(...V([
  'El cuaderno de obra digital solo existe desde junio de 2024: el periodo de prueba es corto y no cubre obras sin cuaderno (para ellas está el modelo de cartera).',
  'La señal es moderada: más de cuatro de cada cinco obras en nivel alto no registrarán el evento en 60 días (precisión de 17,6 %). Por eso se presenta como priorización.',
  'La etiqueta depende de que el supervisor anote el hecho; el subregistro reduce la precisión medida.',
  'En Arequipa la mejora del texto no fue significativa, por el tamaño de la muestra (42 obras con evento).',
  'No se evaluó todavía con supervisores reales (usabilidad y utilidad percibida).',
  'La copia pública en GitHub Pages es de solo lectura: muestra los resultados reales del corte del 31 de agosto de 2026 para las pantallas, departamentos y fichas exportadas, pero no tiene buscador libre, ingreso de analistas ni suscripciones; el sistema completo requiere un servidor (la configuración con HTTPS ya está lista).',
]))
hijos.push(H3('Visión a futuro'))
hijos.push(...V([
  'Validar con supervisores y órganos de control, y medir en campo si la priorización reduce el tiempo de detección.',
  'Ajustar un modelo de lenguaje en español al dominio de obras públicas con asientos etiquetados.',
  'Reentrenar con más meses del cuaderno digital (el propio monitor ya lo recomienda) y mejorar la estimación en regiones con pocos casos.',
  'Pasar de la sensibilidad del modelo a la estimación causal del efecto de intervenciones concretas.',
  'Desplegarlo en un servidor público permanente e integrarlo con los sistemas de las entidades de control.',
]))
hijos.push(caja('Frase final', ['«Los datos para prevenir ya son públicos. SATO los convierte en alertas verificables para que la supervisión llegue antes de que la obra se paralice»']))

// ---------------------------------------------------------------- preguntas
hijos.push(salto())
hijos.push(H1('9. Trabajos y sistemas similares, y qué nos diferencia'))
hijos.push(P('Existen trabajos que predicen el atraso de obras con aprendizaje automático (ML, *machine learning*: programas que aprenden patrones a partir de datos) y sistemas públicos que usan analítica o inteligencia artificial para vigilar compras del Estado. Ninguno de los revisados combina lo que hace SATO: **predecir un atraso definido por la norma, durante la ejecución, con los registros diarios oficiales de todo un país y validación en el futuro**. Los artículos académicos provienen de la revisión verificada del artículo (DOI comprobados en Crossref); los sistemas públicos, de sus fuentes oficiales o de prensa.'))
hijos.push(H2('9.1 Investigaciones académicas'))
hijos.push(tabla(['Trabajo (enlace)', 'Qué hace', 'Diferencia con SATO'], [
  ['Gondia et al., 2020 · https://doi.org/10.1061/(asce)co.1943-7862.0001736', 'Predice el riesgo de atraso de proyectos con árboles de decisión y bayesiano ingenuo (modelo probabilístico simple)', 'Pocos proyectos, sin dimensión temporal ni texto; SATO usa miles de obras y predice el futuro con validación temporal'],
  ['Egwim et al., 2021 · https://doi.org/10.1016/j.mlwa.2021.100166', 'Ensamble apilado (varios modelos combinados) para predecir atrasos', 'Entrenado con encuestas a expertos; SATO usa registros oficiales de la ejecución'],
  ['Sanni-Anibire et al., 2022 · https://doi.org/10.1080/15623599.2020.1768326', 'Riesgo de atraso en edificios altos con redes neuronales (93,75 % de exactitud)', 'Solo 48 respuestas de expertos y sin validación temporal; su exactitud no es comparable'],
  ['Yaseen et al., 2020 · https://doi.org/10.3390/su12041514', 'Bosque aleatorio (muchos árboles que votan) con algoritmo genético', 'Datos de cuestionarios; la exactitud engaña cuando el evento es raro'],
  ['Gallego et al., 2021 · https://doi.org/10.1016/j.ijforecast.2020.06.006', 'Alerta temprana de ineficiencia y corrupción en compras públicas con ML', 'Usa datos del contrato al adjudicar; SATO actualiza el riesgo cada mes durante la obra'],
  ['Fazekas y Kocsis, 2020 · https://doi.org/10.1017/s0007123417000461', 'Indicadores de riesgo de corrupción con 2,8 millones de contratos europeos', 'Indicadores del proceso de compra, no del atraso de la ejecución'],
  ['Son y Lee, 2019 · https://doi.org/10.3390/en12101956', 'Minería de texto (extraer información de documentos) en 13 proyectos petroleros para estimar atraso', 'Texto previo al contrato y solo 13 casos'],
  ['Jamal et al., 2026 · https://doi.org/10.1061/9780784486986.002', 'Analiza reportes diarios de obra con procesamiento de lenguaje natural (PLN: técnicas para que el computador entienda texto)', 'Un solo proyecto y descriptivo, sin predicción'],
  ['Montoya Villanueva et al., 2026 · https://doi.org/10.1080/15623599.2026.2664477', 'Factores para adoptar BIM, ML y gemelos digitales en la infraestructura pública peruana', 'Revisión de literatura; no construye ni evalúa un sistema'],
], [34, 33, 33]))
hijos.push(H2('9.2 Sistemas públicos con analítica o inteligencia artificial'))
hijos.push(tabla(['Sistema (enlace)', 'País', 'Qué hace', 'Diferencia con SATO'], [
  ['ALICE (Analisador de Licitações, Contratos e Editais), CGU y TCU · https://revista.cgu.gov.br/Revista_da_CGU/article/download/530/357/3347', 'Brasil', 'Revisa a diario licitaciones publicadas con minería de texto e IA y alerta indicios de sobreprecio o fraude', 'Vigila la licitación antes del contrato; SATO vigila la ejecución de la obra y anticipa su atraso'],
  ['Indicadores de riesgo de ProZorro y portal DOZORRO · https://ti-ukraine.org/en/news/prozorro-introduces-risk-indicators-to-check-suspicious-tenders/', 'Ucrania', 'Reglas automáticas (35 indicadores) que marcan compras con riesgo de incumplir las normas', 'Son reglas fijas sobre el proceso de compra; SATO usa un modelo que aprende de los datos y lo valida en el futuro'],
  ['Océano y convenio de analítica de la Contraloría con Colombia Compra Eficiente · https://www.colombiacompra.gov.co/?p=9976', 'Colombia', 'Cruce de bases de datos, minería de datos e IA para detectar riesgos de corrupción en la contratación', 'Detecta riesgos de corrupción en contratos; SATO predice el atraso de obras en ejecución'],
  ['INFOBRAS (Contraloría) · https://infobras.contraloria.gob.pe/InfobrasWeb/', 'Perú', 'Registro público del avance de las obras', 'Muestra lo que ya ocurrió; SATO lo usa como fuente y estima lo que puede ocurrir'],
  ['Reporte de obras paralizadas (Contraloría) · https://www.gob.pe/institucion/contraloria/colecciones/18230-obras-paralizadas-documentos', 'Perú', 'Inventario trimestral de obras paralizadas', 'Llega cuando la obra ya se paralizó; SATO busca anticiparse 60 días al atraso formal'],
], [36, 10, 27, 27]))
hijos.push(esp())
hijos.push(caja('Diferenciadores de SATO en una frase cada uno', [
  '**Momento:** predice durante la ejecución y se actualiza cada mes, no solo al adjudicar.',
  '**Fuente:** usa el texto de 2,73 millones de asientos del cuaderno de obra digital, que nadie usaba para predecir.',
  '**Evento:** el atraso lo define la norma (regla del 80 %), así cualquiera puede verificarlo.',
  '**Rigor:** validado en meses futuros que el modelo no vio, con intervalos de confianza y probabilidades calibradas.',
  '**Transparencia:** cada alerta se explica en lenguaje claro y enlaza al asiento oficial que la respalda.',
  '**Escala:** cubre todo el Perú (25 departamentos) y dos modelos: cuaderno digital y cartera INFOBRAS.',
]))

hijos.push(salto())
hijos.push(H1('10. ¿Cómo funciona la predicción? (no es un simulacro)'))
hijos.push(P('Una pregunta frecuente es si las predicciones son reales o un *mock* (datos de ejemplo). **Son reales**: las produce el modelo entrenado aplicado a los datos oficiales de cada obra. Lo que cambia es **cuándo** se ejecuta el modelo: se usa **inferencia por lotes** (*batch scoring*: calcular todas las predicciones de una vez cada vez que llegan datos nuevos), el mismo patrón que usan los bancos para su evaluación mensual de riesgo crediticio.'))
hijos.push(...N([
  '**Los datos llegan una vez al mes:** el OECE publica el cuaderno de obra digital en archivos mensuales y el MEF actualiza el gasto mensual. Entre un corte y otro, los datos de una obra no cambian.',
  '**Cada mes corre el pipeline** (cadena automática de pasos): calcula las variables de cada obra, convierte el texto de los asientos en vectores con Sentence-BERT, aplica el modelo LightGBM a las 2 970 obras vigentes del cuaderno y a las 2 014 de la cartera, calcula las explicaciones TreeSHAP y los escenarios de sensibilidad.',
  '**Los resultados pasan la compuerta de integridad** (32 chequeos) y se guardan en PostgreSQL.',
  '**La web muestra esos resultados** en milisegundos. Si el modelo se ejecutara cada vez que alguien abre una página, daría el mismo número, porque los datos no cambiaron hasta el próximo corte.',
], 'lotes'))
hijos.push(P('**La simulación** («¿Qué cambiaría la estimación?») también la calcula el modelo real: para cada obra se vuelve a ejecutar LightGBM cambiando una sola señal a la vez (por ejemplo, «ejecución financiera al día») y se guardan ambas probabilidades; hay 5 115 escenarios calculados. Es un **análisis de sensibilidad** (cuánto depende la estimación de cada señal), no una promesa de que una acción concreta evitará el atraso.'))
hijos.push(caja('Respuesta técnica para el docente', ['«Usamos inferencia por lotes: en cada corte mensual el modelo LightGBM calcula las probabilidades, las explicaciones TreeSHAP y los escenarios de sensibilidad de todas las obras vigentes; esos resultados pasan una compuerta de integridad y la web los sirve. Es el patrón estándar cuando los datos de entrada se actualizan mensualmente».']))

hijos.push(H1('11. ¿Por qué la versión pública es de solo lectura y por qué aún no está en un servidor?'))
hijos.push(H2('11.1 Qué es la versión pública'))
hijos.push(P(`El enlace ${URL_PUBLICA} está alojado en **GitHub Pages** (servicio gratuito de GitHub que publica páginas web **estáticas**, es decir, archivos fijos sin un programa ni una base de datos detrás). Para publicarlo, un script recorrió todo el sistema con un navegador automático y guardó la respuesta real de cada consulta: 2 053 respuestas de la API y 250 informes PDF. Por eso la copia muestra los resultados reales del modelo, pero **no puede responder consultas nuevas**: la búsqueda libre, el ingreso de analistas, las suscripciones y las combinaciones de filtros fuera del recorrido muestran un aviso.`))
hijos.push(H2('11.2 Por qué no se subió todavía el sistema completo'))
hijos.push(...V([
  '**El sistema completo necesita un servidor encendido todo el tiempo** con tres piezas: la base de datos PostgreSQL, la API y la web. GitHub Pages no ejecuta programas ni bases de datos.',
  '**La base de datos pesa 6,4 GB** (2,4 millones de asientos, 1,4 millones de registros de gasto, 139 159 obras y todas las predicciones y explicaciones). Las bases de datos gratuitas en la nube ofrecen entre 0,5 y 1 GB, que no alcanzan.',
  '**Un servidor adecuado** (unos 4 GB de RAM y 40 GB de disco) tiene costo mensual, o requiere crear una cuenta en un programa gratuito para estudiantes o de nivel gratuito (Azure for Students, Oracle Cloud Always Free), lo que el equipo aún no ha hecho. La cuenta de alojamiento disponible (Hostinger) no tiene un servidor contratado.',
  '**La configuración de producción ya está lista:** Docker Compose con Caddy (servidor web que obtiene el certificado HTTPS automáticamente). Con un servidor, la instalación toma alrededor de una hora.',
  '**Mientras tanto,** el sistema completo se ejecuta en cualquier computadora con Docker restaurando un respaldo de 548 MB (probado desde cero en 8,1 minutos) y puede publicarse temporalmente con un túnel de Cloudflare (conexión segura que expone el equipo local a internet sin abrir puertos).',
]))
hijos.push(caja('Cómo explicarlo en 20 segundos', ['«La versión pública es una copia estática con los resultados reales del modelo, porque el sistema completo necesita un servidor con una base de datos de 6,4 GB que los planes gratuitos no cubren. El despliegue en servidor ya está configurado; solo falta contratar o activar el servidor. Aquí mismo podemos mostrar la versión completa ejecutándose localmente»']))

hijos.push(salto())
hijos.push(H1('12. Preguntas probables del docente y cómo responder'))
const PR = [
  ['¿Por qué no reportan exactitud (accuracy)?', 'Porque el evento ocurre en 5 % de los casos: un modelo que nunca alerta tendría 95 % de exactitud y no serviría. Por eso usamos PR-AUC y ROC-AUC, y comparamos contra la prevalencia.'],
  ['¿Cómo evitaron que el modelo «haga trampa» con el futuro?', 'Con un panel as-of (cada mes solo usa información previa), partición temporal con purga de 60 días y pruebas automáticas que recalculan las variables para detectar fuga.'],
  ['¿El texto realmente aporta o es casualidad?', 'La mejora tiene intervalo de confianza al 95 % que excluye el cero (ROC-AUC +0,032 [0,019; 0,045]), se repite con horizontes de 30 y 90 días, en rolling-origin, con 5 semillas y sin la categoría léxica que menciona la regla del 80 %.'],
  ['¿Qué es TreeSHAP y por qué lo usan?', 'Es un método que reparte la predicción entre las variables usando valores de Shapley (teoría de juegos), exacto para modelos de árboles. Permite decir qué dato subió o bajó el riesgo de cada obra.'],
  ['¿Qué es Sentence-BERT?', 'Un modelo de lenguaje que transforma cada texto en un vector numérico que representa su significado; usamos una versión multilingüe porque los asientos están en español.'],
  ['¿El sistema acusa a entidades o contratistas?', 'No. Es una estimación probabilística para priorizar la supervisión; la interfaz y el PDF lo advierten explícitamente y cada alerta enlaza a la evidencia oficial para que un humano decida.'],
  ['¿Qué tan confiable es la probabilidad?', 'Está calibrada: en el grupo de mayor riesgo se estimó 20,0 % y ocurrió 17,7 %. La interfaz muestra la tasa real de cada nivel.'],
  ['¿Qué pasa si los datos cambian con el tiempo?', 'El monitor calcula la deriva (PSI) de cada variable y la anomalía de la tasa de riesgo alto; hoy marca 8 variables con cambio grande y recomienda reentrenar.'],
  ['¿Cómo garantizan la seguridad?', '13 de 13 casos OWASP aprobados: limitación de tasa, JWT, cabeceras de seguridad, validación de entrada, errores sin trazas, control de acceso y protección contra IP falsificada.'],
  ['¿Por qué LightGBM y no una red neuronal?', 'Con datos tabulares y valores faltantes los árboles con gradient boosting son el estándar; además comparamos con otros algoritmos y la diferencia vino de los datos, no del algoritmo. También permiten explicaciones exactas con TreeSHAP.'],
  ['¿Cuánto costaría operarlo?', 'Usa solo componentes libres y datos abiertos; corre en contenedores Docker en un solo servidor. El costo es el del servidor.'],
  ['¿Las predicciones son reales o un simulacro?', 'Son reales: el modelo entrenado se aplica a los datos oficiales en cada corte mensual (inferencia por lotes) y los resultados se guardan; la web los muestra. Ver la sección 10.'],
  ['¿Por qué la página pública es de solo lectura?', 'Porque GitHub Pages solo aloja archivos fijos; el sistema completo necesita un servidor con una base de datos de 6,4 GB que los planes gratuitos no cubren. La configuración de servidor ya está lista. Ver la sección 11.'],
  ['¿Qué sistemas parecidos existen?', 'ALICE en Brasil, los indicadores de ProZorro en Ucrania y Océano en Colombia vigilan licitaciones y contratos; ninguno predice el atraso durante la ejecución con los registros diarios de obra. Ver la sección 9.'],
  ['¿Qué aporte es nuevo?', 'Hasta donde revisamos, es el primer uso documentado de los asientos abiertos del cuaderno de obra digital para alerta temprana, con una etiqueta normativa reproducible y validación temporal a escala nacional.'],
]
hijos.push(tabla(['Pregunta', 'Respuesta sugerida'], PR, [30, 70], { primeraNegrita: true }))

hijos.push(H1('13. Glosario rápido'))
hijos.push(tabla(['Término', 'En palabras simples'], [
  ['ROC-AUC', 'Probabilidad de que el modelo ponga más riesgo a una obra que se atrasa que a una que no. 0,5 es azar; 1 es perfecto.'],
  ['PR-AUC', 'Mide qué tan bien encuentra los casos raros; se compara con la prevalencia (5,0 %).'],
  ['Prevalencia', 'Porcentaje de casos en que ocurre el evento.'],
  ['Calibración', 'Que un 20 % estimado signifique que ocurre en cerca de 20 de cada 100 casos.'],
  ['Fuga temporal', 'Cuando el modelo usa, sin querer, información del futuro; produce resultados falsamente buenos.'],
  ['As-of', 'Calcular cada dato solo con la información disponible hasta esa fecha.'],
  ['Backtest', 'Simular mes a mes cómo habría funcionado el sistema en el pasado.'],
  ['Bootstrap', 'Remuestrear los datos muchas veces para calcular intervalos de confianza.'],
  ['TreeSHAP', 'Explica cuánto aportó cada dato a la predicción de una obra.'],
  ['Embeddings', 'Representación numérica del significado de un texto.'],
  ['PSI', 'Índice que mide cuánto cambió la distribución de una variable respecto del entrenamiento.'],
  ['OWASP Top 10', 'Lista estándar de los riesgos de seguridad web más importantes.'],
  ['Inferencia por lotes', 'Calcular todas las predicciones de una vez cuando llegan datos nuevos, en lugar de hacerlo en cada visita.'],
  ['Pipeline', 'Cadena automática de pasos que descarga, limpia, integra los datos y ejecuta los modelos.'],
  ['LightGBM', 'Algoritmo que combina muchos árboles de decisión pequeños, cada uno corrigiendo los errores del anterior.'],
  ['Sentence-BERT', 'Modelo de lenguaje que convierte cada texto en un vector numérico que representa su significado.'],
  ['API REST', 'Servicio web que entrega datos en formato JSON a la interfaz u otros sistemas.'],
  ['Docker', 'Tecnología de contenedores: empaqueta un programa con todo lo que necesita para que funcione igual en cualquier equipo.'],
  ['GitHub Pages', 'Servicio gratuito de GitHub que publica sitios web estáticos (archivos fijos, sin servidor ni base de datos).'],
  ['Sitio estático', 'Página formada solo por archivos ya generados; no ejecuta consultas nuevas.'],
  ['MLOps', 'Prácticas para operar, vigilar y actualizar modelos de aprendizaje automático en producción.'],
], [22, 78], { primeraNegrita: true }))

hijos.push(H1('14. Lista de control antes de exponer'))
hijos.push(...V([
  'El enlace público es permanente y no depende de ningún equipo: basta con internet en el aula.',
  `Abrir ${URL_PUBLICA} unos minutos antes y recorrer las pantallas de la demostración.`,
  'Para mostrar la versión completa (búsqueda libre, ingreso de analistas), levantarla en una laptop con `scripts/instalar_laptop.ps1` (ver docs/EJECUTAR_EN_LAPTOP.md).',
  '**Plan B:** si falla internet, mostrar el sistema en `http://localhost:8080` desde una laptop con el sistema instalado; si todo falla, usar las capturas del artículo (figuras 7 a 13).',
  'Tener abierto el artículo en Word y el informe PDF de una obra descargado previamente.',
  'Ensayar los tiempos con cronómetro: 3 / 3,5 / 4,5 / 4 / 5 minutos.',
]))

const doc = new Document({
  creator: 'Equipo SATO',
  lastModifiedBy: 'Equipo SATO',
  title: 'Guía de exposición del proyecto SATO',
  description: 'Guion de exposición para cinco integrantes',
  styles: { default: { document: { run: { font: FUENTE, size: 22 } } } },
  numbering: {
    config: [
      { reference: 'vinetas', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 500, hanging: 260 } } } }] },
      { reference: 'demo', levels: [{ level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 500, hanging: 300 } } } }] },
      { reference: 'lotes', levels: [{ level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 500, hanging: 300 } } } }] },
    ],
  },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1300, bottom: 1300, left: 1300, right: 1300, header: 650, footer: 650 } } },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: 'C9D3DF', space: 4 } }, children: [new TextRun({ text: 'SATO · Guía de exposición', font: FUENTE, size: 17, color: GRIS })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: 'Página ', font: FUENTE, size: 17, color: GRIS }), new TextRun({ children: [PageNumber.CURRENT], font: FUENTE, size: 17, color: GRIS }), new TextRun({ text: ' de ', font: FUENTE, size: 17, color: GRIS }), new TextRun({ children: [PageNumber.TOTAL_PAGES], font: FUENTE, size: 17, color: GRIS })] })] }) },
    children: hijos,
  }],
})

const salida = path.join(__dirname, 'Guia_Exposicion_SATO.docx')
Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(salida, buf)
  console.log('ok', salida)
})
