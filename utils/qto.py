"""
utils/qto.py
------------
Motor de cantidades (Quantity Take-Off) para sistemas EPS/ICF.

QUÉ CAMBIA RESPECTO A `utils/calculador.py`
===========================================
El motor anterior mezclaba geometría, rendimientos, desperdicios y precios en un
único bucle de `data.append({...})`, y producía:

    120 m² -> RD$ 1,493,009  (12,442 RD$/m²)
    obra terminada = 9.6% del total

Faltaban, en su totalidad: mortero de acabado, mallas (zigzag, esquinera, de
unión), anclas, cimentación completa, instalación eléctrica, instalación
sanitaria, ventanas, puertas exteriores, baños, cocina, impermeabilización,
cielo raso y **mano de obra**. En una vivienda real esas partidas son ~75% del
costo. De ahí salía el "83.6% de ahorro" que era constante para cualquier área.

Este motor:

1. Separa **cantidades** de **precios**. `calcular_cantidades()` es física pura
   y se puede validar contra obra ejecutada sin depender de ningún pricebook.
2. Consume la **geometría real** (perímetro, altura, niveles) en vez de
   `m2 * 2.2`.
3. Toma sus parámetros de `data/parametros_tecnicos.yaml`, que transcribe
   `docs/BASE_TECNICA_EPS_ICF.md`.
4. Compara **obra gris contra obra gris** al 27.5%, como pide el documento.

Uso:
    from utils.geometria import Geometria
    from utils.qto import MotorQTO

    geo = Geometria(area_m2=120, perimetro_m=44, altura_muro_m=2.8)
    motor = MotorQTO(geo, precios)
    df = motor.presupuesto()
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

import pandas as pd

from .dominio import Calidad, Sistema, normalizar_calidad, normalizar_sistema, normalizar_zona_riesgo
from .geometria import Geometria
from .parametros import cargar_parametros
from .pricebook import DEFAULT_PRICEBOOK, PRECIOS_POR_VERIFICAR


@dataclass
class Partida:
    """Una línea del presupuesto, con su trazabilidad."""

    categoria: str
    partida: str
    detalle: str
    unidad: str
    cantidad_neta: float
    desperdicio: float
    clave_precio: str | None
    precio_unitario: float
    fuente: str = "[doc]"       # [doc] = BASE_TECNICA | [supuesto] = estimación

    @property
    def cantidad(self) -> float:
        return self.cantidad_neta * (1 + self.desperdicio)

    @property
    def subtotal(self) -> float:
        return self.cantidad * self.precio_unitario

    @property
    def precio_por_verificar(self) -> bool:
        return self.clave_precio in PRECIOS_POR_VERIFICAR

    def a_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.update({
            "cantidad": round(self.cantidad, 2),
            "subtotal": round(self.subtotal, 2),
            "precio_por_verificar": self.precio_por_verificar,
        })
        return d


# Categorías que componen la OBRA GRIS. El resto es obra terminada.
# La distinción importa: [doc] "EPS/ICF ahorra 20-40% en OBRA GRIS (no en
# acabados, que son iguales en ambos sistemas)".
CATEGORIAS_OBRA_GRIS = ("Cimentación", "Muros", "Losa", "Acero", "Mano de obra")

# ---------------------------------------------------------------------------
# Limitaciones conocidas del modelo.
#
# VERIFICADO con NotebookLM del usuario: existen refuerzos y mallas
# especializados documentados en las fuentes técnicas que este motor NO
# calcula, porque corresponden a condiciones de proyecto que Geometria no
# modela todavía (techos a dos aguas, obra híbrida con columnas de acero,
# sistemas de bovedilla/casetón, muros curvos). En vez de omitirlos en
# silencio, se documentan aquí para que la interfaz los muestre
# explícitamente -- el usuario debe presupuestarlos aparte si su proyecto
# los requiere.
# ---------------------------------------------------------------------------
LIMITACIONES_CONOCIDAS = (
    "Techos a dos aguas: requieren malla cumbrera en el vértice superior "
    "(no modelado; este motor solo calcula losa plana/azotea).",
    "Obra híbrida (muros EPS que conectan con columnas de concreto o "
    "marcos de acero): requiere calafateo de malla y acero desplegable en "
    "cada empalme, además de 12-15 anclas/panel en vez de 6 (no modelado).",
    "Muros de colindancia / bardas de lindero: requieren anclaje en ambas "
    "caras (alternado), no modelado como caso distinto del muro estándar.",
    "Sistemas de losa con casetón/bovedilla: requieren malla tipo "
    "gallinero en el aplanado de plafones (este motor solo calcula el "
    "sistema de panel/Qualylosa, no bovedilla).",
    "Vanos circulares, muros curvos o cúpulas: el autoensamble de fábrica "
    "no coincide por el ángulo; requiere malla unión adicional para "
    "'parchar' esas geometrías (no modelado; Geometria es rectangular/L).",
    "Acabados interiores con masilla o enduído flexible: se recomienda "
    "malla de fibra de vidrio para prevenir microfisuras (este motor solo "
    "calcula pintura como acabado de muro).",
    "Puertas de más de 90 cm de ancho: requieren malla zigzag reforzada "
    "(10x1.22 m, mayor calibre) -- se advierte en la partida "
    "correspondiente, pero el producto no está en el pricebook todavía.",
)


class MotorQTO:
    """Motor de cantidades y presupuesto."""

    def __init__(
        self,
        geometria: Geometria,
        precios: dict[str, float] | None = None,
        sistema: str = "isotex",
        calidad: str = "media",
        zona_riesgo: str = "moderado",
        aplanado_mecanizado: bool = False,
        parametros: dict[str, Any] | None = None,
    ):
        self.geo = geometria
        self.precios = dict(precios or DEFAULT_PRICEBOOK)
        self.sistema: Sistema = normalizar_sistema(sistema)
        self.calidad: Calidad = normalizar_calidad(calidad)
        self.zona = normalizar_zona_riesgo(zona_riesgo)
        self.aplanado_mecanizado = aplanado_mecanizado
        self.p = parametros or cargar_parametros()

    # -- helpers ---------------------------------------------------------
    def _precio(self, clave: str) -> float:
        if clave not in self.precios:
            raise KeyError(
                f"El motor pide el precio '{clave}' y no existe en el pricebook. "
                f"Agrégalo a utils/pricebook.py o a data/pricebook.json."
            )
        return float(self.precios[clave])

    def _desp(self, clave: str) -> float:
        return float(self.p["desperdicios"].get(clave, 0.0))

    @property
    def _factores_zona(self) -> dict[str, float]:
        return self.p["zonas_riesgo"][self.zona.value]

    @property
    def _factor_calidad(self) -> float:
        return {Calidad.ECONOMICA: 0.8, Calidad.MEDIA: 1.0,
                Calidad.ALTA: 1.5, Calidad.LUJO: 2.5}[self.calidad]

    def _bultos_concreto(self, volumen_m3: float) -> float:
        return volumen_m3 / self.p["mezclas"]["concreto"]["rendimiento_m3_por_bulto"]

    def _bultos_mortero(self, volumen_m3: float) -> float:
        return volumen_m3 / self.p["mezclas"]["mortero"]["rendimiento_m3_por_bulto"]

    def _m3_arena_mortero(self, bultos: float) -> float:
        botes = self.p["mezclas"]["mortero"]["botes_arena_por_bulto"]
        litros_bote = self.p["mezclas"]["bote_litros"]
        return bultos * botes * litros_bote / 1000.0

    def _jornal(self, area_m2: float, rendimiento_m2_dia: float) -> float:
        """
        Costo de mano de obra: días de cuadrilla x personas x jornal.

        VERIFICADO (revisión de precisión, 2026-07-26): al auditar esta
        fórmula pareció, a primera vista, un posible triple conteo -- ¿por
        qué multiplicar los días por el tamaño de la cuadrilla si el
        rendimiento ya "incluye" a la cuadrilla?

        Se verificó contra la convención estándar de Análisis de Precios
        Unitarios (APU) usada en Centroamérica y el Caribe: el "rendimiento"
        (m²/día) SIEMPRE se reporta como la producción de la CUADRILLA
        COMPLETA, nunca de un trabajador individual. Ejemplo de tabla de
        referencia real: "1 Albañil + 1 Ayudante + 1 Peón -> aplanado
        exterior: 24 m²/día" (rendimiento de los 3, no de uno).
        Fuente: opus-planet.mx/blog/rendimientos-mano-de-obra-construccion-mexico/

        Por tanto `dias = area / rendimiento` son días-CUADRILLA (calendario),
        y `dias * cuadrilla_personas` son persona-días totales -- la fórmula
        correcta para el costo, no un triple conteo. Los rendimientos de
        `docs/BASE_TECNICA_EPS_ICF.md` (15-20 m²/día aplanado manual) siguen
        la misma convención y son, de hecho, más lentos que el pañete
        tradicional (24-25 m²/día) -- coherente con que instalar sobre malla
        de refuerzo es más lento que un repello convencional.
        """
        if rendimiento_m2_dia <= 0:
            return 0.0
        dias = area_m2 / rendimiento_m2_dia
        return dias * self.p["mano_obra"]["cuadrilla_personas"]

    # ==================================================================
    # PARTIDAS
    # ==================================================================

    def _cimentacion(self) -> list[Partida]:
        g, esp = self.geo, self.p["espesores"]
        area = g.area_cimentacion_m2
        f_horm = self._factores_zona["hormigon"]

        vol_replantillo = area * esp["replantillo_m"]
        vol_plantilla = area * esp["plantilla_concreto_pobre_m"]
        vol_platea = area * esp["cimentacion_platea_m"] * f_horm
        # [doc] Manual Técnico Panel Covintec 2011, sección 1.3: "Dentellones
        # perimetrales en línea de ejes... corona 20 cm, base 15 cm, peralte
        # 15 cm". Elemento que faltaba por completo -- se detectó al
        # verificar el manual oficial del fabricante para resolver el
        # conflicto de anclaje.
        vol_dentellon = (
            g.perimetro_efectivo_m
            * ((esp["dentellon_corona_m"] + esp["dentellon_base_m"]) / 2)  # sección trapezoidal
            * esp["dentellon_peralte_m"]
        )

        return [
            # [doc] sección 3: "Replantillo (cimentación): capa 12-15 cm de
            # mezcla en fondo de excavación". Antes esta capa NO existía en el
            # cálculo -- el documento distingue explícitamente replantillo
            # (12-15 cm, en el fondo de la excavación) de la plantilla de
            # concreto pobre (5-10 cm, capa de nivelación sobre el
            # replantillo). Son dos capas físicas distintas; faltaba una.
            Partida("Cimentación", "Replantillo",
                    f"Capa de {esp['replantillo_m']*100:.1f} cm en fondo de excavación",
                    "m³", vol_replantillo, self._desp("concreto"),
                    "H_3000_PSI", self._precio("H_3000_PSI") * 0.60, "[supuesto]"),
            Partida("Cimentación", "Plantilla de concreto pobre",
                    f"Capa de nivelación de {esp['plantilla_concreto_pobre_m']*100:.0f} cm "
                    f"sobre el replantillo",
                    "m³", vol_plantilla, self._desp("concreto"),
                    "H_3000_PSI", self._precio("H_3000_PSI") * 0.75, "[supuesto]"),
            Partida("Cimentación", "Barrera de polietileno",
                    "Membrana anti-humedad bajo losa de cimentación",
                    "m²", area, 0.10, "Polietileno_m2", self._precio("Polietileno_m2"),
                    "[supuesto]"),
            Partida("Cimentación", "Malla electrosoldada 10x10",
                    (f"Refuerzo de platea, traslape "
                     f"{(self.p['mallas']['electrosoldada_traslape']-1)*100:.0f}% "
                     f"(40-60 cm entre paños, hoja 2.50x6.00 m -- verificado con "
                     f"ejemplo numérico resuelto). No incluye el desperdicio adicional "
                     f"por redondear a hojas completas contra el ancho/largo real de "
                     f"la losa (puede ser sustancial; requiere geometría rectangular "
                     f"explícita, no solo área total)."),
                    "m²", area * self.p["mallas"]["electrosoldada_traslape"],
                    self._desp("mallas"), "Malla_Electrosoldada",
                    self._precio("Malla_Electrosoldada"), "[supuesto]"),
            # [doc] Manual Técnico Panel Covintec 2011: "La losa de
            # cimentación tendrá 10 cm de espesor" y "Colado de concreto
            # f'c = 200 kg/cm²". CORREGIDO en esta verificación: la ronda
            # anterior usaba 12.5 cm y H_3500_PSI (≈246 kg/cm²) basándose en
            # BASE_TECNICA_EPS_ICF.md ("250 kg/cm²"); el manual oficial del
            # fabricante -- fuente primaria, corroborada en 5 copias
            # independientes -- especifica 200 kg/cm² (H_3000_PSI ≈ 211
            # kg/cm², la coincidencia real).
            Partida("Cimentación", "Losa de cimentación (platea)",
                    f"Concreto {self.p['resistencias']['cimentacion']} kg/cm² "
                    f"(H_3000_PSI ≈ 211 kg/cm²), espesor {esp['cimentacion_platea_m']*100:.0f} cm",
                    "m³", vol_platea, self._desp("concreto"),
                    "H_3000_PSI", self._precio("H_3000_PSI")),
            Partida("Cimentación", "Dentellón perimetral",
                    f"Sección trapezoidal (corona {esp['dentellon_corona_m']*100:.0f} cm, "
                    f"base {esp['dentellon_base_m']*100:.0f} cm, peralte "
                    f"{esp['dentellon_peralte_m']*100:.0f} cm) bajo el perímetro de la losa",
                    "m³", vol_dentellon, self._desp("concreto"),
                    "H_3000_PSI", self._precio("H_3000_PSI")),
        ]

    def _muros(self) -> list[Partida]:
        g = self.geo
        esp_mortero = self.p["espesores"]["mortero_muro_por_cara_m"]
        mallas = self.p["mallas"]
        anclaje = self.p["anclaje"]

        # --- panel -------------------------------------------------------
        clave_panel = "Panel_Muro"
        precio_panel = self._precio(clave_panel)
        if self.sistema is Sistema.ICF:
            precio_panel *= 1.15
        partidas = [
            Partida("Muros", f"Panel estructural ({self.sistema.value.upper()})",
                    f"{g.n_paneles_muro} piezas de {self.p['panel']['ancho_util_m']} m "
                    f"({g.ml_muros_total:.1f} ml de muro / modulación 1.22 m)",
                    "m²", g.area_panel_comprada_m2, 0.0, clave_panel, precio_panel),
        ]

        # --- mortero (2.5 cm POR CARA, no 12 cm) --------------------------
        # El motor anterior aplicaba 0.12 m de concreto sobre muros Y techo,
        # sobreestimando el volumen ~2.5x respecto a la base técnica.
        area_aplanado = g.area_muros_m2 * 2          # dos caras
        vol_mortero = area_aplanado * esp_mortero
        bultos = self._bultos_mortero(vol_mortero)
        partidas += [
            Partida("Muros", "Mortero de revoque",
                    f"{esp_mortero*100:.1f} cm por cara, 2 capas, sobre {area_aplanado:.0f} m². "
                    f"Rendimiento {self.p['mezclas']['mortero']['rendimiento_m3_por_bulto']*1000:.0f} "
                    f"L/bulto (estimado por analogía con el concreto, NotebookLM del usuario; "
                    f"sin ficha técnica directa del mortero proyectado todavía).",
                    "saco", bultos, self._desp("mortero"),
                    "Mortero_saco", self._precio("Mortero_saco")),
            Partida("Muros", "Arena para mortero",
                    f"Proporción 1 saco : {self.p['mezclas']['mortero']['botes_arena_por_bulto']} botes de 19 L",
                    "m³", self._m3_arena_mortero(bultos), self._desp("mortero"),
                    "Arena_m3", self._precio("Arena_m3")),
            Partida("Muros", "Microfibra sintética + impermeabilizante integral",
                    "Prohibido el uso de CAL: daña la malla de acero del panel",
                    "kg", bultos * self.p["mezclas"]["aditivos"]["microfibra_kg_por_bulto"],
                    self._desp("mortero"), "Microfibra_kg", self._precio("Microfibra_kg")),
        ]

        # --- mallas de refuerzo -------------------------------------------
        # [doc] VERIFICADO con ejemplo numérico resuelto por el usuario
        # (video "Cuantificación de Materiales", NotebookLM): para vano de
        # referencia, conteo empírico documentado (12/13 piezas); para vano
        # no estándar, (perímetro + 4 x excedente diagonal) x 2 caras / 1.22,
        # redondeado hacia arriba POR VANO (no se puede compartir una pieza
        # fraccionaria entre dos ventanas distintas). Ver
        # Geometria.piezas_zigzag_por_ventana/puerta para el detalle.
        piezas_por_ventana = g.piezas_zigzag_por_ventana(
            mallas["zigzag_piezas_por_ventana"], mallas["zigzag_excedente_diagonal_m"],
            mallas["zigzag_lados"])
        piezas_por_puerta = g.piezas_zigzag_por_puerta(
            mallas["zigzag_piezas_por_puerta"], mallas["zigzag_excedente_diagonal_m"],
            mallas["zigzag_lados"])
        piezas_zigzag = g.n_ventanas * piezas_por_ventana + g.n_puertas_total * piezas_por_puerta

        # [doc] VERIFICADO con NotebookLM del usuario: dos productos
        # distintos (interna 10x10/14x14cm, externa 20x20cm, ambas de
        # 2.40m), y el redondeo se hace POR ESQUINA Y POR TIPO, no en
        # agregado. Ejemplo resuelto: una esquina de 2.80m da ceil(2.80/2.40)
        # = 2 piezas internas + 2 externas = 4 piezas, NO ceil(2.80*2/2.40)
        # = 3 (que subestima). Antes: una sola cifra agregada
        # ceil(esquinas*altura/2.40), que además solo cubría una cara.
        piezas_por_esquina_por_tipo = math.ceil(g.altura_efectiva_m / mallas["esquinera_largo_pieza_m"])
        n_esquinas_total = g.esquinas_efectivas * g.niveles
        piezas_esquinera_interna = piezas_por_esquina_por_tipo * n_esquinas_total
        piezas_esquinera_externa = piezas_por_esquina_por_tipo * n_esquinas_total

        # [doc] VERIFICADO con ejemplo numérico resuelto por el usuario
        # (video #37): una habitación de 5x4 m (perímetro 18 ml) da
        # ceil(18/2.40)=8 piezas -- coincide exacto con esta fórmula.
        # Malla interna: 100% del perímetro de unión, siempre.
        # Malla externa en la unión: SOLO si la losa queda "a paño" (al ras
        # del muro exterior); con volado/marquesina el tratamiento exterior
        # cambia. Sin un parámetro de volado en Geometria, se asume "a
        # paño" (caso más común en vivienda residencial dominicana) -- si
        # el proyecto real tiene volado, esta partida de malla externa en
        # la unión debe ajustarse manualmente.
        piezas_esquinera_union_losa = math.ceil(
            g.ml_muros_total * g.niveles / mallas["esquinera_largo_pieza_m"]
        )
        piezas_esquinera_interna += piezas_esquinera_union_losa
        piezas_esquinera_externa += piezas_esquinera_union_losa  # asume losa "a paño"

        # [doc] video "Cuantificación de Materiales": "malla unión necesaria
        # cuando la altura del muro supera los 2.44 m, o en cortes donde no
        # existe la pestaña de autoensamble". Antes solo se estimaba por una
        # fracción arbitraria de paneles cortados ([supuesto]); ahora se
        # suma la condición real de altura (aplicada a lo largo de todo el
        # muro, en la costura horizontal donde el panel se extiende más
        # allá de 2.44 m) como un segundo motivo documentado.
        # [doc] VERIFICADO con ejemplo numérico resuelto por el usuario:
        # "1.22 m (frente) + 1.22 m (atrás) = 2.44 ml -> 2.44/2.40 = 1.01 ->
        # 2 piezas POR CADA PANEL que se encima para ganar altura". Mismo
        # error de principio que ya se corrigió en malla zigzag y malla
        # esquinera: la fórmula anterior trataba TODO el muro como una
        # sola tira continua (ceil(ml_muros_total/2.40)*lados = ~70 piezas
        # para un caso de referencia), en vez de calcular por panel
        # individual y redondear por unidad física (69 paneles x 2 piezas
        # = 138 piezas para el mismo caso) -- una subestimación de casi 2x.
        piezas_union_por_altura = 0
        if g.altura_efectiva_m > mallas["union_altura_umbral_m"]:
            lineal_por_panel = self.p["panel"]["ancho_util_m"] * mallas["union_lados"]
            piezas_por_panel_altura = math.ceil(lineal_por_panel / mallas["union_largo_pieza_m"])
            piezas_union_por_altura = g.n_paneles_muro * piezas_por_panel_altura
        piezas_union_por_cortes = math.ceil(
            g.n_paneles_muro * mallas["union_fraccion_paneles_cortados"]
            * mallas["union_lados"]
        )
        piezas_union = piezas_union_por_altura + piezas_union_por_cortes

        partidas += [
            Partida("Muros", "Malla zigzag en vanos",
                    (f"{g.n_ventanas} ventanas x {piezas_por_ventana} pzas + "
                     f"{g.n_puertas_total} puertas x {piezas_por_puerta} pzas (ambas caras incluidas). "
                     + (f"Vano(s) de referencia (90x90 cm ventana, 215x90 cm puerta): "
                        f"conteo empírico documentado."
                        if g._es_ventana_referencia and g._es_puerta_referencia else
                        f"Vano(s) no estándar: (perímetro + 4x{mallas['zigzag_excedente_diagonal_m']*100:.0f}cm) "
                        f"x2 caras / 1.22 m -- verificado con ejemplo numérico resuelto "
                        f"(video 'Cuantificación de Materiales').")
                     + (f" ⚠️ Puerta(s) de {g.ancho_puerta_m:.2f} m de ancho (>90 cm): el "
                        f"NotebookLM del usuario indica que puertas de más de 90 cm requieren "
                        f"malla zigzag REFORZADA (10x1.22 m, mayor calibre), un producto "
                        f"distinto no incluido en este pricebook -- verificar con proveedor."
                        if g.ancho_puerta_m > 0.90 else "")),
                    "pza", piezas_zigzag, self._desp("mallas"),
                    "Malla_zigzag_pieza", self._precio("Malla_zigzag_pieza")),
            Partida("Muros", "Malla esquinera interna",
                    (f"{n_esquinas_total} esquinas x {piezas_por_esquina_por_tipo} pzas "
                     f"(altura {g.altura_efectiva_m} m / 2.40 m, redondeado por esquina) "
                     f"+ {piezas_esquinera_union_losa} pzas en uniones muro-losa "
                     f"({g.ml_muros_total*g.niveles:.1f} ml / 2.40 m). "
                     f"Cara interior; verificado con ejemplo numérico resuelto (esquina "
                     f"de 2.80 m -> 2 piezas, NotebookLM del usuario)."),
                    "pza", piezas_esquinera_interna, self._desp("mallas"),
                    "Malla_esquinera_interna_pieza", self._precio("Malla_esquinera_interna_pieza")),
            Partida("Muros", "Malla esquinera externa",
                    (f"{n_esquinas_total} esquinas x {piezas_por_esquina_por_tipo} pzas "
                     f"+ {piezas_esquinera_union_losa} pzas en uniones muro-losa (asume losa "
                     f"\"a paño\", sin volado/marquesina -- verificar si aplica). "
                     f"Producto distinto a la interna: 20x20 cm vs 10x10/14x14 cm, "
                     f"mismo largo de 2.40 m."),
                    "pza", piezas_esquinera_externa, self._desp("mallas"),
                    "Malla_esquinera_externa_pieza", self._precio("Malla_esquinera_externa_pieza")),
            Partida("Muros", "Malla de unión",
                    (f"Tira de 10 cm x 2.40 m, ambos lados. "
                     + (f"Uniones horizontales por altura > {mallas['union_altura_umbral_m']} m: "
                        f"{g.n_paneles_muro} paneles x 2 pzas c/u = {piezas_union_por_altura} pzas "
                        f"(verificado con ejemplo numérico resuelto: 1.22 m x 2 caras / 2.40 m = "
                        f"2 pzas por panel) + "
                        if piezas_union_por_altura > 0 else "")
                     + f"cortes de ajuste por modulación + reparación de instalaciones "
                       f"({piezas_union_por_cortes} pzas, [supuesto] "
                       f"{mallas['union_fraccion_paneles_cortados']*100:.0f}% de paneles -- "
                       f"video #46 confirma que son las 2 causas restantes, sin fórmula "
                       f"verificada para cuantificarlas por separado todavía)"),
                    "pza", piezas_union, self._desp("mallas"),
                    "Malla_union_pieza", self._precio("Malla_union_pieza"),
                    "[doc]" if piezas_union_por_altura > 0 else "[supuesto]"),
        ]

        # --- anclas -------------------------------------------------------
        n_anclas = g.n_paneles_muro * anclaje["anclas_por_panel"]
        kg_anclas = (n_anclas * anclaje["longitud_ancla_m"]
                     * anclaje["peso_varilla_3_8_kg_por_m"]
                     * self._factores_zona["acero"])
        partidas.append(
            Partida("Muros", "Anclas / bastones 3/8\" (base + conexión superior a losa)",
                    (f"{n_anclas} anclas ({anclaje['anclas_por_panel']} por panel: 3 en la base "
                     f"cada {anclaje['separacion_m']*100:.0f} cm + 3 en la conexión superior a la "
                     f"losa de techo/entrepiso, siempre presente en este modelo). Base: "
                     f"{anclaje['longitud_empotrada_m']*100:.0f} cm empotrados en la losa de "
                     f"cimentación + {anclaje['longitud_libre_muro_m']*100:.0f} cm libres hacia "
                     f"el muro (Manual Técnico Panel Covintec 2011). Antes: solo 3 anclas "
                     f"(base únicamente) -- faltaba la mitad del anclaje real. No incluye "
                     f"casos especiales (columnas híbridas: 12-15/panel; bardas de "
                     f"colindancia: refuerzo en ambas caras)."),
                    "kg", kg_anclas, self._desp("acero"),
                    "Acero_Varilla", self._precio("Acero_Varilla"))
        )
        return partidas

    def _losa(self) -> list[Partida]:
        g, esp = self.geo, self.p["espesores"]
        partidas: list[Partida] = []

        if g.area_losa_azotea_m2 > 0:
            partidas += [
                Partida("Losa", "Panel de losa",
                        f"{g.n_paneles_losa} piezas moduladas a 1.22 m",
                        "m²", g.area_losa_azotea_m2 + g.area_losa_entrepiso_m2, 0.0,
                        "Panel_Techo", self._precio("Panel_Techo")),
                Partida("Losa", "Capa de compresión (azotea)",
                        f"{esp['losa_azotea_m']*100:.0f} cm, resistencia mín. "
                        f"{self.p['resistencias']['losa_minima']} kg/cm²",
                        "m³", g.area_losa_azotea_m2 * esp["losa_azotea_m"],
                        self._desp("concreto"), "H_3000_PSI", self._precio("H_3000_PSI")),
            ]

        if g.area_losa_entrepiso_m2 > 0:
            partidas.append(
                Partida("Losa", "Capa de compresión (entrepiso)",
                        f"{esp['losa_entrepiso_m']*100:.1f} cm",
                        "m³", g.area_losa_entrepiso_m2 * esp["losa_entrepiso_m"],
                        self._desp("concreto"), "H_3500_PSI", self._precio("H_3500_PSI"))
            )

        area_losa = g.area_losa_azotea_m2 + g.area_losa_entrepiso_m2
        partidas.append(
            Partida("Acero", "Acero de refuerzo en losa",
                    "Acero principal + temperatura",
                    "kg", area_losa * 6.0 * self._factores_zona["acero"],
                    self._desp("acero"), "Acero_Varilla", self._precio("Acero_Varilla"),
                    "[supuesto]")
        )
        return partidas

    def _instalaciones(self) -> list[Partida]:
        area = self.geo.area_m2
        return [
            Partida("Instalaciones", "Instalación eléctrica",
                    "Canalización, cableado, tableros y salidas",
                    "m²", area, 0.0, "Instalacion_electrica_m2",
                    self._precio("Instalacion_electrica_m2"), "[supuesto]"),
            Partida("Instalaciones", "Instalación sanitaria y agua potable",
                    "Alimentación, drenaje y ventilación",
                    "m²", area, 0.0, "Instalacion_sanitaria_m2",
                    self._precio("Instalacion_sanitaria_m2"), "[supuesto]"),
        ]

    def _acabados(self) -> list[Partida]:
        g = self.geo
        f = self._factor_calidad
        clave_piso = "Porcelanato_m2" if self.calidad in (Calidad.ALTA, Calidad.LUJO) else "Ceramica_m2"

        partidas = [
            Partida("Acabados", "Piso",
                    f"Calidad {self.calidad.value}", "m²",
                    g.area_m2, self._desp("acabados"), clave_piso,
                    self._precio(clave_piso) * (f / 1.0 if clave_piso == "Ceramica_m2" else 1.0),
                    "[supuesto]"),
            Partida("Acabados", "Pintura",
                    "Vinílica, 3 manos sobre ambas caras de muro "
                    "(rendimiento de 12 m²/galón: supuesto, sin ficha técnica)", "gal",
                    g.area_muros_m2 * 2 / 12.0, self._desp("acabados"),
                    "Pintura_galon", self._precio("Pintura_galon") * f, "[supuesto]"),
            Partida("Acabados", "Cielo raso",
                    "Suministro e instalación", "m²",
                    g.area_planta_m2, self._desp("acabados"),
                    "Cielo_raso_m2", self._precio("Cielo_raso_m2") * f, "[supuesto]"),
            Partida("Acabados", "Impermeabilización de azotea",
                    "Sistema sobre capa de compresión", "m²",
                    g.area_losa_azotea_m2, self._desp("acabados"),
                    "Impermeabilizante_azotea_m2", self._precio("Impermeabilizante_azotea_m2"),
                    "[supuesto]"),
            Partida("Carpintería", "Puertas interiores",
                    f"{g.n_puertas_interiores} unidades con marco "
                    f"(cantidad estimada por área, no contada del plano)", "ud",
                    g.n_puertas_interiores, 0.0, "Puerta_interior",
                    self._precio("Puerta_interior") * f, "[supuesto]"),
            Partida("Carpintería", "Puertas exteriores",
                    f"{g.n_puertas_exteriores} unidades de seguridad", "ud",
                    g.n_puertas_exteriores, 0.0, "Puerta_exterior",
                    self._precio("Puerta_exterior") * f, "[supuesto]"),
            Partida("Carpintería", "Ventanas de aluminio",
                    f"{g.n_ventanas} ventanas (~1.2 m² c/u: cantidad y tamaño "
                    f"estimados por área, no contados/medidos del plano)", "m²",
                    g.n_ventanas * 1.2, self._desp("acabados"),
                    "Ventana_aluminio_m2", self._precio("Ventana_aluminio_m2") * f, "[supuesto]"),
        ]

        # --- baños --------------------------------------------------------
        n = g.n_banos
        for nombre, clave in (("Inodoros", "Inodoro"), ("Lavamanos", "Lavamanos"),
                              ("Duchas", "Ducha"), ("Grifería", "Griferia_bano")):
            partidas.append(
                Partida("Baños", nombre, f"{n} baño(s) (cantidad estimada por área)", "ud",
                        n, 0.0, clave, self._precio(clave) * f, "[supuesto]")
            )

        # --- cocina -------------------------------------------------------
        ml = g.ml_cocina_m
        partidas += [
            Partida("Cocina", "Gabinetes", f"{ml:.1f} ml (estimado por área)", "ml",
                    ml, 0.0, "Gabinete_cocina_ml", self._precio("Gabinete_cocina_ml") * f, "[supuesto]"),
            Partida("Cocina", "Mesón de granito", f"{ml:.1f} ml (estimado por área)", "ml",
                    ml, 0.0, "Meson_granito_ml", self._precio("Meson_granito_ml") * f, "[supuesto]"),
            Partida("Cocina", "Fregadero", "Suministro e instalación", "ud",
                    1, 0.0, "Fregadero_cocina", self._precio("Fregadero_cocina") * f, "[supuesto]"),
        ]
        return partidas

    def _mano_obra(self) -> list[Partida]:
        g = self.geo
        mo = self.p["mano_obra"]
        jornal = self._precio("MO_jornal_dia")

        rendimiento_aplanado = (mo["aplanado_m2_dia_lanzadora"] if self.aplanado_mecanizado
                                else mo["aplanado_m2_dia_manual"])
        modo = "lanzadora neumática" if self.aplanado_mecanizado else "manual"
        area_aplanado = g.area_muros_m2 * 2

        partidas = [
            # [doc] "Armado de muros: cuadrilla (1 oficial + 2 ayudantes)
            # rinde 18 m²/jornada" (video "Costos del sistema Covintec",
            # NotebookLM del usuario). Antes: 45.0 [supuesto], sin fuente.
            Partida("Mano de obra", "Montaje de panel",
                    f"Rendimiento {mo['montaje_panel_m2_dia']} m²/día",
                    "jornal", self._jornal(g.area_muros_m2, mo["montaje_panel_m2_dia"]),
                    0.0, "MO_jornal_dia", jornal),
            Partida("Mano de obra", f"Aplanado ({modo})",
                    f"{area_aplanado:.0f} m² a {rendimiento_aplanado} m²/día",
                    "jornal", self._jornal(area_aplanado, rendimiento_aplanado),
                    0.0, "MO_jornal_dia", jornal),
            Partida("Mano de obra", "Cimentación",
                    f"Rendimiento {mo['cimentacion_m2_dia']} m²/día",
                    "jornal", self._jornal(g.area_cimentacion_m2, mo["cimentacion_m2_dia"]),
                    0.0, "MO_jornal_dia", jornal, "[supuesto]"),
            # [doc] "Armado de losa (Qualylosa): rendimiento de 15 m²/jornada"
            # (video "Costos del sistema Covintec"). Antes: 30.0 [supuesto].
            Partida("Mano de obra", "Losas",
                    f"Rendimiento {mo['losa_m2_dia']} m²/día",
                    "jornal",
                    self._jornal(g.area_losa_azotea_m2 + g.area_losa_entrepiso_m2, mo["losa_m2_dia"]),
                    0.0, "MO_jornal_dia", jornal),
        ]

        # [doc] "Herramienta menor: 3%" del costo de mano de obra (video
        # "Costos del sistema Covintec", citando Art. 185 de la Ley de Obras
        # Públicas: Costo Directo = materiales + mano de obra + herramienta).
        # Antes: ausente del modelo por completo.
        subtotal_mo = sum(p.cantidad_neta * p.precio_unitario for p in partidas)
        partidas.append(
            Partida("Mano de obra", "Herramienta menor",
                    f"{mo['herramienta_menor_pct']*100:.0f}% del costo de mano de obra "
                    f"(desgaste de herramienta, no incluido en los jornales)",
                    "global", 1.0, 0.0, "MO_jornal_dia",
                    subtotal_mo * mo["herramienta_menor_pct"])
        )
        return partidas

    # ==================================================================
    # API PÚBLICA
    # ==================================================================

    def partidas(self) -> list[Partida]:
        return (self._cimentacion() + self._muros() + self._losa()
                + self._instalaciones() + self._acabados() + self._mano_obra())

    def presupuesto(self) -> pd.DataFrame:
        """DataFrame completo con una fila por partida."""
        df = pd.DataFrame([p.a_dict() for p in self.partidas()])
        columnas = ["categoria", "partida", "detalle", "unidad", "cantidad_neta",
                    "desperdicio", "cantidad", "clave_precio", "precio_unitario",
                    "subtotal", "precio_por_verificar", "fuente"]
        return df[columnas]

    @classmethod
    def limitaciones_conocidas(cls) -> tuple:
        """Condiciones de proyecto que este motor no calcula (ver LIMITACIONES_CONOCIDAS)."""
        return LIMITACIONES_CONOCIDAS

    @classmethod
    def claves_precio_usadas(cls, precios: Optional[Dict[str, float]] = None) -> frozenset:
        """
        Claves del pricebook que este motor consume.

        Se computa EJECUTANDO el motor sobre un escenario representativo
        (2 niveles + calidad alta, para capturar las claves que solo
        aparecen condicionalmente: losa de entrepiso, porcelanato) en vez de
        mantener una lista escrita a mano -- eso fue justo lo que hizo que el
        motor clásico (`BudgetCalculator.CLAVES_PRECIO_USADAS`) se desalineara
        de sus propias partidas.
        """
        from .geometria import Geometria
        from .pricebook import DEFAULT_PRICEBOOK

        precios = precios or DEFAULT_PRICEBOOK
        geo = Geometria(area_m2=120.0, perimetro_m=44.0, niveles=2)
        motor = cls(geo, precios, calidad="alta")
        return frozenset(p.clave_precio for p in motor.partidas() if p.clave_precio)

    def presupuesto_formato_legado(self) -> pd.DataFrame:
        """
        El mismo presupuesto con las columnas que esperan `PDFGenerator`,
        la exportación a Excel y los gráficos de `ui_calculadora.py`
        (`Categoria`, `Material`, `Detalle`, `Cantidad`, `Unidad`,
        `P_Unitario`, `Subtotal` — el esquema exacto de `utils/calculador.py`).

        Existe para que el PDF y el Excel que recibe un cliente muestren las
        MISMAS partidas que sumó el motor QTO. Antes el PDF recibía solo el
        DataFrame de obra gris pero el total impreso incluía obra gris +
        terminada: las filas nunca sumaban el total mostrado.
        """
        df = self.presupuesto()
        return df.rename(columns={
            "partida": "Material",
            "detalle": "Detalle",
            "cantidad": "Cantidad",
            "unidad": "Unidad",
            "precio_unitario": "P_Unitario",
            "subtotal": "Subtotal",
            "categoria": "Categoria",
        })[["Categoria", "Material", "Detalle", "Cantidad", "Unidad", "P_Unitario", "Subtotal"]]

    def total(self) -> float:
        return float(sum(p.subtotal for p in self.partidas()))

    def total_obra_gris(self) -> float:
        return float(sum(p.subtotal for p in self.partidas()
                         if p.categoria in CATEGORIAS_OBRA_GRIS))

    def total_obra_terminada(self) -> float:
        return self.total() - self.total_obra_gris()

    def costo_m2(self) -> float:
        return self.total() / self.geo.area_m2

    def resumen_por_categoria(self) -> pd.DataFrame:
        df = self.presupuesto()
        resumen = (df.groupby("categoria", as_index=False)["subtotal"].sum()
                     .sort_values("subtotal", ascending=False))
        resumen["pct"] = resumen["subtotal"] / resumen["subtotal"].sum() * 100
        resumen["obra"] = resumen["categoria"].apply(
            lambda c: "Gris" if c in CATEGORIAS_OBRA_GRIS else "Terminada"
        )
        return resumen.reset_index(drop=True)

    def partidas_por_verificar(self) -> pd.DataFrame:
        """Partidas cuyo precio sigue siendo referencia, no cotización firme."""
        df = self.presupuesto()
        return df[df["precio_por_verificar"]][
            ["categoria", "partida", "clave_precio", "precio_unitario", "subtotal"]
        ].reset_index(drop=True)

    # -- comparación gris vs gris ---------------------------------------
    def comparar_con_tradicional(self, ahorro_obra_gris: float | None = None) -> dict[str, Any]:
        """
        Comparación honesta contra construcción tradicional.

        [doc] "EPS/ICF ahorra 20-40% en OBRA GRIS (no en acabados, que son
        iguales en ambos sistemas). Default sugerido: 27.5%. El '83%' viejo
        comparaba obra gris EPS vs obra TERMINADA tradicional (peras con
        manzanas)."

        Por eso el ahorro se aplica SOLO sobre la obra gris y los acabados se
        toman idénticos en ambos sistemas.
        """
        cfg = self.p["comparacion_tradicional"]
        ahorro = cfg["ahorro_obra_gris_default"] if ahorro_obra_gris is None else float(ahorro_obra_gris)

        gris_eps = self.total_obra_gris()
        terminada = self.total_obra_terminada()

        # Si EPS cuesta (1 - ahorro) de lo que cuesta la obra gris tradicional,
        # entonces la tradicional cuesta gris_eps / (1 - ahorro).
        gris_tradicional = gris_eps / (1 - ahorro)

        total_eps = gris_eps + terminada
        total_tradicional = gris_tradicional + terminada

        dias_eps = self.geo.area_m2 * cfg["dias_por_m2_eps"]
        dias_trad = self.geo.area_m2 * cfg["dias_por_m2_tradicional"]

        return {
            "eps": {
                "obra_gris": gris_eps,
                "obra_terminada": terminada,
                "costo_total": total_eps,
                "costo_m2": total_eps / self.geo.area_m2,
                "dias": dias_eps,
            },
            "tradicional": {
                "obra_gris": gris_tradicional,
                "obra_terminada": terminada,
                "costo_total": total_tradicional,
                "costo_m2": total_tradicional / self.geo.area_m2,
                "dias": dias_trad,
            },
            "ahorro": {
                "obra_gris_pct": ahorro * 100,
                "obra_gris_rd": gris_tradicional - gris_eps,
                "total_rd": total_tradicional - total_eps,
                # Sobre el TOTAL el ahorro es menor que sobre la obra gris,
                # justamente porque los acabados no cambian. Esta es la cifra
                # defendible frente a un maestro constructor.
                "total_pct": (total_tradicional - total_eps) / total_tradicional * 100,
                "dias": dias_trad - dias_eps,
            },
            "rango_ahorro_gris": (cfg["ahorro_obra_gris_min"] * 100,
                                  cfg["ahorro_obra_gris_max"] * 100),
        }
