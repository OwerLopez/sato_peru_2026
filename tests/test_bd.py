"""Pruebas de base de datos: migraciones sobre una base limpia, idempotencia, recuperacion ante fallos de carga
(reversion transaccional) e integridad referencial y de dominio de la base cargada."""

from __future__ import annotations

import os
import uuid
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest

from tests.conftest import requiere_bd, requiere_servidor

pytestmark = requiere_servidor


def _url_base(nombre: str) -> str:
    u = urlsplit(os.environ["SATO_DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://"))
    return urlunsplit(u._replace(path="/" + nombre))


@pytest.fixture
def base_limpia(monkeypatch):
    """Base de datos vacia y temporal en el mismo servidor; se elimina al terminar."""
    nombre = f"sato_prueba_{uuid.uuid4().hex[:8]}"
    admin = _url_base("postgres")
    with psycopg.connect(admin, autocommit=True) as c:
        c.execute(f'create database "{nombre}"')
    url = _url_base(nombre)
    monkeypatch.setenv("DATABASE_URL", url)
    try:
        yield url
    finally:
        with psycopg.connect(admin, autocommit=True) as c:
            c.execute(f'drop database if exists "{nombre}" with (force)')


def test_migraciones_en_base_limpia_e_idempotentes(base_limpia):
    from sato.serving.load_db import MIGRATIONS, migrate

    with psycopg.connect(base_limpia) as c:
        migrate(c)
        c.commit()
        migrate(c)  # segunda ejecucion: no aplica nada ni falla
        c.commit()
        aplicadas = [r[0] for r in c.execute("select version from public.schema_migrations order by 1")]
        assert aplicadas == sorted(f.name for f in MIGRATIONS.glob("*.sql"))
        tablas = {r[0] for r in c.execute("select table_name from information_schema.tables where table_schema = 'sato'")}
        assert {"obra", "asiento", "prediccion", "cartera_obra", "carga_datos", "servicio_latido", "suscripcion"} <= tablas
        vistas = {r[0] for r in c.execute("select matviewname from pg_matviews where schemaname = 'sato'")}
        assert vistas == {"cartera_riesgo_vigente", "obra_prediccion_vigente"}


def test_toda_clave_foranea_tiene_indice(base_limpia):
    """Regresion: sin indice en la tabla hija, cada DELETE del padre recorre la hija completa (la recarga quedaba detenida)."""
    from sato.serving.load_db import migrate

    with psycopg.connect(base_limpia) as c:
        migrate(c)
        c.commit()
        sin_indice = c.execute("""
            select c.conrelid::regclass::text || '.' || c.conname from pg_constraint c
            where c.contype = 'f' and c.connamespace = 'sato'::regnamespace
              and not exists (select 1 from pg_index i where i.indrelid = c.conrelid
                              and (i.indkey::int2[])[0:cardinality(c.conkey) - 1] @> c.conkey)""").fetchall()
        assert sin_indice == []


def test_restricciones_de_dominio(base_limpia):
    from sato.serving.load_db import migrate

    with psycopg.connect(base_limpia) as c:
        migrate(c)
        c.commit()
        with pytest.raises(psycopg.errors.CheckViolation):
            c.execute("insert into sato.usuario (email, nombre, rol, password_hash) values ('a@b.pe', 'x', 'superusuario', 'h')")
        c.rollback()
        with pytest.raises(psycopg.errors.CheckViolation):
            c.execute("insert into sato.sincronizacion (estado) values ('DESCONOCIDO')")
        c.rollback()
        c.execute("insert into sato.suscripcion (email, token) values ('a@b.pe', 't1')")
        with pytest.raises(psycopg.errors.UniqueViolation):  # "todo el Peru" (NULL) no se puede repetir
            c.execute("insert into sato.suscripcion (email, token) values ('a@b.pe', 't2')")
        c.rollback()


def test_carga_fallida_revierte_y_conserva_los_datos(base_limpia, monkeypatch):
    """Recuperacion: si la carga falla a mitad de camino, la base queda exactamente como estaba y el intento se registra."""
    from sato.config import CURATED
    from sato.serving import load_db

    if not (CURATED / "cuaderno.parquet").exists():
        pytest.skip("requiere los datos del pipeline (data/curated)")
    with psycopg.connect(base_limpia) as c:
        load_db.migrate(c)
        c.execute("insert into sato.corte_datos (fecha_corte, descripcion) values ('2026-01-31', 'corte previo')")
        c.commit()

    original = load_db.copy_df

    def falla_en_obra(conn, table, df):
        if table == "obra":
            raise RuntimeError("falla simulada durante la copia")
        return original(conn, table, df)

    monkeypatch.setattr(load_db, "copy_df", falla_en_obra)
    with pytest.raises(RuntimeError, match="falla simulada"):
        load_db.load()
    with psycopg.connect(base_limpia) as c:
        assert c.execute("select descripcion from sato.corte_datos").fetchall() == [("corte previo",)]
        assert c.execute("select count(*) from sato.entidad").fetchone()[0] == 0  # lo copiado antes del fallo se revirtio
        estado, msj = c.execute("select estado, mensaje from sato.carga_datos order by id desc limit 1").fetchone()
        assert estado == "ERROR" and "falla simulada" in msj


def test_entradas_invalidas_rechazan_la_carga_sin_tocar_la_base(base_limpia, monkeypatch):
    from sato.config import CURATED
    from sato.serving import load_db

    if not (CURATED / "cuaderno.parquet").exists():
        pytest.skip("requiere los datos del pipeline (data/curated)")
    monkeypatch.setitem(load_db.ENTRADAS, "cuaderno", (["cuaderno_id", "columna_que_no_existe"], "cuaderno_id"))
    with pytest.raises(load_db.CargaRechazada, match="columna_que_no_existe"):
        load_db.load()
    with psycopg.connect(base_limpia) as c:
        estado, val = c.execute("select estado, validacion from sato.carga_datos order by id desc limit 1").fetchone()
        assert estado == "RECHAZADA" and val["entradas"]
        assert c.execute("select count(*) from sato.obra").fetchone()[0] == 0


# ---------------------------------------------------------------- integridad de la base cargada


def _uno(sql: str):
    from sato.api import db

    return next(iter(db.one(sql).values()))


@requiere_bd
@pytest.mark.parametrize("nombre,sql", [
    ("prediccion sin obra", "select count(*) from prediccion p where not exists (select 1 from obra o where o.cuaderno_id = p.cuaderno_id)"),
    ("explicacion sin prediccion", "select count(*) from explicacion e where not exists (select 1 from prediccion p where p.id = e.prediccion_id)"),
    ("riesgo de cartera sin obra", "select count(*) from cartera_riesgo r where not exists (select 1 from cartera_obra c using (codigo_infobras))"
     .replace("using (codigo_infobras)", "where c.codigo_infobras = r.codigo_infobras")),
    ("probabilidad fuera de [0,1]", "select count(*) from prediccion where score < 0 or score > 1"),
    ("nivel inconsistente con el umbral", """select count(*) from prediccion p join modelo m on m.id = p.modelo_id
                                             where p.alerta <> (p.nivel = 'ALTO')"""),
    ("vigente con resultado observado", "select count(*) from prediccion where tipo = 'vigente' and y_observado is not null"),
    ("mas de un modelo activo", "select greatest(count(*) - 1, 0) from modelo where activo"),
    ("asientos fuera del cuaderno", "select count(*) from asiento a where not exists (select 1 from obra o where o.cuaderno_id = a.cuaderno_id)"),
    ("activa de cartera sin riesgo", """select count(*) from cartera_obra c where estado_operativo = 'ACTIVA'
                                        and not exists (select 1 from cartera_riesgo_vigente v where v.codigo_infobras = c.codigo_infobras)"""),
    ("obra con primer asiento posterior al ultimo", "select count(*) from obra where primer_asiento > ultimo_asiento"),
])
def test_integridad_de_la_base_cargada(nombre, sql):
    assert _uno(sql) == 0, nombre


@requiere_bd
def test_linaje_completo():
    assert _uno("select count(*) from fuente_archivo") > 0
    assert _uno("select count(*) from fuente_archivo where sha256 is null or length(sha256) <> 64") == 0
    assert _uno("select count(*) from corte_datos") == 1
