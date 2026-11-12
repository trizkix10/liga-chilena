"""Unifica nombres de equipos entre fuentes (API-Football, ESPN, ...).

Uso:
    python src/nombres.py      # lista los nombres en la base y cómo quedan unificados
"""
import re
import sqlite3
import unicodedata
from pathlib import Path

RUTA_DB = Path(__file__).resolve().parent.parent / "data" / "liga.db"

# clave normalizada -> nombre bonito. Agrega aquí si `python src/nombres.py` muestra duplicados.
NOMBRES = {
    "colo colo": "Colo-Colo",
    "universidad de chile": "U. de Chile",
    "universidad catolica": "U. Católica",
    "universidad de concepcion": "U. de Concepción",
    "concepcion": "Deportes Concepción",
    "coquimbo unido": "Coquimbo Unido",
    "everton": "Everton",
    "union la calera": "U. La Calera",
    "la serena": "La Serena",
    "limache": "Limache",
    "nublense": "Ñublense",
    "ohiggins": "O'Higgins",
    "audax italiano": "Audax Italiano",
    "union espanola": "Unión Española",
    "iquique": "Deportes Iquique",
    "copiapo": "Deportes Copiapó",
    "curico unido": "Curicó Unido",
}

# Variantes que se reemplazan antes de buscar en NOMBRES
ALIAS = {
    "everton de vina": "everton",
    "everton de vina del mar": "everton",
    "u catolica": "universidad catolica",
    "u de chile": "universidad de chile",
    "u de concepcion": "universidad de concepcion",
    "u la calera": "union la calera",
    "a italiano": "audax italiano",
    "d la serena": "la serena",
    "everton cd": "everton",
}


def clave(nombre: str) -> str:
    """'Deportes Concepción' -> 'concepcion'; 'Colo-Colo' -> 'colo colo'."""
    s = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    s = s.lower().replace("-", " ").replace(".", " ").replace("'", "")
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"^(deportes|cd|club deportivo) ", "", s)
    return ALIAS.get(s, s)


def canonico(nombre: str) -> str:
    k = clave(nombre)
    return NOMBRES.get(k, k.title())


if __name__ == "__main__":
    con = sqlite3.connect(RUTA_DB)
    nombres = sorted({n for (n,) in con.execute("SELECT local FROM partidos UNION SELECT visita FROM partidos")})
    con.close()
    grupos: dict[str, list[str]] = {}
    for n in nombres:
        grupos.setdefault(canonico(n), []).append(n)
    for canon, originales in sorted(grupos.items()):
        print(f"{canon:<22} <- {originales}")
