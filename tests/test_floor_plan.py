# -*- coding: utf-8 -*-
"""
Tests de utils/floor_plan.py -- el esquema de distribución para el asistente
Texto -> Diseño (leads que describen su casa en lenguaje natural).

    pytest tests/test_floor_plan.py
"""

import re
import sys

sys.path.insert(0, ".")

from utils.floor_plan import generar_esquema_svg  # noqa: E402

HABITACIONES_EJEMPLO = [
    {"tipo": "dormitorio", "nombre": "Dormitorio principal", "area_aprox_m2": 16},
    {"tipo": "bano", "nombre": "Baño principal", "area_aprox_m2": 5},
    {"tipo": "dormitorio", "nombre": "Dormitorio 2", "area_aprox_m2": 12},
    {"tipo": "cocina", "nombre": "Cocina", "area_aprox_m2": 14},
    {"tipo": "sala", "nombre": "Sala de estar", "area_aprox_m2": 20},
    {"tipo": "marquesina", "nombre": "Marquesina", "area_aprox_m2": 15},
]


def test_esquema_vacio_no_revienta():
    """Sin habitaciones, debe devolver un mensaje, no una excepción ni un SVG roto."""
    resultado = generar_esquema_svg([])
    assert "svg" not in resultado.lower() or "Sin programa" in resultado
    assert "<script" not in resultado.lower()


def test_esquema_genera_svg_valido():
    svg = generar_esquema_svg(HABITACIONES_EJEMPLO, area_total_m2=120)
    assert "<svg" in svg
    assert svg.count("<rect") == len(HABITACIONES_EJEMPLO)
    # El SVG debe cerrarse correctamente.
    assert svg.count("<svg") == svg.count("</svg>")


def test_esquema_admite_todos_los_tipos_de_ambiente():
    """No debe fallar (KeyError) con un tipo de ambiente no listado en el mapa de colores."""
    habitaciones = [{"tipo": "estudio_no_mapeado", "nombre": "Estudio", "area_aprox_m2": 10}]
    svg = generar_esquema_svg(habitaciones)
    assert "<rect" in svg
    assert "Estudio" in svg


def test_esquema_escapa_nombres_con_html():
    """Un nombre con caracteres especiales no debe romper el SVG ni inyectar HTML."""
    habitaciones = [{"tipo": "otro", "nombre": '<script>alert(1)</script>', "area_aprox_m2": 10}]
    svg = generar_esquema_svg(habitaciones)
    assert "<script>alert" not in svg
    assert "&lt;script&gt;" in svg


def test_esquema_admite_area_muy_pequena_sin_desbordar():
    """
    Bug potencial: un baño de 4m² da una caja de ~36px a la escala por
    defecto, demasiado chica para el texto de dos líneas. Debe usar un piso
    visual mínimo para que la caja siga siendo legible, sin inflar el área
    que se muestra en la etiqueta.
    """
    habitaciones = [{"tipo": "bano", "nombre": "Medio baño", "area_aprox_m2": 3}]
    svg = generar_esquema_svg(habitaciones)

    anchos = [float(m) for m in re.findall(r'(?<!stroke-)\bwidth="([\d.]+)"', svg)]
    altos = [float(m) for m in re.findall(r'(?<!stroke-)\bheight="([\d.]+)"', svg)]
    assert anchos and altos
    assert min(anchos) >= 50  # piso visual, no colapsa a ~36px
    assert min(altos) >= 50
    # La etiqueta sigue mostrando el área REAL (3 m²), no la inflada.
    assert "3 m²" in svg


def test_esquema_incluye_advertencia_de_que_no_es_plano_final():
    """
    Principio central del diseño: nunca debe presentarse como un plano
    arquitectónico real -- ver docstring de utils/floor_plan.py.
    """
    svg = generar_esquema_svg(HABITACIONES_EJEMPLO)
    assert "NO es un plano arquitectónico final" in svg


def test_esquema_muestra_area_de_referencia_vs_area_del_motor():
    """Si se pasa area_total_m2 (del motor QTO), debe distinguirse del área sumada del esquema."""
    svg = generar_esquema_svg(HABITACIONES_EJEMPLO, area_total_m2=150)
    assert "150" in svg  # el área real del presupuesto queda visible


def test_esquema_no_produce_coordenadas_negativas():
    """Las cajas deben quedar dentro del lienzo, sin coordenadas negativas."""
    svg = generar_esquema_svg(HABITACIONES_EJEMPLO * 3)  # muchos ambientes, varias filas
    xs = [float(m) for m in re.findall(r'x="(-?[\d.]+)"', svg)]
    ys = [float(m) for m in re.findall(r'y="(-?[\d.]+)"', svg)]
    assert all(x >= 0 for x in xs)
    assert all(y >= 0 for y in ys)
