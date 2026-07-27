"""
Tests de la Fase 2: estado unificado, estilos y router único.

    pytest tests/test_estado_y_navegacion.py
"""

import sys

import pytest

sys.path.insert(0, ".")

from utils.estado import CLAVE_ESTADO, ProyectoState  # noqa: E402

# ===========================================================================
# Estado unificado
# ===========================================================================

def test_migra_desde_las_claves_antiguas_calc_y_plan():
    """
    Bug: existían DOS familias de claves para lo mismo (`calc_*` y `plan_*`),
    escritas desde sitios distintos y divergiendo sin aviso.
    """
    antiguo = {
        "calc_area_m2": 180.0,
        "plan_perimetro_m": 58.0,      # solo existía en la familia plan_
        "calc_niveles": 2,
        "calidad_terminados": "económica",
    }
    e = ProyectoState.cargar(antiguo)

    assert e.area_m2 == 180.0
    assert e.perimetro_m == 58.0
    assert e.niveles == 2
    assert e.calidad == "economica"     # normalizado, sin tilde


def test_guardar_y_recargar_es_idempotente():
    estado = {}
    ProyectoState(area_m2=200, perimetro_m=60, niveles=2).guardar(estado)

    recargado = ProyectoState.cargar(estado)
    assert recargado.area_m2 == 200
    assert recargado.perimetro_m == 60
    assert recargado.niveles == 2
    assert CLAVE_ESTADO in estado


def test_mantiene_el_espejo_de_compatibilidad():
    """Los módulos aún no migrados leen `calc_*`; deben seguir viendo lo mismo."""
    estado = {}
    ProyectoState(area_m2=175, perimetro_m=52, niveles=1).guardar(estado)

    assert estado["calc_area_m2"] == 175
    assert estado["calc_perimetro_m"] == 52
    assert estado["calc_niveles"] == 1


def test_sanea_valores_imposibles_y_deja_constancia():
    e = ProyectoState(area_m2=5, altura_muro_m=99, niveles=0).sanear()

    assert e.area_m2 == 10.0        # recortado al mínimo
    assert e.altura_muro_m == 6.0   # recortado al máximo
    assert e.niveles == 1
    assert len(e.avisos) == 3, e.avisos


def test_aplicar_metricas_sustituye_a_sincronizar_parametros_globales():
    """
    La función anterior escribía cinco claves que nadie leía. Ahora las métricas
    entran al estado y de ahí al motor de cantidades.
    """
    e = ProyectoState()
    e.aplicar_metricas(
        {"area_m2": 240, "perimetro_m": 62, "niveles": 2, "altura_muro_m": 3.0},
        origen="Gemini Vision",
    )

    assert e.area_m2 == 240
    assert e.perimetro_m == 62
    assert e.origen_metricas == "Gemini Vision"

    geo = e.geometria()
    assert geo.perimetro_efectivo_m == 62      # llega hasta la geometría
    assert geo.area_losa_entrepiso_m2 > 0      # y reconoce los dos niveles


def test_aplicar_metricas_ignora_basura_sin_romperse():
    e = ProyectoState(area_m2=120)
    e.aplicar_metricas({"area_m2": "no soy un número", "perimetro_m": None})

    assert e.area_m2 == 120                    # conserva el valor anterior
    assert any("no numérico" in a for a in e.avisos)


def test_calidad_invalida_falla_ruidosamente():
    with pytest.raises(ValueError):
        ProyectoState(calidad="carisima").sanear()


# ===========================================================================
# Estilos
# ===========================================================================

def test_la_hoja_de_estilos_existe_y_define_las_clases_usadas():
    from utils.estilos import _leer_css

    css = _leer_css()
    assert css, "no se encontró .streamlit/estilos.css"
    for clase in (".metric-card", ".energy-card", ".page-header", ".iso-btn", ".info-box"):
        assert clase in css, f"falta la clase {clase}"


def test_los_helpers_escapan_html():
    """Antes el nombre del cliente se interpolaba crudo en el HTML del botón."""
    import html as _html

    peligroso = '<script>alert(1)</script>'
    assert "&lt;script&gt;" in _html.escape(peligroso)


# ===========================================================================
# Router unificado
# ===========================================================================

def test_todas_las_paginas_estan_registradas_y_son_invocables():
    """
    Bug: coexistían el menú `st.radio` de app.py y la carpeta `pages/`, que
    Streamlit convierte en navegación automática. Dos barras laterales con
    contenidos distintos y sin estado compartido.
    """
    import app

    app._registrar_paginas()
    assert len(app.PAGINAS) >= 10
    for nombre, funcion in app.PAGINAS.items():
        assert callable(funcion), f"la página '{nombre}' no es invocable"


def test_las_paginas_movidas_exponen_main():
    import importlib

    for modulo in ("paginas.dashboard_financiero", "paginas.analisis_energetico"):
        assert hasattr(importlib.import_module(modulo), "main")


def test_solo_el_crm_queda_como_pagina_independiente():
    """El resto se enruta desde app.py; el admin sigue aparte a propósito."""
    import os

    archivos = [f for f in os.listdir("pages") if f.endswith(".py")]
    assert archivos == ["3_Admin_Leads.py"], archivos


# ===========================================================================
# Programa de ambientes -> geometría real (asistente Texto -> Diseño)
# ===========================================================================

def test_programa_de_ambientes_reemplaza_estimacion_generica():
    """
    Antes: Geometria SOLO podía estimar baños/puertas/ventanas por área
    (fórmula genérica de geometria_defecto.yaml). Si el lead ya dijo
    '3 dormitorios, 2 con baño', eso es un dato real, no una estimación.
    """
    estado = ProyectoState()
    estado.aplicar_metricas({
        "dormitorios": 3, "dormitorios_con_bano": 2, "banos_comunes": 1,
        "tiene_cocina": True, "tiene_sala_estar": True,
    }, origen="Texto → Diseño (IA)")

    assert estado.n_dormitorios == 3
    assert estado.n_banos == 3          # 2 privados + 1 común
    assert estado.n_puertas_interiores == 5  # 3 dormitorios + 2 con baño

    geo = estado.geometria()
    assert geo.n_banos == 3             # ya no la estimación por área
    assert geo.n_puertas_interiores == 5


def test_sin_programa_de_ambientes_geometria_sigue_estimando_por_area():
    """Retrocompatibilidad: sin programa de ambientes, Geometria sigue estimando como antes."""
    estado = ProyectoState(area_m2=120)
    estado.aplicar_metricas({"area_m2": 120}, origen="manual")

    geo = estado.geometria()
    assert geo.banos is None            # sin override explícito
    assert geo.n_banos > 0              # pero la estimación por área sigue funcionando


def test_habitaciones_se_guardan_para_el_esquema_de_planta():
    estado = ProyectoState()
    estado.aplicar_metricas({
        "habitaciones": [{"tipo": "dormitorio", "nombre": "Dormitorio 1", "area_aprox_m2": 14}],
    }, origen="Texto → Diseño (IA)")
    assert len(estado.habitaciones) == 1
    assert estado.habitaciones[0]["nombre"] == "Dormitorio 1"
