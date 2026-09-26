// Prueba de rendimiento del prototipo (k6). Mide latencia y tasa de error de los endpoints de consulta principales.
//   k6 run --summary-export=docs/articulo/evaluacion/k6_resumen.json docs/articulo/evaluacion/k6_carga.js
// Variables: BASE (por defecto http://localhost:8080), VUS (usuarios virtuales), DUR (duracion).
import http from 'k6/http'
import { check, group } from 'k6'

const BASE = __ENV.BASE || 'http://localhost:8080'

export const options = {
  scenarios: {
    consulta: { executor: 'constant-vus', vus: Number(__ENV.VUS || 20), duration: __ENV.DUR || '60s' },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<1500'],
  },
}

export function setup() {
  const r = http.get(`${BASE}/api/v1/radar/cuaderno?limite=50`).json()
  return { ids: r.items.map((x) => x.cuaderno_id), preds: r.items.map((x) => x.prediccion_id) }
}

const DEPS = ['', 'AREQUIPA', 'LIMA', 'CUSCO', 'PIURA']

export default function (data) {
  const dep = DEPS[Math.floor(Math.random() * DEPS.length)]
  const q = dep ? `?departamento=${dep}` : ''
  const i = Math.floor(Math.random() * data.ids.length)
  group('radar', () => {
    check(http.get(`${BASE}/api/v1/resumen${q}`, { tags: { ep: 'resumen' } }), { ok: (r) => r.status === 200 })
    check(http.get(`${BASE}/api/v1/radar/cuaderno${q}${q ? '&' : '?'}limite=100`, { tags: { ep: 'radar_cuaderno' } }), { ok: (r) => r.status === 200 })
    check(http.get(`${BASE}/api/v1/radar/cartera${q}${q ? '&' : '?'}limite=100`, { tags: { ep: 'radar_cartera' } }), { ok: (r) => r.status === 200 })
  })
  group('ficha', () => {
    check(http.get(`${BASE}/api/v1/obras/${data.ids[i]}`, { tags: { ep: 'obra' } }), { ok: (r) => r.status === 200 })
    check(http.get(`${BASE}/api/v1/predicciones/${data.preds[i]}`, { tags: { ep: 'explicacion' } }), { ok: (r) => r.status === 200 })
    check(http.get(`${BASE}/api/v1/obras/${data.ids[i]}/asientos?q=paralizacion&tamanio=20`, { tags: { ep: 'busqueda_texto' } }), { ok: (r) => r.status === 200 })
  })
}
