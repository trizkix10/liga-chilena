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

REGRESION = 0.7       # 1 = las fuerzas de 2026 se mantienen igual; 0 = todos iguales
DEBILES_REF = 4       # un ascendido vale como el promedio de los 4 más débiles


def fuerzas(modelo: ModeloPoisson) -> tuple[float, float, pd.DataFrame]:
    """Saca del GLM: base, localía y (ataque, defensa) de cada equipo, centrados en 0."""
    p = modelo.resultado.params
    base, local = p["Intercept"], p["es_local"]
    att = {e: p.get(f"C(equipo)[T.{e}]", 0.0) for e in modelo.equipos}
    dfn = {e: p.get(f"C(rival)[T.{e}]", 0.0) for e in modelo.equipos}
    f = pd.DataFrame({"ataque": att, "defensa": dfn})
    # Centrar: el promedio de la liga queda en la base
    base += f["ataque"].mean() + f["defensa"].mean()
    f -= f.mean()
    return base, local, f


def simular_2027(equipos: list[str], f: pd.DataFrame, base: float, local: float,
                 n: int = 10_000, semilla: int = 0) -> pd.DataFrame:
    idx = {e: i for i, e in enumerate(equipos)}
    fixture = list(itertools.permutations(equipos, 2))   # ida y vuelta
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


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ascienden", nargs="*", default=[])
    ap.add_argument("-n", type=int, default=10_000)
    args = ap.parse_args()

    # 1) Quién baja: los más probables según la simulación de 2026
    sim26 = simular(2026, 10_000)
    bajan = sim26.sort_values("desciende", ascending=False).index[:DESCENSOS].tolist()
    siguen = [e for e in sim26.index if e not in bajan]

    # 2) Fuerzas con todos los datos, acercadas al promedio
    modelo = ModeloPoisson().entrenar(cargar_partidos())
    base, local, f = fuerzas(modelo)
    f = f * REGRESION

    # 3) Ascendidos
    suben = [canonico(e) for e in args.ascienden] or [f"Ascendido {i + 1}" for i in range(DESCENSOS)]
    # ataque alto = bueno; defensa alta = recibe más goles = malo -> fuerza = ataque - defensa
    fuerza = f.loc[siguen, "ataque"] - f.loc[siguen, "defensa"]
    debiles = fuerza.nsmallest(DEBILES_REF).index
    ref = f.loc[debiles].mean()
    for e in suben:
        f.loc[e] = ref  # si ya existe (ej. jugó Primera antes) igual usa la referencia de ascendido

    equipos = siguen + suben
    print(f"Bajan (estimado): {bajan}")
    print(f"Suben: {suben}\n")

    res = simular_2027(equipos, f, base, local, args.n)
    for c in ["campeon", "top3", "desciende"]:
        res[c] = (res[c] * 100).map(lambda x: f"{x:5.1f}%")
    print(f"Torneo 2027 — {len(equipos)} equipos — {args.n:,} simulaciones\n")
    print(res.to_string())
