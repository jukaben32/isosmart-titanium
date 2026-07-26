# -*- coding: utf-8 -*-
"""
utils/tarifa.py
---------------
FUENTE ÚNICA de la tarifa eléctrica residencial dominicana.

Antes esta lógica vivía dentro de `AnalisisFinancieroRD` (utils/financiera.py) y
`utils/energia.py` la importaba, creando un acoplamiento cruzado entre el módulo
financiero y el energético. Al extraerla aquí, ambos dependen de un dato, no uno
del otro.

⚠️ PENDIENTE DE VERIFICACIÓN
============================
Los bloques de abajo estaban rotulados como "BTS2" e "indexados al mercado
dominicano actual (2026)", pero no hay fuente citada en el repositorio. Antes de
mostrar estas cifras a un cliente hay que contrastarlas con el pliego tarifario
vigente de la SIE. Nota adicional: en RD la tarifa **residencial** es BTS1;
BTS2 corresponde a uso general de baja tensión. Si el proyecto es residencial,
probablemente la categoría rotulada esté equivocada aunque los números sean
razonables.

Los valores se conservan idénticos a los originales para no alterar los
resultados históricos ni romper los tests de regresión existentes.
"""

from __future__ import annotations

from typing import Dict

# Cargo fijo mensual y precio marginal por bloque de consumo (RD$/kWh).
TARIFA_BLOQUES: Dict[str, float] = {
    "fijo": 145.00,      # Cargo fijo mensual (RD$)
    "bloque_1": 7.20,    # 0–100 kWh
    "bloque_2": 9.80,    # 101–200 kWh
    "bloque_3": 13.50,   # 201–300 kWh
    "bloque_4": 15.20,   # >300 kWh
}

# Emisiones del grid dominicano (kg CO2 por kWh).
KG_CO2_POR_KWH = 0.4


def calcular_costo_energia_rd(kwh_mensuales: float,
                              tarifa: Dict[str, float] | None = None) -> float:
    """
    Costo mensual en RD$ aplicando la estructura marginal por bloques.

    Reescrito como bucle sobre los tramos: la versión anterior era una cadena de
    if/elif con los mismos coeficientes repetidos cuatro veces, donde cualquier
    ajuste de tarifa había que hacerlo en cuatro sitios.
    """
    t = tarifa or TARIFA_BLOQUES
    kwh = max(0.0, float(kwh_mensuales))

    costo = t["fijo"]
    tramos = (
        (100.0, t["bloque_1"]),   # 0–100
        (100.0, t["bloque_2"]),   # 101–200
        (100.0, t["bloque_3"]),   # 201–300
        (float("inf"), t["bloque_4"]),  # >300
    )

    restante = kwh
    for ancho, precio in tramos:
        if restante <= 0:
            break
        consumido = min(restante, ancho)
        costo += consumido * precio
        restante -= consumido

    return costo
