"""Predice el torneo 2027 completo (todos contra todos, ida y vuelta).

Supuestos (ajústalos abajo):
  - Bajan los DESCENSOS equipos con más probabilidad de descender en 2026.
  - Suben los equipos que pases con --ascienden (si no, "Ascendido 1", "Ascendido 2").
  - Un ascendido tiene la fuerza promedio de los equipos más débiles de Primera.
  - Las fuerzas se acercan al promedio (REGRESION): entre temporadas hay fichajes,
    cambios de DT, etc., así que el pasado predice peor el año siguiente.

Uso:
    python src/prediccion_2027.py
    python src/prediccion_2027.py --ascienden "Deportes Iquique" "Cobreloa"
"""
import argparse
import itertools

import numpy as np
import pandas as pd

from modelo import ModeloPoisson, cargar_partidos
from nombres import canonico
from simulacion import DESCENSOS, simular

REGRESION = 0.7
DEBILES_REF = 4


def fuerzas(modelo: ModeloPoisson) -> tuple[float, float, pd.DataFrame]:
    """Saca del GLM: base, localía y (ataque, defensa) de cada equipo, centrados en 0."""
    p = modelo.resultado.params
    base, local = p["Intercept"], p["es_local"]
    att = {e: p.get(f"C(equipo)[T.{e}]", 0.0) for e in modelo.equipos}
    dfn = {e: p.get(f"C(rival)[T.{e}]", 0.0) for e in modelo.equipos}
    f = pd.DataFrame({"ataque": att, "defensa": dfn})
    base += f["ataque"].mean() + f["defensa"].mean()
    f -= f.mean()
    return base, local, f


def simular_2027(equipos: list[str], f: pd.DataFrame, base: float, local: float,
                 n: int = 10_000, semilla: int = 0) -> pd.DataFrame:
    idx = {e: i for i, e in enumerate(equipos)}
    fixture = list(itertools.permutations(equipos, 2))
    il = np.array([idx[a] for a, _ in fixture])
    iv = np.array([idx[b] for _, b in fixture])

    att = f.loc[equipos, "ataque"].to_numpy()
    dfn = f.loc[equipos, "defensa"].to_numpy()
    lam_l = np.exp(base + local + att[il] + dfn[iv])
    lam_v = np.exp(base + att[iv] + dfn[il])

    rng = np.random.default_rng(semilla)
    gl = rng.poisson(lam_l, size=(n, len(fixture)))
    gv = rng.poisson(lam_v, size=(n, len(fixture)))

    t = len(equipos)
    pts, dif, gf = (np.zeros((n, t)) for _ in range(3))
    for k in range(len(fixture)):
        pts[:, il[k]] += np.select([gl[:, k] > gv[:, k], gl[:, k] == gv[:, k]], [3, 1], 0)
        pts[:, iv[k]] += np.select([gv[:, k] > gl[:, k], gl[:, k] == gv[:, k]], [3, 1], 0)
        dif[:, il[k]] += gl[:, k] - gv[:, k]
        dif[:, iv[k]] += gv[:, k] - gl[:, k]
        gf[:, il[k]] += gl[:, k]
        gf[:, iv[k]] += gv[:, k]

    puntaje = pts * 1e6 + dif * 1e3 + gf + rng.random(pts.shape) * 1e-3
    pos = (-puntaje).argsort(axis=1).argsort(axis=1) + 1

    return pd.DataFrame({
        "pts_esperados": pts.mean(axis=0).round(1),
        "pos_media": pos.mean(axis=0).round(1),
        "campeon": (pos == 1).mean(axis=0),
        "top3": (pos <= 3).mean(axis=0),
        "desciende": (pos > t - DESCENSOS).mean(axis=0),
    }, index=equipos).sort_values(["campeon", "pts_esperados"], ascending=False)


def proyectar_2027(ascienden: list[str] | None = None, n: int = 10_000):
    """Devuelve (tabla, bajan, suben) con la proyección del torneo 2027."""
    sim26 = simular(2026, 10_000)
    bajan = sim26.sort_values("desciende", ascending=False).index[:DESCENSOS].tolist()
    siguen = [e for e in sim26.index if e not in bajan]

    modelo = ModeloPoisson().entrenar(cargar_partidos())
    base, local, f = fuerzas(modelo)
    f = f * REGRESION

    suben = [canonico(e) for e in (ascienden or [])] or [f"Ascendido {i + 1}" for i in range(DESCENSOS)]
    fuerza = f.loc[siguen, "ataque"] - f.loc[siguen, "defensa"]
    ref = f.loc[fuerza.nsmallest(DEBILES_REF).index].mean()
    for e in suben:
        f.loc[e] = ref

    res = simular_2027(siguen + suben, f, base, local, n)
    return res, bajan, suben


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ascienden", nargs="*", default=[])
    ap.add_argument("-n", type=int, default=10_000)
    args = ap.parse_args()

    res, bajan, suben = proyectar_2027(args.ascienden, args.n)
    print(f"Bajan (estimado): {bajan}")
    print(f"Suben: {suben}\n")
    for c in ["campeon", "top3", "desciende"]:
        res[c] = (res[c] * 100).map(lambda x: f"{x:5.1f}%")
    print(f"Torneo 2027 — {len(res)} equipos — {args.n:,} simulaciones\n")
    print(res.to_string())
