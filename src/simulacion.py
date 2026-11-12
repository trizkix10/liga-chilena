"""Simula lo que queda del torneo miles de veces para estimar quién sale campeón.

Uso:
    python src/simulacion.py 2026            # 10.000 simulaciones
    python src/simulacion.py 2026 50000
"""
import sys

import numpy as np
import pandas as pd

from db import leer
from modelo import ModeloPoisson, cargar_partidos
from nombres import canonico

DESCENSOS = 2


def partidos_pendientes(temporada: int) -> pd.DataFrame:
    df = leer("SELECT local, visita FROM partidos WHERE temporada = :t AND estado = 'NS'", t=temporada)
    df["local"] = df["local"].map(canonico)
    df["visita"] = df["visita"].map(canonico)
    return df


def tabla_actual(jugados: pd.DataFrame) -> pd.DataFrame:
    pts_l = np.select([jugados.gl > jugados.gv, jugados.gl == jugados.gv], [3, 1], 0)
    pts_v = np.select([jugados.gv > jugados.gl, jugados.gl == jugados.gv], [3, 1], 0)
    filas = pd.concat([
        pd.DataFrame({"equipo": jugados.local, "pts": pts_l, "dif": jugados.gl - jugados.gv, "gf": jugados.gl}),
        pd.DataFrame({"equipo": jugados.visita, "pts": pts_v, "dif": jugados.gv - jugados.gl, "gf": jugados.gv}),
    ])
    return filas.groupby("equipo")[["pts", "dif", "gf"]].sum()


def simular(temporada: int, n: int = 10_000, semilla: int = 0) -> pd.DataFrame:
    todos = cargar_partidos()
    modelo = ModeloPoisson().entrenar(todos)
    jugados = todos[todos["temporada"] == temporada]
    pendientes = partidos_pendientes(temporada)

    base = tabla_actual(jugados)
    equipos = sorted(set(base.index) | set(pendientes.local) | set(pendientes.visita))
    base = base.reindex(equipos, fill_value=0)
    idx = {e: i for i, e in enumerate(equipos)}

    lam = np.array([modelo.goles_esperados(l, v) for l, v in zip(pendientes.local, pendientes.visita)])
    il = pendientes.local.map(idx).to_numpy()
    iv = pendientes.visita.map(idx).to_numpy()

    rng = np.random.default_rng(semilla)
    gl = rng.poisson(lam[:, 0], size=(n, len(pendientes)))
    gv = rng.poisson(lam[:, 1], size=(n, len(pendientes)))

    pts = np.tile(base["pts"].to_numpy(), (n, 1)).astype(float)
    dif = np.tile(base["dif"].to_numpy(), (n, 1)).astype(float)
    gf = np.tile(base["gf"].to_numpy(), (n, 1)).astype(float)
    for k in range(len(pendientes)):
        pts[:, il[k]] += np.select([gl[:, k] > gv[:, k], gl[:, k] == gv[:, k]], [3, 1], 0)
        pts[:, iv[k]] += np.select([gv[:, k] > gl[:, k], gl[:, k] == gv[:, k]], [3, 1], 0)
        dif[:, il[k]] += gl[:, k] - gv[:, k]
        dif[:, iv[k]] += gv[:, k] - gl[:, k]
        gf[:, il[k]] += gl[:, k]
        gf[:, iv[k]] += gv[:, k]

    puntaje = pts * 1e6 + dif * 1e3 + gf + rng.random(pts.shape) * 1e-3
    posiciones = (-puntaje).argsort(axis=1).argsort(axis=1) + 1

    t = len(equipos)
    res = pd.DataFrame({
        "pts_actuales": base["pts"].to_numpy(),
        "pts_esperados": pts.mean(axis=0).round(1),
        "campeon": (posiciones == 1).mean(axis=0),
        "top3": (posiciones <= 3).mean(axis=0),
        "desciende": (posiciones > t - DESCENSOS).mean(axis=0),
    }, index=equipos)
    res.attrs["pendientes"] = len(pendientes)
    return res.sort_values(["campeon", "pts_esperados"], ascending=False)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit()
    temporada = int(sys.argv[1])
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 10_000
    res = simular(temporada, n)
    print(f"Temporada {temporada} — {res.attrs['pendientes']} partidos pendientes — {n:,} simulaciones\n")
    tabla = res.copy()
    for c in ["campeon", "top3", "desciende"]:
        tabla[c] = (tabla[c] * 100).map(lambda x: f"{x:5.1f}%")
    print(tabla.to_string())
