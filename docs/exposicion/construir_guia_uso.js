// Construye Guia_Uso_Plataforma_SATO.docx: explicacion en palabras simples de cada pantalla y pestana de la web.
//   node docs/exposicion/construir_guia_uso.js   (requiere el paquete docx; NODE_PATH o DOCX_MODULE)
// Las cifras de ejemplo son las que muestra el sistema al corte del 31 de agosto de 2026.
const fs = require('fs')
const path = require('path')
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, ShadingType, AlignmentType, HeadingLevel,
  Header, Footer, PageNumber, BorderStyle, LevelFormat, TableLayoutType, VerticalAlign, ExternalHyperlink,
} = require(process.env.DOCX_MODULE || 'docx')

const URL_PUBLICA = 'https://owerlopez.github.io/sato_peru_2026/'
const AZUL = '0A1C30'
const AZUL_T = '1F72B4'
const GRIS = '3E4A5B'
const FUENTE = 'Calibri'
const ANCHO = 12240 - 2 * 1300

function runs(texto, base = {}) {
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
const P = (t, o = {}) => new Paragraph({ alignment: o.align || AlignmentType.JUSTIFIED, spacing: { after: o.after ?? 110, line: 276 }, children: runs(t, { size: o.size || 22, color: o.color }) })
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 320, after: 140 }, keepNext: true, border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: AZUL_T, space: 4 } }, children: [new TextRun({ text: t, font: FUENTE, bold: true, size: 30, color: AZUL })] })
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 200, after: 80 }, keepNext: true, children: [new TextRun({ text: t, font: FUENTE, bold: true, size: 24, color: AZUL_T })] })
const V = (items) => items.map((t) => new Paragraph({ numbering: { reference: 'vinetas', level: 0 }, alignment: AlignmentType.LEFT, spacing: { after: 50, line: 264 }, children: runs(t, { size: 22 }) }))
const esp = () => new Paragraph({ spacing: { after: 100 }, children: [] })

function tabla(cab, filas, anchos) {
  const tot = anchos.reduce((a, b) => a + b, 0)
  const ws = anchos.map((x) => Math.floor((x / tot) * ANCHO))
  ws[ws.length - 1] += ANCHO - ws.reduce((a, b) => a + b, 0)
  const borde = { style: BorderStyle.SINGLE, size: 4, color: 'C9D3DF' }
  const celda = (t, w, o = {}) => new TableCell({
    width: { size: w, type: WidthType.DXA }, shading: o.fill ? { type: ShadingType.CLEAR, fill: o.fill, color: 'auto' } : undefined,
    margins: { top: 70, bottom: 70, left: 110, right: 110 }, verticalAlign: VerticalAlign.CENTER,
    children: [new Paragraph({ spacing: { after: 20, line: 252 }, children: runs(String(t), { size: 20, bold: o.bold, color: o.color }) })],
  })
  return new Table({
    width: { size: ANCHO, type: WidthType.DXA }, columnWidths: ws, layout: TableLayoutType.FIXED,
    borders: { top: borde, bottom: borde, left: borde, right: borde, insideHorizontal: borde, insideVertical: borde },
    rows: [
      new TableRow({ tableHeader: true, cantSplit: true, children: cab.map((c, i) => celda(c, ws[i], { fill: AZUL, bold: true, color: 'FFFFFF' })) }),
      ...filas.map((f, r) => new TableRow({ cantSplit: true, children: f.map((c, i) => celda(c, ws[i], { fill: r % 2 ? 'F4F6F9' : undefined, bold: i === 0 })) })),
    ],
  })
}
function caja(titulo, lineas) {
  const b = { style: BorderStyle.SINGLE, size: 4, color: AZUL_T }
  const hijos = [new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: titulo, font: FUENTE, bold: true, size: 21, color: AZUL })] })]
  for (const l of lineas) hijos.push(new Paragraph({ spacing: { after: 50, line: 264 }, children: runs(l, { size: 21 }) }))
  return new Table({
    width: { size: ANCHO, type: WidthType.DXA }, columnWidths: [ANCHO], layout: TableLayoutType.FIXED,
    borders: { top: b, bottom: b, right: b, left: { style: BorderStyle.SINGLE, size: 24, color: AZUL_T }, insideHorizontal: b, insideVertical: b },
    rows: [new TableRow({ cantSplit: true, children: [new TableCell({ width: { size: ANCHO, type: WidthType.DXA }, shading: { type: ShadingType.CLEAR, fill: 'EFF6FC', color: 'auto' }, margins: { top: 100, bottom: 100, left: 180, right: 160 }, children: hijos })] })],
  })
}

// Cada pantalla: para que sirve, que se ve, como usarla y una frase para decir en la exposicion.
function pantalla(num, nombre, menu, para, ve, usar, frase) {
  const out = [H1(`${num}. ${nombre}`), P(`**Dónde está:** ${menu}`), P(`**Para qué sirve:** ${para}`), H2('Qué se ve')]
  out.push(...V(ve))
  if (usar.length) {
    out.push(H2('Cómo usarla'))
    out.push(...V(usar))
  }
  out.push(esp(), caja('Qué decir al mostrarla', [`«${frase}»`]))
  return out
}

const h = []
h.push(new Paragraph({ spacing: { before: 500, after: 80 }, children: [new TextRun({ text: 'GUÍA DE USO DE LA PLATAFORMA', font: FUENTE, bold: true, size: 24, color: AZUL_T })] }))
h.push(new Paragraph({ spacing: { after: 120 }, children: [new TextRun({ text: 'SATO explicado pantalla por pantalla', font: FUENTE, bold: true, size: 42, color: AZUL })] }))
h.push(P('Explicación en palabras simples de cada pantalla y pestaña del sistema, para usarlo y para mostrarlo en la exposición. Las cifras de ejemplo son las que muestra el sistema al corte del 31 de agosto de 2026.', { color: GRIS }))
h.push(esp())
h.push(tabla(['Dato', 'Valor'], [
  ['Enlace público', URL_PUBLICA],
  ['Tipo de enlace', 'Copia pública de solo lectura con los resultados reales del modelo (no tiene buscador libre, ingreso ni suscripción)'],
  ['Versión completa', 'Se ejecuta en una computadora con Docker (ver docs/EJECUTAR_EN_LAPTOP.md)'],
], [24, 76]))

h.push(H1('1. Ideas básicas antes de empezar'))
h.push(...V([
  '**Qué es SATO:** un sistema que avisa qué obras públicas del Perú tienen más riesgo de atrasarse, usando solo datos abiertos del Estado.',
  '**Riesgo alto, medio y bajo:** es un semáforo. Cada nivel tiene color y además un ícono distinto (triángulo para alto, círculo para medio, visto bueno para bajo), así se entiende aunque no se distingan los colores.',
  '**Probabilidad:** un número de 0 % a 100 %. Por ejemplo, 49 % significa que, de 100 obras parecidas, cerca de 49 registrarían el atraso formal en los próximos 60 días.',
  '**Atraso formal:** cuando el cuaderno de obra registra que la obra avanzó menos del 80 % de lo programado (regla de la ley de contrataciones).',
  '**Dos tipos de obras:** las del **cuaderno de obra digital** (contratos con registro diario, desde 2024) y las de la **cartera INFOBRAS** (todas las obras públicas registradas por la Contraloría).',
  '**Íconos «i»:** al pasar el mouse o tocar el ícono «i» aparece una explicación corta de cada término.',
  '**Es una ayuda para priorizar**, no una acusación: indica dónde mirar primero.',
]))

h.push(H1('2. Partes que se repiten en todas las pantallas'))
h.push(tabla(['Parte', 'Qué es'], [
  ['Franja superior oscura', 'Aviso de que es un prototipo de investigación y no un sitio oficial del Estado.'],
  ['Menú lateral izquierdo', 'Acceso a todas las pantallas, agrupadas en Monitoreo, Evidencia y Ayuda. En teléfono se abre con el botón de tres rayas.'],
  ['Selector «Todo el Perú»', 'Cambia el ámbito: al elegir un departamento, todas las pantallas muestran solo sus obras.'],
  ['Recuadro «Datos al corte»', 'Fecha de los datos usados: cuaderno digital al 31 ago. 2026 y cartera INFOBRAS al 31 mar. 2026, y el estado del sistema (operativo o con avisos).'],
  ['Buscador (versión completa)', 'Busca obras por nombre, entidad, código CUI o código INFOBRAS.'],
  ['Recibir alertas e Ingresar (versión completa)', 'Suscripción al resumen semanal por correo e ingreso de analistas.'],
  ['Pie de página', 'Enlaces a los portales oficiales de datos (OECE, MEF, Contraloría y datos abiertos) y a la transparencia del sistema.'],
], [28, 72]))

let n = 3
h.push(...pantalla(n++, 'Panorama', 'Menú → Monitoreo → Panorama (pantalla de inicio).',
  'Dar un resumen del estado de las obras del ámbito elegido en una sola vista.',
  [
    '**Resumen en una frase:** por ejemplo, «En todo el Perú, 190 obras con cuaderno digital tienen riesgo alto de registrar un atraso formal en los próximos 60 días y 1,166 obras de la cartera INFOBRAS tienen riesgo alto de terminar con retraso significativo».',
    '**Cuatro indicadores (tarjetas):** obras en ejecución monitoreadas (4,698), inversión monitoreada (78.1 mil millones de soles), obras en riesgo alto de atraso en 60 días (190, con una línea que muestra cómo cambió mes a mes) e inversión en obras de riesgo alto (51.5 mil millones de soles).',
    '**Obras que requieren atención:** lista de las obras con mayor probabilidad. Tiene dos opciones: «Atraso en 60 días» (cuaderno digital) y «Retraso al término» (cartera INFOBRAS).',
    '**Mapa de riesgo:** cada punto es una obra; los colores indican el nivel. El mapa base está en grises para que resalten los puntos. La pestaña «Por departamento» muestra lo mismo como tabla.',
    '**¿Qué tan confiables son las alertas?:** muestra qué porcentaje de obras de cada nivel terminó registrando el atraso en la validación con datos pasados.',
  ],
  [
    'Pulse una obra de la lista para abrir una **vista previa** con su riesgo y sus principales factores, sin salir de la pantalla.',
    'Use «Solo riesgo alto / Todas» en el mapa para filtrar los puntos.',
    'Cada gráfico tiene la opción de verse como tabla.',
    '«Imprimir resumen» prepara la página para imprimir o guardar en PDF.',
  ],
  'Esta es la vista para un jefe o un auditor: en diez segundos sabe cuántas obras están en riesgo, cuánta inversión representan y dónde están.'))

h.push(...pantalla(n++, 'Alertas del cuaderno', 'Menú → Monitoreo → Alertas del cuaderno.',
  'Ver la lista completa de obras con cuaderno de obra digital y su riesgo de atraso formal en los próximos 60 días.',
  [
    '**Resumen por nivel (cuatro tarjetas):** todas las evaluadas (2,970), riesgo alto (190; 6.4 %), riesgo medio (461; 15.5 %) y riesgo bajo (2,319; 78.1 %). Las tarjetas también funcionan como filtro.',
    '**«En ejecución» o «Todas (incluye históricas)»:** muestra solo las obras vigentes o también las ya terminadas.',
    '**Tabla de obras:** nombre, entidad, código CUI, nivel y probabilidad, ubicación, sector y fecha del último asiento del cuaderno.',
    '**Filtros:** buscar en la lista, sector y orden (por ejemplo, mayor riesgo primero).',
    'En teléfono, la tabla se muestra como tarjetas.',
  ],
  [
    'Pulse una tarjeta de nivel (por ejemplo, «Riesgo alto») para ver solo esas obras.',
    'Pulse «Vista previa» para ver el resumen de una obra, o su nombre para abrir la ficha completa.',
  ],
  'Aquí el supervisor ve su lista de trabajo: ordenada de mayor a menor riesgo, puede empezar por las primeras.'))

h.push(...pantalla(n++, 'Ficha de una obra del cuaderno digital', 'Se abre al pulsar el nombre de una obra en Panorama o en Alertas del cuaderno.',
  'Explicar por qué una obra tiene ese riesgo y mostrar la evidencia oficial que lo respalda.',
  [
    '**Ruta de migas:** «Alertas del cuaderno > Ficha de la obra», para volver atrás.',
    '**Nombre de la obra** (en letras normales) y botón **«Informe técnico PDF»**.',
    '**Resumen del riesgo:** nivel y probabilidad (por ejemplo, «Alto 49 %»), cuántas veces supera el promedio («8.7 veces el promedio»), posición entre las obras evaluadas («10 de 10»: está en el grupo de mayor riesgo) y confiabilidad del nivel («18 de cada 100 obras en nivel alto registraron el atraso formal»).',
    '**Principales factores que elevan el riesgo:** los tres motivos más importantes en lenguaje claro.',
  ],
  [],
  'La ficha convierte el número en una explicación: dice qué tan alto es el riesgo, por qué, y con qué documentos oficiales se puede comprobar.'))

h.push(H2('Pestañas de la ficha'))
h.push(tabla(['Pestaña', 'Qué muestra en palabras simples'], [
  ['Factores y evidencia', '«¿Por qué este nivel de riesgo?»: la lista de datos de la obra que subieron o bajaron el riesgo, con una barra que indica su peso. Cada factor tiene «Ver evidencia», que abre el asiento oficial del cuaderno que lo originó. A la derecha, «Evidencia documental» reúne todos esos registros. La casilla «Mostrar detalle técnico» muestra el nombre interno de la variable y su contribución numérica (TreeSHAP).'],
  ['Evolución del riesgo', 'Cómo cambió la probabilidad mes a mes (gráfico de arriba) y la actividad del cuaderno (gráfico de abajo), con el mismo eje de meses. Permite ver si el riesgo viene subiendo.'],
  ['Cuaderno de obra', 'Los asientos del cuaderno de obra digital de esa obra con su fecha y su texto, y un buscador dentro del texto (por ejemplo: lluvias, falta de pago, expediente). En la copia pública se ve la lista; el buscador funciona en la versión completa.'],
  ['Datos de la obra', 'Datos oficiales: entidad, contratista, ubicación, CUI, montos, plazo y fechas, con la denominación oficial tal como la publica el OECE.'],
  ['Revisión del analista', 'Espacio para que un analista registre su decisión sobre la alerta (solo en la versión completa, con ingreso).'],
], [24, 76]))
h.push(esp())
h.push(P('**Informe técnico PDF:** documento descargable de la obra con portada, resumen del riesgo, escala con el umbral del modelo, evolución, factores con barras, escenarios de sensibilidad («qué cambiaría la estimación»), evidencia y marco normativo.'))

h.push(...pantalla(n++, 'Cartera nacional', 'Menú → Monitoreo → Cartera nacional.',
  'Ver el riesgo de las obras de todo el país registradas en INFOBRAS (todas las modalidades), aunque no tengan cuaderno digital.',
  [
    '**Resumen por nivel** que también filtra, como en Alertas del cuaderno.',
    '**Tabla de obras:** nombre, entidad, ubicación, costo, fin programado y nivel de riesgo de **terminar con un retraso mayor al 30 % del plazo**.',
    '**Estado de la obra:** en ejecución, retraso ya consumado, finalizada o sin registros recientes.',
  ],
  ['Pulse el nombre de una obra para abrir su ficha de cartera.'],
  'El cuaderno digital solo cubre contratos desde 2024; la cartera amplía la vigilancia a todas las obras públicas del país.'))
h.push(H2('Pestañas de la ficha de cartera'))
h.push(tabla(['Pestaña', 'Qué muestra'], [
  ['Factores', 'Los datos de la obra que más influyen en su riesgo de terminar con retraso, en lenguaje claro.'],
  ['Ejecución del gasto', 'Arriba, la probabilidad estimada cada mes; abajo, el gasto devengado (dinero ejecutado) mensual de la inversión según el SIAF del MEF. Si el gasto se detiene, suele subir el riesgo.'],
  ['Datos de la obra', 'Datos oficiales de INFOBRAS y enlaces a las fuentes.'],
], [24, 76]))

h.push(...pantalla(n++, 'Comparador', 'Menú → Monitoreo → Comparador.',
  'Comparar departamentos o tipos de obra para ver dónde se concentran los retrasos.',
  [
    '**Gráfico ordenado por tasa histórica de retraso** de cada grupo (solo grupos con al menos 30 obras con resultado conocido, para no sacar conclusiones con pocos casos).',
    '**Tabla comparativa** con las cifras de cada departamento o tipo de obra (se elige cómo agrupar).',
  ],
  ['Pulse un encabezado de la tabla para ordenarla por esa columna.'],
  'Esta pantalla ayuda a planificar: muestra qué regiones o tipos de obra tienen históricamente más obras con retraso.'))

h.push(...pantalla(n++, 'Validación del modelo', 'Menú → Evidencia → Validación del modelo.',
  'Demostrar, con datos pasados, que las predicciones funcionan y cuánto se puede confiar en ellas.',
  [
    '**Tres preguntas respondidas en lenguaje simple:**',
    '«¿Distingue las obras que se atrasan?» → 77 de 100: al comparar una obra que tuvo atraso con otra que no, el modelo dio más riesgo a la primera en 77 de cada 100 pares (el azar sería 50).',
    '«¿Son realistas las probabilidades?» → 20 % → 18 %: en el grupo de mayor riesgo el modelo estimó 20 % y ocurrió 18 %.',
    '«¿Sirve para priorizar la supervisión?» → revisando el 10 % de obras con mayor riesgo se habría encontrado el 32 % de los atrasos.',
  ],
  [],
  'Aquí mostramos que no pedimos fe: el modelo se evaluó en meses que no conoció y sus probabilidades coinciden con lo que realmente ocurrió.'))
h.push(H2('Pestañas de la validación'))
h.push(tabla(['Pestaña', 'Qué muestra'], [
  ['Alerta a 60 días', 'Si las probabilidades coinciden con lo ocurrido (barras y línea por grupos de riesgo), el resultado real de cada nivel (alto 17.6 %, medio 8.5 %, bajo 3.1 %), cuánto rinde revisar según el riesgo y la anticipación lograda en Arequipa.'],
  ['Cartera INFOBRAS', 'La misma evaluación para el modelo de la cartera: al inicio de la obra y con el seguimiento mensual del gasto.'],
  ['Por sector', 'Qué tan bien funciona el modelo en cada sector (educación, salud, transporte, etc.).'],
  ['Obra por obra', 'Lo estimado frente a lo ocurrido en obras concretas de la cartera, para revisar aciertos y errores uno por uno.'],
  ['Detalle técnico', 'Diseño de la evaluación, matriz de confusión (aciertos y errores del nivel alto), el experimento central «¿aporta el texto de los asientos?» (modelo A frente a B), todos los experimentos y la trazabilidad del modelo en uso.'],
], [24, 76]))

h.push(...pantalla(n++, 'Datos y fuentes', 'Menú → Evidencia → Datos y fuentes.',
  'Mostrar de dónde vienen los datos, qué tan completos están y qué limitaciones tienen.',
  [
    '**Integración de las fuentes:** cuántas obras del cuaderno se enlazaron con su inversión (CUI), con INFOBRAS y con el gasto mensual del SIAF.',
    '**Auditoría de calidad de los datos:** resultado de los 32 chequeos automáticos (sin hallazgos, avisos e informativos).',
    '**Disponibilidad de las fuentes y sincronización:** fecha de cada fuente y de la próxima actualización.',
    '**Limitaciones conocidas:** condiciones de las fuentes que limitan lo que el sistema puede afirmar (por ejemplo, obras sin coordenadas).',
    '**Linaje de los datos:** el camino de cada dato desde el archivo oficial hasta la pantalla.',
  ],
  [],
  'Somos transparentes con los datos: mostramos qué fuentes usamos, qué tan completas están y qué problemas tienen, sin maquillarlos.'))

h.push(...pantalla(n++, 'Estado y monitoreo', 'Menú → Evidencia → Estado y monitoreo.',
  'Mostrar la salud del sistema y si el modelo sigue funcionando bien con datos nuevos.',
  [
    '**Estado de la plataforma:** operativo o con avisos, con la lista de avisos (por ejemplo, «8 variables cambiaron de distribución: conviene evaluar un reentrenamiento»).',
    '**Cuatro indicadores:** datos al corte (31 ago. 2026), última actualización, chequeos sin hallazgos y fecha hasta la que se entrenó el modelo.',
    '**¿El modelo sigue anticipando los atrasos?:** porcentaje de atrasos que ya estaban en nivel alto, mes a mes.',
    '**¿Es normal la cantidad de obras en nivel alto?:** compara el mes actual con la mediana histórica y marca si es un valor atípico.',
    '**¿Cambiaron los datos de entrada del modelo?:** las variables que más cambiaron respecto del entrenamiento.',
    '**Actualizaciones de datos:** historial de cada carga (aplicada, rechazada o con error) con su detalle.',
  ],
  ['Cada gráfico puede verse como tabla; pulse una actualización para ver su detalle.'],
  'El sistema se vigila a sí mismo: si los datos cambian y el modelo empieza a envejecer, lo detecta y lo muestra.'))

h.push(...pantalla(n++, 'Guía y glosario', 'Menú → Ayuda → Guía y glosario.',
  'Explicar cómo leer el sistema y los términos técnicos.',
  [
    '**Glosario:** definiciones simples de términos como probabilidad, nivel de riesgo, atraso formal, CUI o factor.',
    '**Qué puede y qué no puede hacer:** los alcances y los límites del sistema (por ejemplo, que no determina responsabilidades).',
  ],
  [],
  'Pensamos en usuarios sin formación técnica: todo término tiene una explicación a un clic.'))

h.push(H1(`${n++}. Funciones de la versión completa`))
h.push(P('Estas funciones necesitan un servidor con base de datos, por eso no están en la copia pública de solo lectura; sí funcionan en la versión completa instalada en una computadora.'))
h.push(tabla(['Función', 'Qué hace'], [
  ['Buscar', 'Busca en todas las obras (cuaderno digital y cartera) por nombre, entidad, CUI o código INFOBRAS.'],
  ['Recibir alertas', 'Suscripción gratuita a un resumen semanal por correo con las obras de riesgo alto de un departamento o provincia; requiere confirmar el correo.'],
  ['Ingresar', 'Acceso de analistas autorizados para registrar revisiones de las alertas; todo queda en un registro de auditoría.'],
  ['Revisión del analista', 'Registrar si una alerta se revisó y qué se decidió, para evaluar con el tiempo la utilidad de las alertas.'],
], [24, 76]))

h.push(H1(`${n++}. Recorrido sugerido para mostrarlo (3 minutos)`))
h.push(...V([
  '**Panorama:** leer la frase de resumen y los cuatro indicadores; señalar el mapa.',
  '**Alertas del cuaderno:** pulsar la tarjeta «Riesgo alto» y abrir la primera obra.',
  '**Ficha:** leer el nivel, las veces sobre el promedio y la confiabilidad del nivel.',
  '**Factores y evidencia:** pulsar «Ver evidencia» en un factor para mostrar el asiento oficial.',
  '**Informe técnico PDF:** abrirlo y mostrar la portada y la escala de riesgo.',
  '**Validación del modelo:** mostrar las tres preguntas respondidas.',
  '**Estado y monitoreo:** mostrar que el sistema vigila su propio desempeño.',
]))

const doc = new Document({
  creator: 'Equipo SATO', lastModifiedBy: 'Equipo SATO', title: 'Guía de uso de la plataforma SATO', description: 'Explicación de cada pantalla y pestaña',
  styles: { default: { document: { run: { font: FUENTE, size: 22 } } } },
  numbering: { config: [{ reference: 'vinetas', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 500, hanging: 260 } } } }] }] },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1300, bottom: 1300, left: 1300, right: 1300, header: 650, footer: 650 } } },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: 'C9D3DF', space: 4 } }, children: [new TextRun({ text: 'SATO · Guía de uso de la plataforma', font: FUENTE, size: 17, color: GRIS })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: 'Página ', font: FUENTE, size: 17, color: GRIS }), new TextRun({ children: [PageNumber.CURRENT], font: FUENTE, size: 17, color: GRIS }), new TextRun({ text: ' de ', font: FUENTE, size: 17, color: GRIS }), new TextRun({ children: [PageNumber.TOTAL_PAGES], font: FUENTE, size: 17, color: GRIS })] })] }) },
    children: h,
  }],
})
Packer.toBuffer(doc).then((buf) => {
  const salida = path.join(__dirname, 'Guia_Uso_Plataforma_SATO.docx')
  fs.writeFileSync(salida, buf)
  console.log('ok', salida)
})
