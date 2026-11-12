"""Descarga partidos de API-Football y los guarda en SQLite.

Uso:
    python src/datos.py estado                      # cuota usada hoy
    python src/datos.py ligas                       # ligas de Chile y temporadas
    python src/datos.py descargar 265 2024 2025     # liga + temporadas
    python src/datos.py resumen                     # qué hay en la base
"""
import os
import sys

import requests

from db import cargar_env, descripcion, guardar, leer

URL_BASE = "https://v3.football.api-sports.io"


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

    if datos.get("errors"):
        print(f"  ⚠️  Error de la API: {datos['errors']}")
    return datos


def a_filas(respuesta: list) -> list[tuple]:
    """Saca del JSON de la API solo las columnas de la tabla partidos."""
    return [(
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
    ) for p in respuesta]


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
    for temporada in temporadas:
        print(f"Descargando liga {liga}, temporada {temporada}...")
        d = pedir("fixtures", league=liga, season=temporada)
        n = guardar(a_filas(d.get("response", [])))
        print(f"  {n} partidos guardados")


def cmd_resumen() -> None:
    df = leer("""
        SELECT temporada,
               COUNT(*) AS total,
               SUM(CASE WHEN estado IN ('FT','AET','PEN') THEN 1 ELSE 0 END) AS jugados
        FROM partidos GROUP BY temporada ORDER BY temporada
    """)
    print(f"Base de datos: {descripcion()}")
    if df.empty:
        print("La base está vacía. Usa: python src/datos.py descargar 265 2024")
    for f in df.itertuples():
        print(f"{f.temporada}: {f.total} partidos ({f.jugados} jugados)")


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
