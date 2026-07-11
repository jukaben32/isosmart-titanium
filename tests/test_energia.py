# -*- coding: utf-8 -*-
"""
Tests del módulo energético (utils/energia.py).

Cubre las funciones PURAS de análisis de ahorro energético.
Verifica invariantes de negocio (monotonía, signos, coherencia)
para proteger la lógica antes de refactorizar la UI.

Ejecutar:
    uv run --with pandas --with numpy --with streamlit \
        python tests/test_energia.py
"""

import sys
sys.path.insert(0, ".")

from utils.energia import AnalisisEnergetico


def test_carga_termica_isotex_menor_que_tradicional():
    # El aislamiento debe reducir la carga térmica vs tradicional
    iso = AnalisisEnergetico.calcular_carga_termica(120, sistema="isotex")
    trad = AnalisisEnergetico.calcular_carga_termica(120, sistema="tradicional")
    assert iso["carga_termica_btu_h"] < trad["carga_termica_btu_h"]
    # ICF tambien menor que tradicional
    icf = AnalisisEnergetico.calcular_carga_termica(120, sistema="icf")
    assert icf["carga_termica_btu_h"] < trad["carga_termica_btu_h"]
    print("[OK] carga termica: isotex/icf < tradicional")


def test_carga_termica_crece_con_area():
    pequena = AnalisisEnergetico.calcular_carga_termica(80)
    grande = AnalisisEnergetico.calcular_carga_termica(200)
    assert grande["carga_termica_btu_h"] > pequena["carga_termica_btu_h"]
    print("[OK] carga termica crece con el area")


def test_carga_termica_orientacion_desfavorable_mayor():
    normal = AnalisisEnergetico.calcular_carga_termica(120, orientacion="normal")
    desfav = AnalisisEnergetico.calcular_carga_termica(120, orientacion="desfavorable")
    assert desfav["carga_termica_btu_h"] > normal["carga_termica_btu_h"]
    print("[OK] orientacion desfavorable => carga mayor")


def test_consumo_mensual_es_calado():
    r = AnalisisEnergetico.calcular_consumo_mensual(12000, seer=20.0, horas_operacion=10.0)
    # consumo hora = 12000 / (20*1000) = 0.6 kWh
    assert abs(r["consumo_hora_kwh"] - 0.6) < 1e-6
    # diario = 0.6 * 10 = 6 kWh
    assert abs(r["consumo_diario_kwh"] - 6.0) < 1e-6
    # mensual = 6 * 30 = 180 kWh
    assert abs(r["consumo_mensual_kwh"] - 180.0) < 1e-6
    # costo mensual > 0 (tarifa BTS2)
    assert r["consumo_mensual_rd"] > 0
    print("[OK] consumo mensual: calculos coherentes con formula")


def test_ahorro_energetico_estructura_y_signos():
    r = AnalisisEnergetico.calcular_ahorro_energetico(120, sistema="isotex", calidad_equipo="inverter")
    # El isotex debe ahorrar vs tradicional
    assert r.ahorro_mensual_kwh > 0
    assert r.ahorro_mensual_rd > 0
    # ahorro_anual = ahorro_mensual * 12 (tolerancia por floating point)
    assert abs(r.ahorro_anual_rd - r.ahorro_mensual_rd * 12) < 0.5
    assert r.reduccion_pico_demanda_kw > 0
    assert r.co2_evitado_kg_anio > 0
    # ROI en años debe ser finito y positivo
    assert r.roi_energetico_anios > 0 and r.roi_energetico_anios != float('inf')
    print("[OK] ahorro energetico: estructura y signos coherentes")


def test_ahorro_mayor_area_mayor_ahorro():
    r1 = AnalisisEnergetico.calcular_ahorro_energetico(80)
    r2 = AnalisisEnergetico.calcular_ahorro_energetico(200)
    assert r2.ahorro_anual_rd > r1.ahorro_anual_rd
    print("[OK] ahorro energetico: area mayor => ahorro anual mayor")


def test_proyeccion_ahorro_forma_y_crecimiento():
    df = AnalisisEnergetico.generar_proyeccion_ahorro(120, horizonte_anios=10)
    assert len(df) == 10
    # El ahorro acumulado debe crecer monotonicamente
    acum = df["Ahorro_Acumulado_RD"].tolist()
    assert all(acum[i] <= acum[i+1] for i in range(len(acum)-1))
    # CO2 evitado crece con los años
    assert df["CO2_Evitado_kg"].iloc[-1] > df["CO2_Evitado_kg"].iloc[0]
    print("[OK] proyeccion ahorro: 10 filas, crecimiento monotono")


def test_sistema_solar_recomendado_coherente():
    r = AnalisisEnergetico.calcular_sistema_solar_recomendado(120)
    assert r["paneles_necesarios"] > 0
    assert r["capacidad_sistema_kw"] > 0
    assert 0 <= r["autoconsumo_pct"] <= 100
    assert r["costo_estimado_rd"] > 0
    print("[OK] sistema solar: paneles, capacidad y autoconsumo coherentes")


def test_tamano_ac_recomendado():
    r = AnalisisEnergetico.calcular_tamano_ac_recomendado(120, sistema="isotex")
    assert r["toneladas_recomendadas"] > 0
    assert r["num_unidades_recomendado"] >= 1
    assert len(r["equipos_sugeridos"]) > 0
    print("[OK] tamano AC recomendado: equipos sugeridos coherentes")


def test_tabla_comparativa_consumos():
    df = AnalisisEnergetico.generar_tabla_comparativa_consumos(120)
    # 3 sistemas x 4 calidades = 12 filas
    assert len(df) == 12
    assert "Isotex" in df["Sistema"].values
    assert "Tradicional" in df["Sistema"].values
    # Para misma calidad, isotex debe consumir menos que tradicional
    iso_inv = df[(df["Sistema"] == "Isotex") & (df["Calidad_Equipo"] == "Inverter")]["Consumo_mensual_kWh"].iloc[0]
    trad_inv = df[(df["Sistema"] == "Tradicional") & (df["Calidad_Equipo"] == "Inverter")]["Consumo_mensual_kWh"].iloc[0]
    assert iso_inv < trad_inv
    print("[OK] tabla comparativa: 12 filas, isotex < tradicional en inverter")


def run_all():
    print("=" * 55)
    print("TESTS MÓDULO ENERGÉTICO")
    print("=" * 55)
    test_carga_termica_isotex_menor_que_tradicional()
    test_carga_termica_crece_con_area()
    test_carga_termica_orientacion_desfavorable_mayor()
    test_consumo_mensual_es_calado()
    test_ahorro_energetico_estructura_y_signos()
    test_ahorro_mayor_area_mayor_ahorro()
    test_proyeccion_ahorro_forma_y_crecimiento()
    test_sistema_solar_recomendado_coherente()
    test_tamano_ac_recomendado()
    test_tabla_comparativa_consumos()
    print("=" * 55)
    print("TODOS LOS TESTS PASARON [OK]")
    print("=" * 55)


if __name__ == "__main__":
    run_all()
