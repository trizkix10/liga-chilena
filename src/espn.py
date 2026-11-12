"""Descarga partidos de la API pública de ESPN (sin key) y los guarda en SQLite.

Uso:
    python src/espn.py descargar 2025 2026
"""
import calendar
import sys
import time

import requests

from db import guardar

URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/chi.1/scoreboard"
LIGA = 265  # mismo id que API-Football para que todo quede junto
SESION = requests.Session()  # reutiliza la conexión: más rápido


def pedir(fechas: str) -> list:
    r = SESION.get(URL, params={"dates": fechas}, timeout=30)
    r.raise_for_status()
    return r.json().get("events", [])


def pedir_mes(año: int, mes: int) -> list:
    """Intenta pedir el mes completo; si ESPN no acepta rangos, pide día por día."""
    ultimo = calendar.monthrange(año, mes)[1]
    try:
        return pedir(f"{año}{mes:02d}01-{año}{mes:02d}{ultimo}")
    except requests.HTTPError:
        eventos = []
        for dia in range(1, ultimo + 1):
            eventos += pedir(f"{año}{mes:02d}{dia:02d}")
            time.sleep(0.15)
        return eventos


def a_fila(evento: dict, temporada: int) -> tuple | None:
    comp = evento["competitions"][0]
    equipos = {c["homeAway"]: c for c in comp["competitors"]}
    if "home" not in equipos or "away" not in equipos:
        return None

    terminado = comp["status"]["type"]["completed"]
    gl = int(equipos["home"]["score"]) if terminado else None
    gv = int(equipos["away"]["score"]) if terminado else None
    return (
        -int(evento["id"]),          # id negativo: no choca con los de API-Football
        LIGA,
        temporada,
        evento["date"],
        None,                        # ESPN no trae la ronda en este endpoint
        "FT" if terminado else "NS",
        equipos["home"]["team"]["displayName"],
        equipos["away"]["team"]["displayName"],
        gl,
        gv,
    )


def descargar(temporada: int) -> None:
    filas = []
    for mes in range(1, 13):
        eventos = pedir_mes(temporada, mes)
        filas += [f for e in eventos if (f := a_fila(e, temporada))]
        print(f"  {temporada}-{mes:02d}: {len(eventos)} partidos")
        time.sleep(0.5)  # no saturar a ESPN

    guardar(filas)
    jugados = sum(1 for f in filas if f[5] == "FT")
    print(f"Temporada {temporada}: {len(filas)} partidos ({jugados} jugados)")


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) >= 2 and args[0] == "descargar":
        for t in args[1:]:
            descargar(int(t))
    else:
        print(__doc__)
