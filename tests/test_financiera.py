# -*- coding: utf-8 -*-
"""
Tests del módulo financiero (utils/financiera.py).

Cubre las funciones PURAS (sin Streamlit). Las que dependen de
st.session_state (comparar_financiero_densidades) se prueban aparte
mockeando session_state, para no acoplar la lógica de negocio a la UI.

Ejecutar:
    uv run --with pandas --with numpy --with numpy-financial \
        python tests/test_financiera.py
"""

import sys
sys.path.insert(0, ".")

from utils.financiera import (
    AnalisisFinanciero,
    AnalisisFinancieroRD,
    calcular_costo_unitario_por_sistema,
)


def test_costo_energia_rd_bloque_1():
    # 80 kWh -> cargo fijo + 80 * 7.20
    costo = AnalisisFinancieroRD.calcular_costo_energia_rd(80)
    assert abs(costo - (145.00 + 80 * 7.20)) < 0.01
    print("[OK] costo energia bloque 1 (<=100 kWh)")


def test_costo_energia_rd_bloque_2():
    # 150 kWh -> fijo + 100*7.20 + 50*9.80
    costo = AnalisisFinancieroRD.calcular_costo_energia_rd(150)
    esperado = 145.00 + 100 * 7.20 + 50 * 9.80
    assert abs(costo - esperado) < 0.01
    print("[OK] costo energia bloque 2 (101-200 kWh)")


def test_costo_energia_rd_bloque_4():
    # 400 kWh -> todos los bloques + 100*15.20
    costo = AnalisisFinancieroRD.calcular_costo_energia_rd(400)
    esperado = (145.00 + 100 * 7.20 + 100 * 9.80 + 100 * 13.50
                + 100 * 15.20)
    assert abs(costo - esperado) < 0.01
    print("[OK] costo energia bloque 4 (>300 kWh)")


def test_simular_ahorro_termico_monotono():
    # Más área => más ahorro mensual (monotonía lógica del negocio)
    r1 = AnalisisFinancieroRD.simular_ahorro_termico(100)
    r2 = AnalisisFinancieroRD.simular_ahorro_termico(200)
    assert r2["ahorro_mensual_rds"] > r1["ahorro_mensual_rds"]
    assert r2["ahorro_anual_rds"] == round(r2["ahorro_mensual_rds"] * 12, 2)
    print("[OK] simular_ahorro_termico: area mayor => ahorro mayor")


def test_ahorro_energia_mensual_isotex_ahorra():
    r = AnalisisFinanciero.calcular_ahorro_energia_mensual(120, "isotex")
    assert r["ahorro_rd_mes"] > 0
    assert r["ahorro_kwh_mes"] > 0
    print("[OK] ahorro energia mensual isotex > 0")


def test_ahorro_energia_mensual_tradicional_cero():
    r = AnalisisFinanciero.calcular_ahorro_energia_mensual(120, "tradicional")
    assert r["ahorro_rd_mes"] == 0.0
    assert r["ahorro_kwh_mes"] == 0.0
    print("[OK] ahorro energia mensual tradicional = 0")


def test_calcular_roi_devuelve_estructura():
    res = AnalisisFinanciero.calcular_roi(
        area_m2=120,
        costo_total_isotex=1_200_000,
        costo_tradicional=1_500_000,
        horizonte_anios=10,
    )
    # Verifica que todas las métricas existen y son números finitos
    for campo in ["roi_nominal", "roi_anualizado", "payback_anios",
                  "van", "tir", "tco", "ahorro_acumulado"]:
        val = getattr(res, campo)
        assert isinstance(val, (int, float))
        assert val == val  # no es NaN
    assert len(res.flujo_caja) == 11  # año 0 + 10 años
    print("[OK] calcular_roi devuelve ResultadoFinanciero completo")


def test_calcular_roi_isotex_mas_barato_ahorra():
    # Si Isotex es más barato, el ahorro acumulado debe ser positivo
    res = AnalisisFinanciero.calcular_roi(
        area_m2=120,
        costo_total_isotex=1_200_000,
        costo_tradicional=1_500_000,
        horizonte_anios=10,
    )
    assert res.ahorro_acumulado > 0
    print("[OK] calcular_roi: Isotex mas barato => ahorro_acumulado > 0")


def test_calcular_costo_financiamiento_cuota_positiva():
    r = AnalisisFinanciero.calcular_costo_financiamiento(2_000_000, 0.15, 60)
    assert r["cuota_mensual"] > 0
    assert r["total_pagado"] > r["monto_prestamo"]
    assert abs(r["total_intereses"] - (r["total_pagado"] - r["monto_prestamo"])) < 0.01
    print("[OK] calcular_costo_financiamiento: cuota y totales coherentes")


def test_analizar_sensibilidad_area_devuelve_dataframe():
    df = AnalisisFinanciero.analizar_sensibilidad_area(area_min=100, area_max=300, paso=100)
    assert not df.empty
    assert "Costo_Isotex_RD" in df.columns
    assert "Ahorro_RD" in df.columns
    # El ahorro debe ser positivo (Isotex mas barato que tradicional)
    assert (df["Ahorro_RD"] > 0).all()
    print("[OK] analizar_sensibilidad_area devuelve DataFrame coherente")


def test_analizar_sensibilidad_precio_materiales():
    df = AnalisisFinanciero.analizar_sensibilidad_precio_materiales(area_m2=120)
    assert not df.empty
    assert "Variacion_Pct" in df.columns
    # La variacion 0 debe dar el costo base sin diferencia
    base = df[df["Variacion_Pct"] == 0].iloc[0]
    assert abs(base["Diferencia_RD"]) < 0.01
    print("[OK] analizar_sensibilidad_precio_materiales coherente (var 0 => diff 0)")


def test_comparar_financiero_densidades_sin_streamlit():
    # Ahora recibe parametros en lugar de leer st.session_state (testeable)
    df = AnalisisFinanciero.comparar_financiero_densidades(
        area_m2=120, sistema="Paneles Isotex", usar_vigas_h=False
    )
    assert not df.empty
    assert set(["15kg", "20kg", "25kg"]).issubset(set(df["Densidad_Panel"]))
    print("[OK] comparar_financiero_densidades testeable sin st.session_state")


def test_calcular_costo_unitario_por_sistema_dos_sistemas():
    r = calcular_costo_unitario_por_sistema(120)
    assert "Paneles Isotex" in r and "ICF Proform" in r
    assert r["Paneles Isotex"]["costo_total"] > 0
    print("[OK] calcular_costo_unitario_por_sistema: ambos sistemas calculados")


def run_all():
    print("=" * 55)
    print("TESTS MÓDULO FINANCIERO")
    print("=" * 55)
    test_costo_energia_rd_bloque_1()
    test_costo_energia_rd_bloque_2()
    test_costo_energia_rd_bloque_4()
    test_simular_ahorro_termico_monotono()
    test_ahorro_energia_mensual_isotex_ahorra()
    test_ahorro_energia_mensual_tradicional_cero()
    test_calcular_roi_devuelve_estructura()
    test_calcular_roi_isotex_mas_barato_ahorra()
    test_calcular_costo_financiamiento_cuota_positiva()
    test_analizar_sensibilidad_area_devuelve_dataframe()
    test_analizar_sensibilidad_precio_materiales()
    test_comparar_financiero_densidades_sin_streamlit()
    test_calcular_costo_unitario_por_sistema_dos_sistemas()
    print("=" * 55)
    print("TODOS LOS TESTS PASARON [OK]")
    print("=" * 55)


if __name__ == "__main__":
    run_all()
