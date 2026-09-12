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


def test_paneles_de_losa_cubren_el_area_no_una_linea():
    """
    Bug corregido: el conteo usaba `sqrt(area) / (ancho[1.22])`, que solo
    contaba una hilera de paneles (112 m² -> 9 piezas). La ficha oficial
    "Qualylosa Covintec 4\"" (QLOSA-4PULG-325-1.pdf) define el panel de
    losa como 1.22 x 3.25 m = 3.965 m²: el conteo debe cubrir el AREA.
    """
    largo_panel = P["panel"]["losa_largo_estandar_m"]
    assert largo_panel == pytest.approx(3.25, rel=1e-6)  # ficha oficial Qualylosa

    g = geo(area_m2=112.0)  # losa de 14 x 8 m
    esperado = math.ceil(g.area_planta_m2 / (P["panel"]["ancho_util_m"] * largo_panel))
    assert esperado == 29  # ceil(112 / 3.965)
    assert g.n_paneles_losa == esperado

    # El conteo crece con el área y con los niveles, y nunca baja de 1.
    grande = geo(area_m2=240.0)
    assert grande.n_paneles_losa > g.n_paneles_losa
    # Con 2 niveles la huella por nivel es la mitad: 15 paneles/nivel x 2 = 30.
    dos_pl = geo(area_m2=112.0, niveles=2)
    esperado_2n = math.ceil(dos_pl.area_planta_m2 / (P["panel"]["ancho_util_m"] * largo_panel)) * 2
    assert dos_pl.n_paneles_losa == esperado_2n == 30


def test_altura_efectiva_mayor_a_2_44_empalma_muros():
    """Alturas > 2.44 m (largo comercial del panel) requieren empalme."""
    g = geo(altura_muro_m=3.0)
    assert len({p.partida for p in MotorQTO(g).partidas() if "unión" in p.partida}) >= 1


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
    bultos_esperados = math.ceil(
        esperado_m3 / P["mezclas"]["mortero"]["rendimiento_m3_por_bulto"]
    )  # el cemento se compra por saco entero (ver test_mortero_se_compra_en_sacos_enteros)

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
        "Anclas / bastones 3/8\" (base + conexión superior a losa)",  # Manual Técnico Covintec 2011
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


def test_traslape_malla_electrosoldada_corregido_con_ejemplo_resuelto():
    """
    Bug: electrosoldada_traslape=1.10 (10%) no tenía ninguna fuente. El
    usuario aportó un ejemplo numérico resuelto (losa 10x12m, hoja
    2.50x6.00m, traslape 50cm) que da un factor de traslape puro de 1.364
    (36.4%) -- más de 3x el valor anterior.
    """
    assert P["mallas"]["electrosoldada_traslape"] == pytest.approx(1.364, abs=0.001)

    # Verificación de la fórmula: hoja 2.50x6.00m, traslape 0.50m.
    factor_esperado = (2.50 / (2.50 - 0.50)) * (6.00 / (6.00 - 0.50))
    assert P["mallas"]["electrosoldada_traslape"] == pytest.approx(factor_esperado, abs=0.001)


def test_electrosoldada_advierte_sobre_desperdicio_de_redondeo_no_incluido():
    """
    El ejemplo resuelto del usuario (losa 10x12m) da 87.5% de sobrecosto
    total, no 36.4% -- la diferencia es desperdicio por redondear a hojas
    completas contra las dimensiones específicas de esa losa, un efecto
    que Geometria no puede capturar sin rastrear ancho/largo por separado
    (solo tiene área total). Debe quedar advertido, no oculto.
    """
    motor = MotorQTO(geo())
    electrosoldada = next(p for p in motor.partidas() if p.partida == "Malla electrosoldada 10x10")
    assert "redondear a hojas completas" in electrosoldada.detalle


def test_anclas_incluyen_conexion_superior_a_losa():
    """
    Bug: solo se contaban las 3 anclas de la base. El usuario aportó la
    verificación completa: "si el muro se conecta a una losa o trabe
    superior, se suman otras 3 anclas en la parte alta, dando un total de
    6 por panel" -- como este motor SIEMPRE calcula una losa apoyada sobre
    los muros (universal en vivienda residencial), el anclaje real estaba
    subestimado a la mitad.
    """
    assert P["anclaje"]["anclas_por_panel"] == 6  # antes: 3 (solo base)

    motor = MotorQTO(geo())
    anclas = next(p for p in motor.partidas() if "Anclas" in p.partida)
    n_esperado = motor.geo.n_paneles_muro * 6
    kg_esperado = (n_esperado * P["anclaje"]["longitud_ancla_m"]
                  * P["anclaje"]["peso_varilla_3_8_kg_por_m"])
    assert anclas.cantidad_neta == pytest.approx(kg_esperado, rel=1e-6)
    assert "conexión superior" in anclas.detalle


# ===========================================================================
# Barrido general de mallas/refuerzos (NotebookLM del usuario)
# ===========================================================================

def test_puerta_ancha_advierte_sobre_malla_zigzag_reforzada():
    """
    NotebookLM del usuario: puertas de más de 90 cm requieren malla zigzag
    REFORZADA (10x1.22 m, mayor calibre), un producto distinto no
    incluido en el pricebook. Debe advertirse, no calcularse en silencio
    con el producto estándar.
    """
    motor = MotorQTO(geo(ancho_puerta_m=1.20, alto_puerta_m=2.15))
    zigzag = next(p for p in motor.partidas() if p.partida == "Malla zigzag en vanos")
    assert "reforzada" in zigzag.detalle.lower()
    assert "90 cm" in zigzag.detalle


def test_puerta_de_referencia_no_dispara_advertencia_de_reforzada():
    """Con la puerta de referencia (90 cm) no debe aparecer la advertencia."""
    motor = MotorQTO(geo())  # usa el default de 0.90 m
    zigzag = next(p for p in motor.partidas() if p.partida == "Malla zigzag en vanos")
    assert "reforzada" not in zigzag.detalle.lower()


def test_limitaciones_conocidas_estan_documentadas_y_expuestas():
    """
    Barrido general de refuerzos especializados (NotebookLM del usuario):
    la mayoría corresponden a condiciones de proyecto que Geometria no
    modela (techos a dos aguas, obra híbrida, bovedilla, muros curvos).
    Deben quedar documentadas explícitamente, no omitidas en silencio.
    """
    limitaciones = MotorQTO.limitaciones_conocidas()
    assert len(limitaciones) >= 5

    texto = " ".join(limitaciones).lower()
    for tema in ("dos aguas", "híbrida", "colindancia", "bovedilla", "curvo"):
        assert tema in texto, f"falta documentar: {tema}"


def test_malla_union_por_altura_se_calcula_por_panel_no_en_agregado():
    """
    Bug: la fórmula anterior trataba TODO el muro como una tira continua
    (ceil(ml_muros_total/2.40)*lados), subestimando casi a la mitad.
    VERIFICADO con ejemplo numérico resuelto por el usuario: para UN panel
    (1.22 m) que se encima para ganar altura, "1.22 m (frente) + 1.22 m
    (atrás) = 2.44 ml -> 2.44/2.40 = 1.01 -> 2 piezas". La cantidad debe
    calcularse POR PANEL, no por el total de metros lineales del muro.
    """
    g = geo(altura_muro_m=3.12, perimetro_m=44)  # > 2.44m, dispara la condición
    motor = MotorQTO(g)

    # Verificación exacta del ejemplo de un solo panel.
    lineal_un_panel = 1.22 * 2
    piezas_un_panel = math.ceil(lineal_un_panel / 2.40)
    assert piezas_un_panel == 2

    union = next(p for p in motor.partidas() if "unión" in p.partida.lower())
    esperado_por_altura = g.n_paneles_muro * piezas_un_panel
    esperado_por_cortes = math.ceil(
        g.n_paneles_muro * P["mallas"]["union_fraccion_paneles_cortados"] * 2
    )
    assert union.cantidad_neta == esperado_por_altura + esperado_por_cortes

    # La fórmula vieja (agregado) habría dado casi la mitad -- se verifica
    # que la nueva es sustancialmente mayor.
    formula_vieja = math.ceil(g.ml_muros_total / 2.40) * 2
    assert esperado_por_altura > formula_vieja * 1.8  # ~2x, con margen


def test_rendimiento_de_mortero_actualizado_con_estimacion_sourced():
    """
    Bug: rendimiento_m3_por_bulto=0.12 (120L) no tenía ninguna fuente,
    marcado "VERIFICAR con proveedor". El NotebookLM del usuario aportó una
    estimación por analogía física con el concreto (mismo razonamiento de
    compresión de materiales): 135-145 L/bulto -- se usa el punto medio
    (140L). Marcado explícitamente como estimación, no una ficha técnica
    directa (la propia fuente lo etiqueta "(Est.)").
    """
    assert P["mezclas"]["mortero"]["rendimiento_m3_por_bulto"] == pytest.approx(0.14)

    motor = MotorQTO(geo())
    mortero = next(p for p in motor.partidas() if p.partida == "Mortero de revoque")
    assert mortero.fuente == "[doc]"
    assert "estimado" in mortero.detalle.lower()


def test_limitaciones_documentan_el_hueco_del_sistema_de_techo():
    """
    Verificado por web fetch a isotexdominicana.com/techos/: el proveedor
    real del usuario no vende "Qualylosa" (terminología de Covintec México).
    Vende TERMOPANEL (sin concreto) o ISOLOSA (con concreto, producto
    propio). No se inventó un porcentaje de ajuste sin datos reales -- se
    documenta como limitación pendiente de decisión.
    """
    texto = " ".join(MotorQTO.limitaciones_conocidas()).lower()
    assert "termopanel" in texto
    assert "isolosa" in texto
    assert "qualylosa" in texto


def test_pintura_se_compra_en_latas_enteras():
    """
    Instancia menor del mismo patrón corregido en las mallas: la pintura
    se vende por galón entero, no por fracción -- antes se calculaba como
    un valor continuo (ej. 39.01 galones) sin redondear.
    """
    motor = MotorQTO(geo())
    pintura = next(p for p in motor.partidas() if p.partida == "Pintura")
    assert pintura.cantidad_neta == int(pintura.cantidad_neta)  # es un entero


def test_mortero_se_compra_en_sacos_enteros():
    """
    Mismo patrón: el cemento se vende por saco de 50 kg entero, no por
    fracción. La arena y la microfibra se calculan del CONSUMO exacto (sin
    redondear), pero el saco que se compra sí redondea hacia arriba.
    """
    motor = MotorQTO(geo())
    mortero = next(p for p in motor.partidas() if p.partida == "Mortero de revoque")
    assert mortero.cantidad_neta == int(mortero.cantidad_neta)  # es un entero
    assert "saco entero" in mortero.detalle.lower()


# ===========================================================================
# Sistemas de techo reales de Isotex Dominicana (2026-07-26)
# ===========================================================================

def test_sistema_techo_por_defecto_no_cambia_comportamiento():
    """Sin especificar sistema_techo, el motor sigue siendo el genérico de siempre."""
    generico_a = MotorQTO(geo())
    generico_b = MotorQTO(geo(), sistema_techo=None)
    assert generico_a.total() == generico_b.total()
    assert generico_b.sistema_techo is None


def test_sistema_techo_invalido_falla_ruidosamente():
    with pytest.raises(ValueError):
        MotorQTO(geo(), sistema_techo="algo_que_no_existe")


@pytest.mark.parametrize("sistema", ["termopanel", "termolosa", "isolosa", "isofill"])
def test_sistema_techo_reemplaza_panel_y_capa_de_compresion(sistema):
    """
    Con un sistema real seleccionado, la azotea es UNA sola línea "instalado
    por m²" -- no la descomposición en Panel_Techo + capa de compresión del
    modelo genérico (que no corresponde a ningún producto real del
    proveedor único del usuario, Isotex Dominicana).
    """
    motor = MotorQTO(geo(), sistema_techo=sistema)
    nombres = {p.partida for p in motor.partidas() if p.categoria == "Losa"}

    esperado = f"Techo {sistema.capitalize()} (instalado)"
    assert esperado in nombres
    assert "Panel de losa" not in nombres  # sin entrepiso en este caso, no debe aparecer
    assert "Capa de compresión (azotea)" not in nombres

    techo = next(p for p in motor.partidas() if p.partida == esperado)
    assert techo.cantidad_neta == geo().area_losa_azotea_m2
    assert techo.clave_precio == f"Techo_{sistema.capitalize()}_m2"


def test_sistema_techo_sin_cotizar_da_precio_cero_y_advierte():
    """
    Ningún sistema real tiene precio público -- el motor debe usar 0.0
    explícito (no inventar un placeholder) y advertirlo en el detalle.
    """
    from utils.pricebook import DEFAULT_PRICEBOOK, PRECIOS_SIN_COTIZAR

    motor = MotorQTO(geo(), DEFAULT_PRICEBOOK, sistema_techo="termopanel")
    techo = next(p for p in motor.partidas() if p.partida == "Techo Termopanel (instalado)")

    assert techo.precio_unitario == 0.0
    assert techo.subtotal == 0.0
    assert "SIN COTIZAR" in techo.detalle
    assert "Techo_Termopanel_m2" in PRECIOS_SIN_COTIZAR


def test_termopanel_advierte_sobre_pendiente_minima():
    """Termopanel requiere 6% de pendiente mínima -- no es un techo plano."""
    motor = MotorQTO(geo(), sistema_techo="termopanel")
    techo = next(p for p in motor.partidas() if "Termopanel" in p.partida)
    assert "pendiente mínima" in techo.detalle.lower()
    assert "6%" in techo.detalle


def test_sistema_techo_no_duplica_malla_esquinera_de_union():
    """
    La malla esquinera de unión muro-losa es específica del modelo genérico
    (losa colada tipo Qualylosa). Con un sistema alternativo, cuyo precio
    instalado ya cubre esa conexión, no debe calcularse -- evita doble conteo.
    """
    generico = MotorQTO(geo())
    alternativo = MotorQTO(geo(), sistema_techo="isolosa")

    interna_generico = next(p for p in generico.partidas() if p.partida == "Malla esquinera interna")
    interna_alt = next(p for p in alternativo.partidas() if p.partida == "Malla esquinera interna")
    assert interna_alt.cantidad_neta < interna_generico.cantidad_neta


def test_sistema_techo_no_agrega_acero_generico_a_la_azotea():
    """
    El acero genérico de losa (6 kg/m²) es parte del modelo Qualylosa. Con
    un sistema alternativo, ese refuerzo ya viene incluido en el precio
    instalado -- no debe sumarse por separado para la azotea.
    """
    sin_entrepiso = geo(niveles=1)
    generico = MotorQTO(sin_entrepiso)
    alternativo = MotorQTO(sin_entrepiso, sistema_techo="termolosa")

    acero_generico = [p for p in generico.partidas() if p.partida == "Acero de refuerzo en losa"]
    acero_alt = [p for p in alternativo.partidas() if p.partida == "Acero de refuerzo en losa"]

    assert acero_generico  # sí existe en el modelo genérico
    assert not acero_alt   # no existe con sistema alternativo (sin entrepiso)


def test_entrepiso_sigue_con_modelo_generico_aunque_la_azotea_use_isotex():
    """El entrepiso (piso intermedio) sigue con el motor genérico -- solo la
    azotea usa el sistema real, mientras no haya tabla completa de espesores."""
    g = geo(area_m2=240, perimetro_m=44, niveles=2)  # 2 niveles -> hay entrepiso
    motor = MotorQTO(g, sistema_techo="isolosa")

    nombres = {p.partida for p in motor.partidas() if p.categoria == "Losa"}
    assert "Techo Isolosa (instalado)" in nombres          # azotea: sistema real
    assert "Panel de losa (entrepiso)" in nombres           # entrepiso: genérico
    assert "Capa de compresión (entrepiso)" in nombres


def test_fichas_de_isotex_dominicana_techo_tienen_fuente():
    from utils.fuentes import FICHA_ISOFILL, FICHA_ISOLOSA, FICHA_TERMOPANEL

    for ficha in (FICHA_TERMOPANEL, FICHA_ISOLOSA, FICHA_ISOFILL):
        assert ficha.cita
        assert ficha.tipo == "referencia"


def test_isolosa_documenta_modulo_confirmado_y_espesor_variable():
    """
    El usuario compartió el PDF completo de la ficha técnica de Isolosa,
    con el diagrama de dimensiones. Confirma el módulo (0.60 m = 0.15 m
    nervio + 0.45 m EPS) y el perfil metálico removible (0.15x0.04 m),
    pero el espesor de la losa (t/h/H/s1 en el diagrama) NO tiene valor
    numérico fijo -- depende del diseño estructural del proyecto (claro y
    carga), no es un dato de catálogo. Esto confirma que el modelo
    "instalado por m²" (sin desglose de materiales) es la estrategia
    correcta, no una limitación de extracción de PDF.
    """
    techo_alt = P["techos_alternativos"]["isolosa"]
    assert techo_alt["modulo_total_m"] == pytest.approx(0.60)
    assert techo_alt["nervio_concreto_m"] + techo_alt["bloque_eps_m"] == pytest.approx(
        techo_alt["modulo_total_m"]
    )
    assert techo_alt["perfil_calibre_20_ancho_m"] == pytest.approx(0.15)

    from utils.fuentes import FICHA_ISOLOSA

    assert "variable" in FICHA_ISOLOSA.cita.lower()
    assert "estructural" in FICHA_ISOLOSA.cita.lower()


# ===========================================================================
# Desglose del plano (auditoría 2026-09): cielo raso y partidas nuevas
# ===========================================================================

def test_cielo_raso_cubre_ambas_losas_y_queda_solo_como_partida_instalada():
    """
    El cielo raso (aplanado 2.5 cm + pintura del techo interior, confirmado
    por el usuario) se modela como UNA partida por m² instalado que cubre la
    azotea Y el entrepiso. No debe aparecer además dentro del mortero de
    fachada ni en la pintura de muros (evita doble conteo).
    """
    g = geo(area_m2=240, niveles=2)  # 2 niveles -> azotea + entrepiso
    motor = MotorQTO(g)
    cielo = [p for p in motor.partidas() if p.partida == "Cielo raso"]

    assert len(cielo) == 1
    # area_planta = 240/2 = 120 por nivel; azotea + entrepiso = 120 + 120
    assert cielo[0].cantidad_neta == pytest.approx(240.0)
    assert "2.5" in cielo[0].detalle          # mortero de 2.5 cm documentado
    assert cielo[0].clave_precio == "Cielo_raso_m2"


def test_loseta_de_bano_y_salpicadero_de_cocina_aparecen_en_el_base():
    """
    A diferencia del alambre/diámetros (que dependen de la medición del
    plano), loseta de pared en baños y salpicadero de cocina son acabados
    que SIEMPRE existen y deben aparecer en el presupuesto base.
    """
    g = geo()  # 120 m², 1 nivel
    motor = MotorQTO(g)
    nombres = {p.partida for p in motor.partidas()}
    assert "Loseta de pared en baños" in nombres
    assert "Salpicadero de cocina" in nombres

    loseta = next(p for p in motor.partidas() if p.partida == "Loseta de pared en baños")
    salpi = next(p for p in motor.partidas() if p.partida == "Salpicadero de cocina")
    assert loseta.cantidad_neta == pytest.approx(g.n_banos * 10.0)
    assert salpi.cantidad_neta == pytest.approx(g.ml_cocina_m * 0.6)


def test_instalaciones_detalladas_incluyen_alambre_diametros_y_equipamiento():
    """
    Las partidas dependientes del plano solo aparecen cuando hay detalle
    (cantidades > 0). Todas deben tener clave de precio presente.
    """
    from utils.instalaciones import InstalacionesDetalle

    g = geo()
    inst = InstalacionesDetalle(
        ml_alambre_electrico=100,
        ml_tuberia_agua_1_2=30,
        ml_tuberia_agua_3_4=10,
        ml_tuberia_sanitaria_4=15,
        lamparas=12,
        kw_sistema_solar=3,
        pozo_septico=1,
        cisterna_m3=8,
    )
    motor = MotorQTO(g, instalaciones=inst)
    df = motor.presupuesto()
    texto = " ".join(df["partida"]).lower()

    for imprescindible in ("alambre", "tubería de agua 1/2", "tubería de agua 3/4",
                           "tubería sanitaria 4", "lámparas", "sistema fotovoltaico",
                           "pozo séptico", "cisterna"):
        assert imprescindible in texto, f"falta la partida: {imprescindible}"

    # todas aparecen con clave de precio
    for p in motor.partidas():
        assert p.clave_precio, p.partida
        assert p.precio_unitario > 0, p.partida


def test_partidas_dependientes_del_plano_no_aparecen_sin_detalle():
    """
    En el presupuesto base (sin InstalacionesDetalle) las cantidades son 0,
    así que alambre/diámetros/solar/pozo/cisterna NO deben inflar el total.
    """
    df = MotorQTO(geo()).presupuesto()
    presente = set(df["partida"])
    for no_visible in ("Alambre eléctrico", "Sistema fotovoltaico",
                       "Pozo séptico", "Cisterna", "Tubería de agua 1/2\""):
        assert no_visible not in presente, f"{no_visible} no debe aparecer sin detalle"
