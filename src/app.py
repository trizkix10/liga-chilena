"""Página del Predictor Liga Chilena.

Uso:
    streamlit run src/app.py
"""
import numpy as np
import pandas as pd
import streamlit as st
from scipy.stats import poisson

from modelo import ModeloPoisson, cargar_partidos
from prediccion_2027 import proyectar_2027
from simulacion import partidos_pendientes, simular

TEMPORADA = 2026

st.set_page_config(page_title="Predictor Liga Chilena", page_icon="⚽", layout="centered")


# ---------- Cálculos (se guardan en caché para no repetirlos) ----------

@st.cache_resource
def obtener_modelo() -> ModeloPoisson:
    return ModeloPoisson().entrenar(cargar_partidos())


@st.cache_data
def obtener_simulacion(temporada: int) -> pd.DataFrame:
    return simular(temporada)


@st.cache_data
def obtener_pendientes(temporada: int) -> pd.DataFrame:
    return partidos_pendientes(temporada)


@st.cache_data
def obtener_2027(ascienden: tuple[str, ...]):
    return proyectar_2027(list(ascienden))


def equipos_actuales() -> list[str]:
    """Equipos que juegan la temporada actual (no los que ya descendieron)."""
    df = cargar_partidos()
    df = df[df["temporada"] == TEMPORADA]
    return sorted(set(df["local"]) | set(df["visita"]))


def tabla_probabilidades(df: pd.DataFrame, columnas: dict[str, str]) -> None:
    """Muestra una tabla donde las columnas de probabilidad se ven como barras."""
    config = {
        col: st.column_config.ProgressColumn(titulo, min_value=0, max_value=100, format="%.1f%%")
        for col, titulo in columnas.items()
    }
    vista = df.copy()
    for col in columnas:
        vista[col] = vista[col] * 100
    st.dataframe(vista, column_config=config, width="stretch", height=38 * (len(vista) + 1))


# ---------- Página ----------

st.title("⚽ Predictor Liga Chilena")
st.caption("Modelo Poisson entrenado con los partidos de Primera División desde 2022.")

modelo = obtener_modelo()
equipos = equipos_actuales()

tab_partido, tab_fecha, tab_torneo, tab_2027 = st.tabs(
    ["Partido", "Partidos pendientes", f"Campeonato {TEMPORADA}", "Torneo 2027"]
)

# ----- Pestaña 1: un partido -----
with tab_partido:
    col_l, col_v = st.columns(2)
    local = col_l.selectbox("Local", equipos, index=0)
    visita = col_v.selectbox("Visita", equipos, index=1)

    if local == visita:
        st.warning("Elige dos equipos distintos.")
    else:
        r = modelo.predecir(local, visita)
        gl, gv = r["goles_esperados"]

        c1, c2, c3 = st.columns(3)
        c1.metric(f"Gana {local}", f"{r['p_local']:.0%}")
        c2.metric("Empate", f"{r['p_empate']:.0%}")
        c3.metric(f"Gana {visita}", f"{r['p_visita']:.0%}")

        c1, c2, c3 = st.columns(3)
        c1.metric(f"Goles esperados {local}", f"{gl:.2f}")
        c2.metric("Marcador más probable", r["marcador_probable"])
        c3.metric(f"Goles esperados {visita}", f"{gv:.2f}")

        st.subheader("Marcadores más probables")
        goles = np.arange(6)
        matriz = np.outer(poisson.pmf(goles, gl), poisson.pmf(goles, gv))
        marcadores = pd.DataFrame(
            [(f"{i}-{j}", matriz[i, j] * 100) for i in goles for j in goles],
            columns=["Marcador", "Probabilidad"],
        ).nlargest(8, "Probabilidad")
        st.dataframe(
            marcadores,
            hide_index=True,
            width="stretch",
            column_config={
                "Marcador": st.column_config.TextColumn(f"{local} - {visita}"),
                "Probabilidad": st.column_config.ProgressColumn(
                    "Probabilidad", min_value=0, max_value=float(marcadores["Probabilidad"].max()), format="%.1f%%"
                ),
            },
        )

# ----- Pestaña 2: partidos que faltan -----
with tab_fecha:
    pendientes = obtener_pendientes(TEMPORADA)
    if pendientes.empty:
        st.info(f"No quedan partidos por jugar en {TEMPORADA}.")
    else:
        filas = []
        for p in pendientes.itertuples():
            r = modelo.predecir(p.local, p.visita)
            filas.append({
                "Local": p.local,
                "Visita": p.visita,
                "Marcador": r["marcador_probable"],
                "p_local": r["p_local"],
                "p_empate": r["p_empate"],
                "p_visita": r["p_visita"],
            })
        st.write(f"Quedan **{len(filas)} partidos** por jugar. Predicción de cada uno:")
        tabla_probabilidades(
            pd.DataFrame(filas).set_index("Local"),
            {"p_local": "Gana local", "p_empate": "Empate", "p_visita": "Gana visita"},
        )

# ----- Pestaña 3: campeonato en curso -----
with tab_torneo:
    sim = obtener_simulacion(TEMPORADA)
    st.write(
        f"Se juegan los **{sim.attrs.get('pendientes', len(obtener_pendientes(TEMPORADA)))} partidos** "
        "que faltan 10.000 veces y se cuenta dónde termina cada equipo."
    )
    tabla = sim.rename(columns={"pts_actuales": "Pts hoy", "pts_esperados": "Pts finales (esperados)"})
    tabla_probabilidades(tabla, {"campeon": "Campeón", "top3": "Top 3", "desciende": "Desciende"})

# ----- Pestaña 4: torneo siguiente -----
with tab_2027:
    st.write(
        "Proyección del torneo completo, todos contra todos. Es mucho más incierta que la de "
        f"{TEMPORADA}: no considera fichajes ni cambios de DT."
    )
    c1, c2 = st.columns(2)
    sube1 = c1.text_input("Ascendido 1 (opcional)")
    sube2 = c2.text_input("Ascendido 2 (opcional)")
    ascienden = tuple(s.strip() for s in (sube1, sube2) if s.strip())
    if len(ascienden) == 1:
        st.warning("Escribe los dos ascendidos, o deja ambos en blanco.")
    else:
        res, bajan, suben = obtener_2027(ascienden)
        st.write(f"**Bajan (estimado):** {', '.join(bajan)} · **Suben:** {', '.join(suben)}")
        tabla = res.rename(columns={"pts_esperados": "Pts esperados", "pos_media": "Posición media"})
        tabla_probabilidades(tabla, {"campeon": "Campeón", "top3": "Top 3", "desciende": "Desciende"})
