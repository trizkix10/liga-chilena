"""Copia los partidos de SQLite (data/liga.db) a PostgreSQL.

Uso (con Docker corriendo y DATABASE_URL en .env):
    python src/migrar.py
"""
import sys

import pandas as pd
from sqlalchemy import create_engine

from db import COLUMNAS, RUTA_SQLITE, descripcion, guardar, leer, motor

if __name__ == "__main__":
    if motor().url.get_backend_name() != "postgresql":
        sys.exit("Falta DATABASE_URL en .env (o no apunta a PostgreSQL).")
    if not RUTA_SQLITE.exists():
        sys.exit(f"No existe {RUTA_SQLITE}")

    origen = create_engine(f"sqlite:///{RUTA_SQLITE}")
    df = pd.read_sql("SELECT * FROM partidos", origen)[COLUMNAS]
    df = df.astype(object).where(df.notna(), None)   # NaN -> NULL
    n = guardar(list(df.itertuples(index=False, name=None)))

    total = int(leer("SELECT COUNT(*) AS n FROM partidos")["n"][0])
    print(f"{n} partidos copiados a {descripcion()}. Total en la tabla: {total}")
