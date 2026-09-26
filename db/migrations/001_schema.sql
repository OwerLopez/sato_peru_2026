-- SATO-AQP: esquema relacional de la plataforma (PostgreSQL >= 15)
-- Todas las tablas de datos se cargan desde el pipeline (sato.serving.load_db).
-- Datos de dominio: obras (cuadernos de obra digital) de Arequipa, sus asientos,
-- inversiones (MEF), ejecucion SIAF, INFOBRAS (foto), Contraloria (paralizadas),
-- predicciones, explicaciones y evidencia. Mas usuarios, revisiones y auditoria.

create extension if not exists pg_trgm;
create extension if not exists unaccent;

create schema if not exists sato;
set search_path to sato, public;

-- Configuracion de busqueda de texto en espanol sin tildes
do $$ begin
  if not exists (select 1 from pg_ts_config where cfgname = 'es_unaccent') then
    create text search configuration es_unaccent (copy = spanish);
    alter text search configuration es_unaccent alter mapping for hword, hword_part, word with unaccent, spanish_stem;
  end if;
end $$;

-- ---------------------------------------------------------------- linaje
create table fuente_archivo (
  id            serial primary key,
  fuente        text not null,              -- OECE, MEF, MEF-SIAF, INFOBRAS, CONTRALORIA, OECE-CONOSCE
  url           text not null,
  ruta          text not null,
  bytes         bigint,
  sha256        char(64),
  last_modified text,
  descargado_en timestamptz
);

create table corte_datos (
  id              serial primary key,
  fecha_corte     date not null,            -- ultimo dia con asientos observados
  generado_en     timestamptz not null default now(),
  descripcion     text
);

-- ---------------------------------------------------------------- actores
create table entidad (
  ruc     varchar(11) primary key,
  nombre  text not null,
  tipo    text
);

create table contratista (
  ruc     varchar(11) primary key,
  nombre  text not null
);

-- ---------------------------------------------------------------- inversion (MEF)
create table inversion (
  cui               varchar(10) primary key,
  nombre            text not null,
  funcion           text,
  sector            text,
  nivel_gobierno    text,
  tipo_inversion    text,
  monto_viable      numeric(16,2),
  costo_actualizado numeric(16,2),          -- foto a fecha_corte (no se usa en el modelo)
  estado            text,
  fuente            text,                   -- ACTIVO | CERRADO | DESACTIVADO
  departamento      text,
  provincia         text,
  distrito          text,
  ubigeo            varchar(6),
  latitud           double precision,
  longitud          double precision,
  fecha_corte       date
);

-- ---------------------------------------------------------------- obra = contrato con cuaderno de obra digital
create table obra (
  cuaderno_id         uuid primary key,
  contrato_id         text,
  expediente_id       text,
  denominacion        text not null,
  entidad_ruc         varchar(11) references entidad(ruc),
  contratista_ruc     varchar(11) references contratista(ruc),
  es_consorcio        boolean,
  ubigeo              varchar(6),
  departamento        text,
  provincia           text,
  distrito            text,
  latitud             double precision,
  longitud            double precision,
  cui                 varchar(10) references inversion(cui),
  cui_metodo_enlace   text,                 -- regex_cui | regex_snip | bare_7digit | fuzzy_tfidf
  cui_score_enlace    double precision,
  codigo_infobras     text,
  infobras_metodo     text,                 -- cui_ruc | cui_unico
  sector              text,
  plazo_original_dias integer,
  monto_contrato      numeric(16,2),
  url_contrato_seace  text,
  primer_asiento      date,
  ultimo_asiento      date,
  n_asientos          integer,
  historia_completa   boolean,
  fecha_atraso        date,                 -- onset del evento objetivo (primer asiento art.203/207)
  fecha_suspension    date,
  fecha_culminacion   date,
  fecha_recepcion     date,
  fecha_resolucion    date,
  estado_observado    text                  -- EN_EJECUCION | CULMINADA | RESUELTA | INACTIVA
);
create index obra_provincia_idx on obra (provincia);
create index obra_sector_idx on obra (sector);
create index obra_cui_idx on obra (cui);
create index obra_denominacion_trgm on obra using gin (denominacion gin_trgm_ops);

create table asiento (
  id              bigserial primary key,
  cuaderno_id     uuid not null references obra(cuaderno_id) on delete cascade,
  nro_asiento     integer,
  fecha           date not null,
  fecha_hora      timestamp,
  rol             text,
  tipo            text,
  tipo_std        text,
  titulo          text,
  descripcion     text,
  archivo_fuente  text,
  tsv             tsvector generated always as (
                    to_tsvector('sato.es_unaccent', coalesce(titulo, '') || ' ' || coalesce(descripcion, ''))) stored
);
create index asiento_obra_fecha_idx on asiento (cuaderno_id, fecha);
create index asiento_tipo_idx on asiento (tipo_std);
create index asiento_tsv_idx on asiento using gin (tsv);

-- ---------------------------------------------------------------- series y fotos de otras fuentes
create table siaf_mensual (
  cui        varchar(10) not null,
  anio       smallint not null,
  mes        smallint not null,
  devengado  numeric(16,2),
  primary key (cui, anio, mes)
);

create table infobras_obra (
  codigo_infobras            text primary key,
  cui                        varchar(10),
  nombre                     text,
  entidad                    text,
  estado_ejecucion           text,
  modalidad                  text,
  fecha_inicio_obra          date,
  fecha_fin_programada       date,
  fecha_fin_reprogramada     date,
  fecha_fin_real             date,
  plazo_dias                 integer,
  avance_fisico_programado   double precision,
  avance_fisico_real         double precision,
  existe_paralizacion        text,
  causal_paralizacion        text,
  fecha_paralizacion         date,
  n_modificaciones_plazo     integer,
  dias_modificacion_plazo    integer,
  n_adicionales              integer,
  fecha_consulta             date not null      -- foto: NO usar como dato historico
);
create index infobras_cui_idx on infobras_obra (cui);

create table contraloria_paralizada (
  id               serial primary key,
  fecha_corte      date not null,
  codigo_infobras  text,
  cui              varchar(10),
  descripcion_obra text,
  entidad          text,
  provincia        text,
  distrito         text,
  avance_fisico    double precision,
  causal           text,
  sector           text
);
create index contraloria_cui_idx on contraloria_paralizada (cui);

create table mef_seguimiento (
  id              bigserial primary key,
  cui             varchar(10) not null,
  fecha_registro  timestamp not null,
  tipo_registro   text,
  descripcion     text
);
create index mef_seguimiento_cui_idx on mef_seguimiento (cui, fecha_registro);

-- ---------------------------------------------------------------- modelos, predicciones, XAI y evidencia
create table modelo (
  id                 serial primary key,
  nombre             text not null,
  version            text not null,
  objetivo           text not null,           -- atraso | disrupcion
  horizonte_dias     integer not null,
  conjunto_features  text not null,
  algoritmo          text not null,
  entrenado_hasta    date not null,           -- ultimo corte T usado para entrenar
  entrenado_en       timestamptz not null default now(),
  umbral_alerta      double precision not null,
  metricas           jsonb not null,          -- metricas de test temporal ciego
  features           jsonb not null,
  artefacto          text,
  sha256             char(64),
  activo             boolean not null default false,
  unique (nombre, version)
);

create table prediccion (
  id            bigserial primary key,
  modelo_id     integer not null references modelo(id),
  cuaderno_id   uuid not null references obra(cuaderno_id) on delete cascade,
  fecha_corte   date not null,
  tipo          text not null check (tipo in ('backtest', 'vigente')),
  score         double precision not null,
  percentil     double precision,
  nivel         text not null check (nivel in ('ALTO', 'MEDIO', 'BAJO')),
  alerta        boolean not null,
  y_observado   smallint,                     -- 1/0 si el horizonte ya se observo; null si es futuro
  unique (modelo_id, cuaderno_id, fecha_corte)
);
create index prediccion_corte_idx on prediccion (fecha_corte, alerta);
create index prediccion_obra_idx on prediccion (cuaderno_id, fecha_corte);

create table explicacion (
  id             bigserial primary key,
  prediccion_id  bigint not null references prediccion(id) on delete cascade,
  rango          smallint not null,
  feature        text not null,
  grupo          text not null,
  valor          double precision,
  shap           double precision not null,
  descripcion    text not null
);
create index explicacion_pred_idx on explicacion (prediccion_id, rango);

create table evidencia (
  id             bigserial primary key,
  prediccion_id  bigint not null references prediccion(id) on delete cascade,
  feature        text not null,
  fuente         text not null,               -- ASIENTO | SIAF | MEF_SEGUIMIENTO | INFOBRAS | SEACE
  asiento_id     bigint references asiento(id),
  fecha          date,
  referencia     text,
  extracto       text
);
create index evidencia_pred_idx on evidencia (prediccion_id);

create table experimento_resultado (
  id              serial primary key,
  objetivo        text, horizonte integer, conjunto_features text, alcance_entrenamiento text,
  modelo          text, alcance_test text, metricas jsonb not null
);

create table comparacion_ab (
  id serial primary key,
  objetivo text, horizonte integer, variante text, alcance_test text, metrica text,
  a double precision, b double precision, diferencia double precision, ic_inf double precision, ic_sup double precision,
  p_valor double precision, filas integer, obras integer
);

-- ---------------------------------------------------------------- usuarios, revision humana y auditoria
create table usuario (
  id             serial primary key,
  email          text not null unique,
  nombre         text not null,
  rol            text not null check (rol in ('analista', 'admin')),
  password_hash  text not null,
  activo         boolean not null default true,
  creado_en      timestamptz not null default now()
);

-- Las revisiones se referencian por CLAVE NATURAL (obra, corte, version de modelo) y no por
-- prediccion.id, para que la recarga completa e idempotente de datos no las borre.
create table revision_alerta (
  id             bigserial primary key,
  cuaderno_id    uuid not null,
  fecha_corte    date not null,
  modelo_version text not null,
  usuario_id     integer not null references usuario(id),
  decision       text not null check (decision in ('CONFIRMADA', 'DESCARTADA', 'EN_SEGUIMIENTO')),
  comentario     text,
  creado_en      timestamptz not null default now()
);
create index revision_obra_idx on revision_alerta (cuaderno_id, fecha_corte);

create table auditoria (
  id          bigserial primary key,
  ts          timestamptz not null default now(),
  usuario_id  integer references usuario(id),
  accion      text not null,
  recurso     text,
  detalle     jsonb,
  ip          inet
);
create index auditoria_ts_idx on auditoria (ts);
