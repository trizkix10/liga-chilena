from pathlib import Path

import pandas as pd

RUTA_CSV = Path(__file__).resolve().parent.parent / "data" / "partidos.csv"


def puntos(goles_a: int, goles_b: int) -> int:
    """Puntos que obtiene el equipo A: 3 victoria, 1 empate, 0 derrota."""
    if goles_a > goles_b:
        return 3
    if goles_a == goles_b:
        return 1
    return 0


def tabla_posiciones(df: pd.DataFrame) -> pd.DataFrame:
    local = pd.DataFrame({
        "equipo": df["local"],
        "gf": df["gl"],
        "gc": df["gv"],
    })
    visita = pd.DataFrame({
        "equipo": df["visita"],
        "gf": df["gv"],
        "gc": df["gl"],
    })

    filas = pd.concat([local, visita], ignore_index=True)
    filas["pts"] = [puntos(a, b) for a, b in zip(filas["gf"], filas["gc"])]
    filas["pj"] = 1
    filas["pg"] = (filas["pts"] == 3).astype(int)
    filas["pe"] = (filas["pts"] == 1).astype(int)
    filas["pp"] = (filas["pts"] == 0).astype(int)

    tabla = filas.groupby("equipo")[["pj", "pg", "pe", "pp", "gf", "gc", "pts"]].sum()
    tabla["dif"] = tabla["gf"] - tabla["gc"]

    tabla = tabla.sort_values(["pts", "dif", "gf"], ascending=False)
    tabla.insert(0, "pos", range(1, len(tabla) + 1))
    return tabla


if __name__ == "__main__":
    partidos = pd.read_csv(RUTA_CSV)
    print(tabla_posiciones(partidos).to_string())
