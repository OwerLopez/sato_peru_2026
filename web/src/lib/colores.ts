// Paleta de los gráficos (coincide con los tokens de index.css).
// Nivel de riesgo: colores de estado, reservados para ALTO / MEDIO / BAJO.
export const COLOR_NIVEL = { ALTO: '#b42318', MEDIO: '#c4570f', BAJO: '#079455' } as const
// Series categóricas (orden fijo, validado para daltonismo y contraste en todas las parejas):
// azul, violeta y magenta. El magenta queda bajo 3:1 de contraste: se usa siempre con etiqueta o vista de tabla.
export const SERIE = ['#2a78d6', '#4a3aa7', '#e87ba4'] as const
export const COLORES = {
  marca: '#1f72b4',
  marcaOscuro: '#0f4c7f',
  marcaClaro: '#b7d4ee',
  gris: '#8a97a8',
  grisClaro: '#cbd5e1',
  rejilla: '#e5e9f0',
} as const
