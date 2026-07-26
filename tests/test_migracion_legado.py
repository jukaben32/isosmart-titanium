# -*- coding: utf-8 -*-
"""
Guardia contra la reintroducción accidental de motores legado o muertos.

Motivo: durante la revisión de pantallas se encontraron, uno tras otro,
puntos donde una pantalla "nueva" seguía llamando al motor clásico
(`utils/calculador.py`) porque nadie había verificado exhaustivamente todos
los callers tras migrar a `utils/qto.py`. Este test barre el árbol de fuentes
y falla si alguna pantalla vuelve a importar el motor legado o el módulo de
cálculos muerto -- así la próxima vez no depende de que alguien piense en
buscarlo con grep.

    pytest tests/test_migracion_legado.py
"""

import re
from pathlib import Path

# Módulos de UI donde NO debe aparecer una importación viva del motor legado.
# Los propios utils/calculador.py y utils/calculations.py se excluyen (son
# los archivos legado en sí); tests/ se excluye (fija el legado a propósito).
ARCHIVOS_UI = [
    "app.py",
    "ui_core.py",
    "ui_inicio.py",
    "ui_team.py",
    "ui_calculadora.py",
    "ui_presupuesto.py",
    "ui_visor_bim.py",
    "ui_vision.py",
    *[str(p) for p in Path("paginas").glob("*.py")],
    *[str(p) for p in Path("pages").glob("*.py")],
]

# Módulos de utils/ que si importan el legado, arrastran el problema a
# cualquier pantalla que los use (ya pasó con utils/financiera.py).
ARCHIVOS_UTILS_NO_LEGADO = [
    str(p) for p in Path("utils").glob("*.py")
    if p.name not in ("calculador.py", "calculations.py")
]

PATRON_IMPORT_LEGADO = re.compile(
    r"^\s*from\s+utils\.calculador\s+import\s+BudgetCalculator"
    r"|^\s*import\s+utils\.calculador\b"
    r"|BudgetCalculator\.\w+\(",
    re.MULTILINE,
)

PATRON_IMPORT_MUERTO = re.compile(
    r"^\s*from\s+utils\.calculations\s+import"
    r"|^\s*import\s+utils\.calculations\b",
    re.MULTILINE,
)


def _sin_docstring_ni_comentarios(ruta: str) -> str:
    """
    Igual que en tests/test_fuentes.py: se descarta el docstring inicial del
    módulo para no confundir una mención histórica en un comentario
    ('esto ya NO se hace') con una importación real. También se descartan las
    líneas que empiezan con '#' tras eso.
    """
    codigo = Path(ruta).read_text(encoding="utf-8")
    marcador = '"""'
    primera = codigo.find(marcador)
    if primera != -1:
        segunda = codigo.find(marcador, primera + 3)
        if segunda != -1:
            codigo = codigo[segunda + 3:]

    lineas = [ln for ln in codigo.splitlines() if not ln.strip().startswith("#")]
    return "\n".join(lineas)


def test_ninguna_pantalla_importa_el_motor_legado():
    """
    El motor clásico (`BudgetCalculator`) quedó retirado de la ruta de
    cálculo en vivo el 2026-07-26 tras migrar la última pantalla que lo
    usaba. Verificado exhaustivamente uno por uno; este test lo deja
    escrito para que no haga falta repetir la búsqueda a mano.
    """
    ofensores = []
    for ruta in ARCHIVOS_UI:
        if not Path(ruta).exists():
            continue
        cuerpo = _sin_docstring_ni_comentarios(ruta)
        if PATRON_IMPORT_LEGADO.search(cuerpo):
            ofensores.append(ruta)

    assert not ofensores, (
        f"Estas pantallas volvieron a importar el motor legado: {ofensores}. "
        f"Usa utils.qto.MotorQTO en su lugar."
    )


def test_ningun_modulo_de_utils_importa_el_motor_legado():
    """
    Un módulo de utils/ que importe el legado arrastra el problema a
    cualquier pantalla que lo use sin que se note en un grep superficial de
    la propia pantalla -- exactamente como pasó con utils/financiera.py.
    """
    ofensores = []
    for ruta in ARCHIVOS_UTILS_NO_LEGADO:
        cuerpo = _sin_docstring_ni_comentarios(ruta)
        if PATRON_IMPORT_LEGADO.search(cuerpo):
            ofensores.append(ruta)

    assert not ofensores, f"Estos módulos de utils/ importan el motor legado: {ofensores}"


def test_ninguna_pantalla_importa_el_modulo_de_calculos_muerto():
    """utils/calculations.py no tiene ningún caller vivo fuera de su propio test."""
    ofensores = []
    for ruta in ARCHIVOS_UI + ARCHIVOS_UTILS_NO_LEGADO:
        if not Path(ruta).exists():
            continue
        cuerpo = _sin_docstring_ni_comentarios(ruta)
        if PATRON_IMPORT_MUERTO.search(cuerpo):
            ofensores.append(ruta)

    assert not ofensores, f"Código muerto (utils/calculations.py) reconectado en: {ofensores}"


def test_los_archivos_legado_estan_marcados_como_tales():
    """Que quede escrito en el propio archivo, no solo en este test."""
    calculador = Path("utils/calculador.py").read_text(encoding="utf-8")
    assert "MOTOR LEGADO" in calculador

    calculations = Path("utils/calculations.py").read_text(encoding="utf-8")
    assert "CÓDIGO MUERTO" in calculations


def test_motorqto_sigue_siendo_el_unico_motor_activo():
    """Contraparte positiva: MotorQTO debe seguir siendo importable y funcional."""
    from utils.geometria import Geometria
    from utils.pricebook import DEFAULT_PRICEBOOK
    from utils.qto import MotorQTO

    motor = MotorQTO(Geometria(area_m2=120), DEFAULT_PRICEBOOK)
    assert motor.total() > 0


def test_no_reaparece_el_tercer_panel_de_precios_muerto():
    """
    render_pestana_configuracion_precios() era un tercer panel de precios,
    completamente inalcanzable, con un fallback de precio SIN FUENTE
    (Panel_Muro=925, ya corregido a 1072 en utils/pricebook.py). Se eliminó
    en vez de marcarse como muerto porque no había ninguna fórmula que
    rescatar, solo una copia obsoleta de la interfaz real
    (ui_presupuesto.py::render_pestana_pricebook).
    """
    codigo = _sin_docstring_ni_comentarios("ui_calculadora.py")
    assert "def render_pestana_configuracion_precios" not in codigo
    assert "925.00" not in codigo


def test_no_reaparecen_enlaces_de_redes_sociales_muertos():
    """Los enlaces '#' de Facebook/Instagram/YouTube/LinkedIn no llevaban a ningún sitio."""
    codigo = Path("ui_calculadora.py").read_text(encoding="utf-8")
    assert "[Facebook](#)" not in codigo
    assert "facebook.com/IsotexRD" in codigo
