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
    """
    [doc] ventana 90x90 = 12 pzas; puerta = 13 pzas -- AMBAS CARAS incluidas.

    CORREGIDO (verificado con NotebookLM del usuario): el motor venía
    multiplicando estos conteos por 2 otra vez ("zigzag_lados"), duplicando
    la partida. El propio video que dio el ejemplo numérico resuelto aclara
    que 12/13 YA es el total de ambas caras (4 lados x 2 caras = 8 + 4
    diagonales = 12), no un valor "por cara" que haya que doblar.
    """
    g = geo(ventanas=6, puertas_exteriores=2, puertas_interiores=5)
    motor = MotorQTO(g)
    zigzag = next(p for p in motor.partidas() if p.partida == "Malla zigzag en vanos")

    esperado = 6 * 12 + 7 * 13  # antes: esto x 2 (326), ahora: sin duplicar (163)
    assert zigzag.cantidad_neta == esperado
    assert zigzag.cantidad_neta == 163

    esquinera_interna = next(p for p in motor.partidas() if p.partida == "Malla esquinera interna")
    esquinera_externa = next(p for p in motor.partidas() if p.partida == "Malla esquinera externa")
    # Verificado con ejemplo numérico resuelto: esquina de 2.8m -> 2 pzas de
    # CADA tipo (ceil(2.8/2.40)=2), no ceil(2.8*2/2.40)=3 (subestimaría).
    piezas_por_esquina = math.ceil(2.8 / 2.40)
    esperado_por_esquinas = 4 * piezas_por_esquina  # 4 esquinas efectivas por defecto
    assert esquinera_interna.cantidad_neta >= esperado_por_esquinas
    assert esquinera_externa.cantidad_neta == esquinera_interna.cantidad_neta  # mismo conteo, producto distinto


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
    Bug: la platea de cimentación se pagaba con `H_3000_PSI * 1.20`, un
    multiplicador arbitrario sin fuente. Se corrigió inicialmente a
    H_3500_PSI (250 kg/cm² según BASE_TECNICA_EPS_ICF.md), pero el Manual
    Técnico Panel Covintec 2011 (fuente primaria del fabricante) especifica
    200 kg/cm² para esta misma partida -- más cercano a H_3000_PSI
    (≈211 kg/cm²), no a H_3500_PSI (≈246 kg/cm²).
    """
    from utils.pricebook import DEFAULT_PRICEBOOK

    motor = MotorQTO(geo(), DEFAULT_PRICEBOOK)
    platea = next(p for p in motor.partidas() if p.partida == "Losa de cimentación (platea)")

    assert platea.clave_precio == "H_3000_PSI"
    assert platea.precio_unitario == pytest.approx(DEFAULT_PRICEBOOK["H_3000_PSI"])


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
        "Piso", "Pintura",
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
        "Malla esquinera interna",      # (esquinas x altura)/2.40, doc sección 4
        "Malla esquinera externa",      # producto distinto, misma fórmula
        "Aplanado (manual)",            # 15-20 m²/día, doc sección 5
        "Losa de cimentación (platea)",  # 200 kg/cm², Manual Técnico Covintec 2011
        "Anclas / bastones 3/8\" (recibidores de cortante en 'U')",  # Manual Técnico Covintec 2011
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


# ===========================================================================
# Dimensiones reales de vano (continuación de la revisión de precisión)
# ===========================================================================

def test_vanos_de_tamano_por_defecto_no_cambian_el_comportamiento_anterior():
    """
    Sin dimensiones de vano indicadas, el resultado debe usar el conteo de
    referencia documentado (12/13, ya con ambas caras incluidas).
    """
    g = geo()
    assert g._es_ventana_referencia
    assert g._es_puerta_referencia
    assert g.piezas_zigzag_por_ventana(12, 0.40, 2) == 12
    assert g.piezas_zigzag_por_puerta(13, 0.40, 2) == 13


def test_formula_de_vano_no_estandar_verificada_con_ejemplo_resuelto():
    """
    VERIFICADO con un ejemplo numérico resuelto por el usuario (video
    "Cuantificación de Materiales", NotebookLM): una ventana de 1.5x1.2 m
    con excedente de 40 cm/esquina da EXACTAMENTE 12 piezas.

        perímetro (5.4 m) + 4 x 0.40 m (1.6 m) = 7.0 m por cara
        7.0 m x 2 caras = 14.0 m -> 14.0 / 1.22 m = 11.47 -> redondeo: 12

    Un intento anterior de implementar esta fórmula dio un resultado
    físicamente implausible por un error de comparación (se comparó el
    valor de una sola cara contra el conteo de referencia, que ya incluye
    ambas). Con el ejemplo resuelto, la fórmula queda verificada.
    """
    g = geo(ancho_ventana_m=1.5, alto_ventana_m=1.2)
    assert not g._es_ventana_referencia
    assert g.piezas_zigzag_por_ventana(12, 0.40, 2) == 12


def test_ventanas_reales_mas_grandes_aumentan_la_malla_zigzag():
    """Una ventana bastante más grande que la de referencia sí debe pedir más malla."""
    referencia = MotorQTO(geo())
    grande = MotorQTO(geo(ancho_ventana_m=2.5, alto_ventana_m=2.0))

    zz_ref = next(p for p in referencia.partidas() if p.partida == "Malla zigzag en vanos")
    zz_grande = next(p for p in grande.partidas() if p.partida == "Malla zigzag en vanos")

    assert zz_grande.cantidad_neta > zz_ref.cantidad_neta
    assert zz_ref.fuente == "[doc]"
    assert zz_grande.fuente == "[doc]"  # la fórmula para vano no estándar también es [doc], ya verificada


def test_formula_de_vano_es_monotona_con_el_tamano():
    """Una ventana más grande nunca debe implicar menos malla que una más chica."""
    chica = geo(ancho_ventana_m=1.0, alto_ventana_m=1.0)
    grande = geo(ancho_ventana_m=2.0, alto_ventana_m=2.0)

    piezas_chica = chica.piezas_zigzag_por_ventana(12, 0.40, 2)
    piezas_grande = grande.piezas_zigzag_por_ventana(12, 0.40, 2)
    assert piezas_grande > piezas_chica


# ===========================================================================
# Conflicto de anclaje documentado (no resuelto por diseño)
# ===========================================================================

def test_el_conflicto_de_anclaje_fue_resuelto_con_fuente_primaria():
    """
    Encontrado en la ronda anterior: BASE_TECNICA_EPS_ICF.md decía "5 cm
    dentro de cimentación" para las anclas; un manual de instalación
    distinto mencionaba "40-50 cm de empotramiento" para un elemento sin
    identificar con certeza -- una discrepancia de 8-10x sin resolver.

    El Manual Técnico Panel Covintec 2011 (fuente PRIMARIA del fabricante,
    corroborada en 5 copias independientes) lo resuelve con precisión:
    10 cm empotrados + 40 cm libres hacia el muro. Ninguna de las dos cifras
    anteriores era correcta tal cual.
    """
    motor = MotorQTO(geo())
    anclas = next(p for p in motor.partidas() if "Anclas" in p.partida)

    assert anclas.fuente == "[doc]"
    assert "10 cm" in anclas.detalle
    assert "40 cm" in anclas.detalle
    assert "Manual Técnico" in anclas.detalle

    assert P["anclaje"]["longitud_empotrada_m"] == pytest.approx(0.10)
    assert P["anclaje"]["longitud_libre_muro_m"] == pytest.approx(0.40)
    assert P["anclaje"]["longitud_ancla_m"] == pytest.approx(0.50)
    assert "fuente_manual_tecnico_covintec" in P["anclaje"]


def test_dentellon_perimetral_esta_incluido():
    """
    Elemento encontrado en el Manual Técnico Panel Covintec 2011 (sección
    1.3) que no estaba en el modelo: un refuerzo de sección trapezoidal bajo
    el perímetro de la losa de cimentación.
    """
    motor = MotorQTO(geo())
    nombres = {p.partida for p in motor.partidas() if p.categoria == "Cimentación"}
    assert "Dentellón perimetral" in nombres

    dentellon = next(p for p in motor.partidas() if p.partida == "Dentellón perimetral")
    assert dentellon.cantidad_neta > 0
    assert dentellon.fuente == "[doc]"


# ===========================================================================
# Mano de obra: verificación de la convención de rendimiento (no un bug)
# ===========================================================================

def test_jornal_no_es_un_triple_conteo():
    """
    Al auditar `_jornal()` parecía, a primera vista, un posible triple conteo:
    ¿por qué multiplicar días por tamaño de cuadrilla si el rendimiento ya
    "incluye" a la cuadrilla? Se verificó contra la convención estándar de
    Análisis de Precios Unitarios (APU): el rendimiento (m²/día) SIEMPRE se
    reporta como producción de la CUADRILLA completa, nunca de un trabajador
    individual (ej. real de tabla de referencia: "1 Albañil + 1 Ayudante +
    1 Peón -> aplanado exterior: 24 m²/día", no 24 m²/día por persona).

    Este test fija el resultado verificado para que una futura "corrección"
    -- quitar la multiplicación por cuadrilla_personas pensando que es un
    triple conteo -- se note inmediatamente.
    """
    motor = MotorQTO(geo())
    aplanado = next(p for p in motor.partidas() if "Aplanado" in p.partida)

    area_aplanado = motor.geo.area_muros_m2 * 2  # ambas caras
    rendimiento = P["mano_obra"]["aplanado_m2_dia_manual"]
    cuadrilla = P["mano_obra"]["cuadrilla_personas"]

    dias_cuadrilla_esperados = area_aplanado / rendimiento
    persona_dias_esperados = dias_cuadrilla_esperados * cuadrilla

    assert aplanado.cantidad_neta == pytest.approx(persona_dias_esperados, rel=1e-6)
    # Y NO debe coincidir con los días de cuadrilla sin multiplicar (lo que
    # daría una "corrección" errónea si alguien quita el factor de cuadrilla).
    assert aplanado.cantidad_neta != pytest.approx(dias_cuadrilla_esperados, rel=1e-6)


def test_cuadrilla_de_tres_personas_esta_documentada_no_es_arbitraria():
    """cuadrilla_personas=3 corresponde a la composición típica reportada en
    tablas de rendimiento APU para aplanado/repello (1 Albañil + 1 Ayudante +
    1 Peón), no a un número elegido al azar."""
    assert P["mano_obra"]["cuadrilla_personas"] == 3


# ===========================================================================
# NotebookLM del usuario: videos #37, #42, #20/34 (2026-07-26)
# ===========================================================================

def test_rendimientos_de_mano_de_obra_actualizados_con_video_de_costos():
    """
    Bug: montaje_panel_m2_dia=45.0 y losa_m2_dia=30.0 eran [supuesto] sin
    ninguna fuente. El video "Costos del sistema Covintec" (NotebookLM del
    usuario) da los rendimientos reales de cuadrilla:
    - Armado de muros: cuadrilla (1 oficial + 2 ayudantes) rinde 18 m²/día
    - Armado de losa (Qualylosa): 15 m²/día
    Ambos significativamente más lentos que los supuestos anteriores.
    """
    assert P["mano_obra"]["montaje_panel_m2_dia"] == pytest.approx(18.0)
    assert P["mano_obra"]["losa_m2_dia"] == pytest.approx(15.0)

    motor = MotorQTO(geo())
    montaje = next(p for p in motor.partidas() if p.partida == "Montaje de panel")
    losas = next(p for p in motor.partidas() if p.partida == "Losas")
    assert montaje.fuente == "[doc]"
    assert losas.fuente == "[doc]"


def test_herramienta_menor_esta_incluida():
    """
    El video de costos cita el Art. 185 de la Ley de Obras Públicas: el
    Costo Directo incluye materiales + mano de obra + herramienta. La
    herramienta menor (3% de mano de obra) estaba completamente ausente.
    """
    motor = MotorQTO(geo())
    nombres_mo = {p.partida for p in motor.partidas() if p.categoria == "Mano de obra"}
    assert "Herramienta menor" in nombres_mo

    herramienta = next(p for p in motor.partidas() if p.partida == "Herramienta menor")
    otras_mo = [p for p in motor.partidas()
               if p.categoria == "Mano de obra" and p.partida != "Herramienta menor"]
    subtotal_otras = sum(p.subtotal for p in otras_mo)

    assert herramienta.subtotal == pytest.approx(subtotal_otras * 0.03, rel=1e-6)


def test_capa_de_compresion_azotea_corroborada_por_dos_fuentes():
    """
    La ronda anterior había bajado esto a 3.5cm citando una ficha de
    producto específica del Manual Técnico Covintec. El video de
    cuantificación ("4 a 5 cm en azoteas") corrobora el rango original de
    BASE_TECNICA_EPS_ICF.md (5cm) con una fuente independiente -- se revierte
    al punto medio del rango confirmado (4.5cm) en vez del dato de ficha de
    producto, más estrecho.
    """
    assert P["espesores"]["losa_azotea_m"] == pytest.approx(0.045)


def test_formula_de_vano_no_estandar_esta_desplegada_y_verificada():
    """
    Contraparte del intento anterior: con el ejemplo numérico resuelto por
    el usuario, la fórmula quedó verificada y SÍ se desplegó (antes se
    había mantenido la extrapolación conservadora por no poder confirmar
    que la fórmula tenía sentido físico).
    """
    motor = MotorQTO(geo(ancho_ventana_m=1.5, alto_ventana_m=1.2))
    zigzag = next(p for p in motor.partidas() if p.partida == "Malla zigzag en vanos")
    assert "verificado con ejemplo numérico resuelto" in zigzag.detalle


def test_malla_union_incluye_la_condicion_de_altura():
    """
    Video de cuantificación: "malla unión necesaria cuando la altura del
    muro supera los 2.44 m". La altura por defecto del proyecto (2.80 m)
    supera ese umbral, así que la costura horizontal debe estar presente.
    """
    motor = MotorQTO(geo(altura_muro_m=2.80))
    union = next(p for p in motor.partidas() if "unión" in p.partida.lower())
    assert union.fuente == "[doc]"
    assert "2.44" in union.detalle


def test_malla_union_sin_condicion_de_altura_para_muros_bajos():
    """Con un muro de 2.2m (bajo el umbral de 2.44m), no debería activarse esa costura."""
    motor = MotorQTO(geo(altura_muro_m=2.2))
    union = next(p for p in motor.partidas() if "unión" in p.partida.lower())
    assert union.fuente == "[supuesto]"  # solo queda la fracción de cortes, sin la costura


# ===========================================================================
# Malla esquinera: dos productos, redondeo por esquina (no en agregado)
# ===========================================================================

def test_malla_esquinera_es_dos_productos_distintos():
    """
    VERIFICADO con NotebookLM del usuario: la malla esquinera interna
    (10x10/14x14 cm) y la externa (20x20 cm) son productos DISTINTOS, no
    una sola malla que se compra doble. Antes había una sola clave de
    precio tratando ambas caras como el mismo producto.
    """
    motor = MotorQTO(geo())
    nombres = {p.partida for p in motor.partidas() if p.categoria == "Muros"}
    assert "Malla esquinera interna" in nombres
    assert "Malla esquinera externa" in nombres

    interna = next(p for p in motor.partidas() if p.partida == "Malla esquinera interna")
    externa = next(p for p in motor.partidas() if p.partida == "Malla esquinera externa")
    assert interna.clave_precio == "Malla_esquinera_interna_pieza"
    assert externa.clave_precio == "Malla_esquinera_externa_pieza"
    assert interna.clave_precio != externa.clave_precio


def test_malla_esquinera_redondea_por_esquina_no_en_agregado():
    """
    VERIFICADO con ejemplo numérico resuelto por el usuario: una esquina de
    2.80 m da ceil(2.80/2.40) = 2 piezas de CADA tipo (4 en total), no
    ceil(2.80*2/2.40) = 3 (que subestimaría por redondear en agregado en
    vez de por unidad física comprable). Mismo principio que la corrección
    de malla zigzag: no se puede compartir una pieza fraccionaria de
    sobrante entre distintas esquinas.
    """
    # Proyecto de una sola esquina, para aislar el cálculo (perímetro
    # mínimo, geometría simple con las 4 esquinas por defecto -- se verifica
    # el conteo POR esquina dividiendo entre el número de esquinas).
    motor = MotorQTO(geo(altura_muro_m=2.80, perimetro_m=44, niveles=1))
    g = motor.geo

    interna = next(p for p in motor.partidas() if p.partida == "Malla esquinera interna")

    piezas_por_esquina_esperadas = math.ceil(2.80 / 2.40)
    assert piezas_por_esquina_esperadas == 2  # el ejemplo resuelto del usuario

    # La partida incluye también las uniones muro-losa; se descuenta esa
    # parte para verificar solo el componente de esquinas.
    piezas_union = math.ceil(g.ml_muros_total * g.niveles / 2.40)
    piezas_solo_esquinas = interna.cantidad_neta - piezas_union

    assert piezas_solo_esquinas == g.esquinas_efectivas * g.niveles * piezas_por_esquina_esperadas


def test_malla_esquinera_incluye_uniones_muro_losa():
    """
    Video #37: la esquinera "también se debe incluir en las uniones entre
    muro y losa" -- antes esto no estaba modelado en absoluto.
    """
    motor = MotorQTO(geo())
    interna = next(p for p in motor.partidas() if p.partida == "Malla esquinera interna")
    assert "unión" in interna.detalle.lower() or "union" in interna.detalle.lower()
    assert "muro-losa" in interna.detalle


def test_union_muro_losa_reproduce_el_ejemplo_de_la_habitacion():
    """
    VERIFICADO con ejemplo numérico resuelto: habitación de 5x4 m
    (perímetro 18 ml) -> ceil(18/2.40) = 8 tiras de malla esquinera
    interna en la unión muro-losa.
    """
    motor = MotorQTO(geo(area_m2=20, perimetro_m=18, niveles=1))
    piezas_esperadas = math.ceil(18 / 2.40)
    assert piezas_esperadas == 8

    interna = next(p for p in motor.partidas() if p.partida == "Malla esquinera interna")
    # La partida incluye también las esquinas propiamente dichas; se
    # verifica que el componente de unión (perímetro/2.40) esté presente.
    assert interna.cantidad_neta >= piezas_esperadas


def test_esquinas_concavas_y_convexas_reciben_el_mismo_tratamiento():
    """
    VERIFICADO: no hace falta distinguir esquinas entrantes (cóncavas) de
    salientes (convexas) -- ambas llevan una tira interna y una externa.
    Una casa en L (6 esquinas típicas) simplemente usa un conteo mayor.
    """
    rectangular = MotorQTO(geo(esquinas=4))
    forma_l = MotorQTO(geo(esquinas=6))

    interna_rect = next(p for p in rectangular.partidas() if p.partida == "Malla esquinera interna")
    interna_l = next(p for p in forma_l.partidas() if p.partida == "Malla esquinera interna")
    assert interna_l.cantidad_neta > interna_rect.cantidad_neta


def test_malla_union_documenta_las_tres_causas_reales():
    """
    VERIFICADO con NotebookLM del usuario (video #46): hay exactamente TRES
    motivos documentados para necesitar malla unión -- cortes de ajuste por
    modulación, reparación de instalaciones, y uniones horizontales por
    altura. Antes solo se mencionaban dos genéricamente ("cortes de
    panel"). El tercer motivo (uniones horizontales) ya tenía fórmula
    exacta; los otros dos siguen combinados en una fracción [supuesto]
    porque no hay ejemplo numérico resuelto que la verifique todavía --
    no se debe inventar una fórmula sin esa verificación (lección de la
    malla zigzag).
    """
    motor = MotorQTO(geo(altura_muro_m=2.80))
    union = next(p for p in motor.partidas() if "unión" in p.partida.lower())
    assert "modulación" in union.detalle
    assert "instalaciones" in union.detalle


def test_desperdicio_de_panel_corroborado_por_dato_real():
    """
    El video #46 reporta ~3% de desperdicio real en proyectos bien
    modulados, mucho menor que un desperdicio porcentual típico de obra
    (5-10%) -- corrobora la decisión de no aplicar % de desperdicio al
    panel y usar redondeo por modulación en su lugar.
    """
    from utils.parametros import cargar_parametros

    p = cargar_parametros()
    assert "Panel_Muro" not in {
        k for k in ("concreto", "mortero", "acero", "mallas", "acabados")
    }  # el panel nunca tuvo su propia clave de desperdicio porcentual
    assert p["desperdicios"].keys() == {"concreto", "mortero", "acero", "mallas", "acabados"}
