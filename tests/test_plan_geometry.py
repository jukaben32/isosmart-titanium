# -*- coding: utf-8 -*-
"""
Tests de utils/plan_geometry.py -- la extracción geométrica desde el plano
(canvas interactivo: calibración de escala + trazado de polígono).

Este módulo no tenía NINGÚN test. Es la pieza más sensible de la cadena de
precisión que pide el usuario: un error aquí (mala calibración, polígono
equivocado) se propaga silenciosamente a TODA la geometría y, por tanto, a
TODO el presupuesto -- el motor QTO puede estar impecable y el resultado
seguir siendo incorrecto si la entrada geométrica está mal.

    pytest tests/test_plan_geometry.py
"""

import math
import sys

sys.path.insert(0, ".")

from utils.plan_geometry import (  # noqa: E402
    contar_lineas_calibracion,
    contar_poligonos,
    extract_line_segments,
    extract_points,
    polygon_area_perimeter,
    polygon_from_canvas,
    scale_from_canvas_line,
)


def _linea(x1, y1, x2, y2):
    return {"type": "line", "x1": x1, "y1": y1, "x2": x2, "y2": y2}


def _poligono(puntos_relativos, left=0.0, top=0.0):
    return {
        "type": "polygon", "left": left, "top": top,
        "points": [{"x": x, "y": y} for x, y in puntos_relativos],
    }


# ===========================================================================
# Shoelace: área y perímetro en px
# ===========================================================================

def test_shoelace_rectangulo_simple():
    """Un rectángulo 100x50 px: área=5000, perímetro=300."""
    pts = [(0, 0), (100, 0), (100, 50), (0, 50)]
    area, per = polygon_area_perimeter(pts)
    assert area == 5000.0
    assert per == 300.0


def test_shoelace_es_invariante_al_sentido_de_trazado():
    """El área no debe depender de si se trazó en sentido horario o antihorario."""
    horario = [(0, 0), (0, 50), (100, 50), (100, 0)]
    antihorario = [(0, 0), (100, 0), (100, 50), (0, 50)]
    area_h, _ = polygon_area_perimeter(horario)
    area_a, _ = polygon_area_perimeter(antihorario)
    assert area_h == area_a == 5000.0


def test_shoelace_poligono_no_rectangular():
    """Triángulo rectángulo de catetos 30 y 40 px: área = 30*40/2 = 600."""
    pts = [(0, 0), (30, 0), (0, 40)]
    area, per = polygon_area_perimeter(pts)
    assert area == 600.0
    assert per == 30 + 40 + 50.0  # hipotenusa = 50 (3-4-5)


def test_shoelace_con_menos_de_3_puntos_devuelve_cero():
    """Un polígono necesita al menos 3 vértices; menos de eso no es un área."""
    assert polygon_area_perimeter([]) == (0.0, 0.0)
    assert polygon_area_perimeter([(0, 0)]) == (0.0, 0.0)
    assert polygon_area_perimeter([(0, 0), (10, 10)]) == (0.0, 0.0)


def test_shoelace_area_grande_no_pierde_precision():
    """Un plano grande (edificio de varios miles de m² en px) no debe acumular error visible."""
    lado = 5000.0  # px
    pts = [(0, 0), (lado, 0), (lado, lado), (0, lado)]
    area, per = polygon_area_perimeter(pts)
    # Para un cuadrado con estas coordenadas, área y perímetro son exactos en
    # coma flotante (no hace falta tolerancia).
    assert area == lado * lado
    assert per == 4 * lado


# ===========================================================================
# Calibración de escala (m/px)
# ===========================================================================

def test_escala_se_calcula_desde_la_linea_de_calibracion():
    """100 px = 2.5 m reales -> 0.025 m/px."""
    objetos = [_linea(0, 0, 100, 0)]
    escala = scale_from_canvas_line(objetos, 2.5)
    assert escala == 0.025


def test_escala_funciona_con_linea_diagonal():
    """La distancia se calcula con Pitágoras, no solo delta-x."""
    # Línea de 3-4-5: de (0,0) a (3,4) mide 5 px.
    objetos = [_linea(0, 0, 3, 4)]
    escala = scale_from_canvas_line(objetos, 10.0)  # 5 px = 10 m reales
    assert escala == 2.0  # 10 / 5


def test_escala_ignora_lineas_de_longitud_cero():
    """Una línea sin longitud (clic accidental) no debe producir división por cero."""
    objetos = [_linea(50, 50, 50, 50), _linea(0, 0, 100, 0)]
    escala = scale_from_canvas_line(objetos, 2.5)
    assert escala == 0.025  # usa la segunda línea, la primera es degenerada


def test_escala_sin_lineas_devuelve_none():
    assert scale_from_canvas_line([], 2.5) is None
    assert scale_from_canvas_line([_poligono([(0, 0), (1, 0), (1, 1)])], 2.5) is None


def test_escala_con_longitud_real_invalida_devuelve_none():
    objetos = [_linea(0, 0, 100, 0)]
    assert scale_from_canvas_line(objetos, 0) is None
    assert scale_from_canvas_line(objetos, -5) is None


# ===========================================================================
# Extracción de polígono
# ===========================================================================

def test_polygon_from_canvas_aplica_el_offset_left_top():
    """drawable-canvas guarda puntos relativos a (left, top); hay que sumarlos."""
    objetos = [_poligono([(0, 0), (10, 0), (10, 10)], left=100, top=50)]
    pts = polygon_from_canvas(objetos)
    assert pts == [(100, 50), (110, 50), (110, 60)]


def test_polygon_from_canvas_ignora_poligonos_degenerados():
    """Un polígono con menos de 3 puntos no es un área válida."""
    objetos = [_poligono([(0, 0), (10, 0)])]  # solo 2 puntos
    assert polygon_from_canvas(objetos) is None


def test_polygon_from_canvas_sin_poligonos_devuelve_none():
    assert polygon_from_canvas([]) is None
    assert polygon_from_canvas([_linea(0, 0, 10, 10)]) is None


# ===========================================================================
# Ambigüedad: más de una línea o polígono trazado
#
# Bug potencial (revisión "cada detalle de la obra", 2026-07-26):
# `scale_from_canvas_line` y `polygon_from_canvas` usan SIEMPRE el primer
# objeto que encuentran, en silencio. Si el usuario dibuja más de una línea o
# polígono (por error, o para recalibrar), la medición usada puede no ser la
# que el usuario cree que está usando -- un error de calibración se propaga
# a TODA la geometría y de ahí a todo el presupuesto.
# ===========================================================================

def test_detecta_multiples_lineas_de_calibracion():
    objetos = [_linea(0, 0, 100, 0), _linea(0, 0, 50, 0)]
    assert contar_lineas_calibracion(objetos) == 2

    # La función de escala sigue funcionando (usa la primera), pero ahora
    # la ambigüedad es detectable para que la UI la advierta.
    escala = scale_from_canvas_line(objetos, 2.5)
    assert escala == 2.5 / 100  # confirma que fue la PRIMERA, no la segunda


def test_una_sola_linea_no_genera_ambiguedad():
    objetos = [_linea(0, 0, 100, 0)]
    assert contar_lineas_calibracion(objetos) == 1


def test_detecta_multiples_poligonos():
    objetos = [
        _poligono([(0, 0), (10, 0), (10, 10)]),
        _poligono([(20, 20), (30, 20), (30, 30)]),
    ]
    assert contar_poligonos(objetos) == 2

    # Confirma que se usó el PRIMER polígono, no un promedio ni el último.
    pts = polygon_from_canvas(objetos)
    assert pts == [(0, 0), (10, 0), (10, 10)]


def test_poligonos_degenerados_no_cuentan_como_ambiguedad():
    """Un polígono de menos de 3 puntos no compite por ser 'el trazado'."""
    objetos = [
        _poligono([(0, 0), (10, 0)]),  # degenerado, 2 puntos
        _poligono([(20, 20), (30, 20), (30, 30)]),  # válido
    ]
    assert contar_poligonos(objetos) == 1


def test_contadores_con_lista_vacia():
    assert contar_lineas_calibracion([]) == 0
    assert contar_poligonos([]) == 0
    assert contar_lineas_calibracion(None) == 0
    assert contar_poligonos(None) == 0


# ===========================================================================
# Extracción de segmentos y puntos (usados por el visor BIM)
# ===========================================================================

def test_extract_line_segments_desde_polilinea():
    obj = {"type": "polyline", "left": 0, "top": 0,
           "points": [{"x": 0, "y": 0}, {"x": 10, "y": 0}, {"x": 10, "y": 10}]}
    segs = extract_line_segments([obj])
    assert len(segs) == 2
    assert segs[0] == ((0, 0), (10, 0))
    assert segs[1] == ((10, 0), (10, 10))


def test_extract_points_desde_circulos():
    obj = {"type": "circle", "left": 5, "top": 5, "radius": 3}
    pts = extract_points([obj])
    assert len(pts) == 1


# ===========================================================================
# Integración: la cadena completa calibración -> shoelace -> m² reales
# ===========================================================================

def test_cadena_completa_calibracion_a_metros_cuadrados():
    """
    Reproduce exactamente el flujo de la UI: el usuario calibra con una línea
    de longitud real conocida y traza un rectángulo de dimensiones reales
    conocidas; el resultado en m² debe coincidir con la geometría real, no
    solo con la de píxeles.
    """
    m_por_px_esperado = 2.5 / 100  # 100 px = 2.5 m reales
    ancho_m, alto_m = 10.0, 8.0
    ancho_px = ancho_m / m_por_px_esperado
    alto_px = alto_m / m_por_px_esperado

    objetos = [
        _linea(0, 0, 100, 0),
        _poligono([(0, 0), (ancho_px, 0), (ancho_px, alto_px), (0, alto_px)]),
    ]

    escala = scale_from_canvas_line(objetos, 2.5)
    pts = polygon_from_canvas(objetos)
    area_px2, perimetro_px = polygon_area_perimeter(pts)

    area_m2 = area_px2 * escala**2
    perimetro_m = perimetro_px * escala

    assert math.isclose(area_m2, ancho_m * alto_m, rel_tol=1e-9)
    assert math.isclose(area_m2, 80.0, rel_tol=1e-9)
    assert math.isclose(perimetro_m, 2 * (ancho_m + alto_m), rel_tol=1e-9)
