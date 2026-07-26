# -*- coding: utf-8 -*-
"""
Tests de la revisión de pantallas: Dashboard Financiero y utils/financiera.py.

    pytest tests/test_dashboard_financiero.py
"""

import sys

import pytest

sys.path.insert(0, ".")

from utils.financiera import AnalisisFinanciero  # noqa: E402
from utils.geometria import Geometria  # noqa: E402
from utils.pricebook import DEFAULT_PRICEBOOK  # noqa: E402
from utils.qto import MotorQTO  # noqa: E402


# ===========================================================================
# El flujo de caja acumulado ya no contradice al ROI
# ===========================================================================

def test_flujo_de_caja_no_resta_el_costo_total_completo():
    """
    Bug: `acumulado = flujo_neto - costo_total` restaba el costo TOTAL de la
    construcción en el año 1, así que la curva de flujo acumulado nunca se
    acercaba a cero en 20 años -- contradiciendo directamente el ROI positivo
    que la misma página mostraba arriba (calculado con `calcular_roi()`, ya
    corregido en la Fase 1).
    """
    geo = Geometria(area_m2=120)
    motor = MotorQTO(geo, DEFAULT_PRICEBOOK, sistema="isotex")
    comp = motor.comparar_con_tradicional()

    df = AnalisisFinanciero.generar_proyeccion_flujo_caja(
        area_m2=120,
        costo_total=comp["eps"]["costo_total"],
        costo_tradicional=comp["tradicional"]["costo_total"],
        horizonte_anios=20,
    )

    # Si EPS es más barato (que es el caso aquí, ver test_qto.py), no hay
    # sobrecosto que recuperar: el flujo acumulado debe ser positivo desde
    # el año 1, igual que el ROI.
    assert df["Acumulado_Nominal"].iloc[0] > 0


def test_flujo_de_caja_y_roi_cuentan_la_misma_historia():
    """
    Antes: la tarjeta de ROI decía "positivo" y el gráfico de flujo acumulado
    decía "permanentemente negativo" con los MISMOS datos de entrada. Deben
    coincidir en signo.
    """
    geo = Geometria(area_m2=120)
    motor = MotorQTO(geo, DEFAULT_PRICEBOOK, sistema="isotex")
    comp = motor.comparar_con_tradicional()
    total_isotex = comp["eps"]["costo_total"]
    total_tradicional = comp["tradicional"]["costo_total"]

    roi = AnalisisFinanciero.calcular_roi(
        area_m2=120, costo_total_isotex=total_isotex,
        costo_tradicional=total_tradicional, horizonte_anios=20,
    )
    flujo = AnalisisFinanciero.generar_proyeccion_flujo_caja(
        area_m2=120, costo_total=total_isotex,
        costo_tradicional=total_tradicional, horizonte_anios=20,
    )

    assert (roi.van > 0) == (flujo["Acumulado_Nominal"].iloc[0] > 0)


def test_flujo_de_caja_sin_costo_tradicional_no_asume_sobrecosto_falso():
    """Retrocompatibilidad: si no se pasa costo_tradicional, no debe inventar uno."""
    df = AnalisisFinanciero.generar_proyeccion_flujo_caja(
        area_m2=120, costo_total=2_000_000, horizonte_anios=5,
    )
    # Sin diferencial conocido, el año 1 no debe partir de -costo_total.
    assert df["Acumulado_Nominal"].iloc[0] > -100_000


# ===========================================================================
# Las funciones de sensibilidad ya no usan el motor clásico
# ===========================================================================

def test_sensibilidad_area_usa_el_motor_qto():
    """
    Bug: usaba BudgetCalculator (motor clásico), que da 9.6% de obra
    terminada y un ahorro fijo del 83.6% para cualquier área.
    """
    df = AnalisisFinanciero.analizar_sensibilidad_area(area_min=60, area_max=300, paso=60)
    porcentajes = sorted(set(round(p, 2) for p in df["Ahorro_Pct"]))
    assert len(porcentajes) > 1, "el ahorro no puede ser constante para cualquier área"
    assert all(5 < p < 45 for p in porcentajes)


def test_sensibilidad_area_es_coherente_con_el_motor_qto_directo():
    """El resultado de la función debe coincidir con llamar a MotorQTO a mano."""
    df = AnalisisFinanciero.analizar_sensibilidad_area(area_min=120, area_max=120, paso=60)
    fila = df.iloc[0]

    motor = MotorQTO(Geometria(area_m2=120), DEFAULT_PRICEBOOK, sistema="isotex")
    comp = motor.comparar_con_tradicional()

    assert fila["Costo_Isotex_RD"] == pytest.approx(comp["eps"]["costo_total"])
    assert fila["Ahorro_Pct"] == pytest.approx(comp["ahorro"]["total_pct"])


def test_sensibilidad_precio_materiales_usa_el_motor_qto():
    df = AnalisisFinanciero.analizar_sensibilidad_precio_materiales(area_m2=120)
    fila_base = df[df["Variacion_Pct"] == 0].iloc[0]

    motor = MotorQTO(Geometria(area_m2=120), DEFAULT_PRICEBOOK, sistema="isotex")
    assert fila_base["Costo_Ajustado_RD"] == pytest.approx(motor.total())


def test_sensibilidad_precio_materiales_escala_linealmente():
    df = AnalisisFinanciero.analizar_sensibilidad_precio_materiales(
        area_m2=120, variacion_pct=[-20, 0, 20]
    )
    base = df[df["Variacion_Pct"] == 0]["Costo_Ajustado_RD"].iloc[0]
    mas20 = df[df["Variacion_Pct"] == 20]["Costo_Ajustado_RD"].iloc[0]
    assert mas20 == pytest.approx(base * 1.2)


# ===========================================================================
# La comparación por densidad ya no oculta que es un parámetro fantasma
# ===========================================================================

def test_densidades_ya_no_fingen_una_diferencia_de_costo_inexistente():
    """
    Bug: la función devolvía tres filas con costo IDÉNTICO (verificado:
    RD$1,218,757.16 para "15kg", "20kg" y "25kg") sin ninguna advertencia --
    el parámetro de densidad nunca entraba en el cálculo. Ahora debe admitirlo
    explícitamente en vez de simularlo.
    """
    df = AnalisisFinanciero.comparar_financiero_densidades(area_m2=120)

    costos = df["Costo_Total_RD"].round(2).unique()
    assert len(costos) == 1, "si el costo difiere, la nota de aviso ya no aplica"
    assert "nota" in df.columns
    assert all("no distingue precio por espesor" in nota for nota in df["nota"])


def test_densidades_usa_el_motor_qto():
    df = AnalisisFinanciero.comparar_financiero_densidades(area_m2=120)
    motor = MotorQTO(Geometria(area_m2=120), DEFAULT_PRICEBOOK, sistema="isotex")
    assert df["Costo_Total_RD"].iloc[0] == pytest.approx(motor.total())
