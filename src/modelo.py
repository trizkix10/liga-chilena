"""Modelo Poisson para predecir partidos.

Idea: los goles de un equipo siguen una distribución de Poisson con media
    λ = exp(base + localía + ataque_equipo + defensa_rival)
Se ajusta con una regresión de Poisson (GLM) sobre los partidos guardados.

Uso:
    python src/modelo.py equipos
    python src/modelo.py predecir "Colo Colo" "Coquimbo"
    python src/modelo.py evaluar            # entrena 2022-2023, prueba en 2024
"""
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy.stats import poisson

from nombres import canonico, clave

RUTA_DB = Path(__file__).resolve().parent.parent / "data" / "liga.db"
MAX_GOLES = 10          # marcadores 0..10 para cada equipo
VIDA_MEDIA_DIAS = 365   # un partido de hace 1 año pesa la mitad que uno de hoy


# ---------- Datos ----------

def cargar_partidos() -> pd.DataFrame:
    con = sqlite3.connect(RUTA_DB)
    df = pd.read_sql(
        "SELECT * FROM partidos WHERE estado IN ('FT','AET','PEN') AND gl IS NOT NULL",
        con,
    )
    con.close()
    # Unificar nombres entre fuentes (API-Football / ESPN)
    df["local"] = df["local"].map(canonico)
    df["visita"] = df["visita"].map(canonico)
    df["fecha"] = pd.to_datetime(df["fecha"], utc=True, format="mixed")
    return df.sort_values("fecha").reset_index(drop=True)


def a_formato_largo(df: pd.DataFrame) -> pd.DataFrame:
    """Cada partido -> 2 filas: (equipo, rival, local?, goles)."""
    local = pd.DataFrame({"equipo": df["local"], "rival": df["visita"],
                          "es_local": 1, "goles": df["gl"], "fecha": df["fecha"]})
    visita = pd.DataFrame({"equipo": df["visita"], "rival": df["local"],
                           "es_local": 0, "goles": df["gv"], "fecha": df["fecha"]})
    return pd.concat([local, visita], ignore_index=True)


# ---------- Modelo ----------

class ModeloPoisson:
    def entrenar(self, df: pd.DataFrame) -> "ModeloPoisson":
        largo = a_formato_largo(df)
        # Peso por antigüedad: partidos recientes importan más
        dias = (largo["fecha"].max() - largo["fecha"]).dt.days
        pesos = 0.5 ** (dias / VIDA_MEDIA_DIAS)

        self.resultado = smf.glm(
            "goles ~ es_local + C(equipo) + C(rival)",
            data=largo,
            family=sm.families.Poisson(),
            freq_weights=pesos,
        ).fit()
        self.equipos = sorted(set(largo["equipo"]))
        return self

    def goles_esperados(self, local: str, visita: str) -> tuple[float, float]:
        filas = pd.DataFrame({
            "equipo":   [local, visita],
            "rival":    [visita, local],
            "es_local": [1, 0],
        })
        lam = self.resultado.predict(filas).to_numpy()
        return float(lam[0]), float(lam[1])

    def predecir(self, local: str, visita: str) -> dict:
        lam_l, lam_v = self.goles_esperados(local, visita)
        goles = np.arange(MAX_GOLES + 1)
        # Matriz: fila = goles local, columna = goles visita
        matriz = np.outer(poisson.pmf(goles, lam_l), poisson.pmf(goles, lam_v))

        i, j = np.unravel_index(matriz.argmax(), matriz.shape)
        return {
            "local": local,
            "visita": visita,
            "goles_esperados": (round(lam_l, 2), round(lam_v, 2)),
            "p_local": float(np.tril(matriz, -1).sum()),
            "p_empate": float(np.trace(matriz)),
            "p_visita": float(np.triu(matriz, 1).sum()),
            "marcador_probable": f"{i}-{j}",
        }


# ---------- Utilidades ----------

def buscar_equipo(nombre: str, equipos: list[str]) -> str:
    """Permite escribir 'coquimbo' en vez de 'Coquimbo Unido'."""
    coincidencias = [e for e in equipos if clave(nombre) in clave(e)]
    if len(coincidencias) == 1:
        return coincidencias[0]
    if not coincidencias:
        sys.exit(f"No encontré '{nombre}'. Usa: python src/modelo.py equipos")
    sys.exit(f"'{nombre}' es ambiguo: {coincidencias}")


def resultado_real(gl: int, gv: int) -> int:
    """0 = gana local, 1 = empate, 2 = gana visita."""
    return 0 if gl > gv else (1 if gl == gv else 2)


def evaluar() -> None:
    df = cargar_partidos()
    ultima = df["temporada"].max()
    train, test = df[df["temporada"] < ultima], df[df["temporada"] == ultima]
    print(f"Entrena con {sorted(int(t) for t in train['temporada'].unique())}, prueba en {ultima} ({len(test)} partidos)")

    modelo = ModeloPoisson().entrenar(train)
    conocidos = set(modelo.equipos)
    test = test[test["local"].isin(conocidos) & test["visita"].isin(conocidos)]
    print(f"Partidos evaluables (equipos conocidos): {len(test)}")

    probs, reales = [], []
    for _, p in test.iterrows():
        pr = modelo.predecir(p["local"], p["visita"])
        probs.append([pr["p_local"], pr["p_empate"], pr["p_visita"]])
        reales.append(resultado_real(p["gl"], p["gv"]))
    probs, reales = np.array(probs), np.array(reales)

    # Línea base: frecuencias históricas de L/E/V en el entrenamiento
    base = np.bincount([resultado_real(a, b) for a, b in zip(train["gl"], train["gv"])], minlength=3)
    base = base / base.sum()

    def log_loss(p):
        return -np.mean(np.log(np.clip(p[np.arange(len(reales)), reales], 1e-12, 1)))

    print(f"\n{'':<22}{'log loss':>10}{'acierto':>10}")
    print(f"{'Modelo Poisson':<22}{log_loss(probs):>10.3f}{(probs.argmax(1) == reales).mean():>10.1%}")
    print(f"{'Base (frecuencias)':<22}{log_loss(np.tile(base, (len(reales), 1))):>10.3f}{(reales == base.argmax()).mean():>10.1%}")
    print("\nlog loss: más bajo = mejor. Si el modelo no le gana a la base, algo anda mal.")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
    elif args[0] == "evaluar":
        evaluar()
    else:
        modelo = ModeloPoisson().entrenar(cargar_partidos())
        if args[0] == "equipos":
            print("\n".join(modelo.equipos))
        elif args[0] == "predecir" and len(args) == 3:
            local = buscar_equipo(args[1], modelo.equipos)
            visita = buscar_equipo(args[2], modelo.equipos)
            r = modelo.predecir(local, visita)
            print(f"{r['local']} vs {r['visita']}")
            print(f"  Goles esperados: {r['goles_esperados'][0]} - {r['goles_esperados'][1]}")
            print(f"  Local {r['p_local']:.1%} | Empate {r['p_empate']:.1%} | Visita {r['p_visita']:.1%}")
            print(f"  Marcador más probable: {r['marcador_probable']}")
        else:
            print(__doc__)
