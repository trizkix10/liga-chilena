"""Descarga partidos de API-Football y los guarda en SQLite.

Uso:
    python src/datos.py estado                      # cuota usada hoy
    python src/datos.py ligas                       # ligas de Chile y temporadas
    python src/datos.py descargar 265 2024 2025     # liga + temporadas
    python src/datos.py resumen                     # qué hay en la base
"""
import os
import sqlite3
import sys
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parent.parent
RUTA_DB = RAIZ / "data" / "liga.db"
URL_BASE = "https://v3.football.api-sports.io"


# ---------- Configuración ----------

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


def pedir(endpoint: str, **params) -> dict:
    """Hace un GET a la API y devuelve el JSON. Cada llamada gasta 1 de las 100 diarias."""
    key = os.environ.get("API_FOOTBALL_KEY")
    if not key:
        sys.exit("Falta API_FOOTBALL_KEY en .env")

    r = requests.get(
        f"{URL_BASE}/{endpoint}",
        headers={"x-apisports-key": key},
        params=params,
        timeout=30,
    )
    r.raise_for_status()
    datos = r.json()

    restantes = r.headers.get("x-ratelimit-requests-remaining")
    if restantes is not None:
        print(f"  (peticiones restantes hoy: {restantes})")

    # La API responde 200 aunque haya error; los errores vienen en "errors"
    if datos.get("errors"):
        print(f"  ⚠️  Error de la API: {datos['errors']}")
    return datos


# ---------- Base de datos ----------

def conectar() -> sqlite3.Connection:
    RUTA_DB.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(RUTA_DB)
    con.execute("""
        CREATE TABLE IF NOT EXISTS partidos (
            id         INTEGER PRIMARY KEY,   -- id del partido en la API
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
    """)
    return con


def guardar_partidos(con: sqlite3.Connection, respuesta: list) -> int:
    filas = []
    for p in respuesta:
        filas.append((
            p["fixture"]["id"],
            p["league"]["id"],
            p["league"]["season"],
            p["fixture"]["date"],
            p["league"]["round"],
            p["fixture"]["status"]["short"],
            p["teams"]["home"]["name"],
            p["teams"]["away"]["name"],
            p["goals"]["home"],
            p["goals"]["away"],
        ))
    # INSERT OR REPLACE: si el partido ya existe, lo actualiza (ej. se jugó)
    con.executemany(
        "INSERT OR REPLACE INTO partidos VALUES (?,?,?,?,?,?,?,?,?,?)", filas
    )
    con.commit()
    return len(filas)


# ---------- Comandos ----------

def cmd_estado() -> None:
    d = pedir("status")
    resp = d.get("response") or {}
    if resp:
        print("Plan:", resp["subscription"]["plan"])
        print("Usadas hoy:", resp["requests"]["current"], "/", resp["requests"]["limit_day"])


def cmd_ligas() -> None:
    d = pedir("leagues", country="Chile")
    for item in d.get("response", []):
        liga = item["league"]
        años = [s["year"] for s in item["seasons"]]
        print(f"{liga['id']:>5}  {liga['name']:<30} {liga['type']:<6} temporadas: {años[-6:]}")


def cmd_descargar(liga: int, temporadas: list[int]) -> None:
    con = conectar()
    for temporada in temporadas:
        print(f"Descargando liga {liga}, temporada {temporada}...")
        d = pedir("fixtures", league=liga, season=temporada)
        n = guardar_partidos(con, d.get("response", []))
        print(f"  {n} partidos guardados")
    con.close()


def cmd_resumen() -> None:
    con = conectar()
    filas = con.execute("""
        SELECT temporada,
               COUNT(*)                                   AS total,
               SUM(estado IN ('FT','AET','PEN'))           AS jugados
        FROM partidos GROUP BY temporada ORDER BY temporada
    """).fetchall()
    if not filas:
        print("La base está vacía. Usa: python src/datos.py descargar 265 2025")
    for temporada, total, jugados in filas:
        print(f"{temporada}: {total} partidos ({jugados} jugados)")
    con.close()


if __name__ == "__main__":
    cargar_env()
    args = sys.argv[1:]
    if not args:
        print(__doc__)
    elif args[0] == "estado":
        cmd_estado()
    elif args[0] == "ligas":
        cmd_ligas()
    elif args[0] == "descargar" and len(args) >= 3:
        cmd_descargar(int(args[1]), [int(a) for a in args[2:]])
    elif args[0] == "resumen":
        cmd_resumen()
    else:
        print(__doc__)
