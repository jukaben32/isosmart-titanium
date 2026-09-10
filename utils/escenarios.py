"""Escenarios de presupuesto para comparar decisiones de diseño."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from .geometria import Geometria
from .instalaciones import InstalacionesDetalle
from .qto import MotorQTO


@dataclass(frozen=True)
class EscenarioPresupuesto:
    clave: str
    nombre: str
    sistema: str = "Paneles Isotex"
    calidad: str = "media"
    zona_riesgo: str = "moderado"
    aplanado_mecanizado: bool = False
    sistema_techo: str | None = None


ESCENARIOS_BASE: tuple[EscenarioPresupuesto, ...] = (
    EscenarioPresupuesto("economico", "Económico", calidad="economica"),
    EscenarioPresupuesto("medio", "Medio residencial", calidad="media"),
    EscenarioPresupuesto("alto", "Alto premium", calidad="alta", zona_riesgo="alto"),
    EscenarioPresupuesto("lujo", "Lujo", calidad="lujo", zona_riesgo="alto"),
    EscenarioPresupuesto(
        "lujo_mecanizado",
        "Lujo con lanzadora",
        calidad="lujo",
        zona_riesgo="alto",
        aplanado_mecanizado=True,
    ),
    EscenarioPresupuesto(
        "lujo_isolosa",
        "Lujo + Isolosa cotizada aparte",
        calidad="lujo",
        zona_riesgo="alto",
        sistema_techo="isolosa",
    ),
)


def calcular_escenarios(
    geometria: Geometria,
    precios: dict[str, float],
    instalaciones: InstalacionesDetalle | dict[str, Any] | None = None,
    escenarios: tuple[EscenarioPresupuesto, ...] = ESCENARIOS_BASE,
) -> pd.DataFrame:
    """Devuelve una tabla comparativa de escenarios usando el mismo MotorQTO."""
    filas = []
    for esc in escenarios:
        motor = MotorQTO(
            geometria,
            precios,
            sistema=esc.sistema,
            calidad=esc.calidad,
            zona_riesgo=esc.zona_riesgo,
            aplanado_mecanizado=esc.aplanado_mecanizado,
            sistema_techo=esc.sistema_techo,
            instalaciones=instalaciones,
        )
        comparacion = motor.comparar_con_tradicional()
        filas.append({
            "clave": esc.clave,
            "escenario": esc.nombre,
            "sistema": esc.sistema,
            "calidad": esc.calidad,
            "zona_riesgo": esc.zona_riesgo,
            "aplanado": "mecanizado" if esc.aplanado_mecanizado else "manual",
            "techo": esc.sistema_techo or "generico",
            "total": round(motor.total(), 2),
            "costo_m2": round(motor.costo_m2(), 2),
            "obra_gris": round(motor.total_obra_gris(), 2),
            "obra_terminada": round(motor.total_obra_terminada(), 2),
            "ahorro_total_pct": round(comparacion["ahorro"]["total_pct"], 2),
            "incompleto": bool(esc.sistema_techo and motor._precio(f"Techo_{esc.sistema_techo.capitalize()}_m2") == 0),
        })
    return pd.DataFrame(filas)

