"""
Tests del motor de cantidades (utils/qto.py) y del modelo geométrico.

A diferencia de tests/comparar_calculadoras.py —que fija los números del motor
antiguo y por tanto garantiza que el error del 300% no cambie nunca— estos tests
comprueban **propiedades físicas y de negocio**: que las cantidades respondan a
la geometría, que respeten los espesores de la base técnica, y que la
comparación sea gris contra gris.

    pytest tests/test_qto.py
"""

import math
import sys

import pytest

sys.path.insert(0, ".")

from utils.geometria import Geometria  # noqa: E402
from utils.parametros import cargar_parametros  # noqa: E402
from utils.qto import CATEGORIAS_OBRA_GRIS, MotorQTO  # noqa: E402

P = cargar_parametros()


def geo(**kwargs) -> Geometria:
    base = dict(area_m2=120.0, perimetro_m=44.0, altura_muro_m=2.8, niveles=1)
    base.update(kwargs)
    return Geometria(**base)


# ===========================================================================
# Geometría: el cable que faltaba entre la visión artificial y el cálculo
# ===========================================================================

def test_area_de_muros_depende_del_perimetro_real():
    """
    Bug corregido: el motor usaba `area_muros = m2 * 2.2`, una constante. Dos
    casas de 120 m² con perímetros muy distintos (compacta vs alargada)
    cotizaban exactamente igual, y toda la extracción geométrica era decorativa.
    """
    compacta = geo(perimetro_m=44.0)
    alargada = geo(perimetro_m=70.0)

    assert alargada.area_muros_m2 > compacta.area_muros_m2
    assert alargada.n_paneles_muro > compacta.n_paneles_muro

    total_compacta = MotorQTO(compacta).total()
    total_alargada = MotorQTO(alargada).total()
    assert total_alargada > total_compacta, "el perímetro debe mover el presupuesto"


def test_niveles_afectan_muros_y_entrepiso():
    una_planta = geo(area_m2=240.0, perimetro_m=44.0, niveles=1)
    dos_plantas = geo(area_m2=240.0, perimetro_m=44.0, niveles=2)

    assert dos_plantas.area_losa_entrepiso_m2 > 0
    assert una_planta.area_losa_entrepiso_m2 == 0
    # Misma área construida pero la mitad de huella: menos cimentación.
    assert dos_plantas.area_cimentacion_m2 < una_planta.area_cimentacion_m2


def test_perimetro_estimado_es_razonable_si_no_se_conoce():
    """Sin perímetro se estima con proporción 3:2, no con un cuadrado."""
    g = Geometria(area_m2=120.0)
    assert 40 < g.perimetro_efectivo_m < 50
    # Un cuadrado daría el mínimo teórico y subestimaría los muros.
    assert g.perimetro_efectivo_m > 4 * math.sqrt(120)


def test_geometria_rechaza_valores_imposibles():
    with pytest.raises(ValueError):
        Geometria(area_m2=0)
    with pytest.raises(ValueError):
        Geometria(area_m2=120, niveles=0)
    with pytest.raises(ValueError):
        Geometria(area_m2=120, perimetro_m=-5)


def test_geometria_se_construye_desde_session_state():
    """Las claves que la app escribía y nunca leía ahora tienen un consumidor."""
    estado = {
        "calc_area_m2": 180.0,
        "calc_perimetro_m": 58.0,
        "calc_altura_muro_m": 3.0,
        "calc_niveles": 2,
    }
    g = Geometria.desde_session_state(estado)
    assert g.area_m2 == 180.0
    assert g.perimetro_efectivo_m == 58.0
    assert g.altura_efectiva_m == 3.0
    assert g.niveles == 2


def test_paneles_se_modulan_a_1_22_hacia_arriba():
    """[doc] metros lineales / 1.22 -> piezas, redondeando hacia arriba."""
    g = geo()
    esperado = math.ceil(g.ml_muros_total / P["panel"]["ancho_util_m"])
    assert g.n_paneles_muro == esperado
    assert g.area_panel_comprada_m2 >= g.area_muros_m2  # la modulación agrega merma real


# ===========================================================================
# Espesores: coherencia con docs/BASE_TECNICA_EPS_ICF.md
# ===========================================================================

def test_mortero_usa_2_5_cm_por_cara_no_12_cm():
    """
    Bug: `vol_hormigon = (area_muros + area_techo) * 0.12` aplicaba 12 cm de
    concreto sobre muros y techo. La base técnica especifica 2.5 cm de mortero
    por cara. El motor anterior sobreestimaba el volumen ~2.5x.
    """
    g = geo()
    motor = MotorQTO(g)
    mortero = next(p for p in motor.partidas() if p.partida == "Mortero de revoque")

    esperado_m3 = g.area_muros_m2 * 2 * P["espesores"]["mortero_muro_por_cara_m"]
    bultos_esperados = esperado_m3 / P["mezclas"]["mortero"]["rendimiento_m3_por_bulto"]

    assert mortero.cantidad_neta == pytest.approx(bultos_esperados, rel=1e-6)


def test_losa_azotea_usa_5_cm():
    g = geo()
    motor = MotorQTO(g)
    losa = next(p for p in motor.partidas() if "azotea" in p.partida)
    esperado = g.area_losa_azotea_m2 * P["espesores"]["losa_azotea_m"]
    assert losa.cantidad_neta == pytest.approx(esperado, rel=1e-6)


def test_mallas_siguen_las_formulas_del_documento():
    """[doc] ventana 90x90 = 12 pzas; puerta = 13 pzas; AMBOS LADOS (x2)."""
    g = geo(ventanas=6, puertas_exteriores=2, puertas_interiores=5)
    motor = MotorQTO(g)
    zigzag = next(p for p in motor.partidas() if p.partida == "Malla zigzag en vanos")

    esperado = (6 * 12 + 7 * 13) * 2
    assert zigzag.cantidad_neta == esperado

    esquinera = next(p for p in motor.partidas() if p.partida == "Malla esquinera")
    assert esquinera.cantidad_neta == math.ceil(4 * 2.8 / 2.40)


def test_anclas_son_tres_por_panel():
    """[doc] anclas de 3/8", cada 40 cm, 3 por panel."""
    g = geo()
    motor = MotorQTO(g)
    anclas = next(p for p in motor.partidas() if "Anclas" in p.partida)
    n_esperadas = g.n_paneles_muro * P["anclaje"]["anclas_por_panel"]
    kg = (n_esperadas * P["anclaje"]["longitud_ancla_m"]
          * P["anclaje"]["peso_varilla_3_8_kg_por_m"])
    assert anclas.cantidad_neta == pytest.approx(kg, rel=1e-6)


# ===========================================================================
# Completitud del presupuesto
# ===========================================================================

def test_el_presupuesto_incluye_todas_las_partidas_criticas():
    """
    Bug: el motor anterior omitía instalaciones, ventanas, baños, cocina,
    impermeabilización, cielo raso y mano de obra. La obra terminada quedaba en
    el 9.6% del total cuando en una vivienda real es 35-50%.
    """
    df = MotorQTO(geo()).presupuesto()
    texto = " ".join(df["partida"]).lower()

    for imprescindible in ("eléctrica", "sanitaria", "ventana", "inodoro",
                           "gabinete", "impermeabiliz", "cielo raso",
                           "aplanado", "mortero", "malla", "ancla"):
        assert imprescindible in texto, f"falta la partida: {imprescindible}"


def test_obra_terminada_es_una_fraccion_realista():
    motor = MotorQTO(geo())
    fraccion = motor.total_obra_terminada() / motor.total()
    assert 0.30 <= fraccion <= 0.60, f"obra terminada = {fraccion:.1%} (antes 9.6%)"


def test_todas_las_partidas_tienen_precio_y_cantidad_positiva():
    for p in MotorQTO(geo()).partidas():
        assert p.cantidad >= 0, p.partida
        assert p.precio_unitario > 0, p.partida
        assert p.clave_precio, p.partida


def test_mano_de_obra_esta_presente_y_pesa():
    motor = MotorQTO(geo())
    mo = sum(p.subtotal for p in motor.partidas() if p.categoria == "Mano de obra")
    assert mo > 0
    assert mo / motor.total() > 0.05, "la mano de obra no puede ser marginal"


def test_lanzadora_neumatica_abarata_el_aplanado():
    """[doc] manual 15-20 m²/día vs lanzadora 60-70 m²/día."""
    manual = MotorQTO(geo(), aplanado_mecanizado=False).total()
    mecanizado = MotorQTO(geo(), aplanado_mecanizado=True).total()
    assert mecanizado < manual


# ===========================================================================
# Comparación gris vs gris
# ===========================================================================

def test_comparacion_es_gris_contra_gris():
    """
    [doc] "El '83%' viejo comparaba obra gris EPS vs obra TERMINADA tradicional
    (peras con manzanas). Corregir a comparación gris vs gris."
    """
    c = MotorQTO(geo()).comparar_con_tradicional()

    # Los acabados son idénticos en ambos sistemas.
    assert c["eps"]["obra_terminada"] == c["tradicional"]["obra_terminada"]
    # El ahorro se aplica solo sobre la obra gris.
    assert c["ahorro"]["obra_gris_pct"] == pytest.approx(27.5)
    # Y por tanto sobre el total es necesariamente menor.
    assert c["ahorro"]["total_pct"] < c["ahorro"]["obra_gris_pct"]


def test_el_ahorro_ya_no_es_una_constante_del_83_por_ciento():
    """
    Bug: `comparar_sistemas` devolvía 83.6% para 60, 120 y 300 m² por igual,
    porque era el cociente de dos constantes por m², no un cálculo.
    """
    porcentajes = [
        MotorQTO(geo(area_m2=a, perimetro_m=p)).comparar_con_tradicional()["ahorro"]["total_pct"]
        for a, p in ((60, 32), (120, 44), (300, 70))
    ]
    assert len(set(round(x, 3) for x in porcentajes)) > 1, "el ahorro debe variar con el proyecto"
    assert all(5 < x < 45 for x in porcentajes), f"fuera del rango defendible: {porcentajes}"


def test_costo_por_m2_baja_con_el_tamano():
    """Economía de escala: partidas fijas repartidas sobre más área."""
    chico = MotorQTO(geo(area_m2=60, perimetro_m=32)).costo_m2()
    grande = MotorQTO(geo(area_m2=300, perimetro_m=70)).costo_m2()
    assert grande < chico


# ===========================================================================
# Trazabilidad de precios
# ===========================================================================

def test_los_precios_de_referencia_estan_marcados():
    """
    [doc] "NO inventar cifras: mientras tanto, referencia Covintex convertida".
    Las partidas con precio no verificado deben poder identificarse para que la
    UI y el PDF lo adviertan.
    """
    motor = MotorQTO(geo())
    por_verificar = motor.partidas_por_verificar()
    assert len(por_verificar) > 0
    assert "Instalacion_electrica_m2" in set(por_verificar["clave_precio"])


def test_precio_ausente_falla_ruidosamente():
    """Un pricebook incompleto debe reventar, no cotizar con ceros."""
    with pytest.raises(KeyError, match="pricebook"):
        MotorQTO(geo(), precios={"Panel_Muro": 925.0}).partidas()


def test_calidad_mueve_el_presupuesto_de_forma_significativa():
    """
    En el motor anterior "económica" y "lujo" diferían solo un 7%, porque los
    acabados eran 3 líneas. Ahora la calidad afecta pisos, pintura, cielo raso,
    carpintería, baños y cocina.
    """
    economica = MotorQTO(geo(), calidad="economica").total()
    lujo = MotorQTO(geo(), calidad="lujo").total()
    assert lujo / economica > 1.30, f"la calidad apenas mueve el total: {lujo/economica:.2f}x"


def test_zona_de_riesgo_incrementa_acero():
    base = MotorQTO(geo(), zona_riesgo="moderado").total()
    huracan = MotorQTO(geo(), zona_riesgo="muy alto").total()
    assert huracan > base


def test_categorias_de_obra_gris_son_coherentes():
    resumen = MotorQTO(geo()).resumen_por_categoria()
    grises = set(resumen[resumen["obra"] == "Gris"]["categoria"])
    assert grises <= set(CATEGORIAS_OBRA_GRIS)
    assert resumen["pct"].sum() == pytest.approx(100.0, rel=1e-6)


# ===========================================================================
# Precisión de la cimentación (revisión "cada detalle de la obra", 2026-07-26)
# ===========================================================================

def test_replantillo_es_una_capa_distinta_de_la_plantilla():
    """
    Bug: `data/parametros_tecnicos.yaml` define `replantillo_m` (12-15 cm,
    [doc] sección 3) pero el motor nunca lo usaba -- una capa de cimentación
    completa, documentada, estaba ausente del cálculo. El documento distingue
    explícitamente replantillo (fondo de excavación) de la plantilla de
    concreto pobre (nivelación, sobre el replantillo): son dos partidas, no una.
    """
    motor = MotorQTO(geo())
    nombres = {p.partida for p in motor.partidas() if p.categoria == "Cimentación"}
    assert "Replantillo" in nombres
    assert "Plantilla de concreto pobre" in nombres

    replantillo = next(p for p in motor.partidas() if p.partida == "Replantillo")
    plantilla = next(p for p in motor.partidas() if p.partida == "Plantilla de concreto pobre")
    assert replantillo.cantidad_neta != plantilla.cantidad_neta  # espesores distintos
    esperado_replantillo = geo().area_cimentacion_m2 * P["espesores"]["replantillo_m"]
    assert replantillo.cantidad_neta == pytest.approx(esperado_replantillo, rel=1e-6)


def test_cimentacion_usa_la_resistencia_de_concreto_correcta():
    """
    Bug: la platea de cimentación (250 kg/cm² según el doc) se pagaba con
    `H_3000_PSI * 1.20`, un multiplicador arbitrario sin fuente, mientras el
    pricebook YA tenía `H_3500_PSI` (~246 kg/cm², la resistencia disponible
    más cercana a los 250 kg/cm² requeridos). Ahora usa esa clave
    directamente en vez de fabricar un precio sintético.
    """
    from utils.pricebook import DEFAULT_PRICEBOOK

    motor = MotorQTO(geo(), DEFAULT_PRICEBOOK)
    platea = next(p for p in motor.partidas() if p.partida == "Losa de cimentación (platea)")

    assert platea.clave_precio == "H_3500_PSI"
    assert platea.precio_unitario == pytest.approx(DEFAULT_PRICEBOOK["H_3500_PSI"])


def test_todas_las_cimentacion_tienen_precio_positivo():
    """Verificación de cordura tras agregar la capa de replantillo."""
    motor = MotorQTO(geo())
    for p in motor.partidas():
        if p.categoria == "Cimentación":
            assert p.cantidad_neta > 0, p.partida
            assert p.subtotal > 0, p.partida


# ===========================================================================
# Trazabilidad correcta del campo `fuente` por partida
# ===========================================================================

def test_partidas_sin_formula_del_documento_no_se_marcan_doc():
    """
    Bug: el campo `fuente` de `Partida` tiene un valor por defecto "[doc]".
    Partidas cuya cantidad depende de supuestos de geometria_defecto.yaml
    (conteo de puertas/ventanas/baños por área, cobertura de pintura,
    longitud de anclas) se etiquetaban "[doc]" por omisión, sin que nadie lo
    hubiera decidido explícitamente -- exactamente el patrón de dato "con
    apariencia de fuente" que esta auditoría persigue en el resto de la app.
    """
    motor = MotorQTO(geo())
    partidas_por_nombre = {p.partida: p for p in motor.partidas()}

    deben_ser_supuesto = (
        "Anclas / bastones 3/8\"", "Piso", "Pintura",
        "Puertas interiores", "Ventanas de aluminio",
        "Inodoros", "Lavamanos", "Duchas", "Grifería",
        "Gabinetes", "Mesón de granito", "Fregadero",
        "Replantillo", "Malla electrosoldada 10x10",
    )
    for nombre in deben_ser_supuesto:
        assert partidas_por_nombre[nombre].fuente == "[supuesto]", (
            f"'{nombre}' no tiene una fórmula de docs/BASE_TECNICA_EPS_ICF.md "
            f"y no debería marcarse [doc]"
        )


def test_partidas_con_formula_real_del_documento_si_se_marcan_doc():
    """Contraparte: las que SÍ vienen literalmente del documento deben conservar [doc]."""
    motor = MotorQTO(geo())
    partidas_por_nombre = {p.partida: p for p in motor.partidas()}

    deben_ser_doc = (
        "Mortero de revoque",           # 2.5 cm/cara, doc sección 2
        "Malla zigzag en vanos",        # 12/13 piezas x2, doc sección 4
        "Malla esquinera",              # (esquinas x altura)/2.40, doc sección 4
        "Aplanado (manual)",            # 15-20 m²/día, doc sección 5
        "Losa de cimentación (platea)",  # 250 kg/cm², doc sección 2
    )
    for nombre in deben_ser_doc:
        assert partidas_por_nombre[nombre].fuente == "[doc]", nombre


def test_malla_zigzag_advierte_sobre_el_tamano_de_vano_asumido():
    """
    Limitación real: Geometria no rastrea las dimensiones de ventanas/puertas,
    solo su cantidad. La fórmula del documento (12/13 piezas) está calibrada
    para vanos de referencia (90x90 cm ventana, 215x90 cm puerta); si los
    vanos reales del proyecto son más grandes, la malla se queda corta. Debe
    quedar advertido en el detalle de la partida, no asumido en silencio.
    """
    motor = MotorQTO(geo())
    zigzag = next(p for p in motor.partidas() if p.partida == "Malla zigzag en vanos")
    assert "90x90" in zigzag.detalle or "referencia" in zigzag.detalle.lower()
