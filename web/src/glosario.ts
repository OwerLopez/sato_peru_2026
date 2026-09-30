// Glosario único de la plataforma: alimenta la ayuda contextual (ícono de información) y la página de ayuda.
export const GLOSARIO = {
  atraso_formal: {
    termino: 'Atraso formal (causal del 80 %)',
    definicion:
      'Asiento del cuaderno de obra que registra que lo ejecutado acumulado es menor al 80 % de lo programado, o que se ordena un calendario acelerado. Es la señal de atraso que exige la norma (Reglamento de la Ley 30225, art. 203; Reglamento de la Ley 32069, art. 207).',
  },
  retraso_significativo: {
    termino: 'Retraso significativo al término',
    definicion: 'La obra termina después de su fecha programada original más un 30 % adicional de su plazo original. Se usa para la cartera INFOBRAS.',
  },
  probabilidad: {
    termino: 'Probabilidad estimada',
    definicion:
      'Estimación del modelo de que ocurra el evento, calculada solo con información disponible a la fecha del corte. Es una estimación, no una certeza: indica qué obras revisar primero.',
  },
  nivel: {
    termino: 'Nivel de riesgo (alto, medio, bajo)',
    definicion:
      'Tramos de la probabilidad estimada. Los umbrales se fijaron con datos de validación, antes de medir el desempeño, y su tasa real de acierto se muestra en la sección de validación.',
  },
  escala: {
    termino: 'Posición relativa (1 a 10)',
    definicion: 'Ubica la obra entre todas las evaluadas en el mismo corte: 10 significa que está en el 10 % de mayor riesgo; 1, en el 10 % de menor riesgo.',
  },
  veces_promedio: {
    termino: 'Veces el promedio',
    definicion: 'Cuántas veces es mayor (o menor) la probabilidad de esta obra frente a la tasa promedio observada en el periodo de validación.',
  },
  confiabilidad: {
    termino: 'Confiabilidad del nivel',
    definicion:
      'Proporción de obras de ese nivel que realmente tuvieron el evento en la simulación con datos pasados (backtest): el modelo se aplicó mes a mes solo con información de esa fecha y luego se comparó con lo ocurrido.',
  },
  factor: {
    termino: 'Factor explicativo',
    definicion:
      'Dato real de la obra que más movió la estimación. Se calcula con TreeSHAP, un método que reparte la predicción entre las variables. Indica asociación estadística, no una causa comprobada.',
  },
  cuaderno: {
    termino: 'Cuaderno de obra digital',
    definicion: 'Registro oficial y obligatorio de las ocurrencias de una obra por contrata, publicado como datos abiertos por el OECE desde junio de 2024.',
  },
  cartera: {
    termino: 'Cartera INFOBRAS',
    definicion: 'Registro nacional de obras públicas de la Contraloría General de la República. Incluye todas las modalidades de ejecución (contrata, administración directa, núcleo ejecutor, obras por impuestos).',
  },
  cui: {
    termino: 'CUI',
    definicion: 'Código Único de Inversión asignado por el MEF (Invierte.pe) a cada proyecto de inversión pública.',
  },
  devengado: {
    termino: 'Devengado (SIAF)',
    definicion: 'Gasto reconocido como obligación de pago en el Sistema Integrado de Administración Financiera del MEF. Se usa con un mes de rezago.',
  },
  pia: { termino: 'PIA', definicion: 'Presupuesto Institucional de Apertura: presupuesto asignado a la inversión al inicio del año.' },
  corte: {
    termino: 'Corte',
    definicion: 'Fecha a la que corresponde la predicción. El modelo solo usa datos registrados hasta esa fecha.',
  },
  backtest: {
    termino: 'Validación con datos pasados (backtest)',
    definicion:
      'Simulación de cómo habría funcionado el sistema: en cada mes del pasado se estimó el riesgo solo con la información de esa fecha y luego se comparó con lo que realmente ocurrió.',
  },
  roc_auc: {
    termino: 'ROC-AUC',
    definicion:
      'Probabilidad de que el modelo asigne más riesgo a una obra que sí tuvo el evento que a una que no lo tuvo. 0.5 equivale al azar y 1 a un orden perfecto.',
  },
  pr_auc: {
    termino: 'PR-AUC',
    definicion: 'Resume la precisión obtenida al revisar cada vez más obras en orden de riesgo. Debe compararse con la tasa promedio del evento (valor del azar).',
  },
  calibracion: {
    termino: 'Calibración',
    definicion: 'Coincidencia entre la probabilidad estimada y la frecuencia real: si el modelo dice 20 %, alrededor de 20 de cada 100 obras deberían tener el evento.',
  },
  intervalo: {
    termino: 'Intervalo de confianza (IC 95 %)',
    definicion: 'Rango de valores compatible con los datos al remuestrear las obras 1 000 veces (bootstrap). Si no incluye el cero, la diferencia es estadísticamente consistente.',
  },
  deriva: {
    termino: 'Cambio en los datos de entrada (PSI)',
    definicion:
      'Índice de estabilidad poblacional: compara cómo se distribuye cada variable en el último corte frente al periodo con el que se entrenó el modelo. Por debajo de 0,10 no hay cambio relevante; entre 0,10 y 0,25 hay un cambio moderado; sobre 0,25 el cambio es grande y conviene evaluar un reentrenamiento.',
  },
  deteccion: {
    termino: 'Atrasos anticipados',
    definicion:
      'De las obras que registraron el atraso formal en los 60 días siguientes a un corte, proporción que ya estaba en nivel alto en ese corte. Solo se calcula para cortes cuyo plazo de 60 días ya venció.',
  },
  compuerta: {
    termino: 'Compuerta de integridad',
    definicion:
      'Control automático que se ejecuta antes de publicar cada actualización de datos. Si una tabla importante pierde más del 20 % de sus filas o falla un chequeo crítico, la actualización se descarta y se siguen mostrando los datos anteriores.',
  },
  conciliacion: {
    termino: 'Conciliación de registros',
    definicion: 'Cuenta de filas de cada fuente: cuántas llegaron, cuántas se cargaron y cuántas se descartaron y por qué. Permite comprobar que no se pierden registros sin explicación.',
  },
} as const

export type Termino = keyof typeof GLOSARIO
