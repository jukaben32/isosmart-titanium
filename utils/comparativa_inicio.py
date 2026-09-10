"""
utils/comparativa_inicio.py
---------------------------
Calculo ligero para la comparativa de la pagina de inicio.

La pantalla de Inicio necesita responder rapido a un area deslizable sin
duplicar la logica del presupuesto detallado. Este modulo mantiene esa pieza
sin Streamlit, para que pueda probarse con pytest.
"""

from __future__ import annotations

from typing import Any

from .dominio import Calidad, Sistema
from .geometria import Geometria
from .pricebook import DEFAULT_PRICEBOOK
from .qto import MotorQTO


def calcular_comparativa_area(
    area_m2: float,
    precios: dict[str, float] | None = None,
    sistema: str = Sistema.ISOTEX.value,
    calidad: str = Calidad.MEDIA.value,
    niveles: int = 1,
    altura_muro_m: float = 2.80,
) -> dict[str, Any]:
    """
    Calcula la comparativa EPS/ICF vs tradicional para un area tentativa.

    Cuando solo conocemos los metros cuadrados, `Geometria` estima el perimetro
    con una proporcion residencial 3:2. Eso hace que muros, vanos, banos,
    cocina e instalaciones cambien junto con el area en vez de usar un numero
    fijo de 120 m2.
    """
    area = float(area_m2)
    if area <= 0:
        raise ValueError("area_m2 debe ser positiva")

    geo = Geometria(
        area_m2=area,
        altura_muro_m=float(altura_muro_m),
        niveles=int(niveles),
    )
    motor = MotorQTO(
        geo,
        precios or DEFAULT_PRICEBOOK,
        sistema=sistema,
        calidad=calidad,
    )
    comp = motor.comparar_con_tradicional()
    por_verificar = motor.partidas_por_verificar()
    monto_por_verificar = float(por_verificar["subtotal"].sum()) if not por_verificar.empty else 0.0

    return {
        "area_m2": area,
        "geometria": geo.resumen(),
        "comparativa": comp,
        "monto_por_verificar": monto_por_verificar,
        "pct_por_verificar": (monto_por_verificar / motor.total() * 100) if motor.total() else 0.0,
    }
