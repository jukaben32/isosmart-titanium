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
        """Costo de mano de obra: días de cuadrilla x personas x jornal."""
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
                    f"Refuerzo de platea (traslape {(self.p['mallas']['electrosoldada_traslape']-1)*100:.0f}%)",
                    "m²", area * self.p["mallas"]["electrosoldada_traslape"],
                    self._desp("mallas"), "Malla_Electrosoldada",
                    self._precio("Malla_Electrosoldada"), "[supuesto]"),
            # [doc] sección 2: "Resistencia cimentación/zapata: 250 kg/cm²".
            # Antes: `H_3000_PSI * 1.20`, un multiplicador arbitrario sobre el
            # concreto de losa (≈211 kg/cm², para el requisito de 200 kg/cm²
            # de losa). H_3500_PSI (≈246 kg/cm²) YA EXISTE en el pricebook y
            # es la resistencia correcta para cimentación -- se usa
            # directamente en vez de fabricar un precio sintético con un
            # multiplicador sin fuente.
            Partida("Cimentación", "Losa de cimentación (platea)",
                    f"Concreto {self.p['resistencias']['cimentacion']} kg/cm² "
                    f"(H_3500_PSI ≈ 246 kg/cm², la resistencia disponible más cercana), "
                    f"espesor {esp['cimentacion_platea_m']*100:.1f} cm",
                    "m³", vol_platea, self._desp("concreto"),
                    "H_3500_PSI", self._precio("H_3500_PSI")),
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
                    f"{esp_mortero*100:.1f} cm por cara, 2 capas, sobre {area_aplanado:.0f} m²",
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
        # [doc] la fórmula (12/13 piezas por vano, x2 lados) está calibrada
        # para los vanos de referencia del documento (ventana 90x90,
        # puerta 215x90). Si el proyecto real tiene vanos más grandes,
        # `Geometria.factor_escala_ventana/puerta` escala la cantidad en
        # proporción al perímetro del vano -- una extrapolación razonable
        # ([supuesto], no una fórmula documentada para tamaño arbitrario),
        # que por defecto es 1.0 (sin vanos indicados = tamaño de referencia,
        # comportamiento idéntico al anterior).
        piezas_zigzag_base = (
            g.n_ventanas * mallas["zigzag_piezas_por_ventana"] * g.factor_escala_ventana
            + g.n_puertas_total * mallas["zigzag_piezas_por_puerta"] * g.factor_escala_puerta
        )
        piezas_zigzag = piezas_zigzag_base * mallas["zigzag_lados"]

        piezas_esquinera = math.ceil(
            g.esquinas_efectivas * g.altura_efectiva_m * g.niveles
            / mallas["esquinera_largo_pieza_m"]
        )
        piezas_union = math.ceil(
            g.n_paneles_muro * mallas["union_fraccion_paneles_cortados"]
            * mallas["union_lados"]
        )

        partidas += [
            Partida("Muros", "Malla zigzag en vanos",
                    (f"{g.n_ventanas} ventanas x 12 pzas + {g.n_puertas_total} puertas x 13 pzas, "
                     f"ambos lados. Calibrado para vanos de referencia (ventana 90x90 cm, "
                     f"puerta 215x90 cm)"
                     + (f"; ESCALADO a ventana real {g.ancho_ventana_m:.2f}x{g.alto_ventana_m:.2f} m "
                        f"(factor {g.factor_escala_ventana:.2f}x, extrapolación por perímetro, "
                        f"no una fórmula documentada)"
                        if g.factor_escala_ventana != 1.0 else "")
                     + (f"; ESCALADO a puerta real {g.ancho_puerta_m:.2f}x{g.alto_puerta_m:.2f} m "
                        f"(factor {g.factor_escala_puerta:.2f}x)"
                        if g.factor_escala_puerta != 1.0 else "")),
                    "pza", piezas_zigzag, self._desp("mallas"),
                    "Malla_zigzag_pieza", self._precio("Malla_zigzag_pieza"),
                    "[doc]" if g.factor_escala_ventana == g.factor_escala_puerta == 1.0 else "[supuesto]"),
            Partida("Muros", "Malla esquinera",
                    f"({g.esquinas_efectivas} esquinas x {g.altura_efectiva_m} m) / 2.40 m",
                    "pza", piezas_esquinera, self._desp("mallas"),
                    "Malla_esquinera_pieza", self._precio("Malla_esquinera_pieza")),
            Partida("Muros", "Malla de unión en cortes",
                    "Tira de 10 cm x 2.40 m, ambos lados, en cortes de panel",
                    "pza", piezas_union, self._desp("mallas"),
                    "Malla_union_pieza", self._precio("Malla_union_pieza"), "[supuesto]"),
        ]

        # --- anclas -------------------------------------------------------
        n_anclas = g.n_paneles_muro * anclaje["anclas_por_panel"]
        kg_anclas = (n_anclas * anclaje["longitud_ancla_m"]
                     * anclaje["peso_varilla_3_8_kg_por_m"]
                     * self._factores_zona["acero"])
        partidas.append(
            Partida("Muros", "Anclas / bastones 3/8\"",
                    f"{n_anclas} anclas (3 por panel, cada {anclaje['separacion_m']*100:.0f} cm), "
                    f"5 cm dentro de cimentación (longitud total de ancla: supuesto). "
                    f"⚠️ El manual oficial de instalación del fabricante describe barras "
                    f"de arranque a 30 cm con 40-50 cm de empotramiento -- posible refuerzo "
                    f"ADICIONAL no incluido aquí. Ver data/parametros_tecnicos.yaml::anclaje "
                    f"para el conflicto sin resolver; confirmar con ingeniero estructural.",
                    "kg", kg_anclas, self._desp("acero"),
                    "Acero_Varilla", self._precio("Acero_Varilla"), "[supuesto]")
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

        return [
            Partida("Mano de obra", "Montaje de panel",
                    f"Rendimiento {mo['montaje_panel_m2_dia']} m²/día",
                    "jornal", self._jornal(g.area_muros_m2, mo["montaje_panel_m2_dia"]),
                    0.0, "MO_jornal_dia", jornal, "[supuesto]"),
            Partida("Mano de obra", f"Aplanado ({modo})",
                    f"{area_aplanado:.0f} m² a {rendimiento_aplanado} m²/día",
                    "jornal", self._jornal(area_aplanado, rendimiento_aplanado),
                    0.0, "MO_jornal_dia", jornal),
            Partida("Mano de obra", "Cimentación",
                    f"Rendimiento {mo['cimentacion_m2_dia']} m²/día",
                    "jornal", self._jornal(g.area_cimentacion_m2, mo["cimentacion_m2_dia"]),
                    0.0, "MO_jornal_dia", jornal, "[supuesto]"),
            Partida("Mano de obra", "Losas",
                    f"Rendimiento {mo['losa_m2_dia']} m²/día",
                    "jornal",
                    self._jornal(g.area_losa_azotea_m2 + g.area_losa_entrepiso_m2, mo["losa_m2_dia"]),
                    0.0, "MO_jornal_dia", jornal, "[supuesto]"),
        ]

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
