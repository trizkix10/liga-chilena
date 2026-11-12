"""Calcula todo y lo guarda en web/datos.js para la página HTML.

La página (web/index.html) no necesita servidor: lee datos.js y calcula
la predicción de cualquier partido en el navegador.

Uso:
    python src/exportar.py
    open web/index.html
"""
import json
from datetime import date
from pathlib import Path

import pandas as pd

from db import leer
from modelo import ModeloPoisson, cargar_partidos
from nombres import canonico
from prediccion_2027 import fuerzas, proyectar_2027
from simulacion import simular, tabla_actual

TEMPORADA = 2026
RUTA_SALIDA = Path(__file__).resolve().parent.parent / "web" / "datos.js"


def pendientes_con_fecha(temporada: int) -> pd.DataFrame:
    df = leer(
        "SELECT fecha, local, visita FROM partidos WHERE temporada = :t AND estado = 'NS' ORDER BY fecha",
        t=temporada,
    )
    df["local"] = df["local"].map(canonico)
    df["visita"] = df["visita"].map(canonico)
    df["fecha"] = (pd.to_datetime(df["fecha"], utc=True, format="mixed")
                   .dt.tz_convert("America/Santiago").dt.strftime("%Y-%m-%d"))
    return df


def a_registros(df: pd.DataFrame) -> list[dict]:
    return json.loads(df.reset_index(names="equipo").to_json(orient="records"))


if __name__ == "__main__":
    partidos = cargar_partidos()
    modelo = ModeloPoisson().entrenar(partidos)
    base, local, f = fuerzas(modelo)

    actuales = partidos[partidos["temporada"] == TEMPORADA]
    equipos = sorted(set(actuales["local"]) | set(actuales["visita"]))

    tabla = tabla_actual(actuales)
    sim = simular(TEMPORADA)
    sim["dif"] = tabla["dif"].reindex(sim.index).fillna(0).astype(int)
    sim["pj"] = pd.concat([actuales["local"], actuales["visita"]]).value_counts().reindex(sim.index).fillna(0).astype(int)

    res27, bajan, suben = proyectar_2027()

    datos = {
        "generado": date.today().isoformat(),
        "temporada": TEMPORADA,
        "partidos_usados": len(partidos),
        "temporadas": sorted(int(t) for t in partidos["temporada"].unique()),
        "base": round(float(base), 4),
        "local": round(float(local), 4),
        "fuerzas": {e: {"a": round(float(f.loc[e, "ataque"]), 4), "d": round(float(f.loc[e, "defensa"]), 4)}
                    for e in equipos},
        "pendientes": pendientes_con_fecha(TEMPORADA).to_dict(orient="records"),
        "campeonato": a_registros(sim),
        "torneo2027": {"bajan": bajan, "suben": suben, "tabla": a_registros(res27)},
    }

    RUTA_SALIDA.parent.mkdir(exist_ok=True)
    RUTA_SALIDA.write_text("const DATOS = " + json.dumps(datos, ensure_ascii=False, indent=1) + ";\n", encoding="utf-8")
    print(f"Listo: {RUTA_SALIDA} ({len(equipos)} equipos, {len(datos['pendientes'])} partidos pendientes)")
