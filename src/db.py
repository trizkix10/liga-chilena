"""Conexión a la base de datos.

Si en .env existe DATABASE_URL se usa PostgreSQL (el de Docker).
Si no, se usa el archivo SQLite data/liga.db. El resto del código no cambia.
"""
import os
from functools import lru_cache
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

RAIZ = Path(__file__).resolve().parent.parent
RUTA_SQLITE = RAIZ / "data" / "liga.db"
COLUMNAS = ["id", "liga", "temporada", "fecha", "ronda", "estado", "local", "visita", "gl", "gv"]


def cargar_env() -> None:
    """Lee .env (CLAVE=valor) y lo pasa a variables de entorno."""
    ruta = RAIZ / ".env"
    if not ruta.exists():
        return
    for linea in ruta.read_text().splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#") and "=" in linea:
            clave, valor = linea.split("=", 1)
            os.environ.setdefault(clave.strip(), valor.strip())


@lru_cache
def motor() -> Engine:
    cargar_env()
    url = os.environ.get("DATABASE_URL")
    if not url:
        RUTA_SQLITE.parent.mkdir(exist_ok=True)
        url = f"sqlite:///{RUTA_SQLITE}"
    return create_engine(url)


def crear_tabla(eng: Engine | None = None) -> None:
    with (eng or motor()).begin() as con:
        con.execute(text("""
            CREATE TABLE IF NOT EXISTS partidos (
                id         BIGINT PRIMARY KEY,    -- id del partido (negativo = viene de ESPN)
                liga       INTEGER,
                temporada  INTEGER,
                fecha      TEXT,
                ronda      TEXT,
                estado     TEXT,                  -- FT = terminado, NS = no empezado
                local      TEXT,
                visita     TEXT,
                gl         INTEGER,
                gv         INTEGER
            )
        """))


def guardar(filas: list[tuple], eng: Engine | None = None) -> int:
    """Inserta partidos; si el id ya existe, lo actualiza (upsert)."""
    if not filas:
        return 0
    crear_tabla(eng)
    actualizar = ", ".join(f"{c} = excluded.{c}" for c in COLUMNAS[1:])
    sql = text(
        f"INSERT INTO partidos ({', '.join(COLUMNAS)}) "
        f"VALUES ({', '.join(':' + c for c in COLUMNAS)}) "
        f"ON CONFLICT (id) DO UPDATE SET {actualizar}"
    )
    with (eng or motor()).begin() as con:
        con.execute(sql, [dict(zip(COLUMNAS, f)) for f in filas])
    return len(filas)


def leer(sql: str, **params) -> pd.DataFrame:
    """Ejecuta un SELECT y devuelve un DataFrame. Parámetros con :nombre."""
    crear_tabla()
    with motor().connect() as con:
        return pd.read_sql(text(sql), con, params=params)


def descripcion() -> str:
    url = motor().url
    return "PostgreSQL" if url.get_backend_name() == "postgresql" else f"SQLite ({RUTA_SQLITE.name})"
