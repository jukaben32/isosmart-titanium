# -*- coding: utf-8 -*-
"""
Tests de trazabilidad de datos (utils/fuentes.py y ui_inicio.py).

Motivo: la pantalla de inicio mostraba nueve cifras y tres afirmaciones de
texto sin fuente. Este archivo pone reglas duras para que eso no vuelva a
pasar sin que un test lo note.

    pytest tests/test_fuentes.py
"""

import sys

import pytest

sys.path.insert(0, ".")

from utils.fuentes import (  # noqa: E402
    FICHA_COVINTEC,
    SIN_FUENTE_CONOCIDA,
    TIPO_CAMBIO_MXN_DOP,
    COSTO_TRADICIONAL_RD_M2,
    Fuente,
    convertir_mxn_a_dop,
)


# ===========================================================================
# El tipo `Fuente` no permite datos sin cita
# ===========================================================================

def test_una_fuente_sin_cita_no_se_puede_crear():
    """
    Antes 'Excelente/Regular', '45dB/20dB' y 'Alta/Media' eran texto fijo sin
    ninguna cita. `Fuente` hace ese estado irrepresentable para datos activos.
    """
    with pytest.raises(ValueError):
        Fuente(valor="Excelente", tipo="referencia", cita="")


def test_tipo_invalido_se_rechaza():
    with pytest.raises(ValueError):
        Fuente(valor="x", tipo="inventado", cita="algo")


def test_no_disponible_puede_omitir_cita_pero_no_valor_falso():
    """Un dato marcado 'no_disponible' no debe llevar un valor de reemplazo."""
    f = Fuente(valor="", tipo="no_disponible", cita="motivo de por qué no se sabe")
    assert f.valor == ""
    assert f.etiqueta == "❓ No disponible"


def test_html_footnote_escapa_y_no_reproduce_html_crudo():
    f = Fuente(valor="1", tipo="referencia", cita='<script>alert(1)</script>')
    html_out = f.html_footnote()
    assert "<script>" not in html_out
    assert "&lt;script&gt;" in html_out


# ===========================================================================
# Todas las fichas técnicas citadas tienen URL verificable
# ===========================================================================

def test_ficha_covintec_tiene_cita_y_url_cada_una():
    assert len(FICHA_COVINTEC) >= 5
    for clave, fuente in FICHA_COVINTEC.items():
        assert fuente.cita, f"{clave} no tiene cita"
        assert fuente.url and fuente.url.startswith("http"), f"{clave} no tiene URL"
        assert fuente.tipo in ("verificado", "referencia")


def test_costo_tradicional_cita_el_indice_oficial():
    """
    [doc] ICDV (ACOPROVI + ONE), no un número inventado por la app.
    """
    assert "ICDV" in COSTO_TRADICIONAL_RD_M2.cita
    assert COSTO_TRADICIONAL_RD_M2.url


# ===========================================================================
# Lo que la app YA NO afirma queda documentado, no borrado en silencio
# ===========================================================================

def test_afirmaciones_retiradas_estan_documentadas():
    """
    'Resistencia sísmica: alta (flexible) vs media (rígido)' y '180 vs 300
    días' no tenían ninguna fuente. En vez de simplemente borrarlas, quedan
    registradas como 'no_disponible' para que nadie las reintroduzca sin
    darse cuenta de que ya se investigaron y no había respaldo.
    """
    assert len(SIN_FUENTE_CONOCIDA) >= 2
    for clave, fuente in SIN_FUENTE_CONOCIDA.items():
        assert fuente.tipo == "no_disponible"
        assert fuente.valor == "", f"{clave} no debería tener un valor de reemplazo"
        assert len(fuente.cita) > 20, f"{clave} necesita explicar por qué no hay fuente"


# ===========================================================================
# Conversión de moneda trazable
# ===========================================================================

def test_conversion_mxn_dop_usa_la_tasa_declarada():
    assert convertir_mxn_a_dop(100) == pytest.approx(100 * TIPO_CAMBIO_MXN_DOP)


def test_tasa_de_cambio_es_positiva_y_razonable():
    """Un DOP vale menos que un MXN; la tasa debe reflejarlo (>1, no billones)."""
    assert 1.0 < TIPO_CAMBIO_MXN_DOP < 10.0


# ===========================================================================
# La homepage usa el motor QTO real, no el motor clásico ni cifras fijas
# ===========================================================================

def _cuerpo_sin_docstring_de_modulo(ruta: str) -> str:
    """
    Devuelve el código fuente sin el docstring inicial del módulo, para no
    confundir las menciones históricas dentro de un comentario ('esto ya NO
    se hace') con el código que realmente se ejecuta.
    """
    codigo = open(ruta, encoding="utf-8").read()
    marcador = '"""'
    primera = codigo.find(marcador)
    if primera == -1:
        return codigo
    segunda = codigo.find(marcador, primera + 3)
    if segunda == -1:
        return codigo
    return codigo[segunda + 3:]


def test_ui_inicio_no_usa_el_motor_clasico():
    """
    Bug: ui_inicio.py llamaba a `BudgetCalculator.comparar_sistemas()`, que
    producía el 83.6% de ahorro constante (gris EPS vs terminada tradicional).
    """
    cuerpo = _cuerpo_sin_docstring_de_modulo("ui_inicio.py")
    helper = _cuerpo_sin_docstring_de_modulo("utils/comparativa_inicio.py")
    assert "comparar_sistemas" not in cuerpo
    assert "comparar_sistemas" not in helper
    assert "calcular_comparativa_area" in cuerpo
    assert "MotorQTO" in helper
    assert "comparar_con_tradicional" in helper


def test_ui_inicio_no_contiene_texto_fijo_sin_fuente():
    """
    Antes: 'Excelente', 'Regular', 'Hasta 45dB', '~20dB', 'Alta (flexible)',
    'Media (rígido)', '-30%', '-40%', '-5°C' aparecían como texto plano en el
    código que se ejecuta (el docstring puede mencionarlos como contexto
    histórico; el cuerpo del módulo no debe volver a usarlos).
    """
    cuerpo = _cuerpo_sin_docstring_de_modulo("ui_inicio.py")
    for texto_prohibido in ("~20dB", "Media (rígido)", "-40%", "-5°C",
                            "70% menos peso", "3 veces más rápido"):
        assert texto_prohibido not in cuerpo, f"reapareció el texto sin fuente: {texto_prohibido!r}"


def test_ui_inicio_importa_el_sistema_de_fuentes():
    codigo = open("ui_inicio.py", encoding="utf-8").read()
    assert "from utils.fuentes import" in codigo
    assert "FICHA_COVINTEC" in codigo


def test_ui_inicio_es_utf8_valido():
    """Un heredoc de bash corrompió este archivo una vez; que no vuelva a pasar en silencio."""
    with open("ui_inicio.py", encoding="utf-8") as f:
        contenido = f.read()
    assert "República Dominicana" in contenido
    assert "página" in contenido


def test_ui_inicio_pagina_inicio_es_invocable():
    """La página debe ejecutarse sin lanzar NameError ni ImportError."""
    import importlib

    import ui_inicio
    importlib.reload(ui_inicio)
    assert callable(ui_inicio.pagina_inicio)


# ===========================================================================
# El pricebook: precios reemplazados llevan comentario de origen
# ===========================================================================

def test_precios_covintec_reemplazados_estan_documentados_en_pricebook():
    codigo = open("utils/pricebook.py", encoding="utf-8").read()
    assert "Materiales La Libertad" in codigo
    assert "Paneles y Plafones MG" in codigo
    assert "1,072" in codigo or "1072" in codigo


def test_panel_muro_ya_no_es_el_precio_sin_fuente_original():
    from utils.pricebook import DEFAULT_PRICEBOOK

    assert DEFAULT_PRICEBOOK["Panel_Muro"] != 925.00
    assert DEFAULT_PRICEBOOK["Panel_Muro"] == pytest.approx(1072.0, abs=1.0)


# ===========================================================================
# Testimonios y galería fabricados en ui_team.py
# ===========================================================================

def _codigo_ejecutable(ruta: str) -> str:
    """Descarta docstring inicial y líneas de comentario (mismo patrón que
    _cuerpo_sin_docstring_de_modulo en tests/test_migracion_legado.py): una
    mención histórica en un comentario no debe confundirse con el texto que
    realmente ve el usuario."""
    codigo = open(ruta, encoding="utf-8").read()
    marcador = '"""'
    primera = codigo.find(marcador)
    if primera != -1:
        segunda = codigo.find(marcador, primera + 3)
        if segunda != -1:
            codigo = codigo[segunda + 3:]
    return "\n".join(ln for ln in codigo.splitlines() if not ln.strip().startswith("#"))


def test_ui_team_no_contiene_testimonios_fabricados():
    """
    Bug: el propio código marcaba la sección como "Testimonios (placeholder)"
    pero se mostraba al usuario como reseñas reales atribuidas a personas
    con nombre ("Juan P.", "Arq. María G."). Presentar citas inventadas como
    testimonios reales es publicidad engañosa, no un dato con fuente débil.
    """
    codigo = _codigo_ejecutable("ui_team.py")
    assert "Juan P." not in codigo
    assert "Arq. María G." not in codigo


def test_ui_team_no_presenta_fotos_de_stock_como_proyectos_reales():
    """
    Bug: fotos de stock de Unsplash con pies de foto como si fueran proyectos
    propios terminados ("Vivienda Unifamiliar - 150m²", "Edificio de
    Apartamentos"). Ahora deben estar marcadas explícitamente como
    ilustrativas.
    """
    codigo = _codigo_ejecutable("ui_team.py")
    assert "Vivienda Unifamiliar - 150m²" not in codigo
    assert "Edificio de Apartamentos" not in codigo
    assert 'caption="Local Comercial"' not in codigo
    assert "ilustrativ" in codigo.lower()


def test_ui_team_admite_la_falta_de_testimonios_reales():
    codigo = open("ui_team.py", encoding="utf-8").read()
    assert "no se han recopilado testimonios" in codigo.lower()


# ===========================================================================
# Fuente local (Isotex Dominicana) — verificada como contacto real
# ===========================================================================

def test_ficha_isotex_dominicana_tiene_cita_y_url_cada_una():
    from utils.fuentes import FICHA_ISOTEX_DOMINICANA

    assert len(FICHA_ISOTEX_DOMINICANA) >= 5
    for clave, fuente in FICHA_ISOTEX_DOMINICANA.items():
        assert fuente.cita, f"{clave} no tiene cita"
        assert fuente.url and "isotexdominicana.com" in fuente.url, f"{clave} sin URL local"


def test_afirmacion_de_ahorro_del_fabricante_no_se_marca_como_verificada():
    """
    El "hasta 65%" es una afirmación de marketing del propio fabricante, no
    una medición independiente. No debe colarse como tipo='verificado'.
    """
    from utils.fuentes import FICHA_ISOTEX_DOMINICANA

    ahorro = FICHA_ISOTEX_DOMINICANA["mpanel_ahorro_energetico_pct"]
    assert ahorro.tipo == "referencia"
    assert "FABRICANTE" in ahorro.cita or "fabricante" in ahorro.cita
