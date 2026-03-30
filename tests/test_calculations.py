# -*- coding: utf-8 -*-
"""
Pruebas unitarias para IsoSmart Titanium
"""

import sys
sys.path.append('.')

from utils.calculations import (
    CalculadoraEstructural,
    CalculadoraMateriales
)


def test_carga_muerta():
    """Prueba cálculo de carga muerta"""
    calc = CalculadoraEstructural()
    resultado = calc.calcular_carga_muerta(100, 'isotex')
    assert resultado == 18000  # 100 m² * 180 kg/m²
    print("[OK] Carga muerta")


def test_carga_viva():
    """Prueba cálculo de carga viva"""
    calc = CalculadoraEstructural()
    resultado = calc.calcular_carga_viva(100, 'vivienda')
    assert resultado == 15000  # 100 m² * 150 kg/m²
    print("[OK] Carga viva")


def test_espesor_losa():
    """Prueba cálculo de espesor de losa"""
    calc = CalculadoraEstructural()
    resultado = calc.calcular_espesor_losa(4, 'isotex')
    assert resultado >= 12  # Mínimo 12 cm
    print("[OK] Espesor losa")


def test_acero_losa():
    """Prueba cálculo de acero de losa"""
    calc = CalculadoraEstructural()
    resultado = calc.calcular_acero_losa(100, 5)
    assert 'total_kg' in resultado
    assert resultado['total_kg'] > 0
    print("[OK] Acero losa")


def test_volumen_concreto():
    """Prueba cálculo de volumen de concreto"""
    calc = CalculadoraEstructural()
    resultado = calc.calcular_volumen_concreto(200, 100)
    assert 'volumen_total_m3' in resultado
    assert resultado['volumen_con_desperdicio'] > resultado['volumen_total_m3']
    print("[OK] Volumen concreto")


def test_materiales_muro_isotex():
    """Prueba cálculo de materiales para Isotex"""
    calc = CalculadoraMateriales()
    resultado = calc.calcular_materiales_muro(100, 'isotex')
    assert 'paneles_isotex' in resultado
    assert resultado['paneles_isotex'] > 0
    print("[OK] Materiales Isotex")


def test_materiales_muro_icf():
    """Prueba cálculo de materiales para ICF"""
    calc = CalculadoraMateriales()
    resultado = calc.calcular_materiales_muro(100, 'icf')
    assert 'bloques_icf' in resultado
    assert resultado['bloques_icf'] > 0
    print("[OK] Materiales ICF")


def test_acabados():
    """Prueba cálculo de acabados"""
    calc = CalculadoraMateriales()
    resultado = calc.calcular_acabados(100, 200)
    assert 'pintura_galones' in resultado
    assert resultado['pintura_galones'] > 0
    print("[OK] Acabados")


def run_all_tests():
    """Ejecuta todas las pruebas"""
    print("=" * 40)
    print("IsoSmart Titanium - Suite de Pruebas")
    print("=" * 40)
    print()

    test_carga_muerta()
    test_carga_viva()
    test_espesor_losa()
    test_acero_losa()
    test_volumen_concreto()
    test_materiales_muro_isotex()
    test_materiales_muro_icf()
    test_acabados()

    print()
    print("=" * 40)
    print("Todas las pruebas pasaron [OK]")
    print("=" * 40)


if __name__ == "__main__":
    run_all_tests()
