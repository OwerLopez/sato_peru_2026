import { describe, expect, it } from 'vitest'
import { claveDatos } from './estatico'

// Claves calculadas por scripts/exportar_estatico.py (clave()): la copia estatica solo funciona si ambos lados coinciden.
describe('claveDatos coincide con el exportador', () => {
  it.each([
    ['/ambitos', 'b45bde2d3b2e7507'],
    ['/obras?solo_vigentes=true&pagina=1&tamanio=25', '6ded44471447b8ad'],
    ['/obras?departamento=SAN+MARTIN&nivel=ALTO', '8a761fb5697fcb37'],
    ['/ambitos/SAN%20MARTIN/provincias', '932fedf3bb3732b9'],
    ['/buscar?q=colegio%20%C3%B1', '453f4dd351202b41'],
  ])('%s', (ruta, clave) => {
    expect(claveDatos(ruta)).toBe(clave)
  })

  it('no depende del orden de los parametros', () => {
    expect(claveDatos('/obras?tamanio=25&pagina=1&solo_vigentes=true')).toBe(claveDatos('/obras?solo_vigentes=true&pagina=1&tamanio=25'))
  })
})
