// Construye Articulo_Cientifico_Final.docx a partir de contenido.js y referencias.js.
//   node docs/articulo/fuente/construir.js
// Las citas se escriben como [@clave] o [@a,@b]; se numeran en orden de primera aparicion (IEEE) y la lista de referencias
// se genera solo con las claves citadas. Una clave inexistente detiene la construccion.
const fs = require('fs')
const path = require('path')
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, WidthType, ShadingType, AlignmentType,
  HeadingLevel, Header, Footer, PageNumber, BorderStyle, LevelFormat, TableLayoutType, VerticalAlign, PageBreak,
} = require(process.env.DOCX_MODULE || 'docx')

const DIR = __dirname
const ROOT = path.resolve(DIR, '..')
const { meta, secciones, anexos } = require('./contenido.js')
const REFS = require('./referencias.js')
const MET = JSON.parse(fs.readFileSync(path.join(ROOT, 'evaluacion', 'metricas_prototipo.json'), 'utf8'))
// {{ruta.a.valor|formato}}: valores medidos del prototipo (evaluacion/metricas_prototipo.json); formato n0/n1 con coma decimal
function metrica(ruta) {
  const [r, fmt] = ruta.split('|')
  let v = MET
  for (const k of r.split('.')) { if (v == null || !(k in v)) throw new Error('metrica inexistente: ' + r); v = v[k] }
  if (typeof v === 'number') {
    const dec = fmt === 'n1' ? 1 : fmt === 'n2' ? 2 : 0
    const t = v.toFixed(dec).split('.')
    t[0] = t[0].replace(/\B(?=(\d{3})+(?!\d))/g, ' ')
    return t.join(',')
  }
  return String(v)
}

const AZUL = '1F4E79'
const AZUL_T = '2E74B5'
const FUENTE = 'Arial'
const ANCHO = 12240 - 2 * 1418 // Carta, margenes 2,5 cm

// ---------- citas ----------
const orden = []
function numero(clave) {
  if (!REFS[clave]) throw new Error(`referencia inexistente: ${clave}`)
  let i = orden.indexOf(clave)
  if (i < 0) { orden.push(clave); i = orden.length - 1 }
  return i + 1
}
function resolverCitas(texto) {
  return texto.replace(/\[(@[^\]]+)\]/g, (_, grupo) => {
    const ns = grupo.split(',').map((s) => numero(s.trim().replace(/^@/, ''))).sort((a, b) => a - b)
    const partes = []
    for (let k = 0; k < ns.length; k++) {
      let j = k
      while (j + 1 < ns.length && ns[j + 1] === ns[j] + 1) j++
      partes.push(j - k >= 2 ? `${ns[k]}–${ns[j]}` : ns.slice(k, j + 1).join('], ['))
      k = j
    }
    return `[${partes.join('], [')}]`
  })
}

// ---------- texto enriquecido: **negrita**, *cursiva* ----------
function runs(texto, base = {}) {
  const out = []
  const t = resolverCitas(texto)
  const rx = /(\*\*[^*]+\*\*|\*[^*]+\*|_\{[^}]+\})/g
  let last = 0
  let m
  while ((m = rx.exec(t))) {
    if (m.index > last) out.push(new TextRun({ text: t.slice(last, m.index), font: FUENTE, ...base }))
    const s = m[0]
    if (s.startsWith('_{')) out.push(new TextRun({ text: s.slice(2, -1), subScript: true, font: FUENTE, ...base }))
    else if (s.startsWith('**')) out.push(new TextRun({ text: s.slice(2, -2), bold: true, font: FUENTE, ...base }))
    else out.push(new TextRun({ text: s.slice(1, -1), italics: true, font: FUENTE, ...base }))
    last = m.index + s.length
  }
  if (last < t.length) out.push(new TextRun({ text: t.slice(last), font: FUENTE, ...base }))
  return out
}

let palabras = {}
let seccionActual = 'Preliminares'
function contar(t) {
  const n = t.replace(/\[@[^\]]+\]/g, '').replace(/[*]/g, '').split(/\s+/).filter((w) => /[\p{L}\p{N}]/u.test(w)).length
  palabras[seccionActual] = (palabras[seccionActual] || 0) + n
}

const P = (texto, opt = {}) => {
  contar(texto)
  return new Paragraph({
    alignment: opt.align || AlignmentType.JUSTIFIED,
    spacing: { after: opt.after ?? 120, line: 264 },
    indent: opt.indent,
    keepNext: opt.keepNext,
    children: runs(texto, { size: opt.size || 21 }),
  })
}

const H1 = (t) => {
  seccionActual = t
  return new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 280, after: 120 }, keepNext: true, children: [new TextRun({ text: t, font: 'Calibri', bold: true, size: 26, color: AZUL_T })] })
}
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 180, after: 80 }, keepNext: true, children: [new TextRun({ text: t, font: 'Calibri', bold: true, size: 22, color: AZUL_T })] })

function vinetas(items) {
  return items.map((t) => {
    contar(t)
    return new Paragraph({ numbering: { reference: 'vinetas', level: 0 }, alignment: AlignmentType.JUSTIFIED, spacing: { after: 60, line: 264 }, children: runs(t, { size: 21 }) })
  })
}

let nFig = 0
let nTab = 0
const figIds = {}
const tabIds = {}

function figura(b) {
  nFig++
  figIds[b.id] = nFig
  const file = path.join(ROOT, b.archivo)
  if (!fs.existsSync(file)) throw new Error(`figura inexistente: ${file}`)
  const buf = fs.readFileSync(file)
  const w = buf.readUInt32BE(16)
  const h = buf.readUInt32BE(20)
  const ancho = Math.round((b.ancho || 1) * 610)
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 60 }, keepNext: true, children: [new ImageRun({ type: 'png', data: buf, transformation: { width: ancho, height: Math.round((ancho * h) / w) }, altText: { title: `Figura ${nFig}`, description: b.titulo, name: b.id } })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [new TextRun({ text: `Fig. ${nFig}. `, bold: true, font: FUENTE, size: 18 }), ...runs(b.titulo, { size: 18 })] }),
  ]
}

function celda(texto, opt) {
  return new TableCell({
    width: { size: opt.w, type: WidthType.DXA },
    shading: opt.head ? { type: ShadingType.CLEAR, fill: 'DCE6F1', color: 'auto' } : opt.alt ? { type: ShadingType.CLEAR, fill: 'F5F8FC', color: 'auto' } : undefined,
    margins: { top: 50, bottom: 50, left: 80, right: 80 },
    verticalAlign: VerticalAlign.CENTER,
    children: String(texto).split('\n').map((linea) => new Paragraph({ alignment: opt.align || AlignmentType.LEFT, keepNext: !!opt.keepNext, spacing: { after: 0, line: 240 }, children: runs(linea, { size: opt.size || 16, bold: opt.head }) })),
  })
}

function tabla(b) {
  nTab++
  tabIds[b.id] = nTab
  const total = b.anchos.reduce((a, c) => a + c, 0)
  const ws = b.anchos.map((x) => Math.floor((x / total) * ANCHO))
  ws[ws.length - 1] += ANCHO - ws.reduce((a, c) => a + c, 0)
  const size = b.tam || 16
  const num = b.numericas || []
  const filas = [
    new TableRow({ tableHeader: true, cantSplit: true, children: b.cab.map((c, i) => celda(c, { w: ws[i], head: true, size, keepNext: true, align: AlignmentType.CENTER })) }),
    ...b.filas.map((f, r) => new TableRow({ cantSplit: true, children: f.map((c, i) => celda(c, { w: ws[i], alt: r % 2 === 1, size, keepNext: (b.filas.length <= 8 && r < b.filas.length - 1) || (!!b.nota && r === b.filas.length - 1), align: num.includes(i) ? AlignmentType.CENTER : AlignmentType.LEFT })) })),
  ]
  const borde = { style: BorderStyle.SINGLE, size: 4, color: '8EAADB' }
  const out = [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 160, after: 80 }, keepNext: true, children: [new TextRun({ text: `Tabla ${nTab}. `, bold: true, font: FUENTE, size: 18 }), ...runs(b.titulo, { size: 18 })] }),
    new Table({ width: { size: ANCHO, type: WidthType.DXA }, columnWidths: ws, layout: TableLayoutType.FIXED, borders: { top: borde, bottom: borde, left: borde, right: borde, insideHorizontal: borde, insideVertical: borde }, rows: filas }),
  ]
  out.push(new Paragraph({ spacing: { after: 60 }, children: b.nota ? runs(`Nota: ${b.nota}`, { size: 16, italics: true }) : [] }))
  if (b.nota) contar(b.nota)
  return out
}

function bloque(b) {
  if (typeof b === 'string') return [P(b)]
  if (b.h2) return [H2(b.h2)]
  if (b.vinetas) return vinetas(b.vinetas)
  if (b.fig) return figura(b.fig)
  if (b.tabla) return tabla(b.tabla)
  if (b.salto) return [new Paragraph({ children: [new PageBreak()] })]
  throw new Error('bloque desconocido ' + JSON.stringify(b).slice(0, 80))
}

// referencias a figuras/tablas: {fig:id} {tab:id} se resuelven en una segunda pasada (se numeran en orden de aparicion)
function prenumerar(lista) {
  let f = 0
  let t = 0
  for (const b of lista) {
    if (b.fig) figIds[b.fig.id] = ++f
    if (b.tabla) tabIds[b.tabla.id] = ++t
  }
}
function sustituirRefs(obj) {
  const rep = (s) => s.replace(/\{fig:([\w-]+)\}/g, (_, id) => { if (!figIds[id]) throw new Error('fig ' + id); return `Fig. ${figIds[id]}` })
    .replace(/\{tab:([\w-]+)\}/g, (_, id) => { if (!tabIds[id]) throw new Error('tab ' + id); return `Tabla ${tabIds[id]}` })
  if (typeof obj === 'string') return rep(obj).replace(/\{\{([^}]+)\}\}/g, (_, r) => metrica(r))
  if (Array.isArray(obj)) return obj.map(sustituirRefs)
  if (obj && typeof obj === 'object') { const o = {}; for (const k in obj) o[k] = sustituirRefs(obj[k]); return o }
  return obj
}

// ---------- ensamblado ----------
const todos = [...secciones.flatMap((s) => s.bloques), ...anexos.flatMap((s) => s.bloques)]
prenumerar(todos)
const S = sustituirRefs(secciones)
const A = sustituirRefs(anexos)

const hijos = []
// Titulo y autores
hijos.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 200 }, children: [new TextRun({ text: meta.titulo, font: 'Calibri', bold: true, size: 32, color: AZUL })] }))
contar(meta.titulo)
palabras = { 'Título': palabras.Preliminares }
for (const a of meta.autores) {
  hijos.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 20 }, children: [new TextRun({ text: a.nombre, font: FUENTE, bold: true, size: 21 })] }))
  hijos.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 100 }, children: [new TextRun({ text: a.afiliacion, font: FUENTE, italics: true, size: 18 })] }))
}
// Resumen / Abstract
function resumen(titulo, texto, kwTitulo, kw) {
  seccionActual = titulo
  hijos.push(new Paragraph({ spacing: { before: 200, after: 80 }, border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: '8EAADB', space: 2 } }, children: [new TextRun({ text: titulo, font: 'Calibri', bold: true, size: 22, color: AZUL_T })] }))
  hijos.push(P(texto, { size: 20 }))
  hijos.push(new Paragraph({ spacing: { after: 160 }, children: [new TextRun({ text: kwTitulo + ': ', bold: true, font: FUENTE, size: 20 }), new TextRun({ text: kw, font: FUENTE, size: 20, italics: true })] }))
}
resumen('RESUMEN', meta.resumen, 'Palabras clave', meta.palabras_clave)
resumen('ABSTRACT', meta.abstract, 'Keywords', meta.keywords)

for (const s of S) {
  hijos.push(H1(s.titulo))
  for (const b of s.bloques) hijos.push(...bloque(b))
}

// Referencias
seccionActual = 'REFERENCIAS'
hijos.push(H1('REFERENCIAS'))
orden.forEach((k, i) => {
  hijos.push(new Paragraph({ alignment: AlignmentType.LEFT, spacing: { after: 60, line: 240 }, indent: { left: 540, hanging: 540 }, children: [new TextRun({ text: `[${i + 1}]\t`, font: FUENTE, size: 18 }), ...runs(REFS[k].ieee, { size: 18 })], tabStops: [{ type: 'left', position: 540 }] }))
})

for (const [i, s] of A.entries()) {
  if (i === 0) hijos.push(new Paragraph({ children: [new PageBreak()] }))
  hijos.push(H1(s.titulo))
  for (const b of s.bloques) hijos.push(...bloque(b))
}

const doc = new Document({
  creator: meta.autores[0].nombre,
  lastModifiedBy: meta.autores[0].nombre,
  title: meta.titulo,
  description: 'Artículo científico de investigación aplicada',
  styles: { default: { document: { run: { font: FUENTE, size: 21 } } } },
  numbering: { config: [{ reference: 'vinetas', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] }] },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1418, bottom: 1418, left: 1418, right: 1418, header: 700, footer: 700 } } },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: '8EAADB', space: 4 } }, children: [new TextRun({ text: meta.encabezado, font: FUENTE, italics: true, size: 16, color: '404040' })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: 'Página ', font: FUENTE, size: 16, color: AZUL_T }), new TextRun({ children: [PageNumber.CURRENT], font: FUENTE, size: 16, color: AZUL_T }), new TextRun({ text: ' | ', font: FUENTE, size: 16 }), new TextRun({ children: [PageNumber.TOTAL_PAGES], font: FUENTE, size: 16 })] })] }) },
    children: hijos,
  }],
})

const salida = path.join(ROOT, 'Articulo_Cientifico_Final.docx')
Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(salida, buf)
  const noCitadas = Object.keys(REFS).filter((k) => !orden.includes(k))
  fs.writeFileSync(path.join(DIR, 'control_construccion.json'), JSON.stringify({ palabras, figuras: nFig, tablas: nTab, referencias_citadas: orden.length, no_citadas: noCitadas }, null, 1))
  console.log('ok', salida)
  console.log('palabras por seccion', palabras)
  console.log('figuras', nFig, 'tablas', nTab, 'referencias', orden.length, 'no citadas', noCitadas)
})
