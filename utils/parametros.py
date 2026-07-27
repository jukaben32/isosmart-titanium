"""
utils/parametros.py
-------------------
Carga de `data/parametros_tecnicos.yaml`.

Separación deliberada: las FÓRMULAS son código (utils/qto.py) y los PARÁMETROS
son datos (el YAML). Antes ambos estaban mezclados dentro de los `data.append`
de `calcular_obra_grisa`, de modo que ajustar un espesor obligaba a editar
Python y arriesgarse a romper el cálculo.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Dict

RUTA_DEFECTO = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "parametros_tecnicos.yaml",
)


@lru_cache(maxsize=8)
def cargar_parametros(ruta: str = RUTA_DEFECTO) -> dict[str, Any]:
    """
    Devuelve los parámetros técnicos. Cacheado: se lee una vez por proceso.

    Falla ruidosamente si el archivo no existe o está mal formado. Un motor de
    presupuesto que arranca con parámetros a medias es peor que uno que no
    arranca: produce cifras plausibles y equivocadas.
    """
    import yaml

    if not os.path.exists(ruta):
        raise FileNotFoundError(
            f"No se encontró {ruta}. Es la base técnica del cálculo (espesores, "
            f"rendimientos, mallas) y el motor no puede operar sin ella."
        )

    with open(ruta, encoding="utf-8") as f:
        datos = yaml.safe_load(f)

    if not isinstance(datos, dict):
        raise ValueError(f"{ruta} no contiene un mapeo YAML válido.")

    for seccion in ("panel", "espesores", "mezclas", "mallas", "mano_obra",
                    "geometria_defecto", "desperdicios", "comparacion_tradicional"):
        if seccion not in datos:
            raise ValueError(f"{ruta}: falta la sección obligatoria '{seccion}'.")

    return datos


def limpiar_cache() -> None:
    """Para tests o para recargar tras editar el YAML en caliente."""
    cargar_parametros.cache_clear()
