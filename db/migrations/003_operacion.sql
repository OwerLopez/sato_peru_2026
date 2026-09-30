-- 003: operacion autocontrolada y rendimiento
--   * historial de cargas con su validacion, conciliacion de registros y compuerta de integridad;
--   * latido de los servicios en segundo plano (worker) para saber si estan vivos;
--   * vigencia del enlace de confirmacion de suscripciones;
--   * vistas materializadas del riesgo vigente de cada obra (evitan un join lateral por fila en listados y agregados).
set search_path to sato, public;

create table if not exists carga_datos (
  id            bigserial primary key,
  inicio        timestamptz not null default now(),
  fin           timestamptz,
  estado        text not null check (estado in ('EN_CURSO', 'OK', 'RECHAZADA', 'ERROR')),
  conteos       jsonb,          -- filas cargadas por tabla
  conciliacion  jsonb,          -- filas de origen, cargadas y descartadas (con motivo) por tabla
  validacion    jsonb,          -- resultado de la validacion de entradas y de la compuerta de integridad
  mensaje       text
);
create index if not exists carga_datos_inicio_idx on carga_datos (inicio desc);

create table if not exists servicio_latido (
  servicio  text primary key,
  ts        timestamptz not null default now(),
  detalle   jsonb
);

alter table suscripcion add column if not exists token_creado_en timestamptz not null default now();

-- La restriccion unica original trataba los NULL como distintos: una suscripcion a "todo el Peru" (sin departamento)
-- podia repetirse y el correo recibia resumenes duplicados. Se conservan la confirmada o la mas antigua de cada grupo.
delete from suscripcion s using (
  select id, row_number() over (partition by email, departamento, provincia order by confirmada desc, id) rn from suscripcion) d
where s.id = d.id and d.rn > 1;
alter table suscripcion drop constraint if exists suscripcion_email_departamento_provincia_key;
alter table suscripcion add constraint suscripcion_ambito_unico unique nulls not distinct (email, departamento, provincia);

-- sincronizaciones rechazadas por la compuerta de integridad se distinguen de los errores
alter table sincronizacion drop constraint if exists sincronizacion_estado_check;
alter table sincronizacion add constraint sincronizacion_estado_check check (estado in ('EN_CURSO', 'OK', 'ERROR', 'RECHAZADA'));

-- limite de intentos de ingreso por cuenta (consulta por accion y fecha)
create index if not exists auditoria_accion_ts_idx on auditoria (accion, ts);

-- riesgo vigente de cada obra de la cartera: el modelo de seguimiento si existe, y el corte mas reciente
create materialized view if not exists cartera_riesgo_vigente as
  select distinct on (r.codigo_infobras)
         r.codigo_infobras, r.id riesgo_id, r.tipo modelo, r.fecha_corte, r.score, r.nivel
  from cartera_riesgo r
  order by r.codigo_infobras, (r.tipo = 'seguimiento') desc, r.fecha_corte desc;
create unique index if not exists cartera_riesgo_vigente_pk on cartera_riesgo_vigente (codigo_infobras);
create index if not exists cartera_riesgo_vigente_score_idx on cartera_riesgo_vigente (score desc);

-- ultima prediccion del modelo activo para cada obra con cuaderno de obra digital
create materialized view if not exists obra_prediccion_vigente as
  select distinct on (p.cuaderno_id)
         p.cuaderno_id, p.id prediccion_id, p.fecha_corte, p.score, p.nivel, p.alerta, p.percentil, p.tipo
  from prediccion p join modelo m on m.id = p.modelo_id and m.activo
  order by p.cuaderno_id, p.fecha_corte desc;
create unique index if not exists obra_prediccion_vigente_pk on obra_prediccion_vigente (cuaderno_id);
create index if not exists obra_prediccion_vigente_score_idx on obra_prediccion_vigente (score desc);

-- Indices de claves foraneas: sin ellos, borrar un registro referenciado obliga a recorrer toda la tabla hija
-- (con 2,4 millones de asientos, la recarga con DELETE quedaba detenida verificando evidencia.asiento_id).
create index if not exists evidencia_asiento_idx on evidencia (asiento_id);
create index if not exists obra_entidad_idx on obra (entidad_ruc);
create index if not exists obra_contratista_idx on obra (contratista_ruc);
create index if not exists auditoria_usuario_idx on auditoria (usuario_id);
create index if not exists revision_usuario_idx on revision_alerta (usuario_id);
create index if not exists envio_correo_suscripcion_idx on envio_correo (suscripcion_id);
