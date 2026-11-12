# ⚽ Predictor Liga Chilena

Predice partidos de la Primera División de Chile, simula el campeonato en curso y proyecta el torneo siguiente.

- **Partidos:** probabilidad de victoria local / empate / visita, goles esperados y marcador más probable.
- **Campeonato:** probabilidad de salir campeón, terminar top 3 o descender (Monte Carlo, 10.000 simulaciones).
- **Próximo torneo:** proyección completa del torneo 2027.

## Cómo funciona

1. **Datos:** resultados 2022–2024 desde [API-Football](https://www.api-football.com/) y 2025–2026 desde la API pública de ESPN, guardados en SQLite (`data/liga.db`).
2. **Unificación de nombres:** cada fuente escribe distinto a los equipos (`Colo Colo` / `Colo-Colo`); `src/nombres.py` los normaliza.
3. **Modelo Poisson:** los goles de cada equipo siguen una distribución de Poisson con media
   `λ = exp(base + localía + ataque_equipo + defensa_rival)`, ajustada con una regresión de Poisson (GLM).
   Los partidos recientes pesan más (vida media de 1 año).
4. **Simulación:** se sortean los partidos pendientes miles de veces y se cuentan las posiciones finales.

### Evaluación (entrenado 2022–2025, probado en 2026)

| Modelo | Log loss | Acierto |
|---|---|---|
| Poisson | **1.020** | **50.6%** |
| Base (frecuencias históricas) | 1.051 | 47.6% |

## Instalación

```bash
git clone https://github.com/trizkix10/liga-chilena.git
cd liga-chilena
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Crea un archivo `.env` con tu key gratuita de API-Football:

```
API_FOOTBALL_KEY=tu_key
```

## Uso

```bash
# Descargar datos
python src/datos.py descargar 265 2022 2023 2024
python src/espn.py descargar 2025 2026
python src/datos.py resumen

# Revisar nombres de equipos unificados
python src/nombres.py

# Modelo
python src/modelo.py evaluar
python src/modelo.py predecir "coquimbo" "colo"

# Simulaciones
python src/simulacion.py 2026
python src/prediccion_2027.py --ascienden "Equipo 1" "Equipo 2"

# Página HTML (sin servidor)
python src/exportar.py
open web/index.html

# Página con Streamlit
streamlit run src/app.py
```

## Estructura

```
liga-chilena/
├── data/
│   └── partidos.csv          # datos de ejemplo
├── src/
│   ├── datos.py              # descarga desde API-Football → SQLite
│   ├── espn.py               # descarga desde ESPN → SQLite
│   ├── nombres.py            # unificación de nombres de equipos
│   ├── modelo.py             # modelo Poisson + evaluación
│   ├── simulacion.py         # Monte Carlo del torneo en curso
│   ├── prediccion_2027.py    # proyección del torneo siguiente
│   └── tabla.py              # tabla de posiciones (ejercicio inicial)
└── requirements.txt
```

## Limitaciones

- El plan gratis de API-Football solo da acceso a 2022–2024.
- La API de ESPN no es oficial y puede cambiar sin aviso.
- El modelo no considera lesiones, fichajes ni cambios de DT.
- Los equipos recién ascendidos tienen pocos datos, así que sus predicciones son menos precisas.

## Próximos pasos

- [ ] API con FastAPI
- [x] Página web (HTML en `web/` y Streamlit en `src/app.py`)
- [ ] Datos de Primera B
- [ ] Copa Chile y Copa de la Liga

---
Proyecto de Diego Malebran — Ingeniería Civil en Computación e Informática, UCN Coquimbo.
