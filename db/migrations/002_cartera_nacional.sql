-- SATO 2.0: cartera nacional INFOBRAS (todas las modalidades), modelos de inicio y seguimiento,
-- simulador de sensibilidad, suscripciones, sincronizacion y configuracion.
set search_path to sato, public;

create table if not exists cartera_obra (
  codigo_infobras         text primary key,
  cui                     text,            -- tal como lo publica INFOBRAS (puede contener errores de digitacion)
  nombre                  text not null,
  entidad                 text,
  codigo_entidad          text,
  ruc_ejecucion           text,
  contratista             text,
  departamento            text,
  provincia               text,
  distrito                text,
  estado_ejecucion        text,
  estado_operativo        text,            -- ACTIVA | CONSUMADO | FINALIZADA | DESACTUALIZADA | OTRO
  fecha_inicio            date,
  plazo_dias              integer,
  fin_programado          date,
  fin_real                date,
  sobreplazo              double precision, -- (fin real - fin programado) / plazo
  costo                   numeric(16,2),
  modalidad               text,
  tipo_obra               text,
  retraso_significativo   smallint,         -- etiqueta observada (umbral 30 %); null si aun no determinable
  latitud                 double precision,
  longitud                double precision,
  cuaderno_id             uuid
);
create index if not exists cartera_dep_idx on cartera_obra (departamento, provincia);
create index if not exists cartera_estado_idx on cartera_obra (estado_operativo);
create index if not exists cartera_nombre_trgm on cartera_obra using gin (nombre gin_trgm_ops);

create table if not exists cartera_riesgo (
  id               bigserial primary key,
  codigo_infobras  text not null references cartera_obra(codigo_infobras) on delete cascade,
  tipo             text not null check (tipo in ('inicio', 'seguimiento')),
  fecha_corte      date not null,
  score            double precision not null,
  nivel            text not null check (nivel in ('ALTO', 'MEDIO', 'BAJO')),
  y_observado      smallint,
  modelo_origen    text
);
create index if not exists cartera_riesgo_obra_idx on cartera_riesgo (codigo_infobras, tipo, fecha_corte);
create index if not exists cartera_riesgo_corte_idx on cartera_riesgo (tipo, fecha_corte);

create table if not exists cartera_explicacion (
  id               bigserial primary key,
  riesgo_id        bigint not null references cartera_riesgo(id) on delete cascade,
  rango            smallint not null,
  feature          text not null,
  grupo            text not null,
  valor            double precision,
  shap             double precision not null,
  descripcion      text not null
);
create index if not exists cartera_expl_idx on cartera_explicacion (riesgo_id, rango);

create table if not exists simulacion (
  id               bigserial primary key,
  prediccion_id    bigint not null references prediccion(id) on delete cascade,
  escenario        text not null,
  descripcion      text not null,
  score_base       double precision not null,
  score_escenario  double precision not null,
  alerta_escenario boolean not null
);
create index if not exists simulacion_pred_idx on simulacion (prediccion_id);

create table if not exists configuracion (
  clave  text primary key,
  valor  jsonb not null
);

create table if not exists suscripcion (
  id            bigserial primary key,
  email         text not null,
  departamento  text,
  provincia     text,
  token         text not null unique,
  confirmada    boolean not null default false,
  activa        boolean not null default true,
  creado_en     timestamptz not null default now(),
  ultimo_envio  timestamptz,
  unique (email, departamento, provincia)
);

create table if not exists sincronizacion (
  id           bigserial primary key,
  inicio       timestamptz not null default now(),
  fin          timestamptz,
  estado       text not null check (estado in ('EN_CURSO', 'OK', 'ERROR')),
  pasos        jsonb,
  mensaje      text,
  corte_datos  date
);

create table if not exists envio_correo (
  id            bigserial primary key,
  suscripcion_id bigint references suscripcion(id) on delete cascade,
  enviado_en    timestamptz not null default now(),
  modo          text not null,           -- smtp | archivo (sin SMTP configurado)
  obras         integer not null,
  destino       text
);

create index if not exists obra_departamento_idx on obra (departamento);
