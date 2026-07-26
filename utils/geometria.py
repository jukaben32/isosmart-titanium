# -*- coding: utf-8 -*-
"""
utils/geometria.py
------------------
Modelo geométrico del proyecto. **Sin Streamlit.**

POR QUÉ EXISTE
==============
Toda la capa de visión artificial de la app (canvas con calibración de escala,
lectura de cotas con Gemini, Text-to-Design) escribía sus resultados en
`st.session_state`:

    calc_perimetro_m, calc_niveles, calc_altura_muro_m, calc_espesor_muro_m

La auditoría encontró **cinco escrituras y cero lecturas**. El motor de
presupuesto ni siquiera aceptaba esos parámetros: usaba `area_muros = m2 * 2.2`,
una constante. Es decir, el usuario calibraba la escala, trazaba el polígono, la
IA leía las cotas... y el presupuesto salía idéntico a escribir el área a mano.

Esta clase es el contrato que faltaba entre la extracción geométrica y el
cálculo de cantidades.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .parametros import cargar_parametros


@dataclass(frozen=True)
class Geometria:
    """
    Geometría de un proyecto residencial.

    `area_m2` es el área construida TOTAL (todos los niveles), coherente con lo
    que devuelve el asistente Text-to-Design.
    """

    area_m2: float
    perimetro_m: Optional[float] = None
    altura_muro_m: Optional[float] = None
    niveles: int = 1
    esquinas: Optional[int] = None

    # Vanos y ambientes. Si no se indican, se estiman por área.
    ventanas: Optional[int] = None
    puertas_exteriores: Optional[int] = None
    puertas_interiores: Optional[int] = None
    banos: Optional[int] = None
    ml_cocina: Optional[float] = None

    parametros: Dict[str, Any] = field(default_factory=cargar_parametros, repr=False)

    # -- validación ------------------------------------------------------
    def __post_init__(self):
        if self.area_m2 <= 0:
            raise ValueError(f"area_m2 debe ser positiva, recibido: {self.area_m2}")
        if self.niveles < 1:
            raise ValueError(f"niveles debe ser >= 1, recibido: {self.niveles}")
        if self.perimetro_m is not None and self.perimetro_m <= 0:
            raise ValueError(f"perimetro_m debe ser positivo, recibido: {self.perimetro_m}")

    # -- helpers ---------------------------------------------------------
    @property
    def _defecto(self) -> Dict[str, Any]:
        return self.parametros["geometria_defecto"]

    @property
    def area_planta_m2(self) -> float:
        """Huella en planta: el área construida repartida entre los niveles."""
        return self.area_m2 / self.niveles

    @property
    def perimetro_efectivo_m(self) -> float:
        """
        Perímetro real si se conoce; si no, el de un rectángulo 3:2 de la misma
        área en planta.

        Un cuadrado daría el perímetro mínimo posible y subestimaría los muros de
        forma sistemática; la proporción 3:2 es más representativa de una
        vivienda real.
        """
        if self.perimetro_m:
            return float(self.perimetro_m)
        lado_corto = math.sqrt(self.area_planta_m2 / 1.5)
        return 2 * (lado_corto + 1.5 * lado_corto)

    @property
    def altura_efectiva_m(self) -> float:
        return float(self.altura_muro_m or self._defecto["altura_muro_m"])

    @property
    def esquinas_efectivas(self) -> int:
        return int(self.esquinas or self._defecto["esquinas"])

    # -- superficies -----------------------------------------------------
    @property
    def ml_muros_perimetrales(self) -> float:
        """Metros lineales de muro exterior, sumando todos los niveles."""
        return self.perimetro_efectivo_m * self.niveles

    @property
    def ml_muros_interiores(self) -> float:
        return self.ml_muros_perimetrales * self._defecto["factor_muros_interiores"]

    @property
    def ml_muros_total(self) -> float:
        return self.ml_muros_perimetrales + self.ml_muros_interiores

    @property
    def area_muros_perimetrales_m2(self) -> float:
        return self.ml_muros_perimetrales * self.altura_efectiva_m

    @property
    def area_muros_interiores_m2(self) -> float:
        return self.ml_muros_interiores * self.altura_efectiva_m

    @property
    def area_muros_m2(self) -> float:
        """
        Superficie total de muro. Reemplaza el `m2 * 2.2` hardcodeado: ahora
        responde al perímetro, la altura y el número de niveles reales.
        """
        return self.ml_muros_total * self.altura_efectiva_m

    @property
    def area_losa_azotea_m2(self) -> float:
        return self.area_planta_m2

    @property
    def area_losa_entrepiso_m2(self) -> float:
        return self.area_planta_m2 * max(0, self.niveles - 1)

    @property
    def area_cimentacion_m2(self) -> float:
        return self.area_planta_m2

    # -- vanos y ambientes ------------------------------------------------
    def _por_100m2(self, clave: str) -> int:
        return max(1, round(self._defecto[clave] * self.area_m2 / 100.0))

    @property
    def n_ventanas(self) -> int:
        return int(self.ventanas if self.ventanas is not None
                   else self._por_100m2("ventanas_por_100m2"))

    @property
    def n_puertas_exteriores(self) -> int:
        return int(self.puertas_exteriores if self.puertas_exteriores is not None
                   else self._defecto["puertas_ext_por_vivienda"])

    @property
    def n_puertas_interiores(self) -> int:
        return int(self.puertas_interiores if self.puertas_interiores is not None
                   else self._por_100m2("puertas_int_por_100m2"))

    @property
    def n_puertas_total(self) -> int:
        return self.n_puertas_exteriores + self.n_puertas_interiores

    @property
    def n_banos(self) -> int:
        return int(self.banos if self.banos is not None
                   else self._por_100m2("banos_por_100m2"))

    @property
    def ml_cocina_m(self) -> float:
        if self.ml_cocina is not None:
            return float(self.ml_cocina)
        return self._defecto["metros_lineales_cocina_por_100m2"] * self.area_m2 / 100.0

    # -- paneles ---------------------------------------------------------
    @property
    def n_paneles_muro(self) -> int:
        """
        [doc] "Muros: metros lineales / 1.22 m -> piezas (redondear hacia
        arriba). No descontar vanos."

        El redondeo por modulación sustituye al 5% de desperdicio plano que
        usaba el motor anterior, y es físicamente más exacto.
        """
        ancho = self.parametros["panel"]["ancho_util_m"]
        return math.ceil(self.ml_muros_total / ancho)

    @property
    def area_panel_comprada_m2(self) -> float:
        """Superficie de panel realmente facturada tras la modulación a 1.22 m."""
        ancho = self.parametros["panel"]["ancho_util_m"]
        return self.n_paneles_muro * ancho * self.altura_efectiva_m

    @property
    def n_paneles_losa(self) -> int:
        """[doc] Losas: largo del claro / 1.22 m -> piezas (redondear hacia arriba)."""
        ancho = self.parametros["panel"]["ancho_util_m"]
        lado = math.sqrt(self.area_planta_m2)
        piezas_por_nivel = math.ceil(lado / ancho)
        return piezas_por_nivel * self.niveles

    # -- interoperabilidad ------------------------------------------------
    @classmethod
    def desde_session_state(cls, estado: Dict[str, Any]) -> Geometria:
        """
        Construye la geometría a partir de las claves que la app ya escribía y
        nunca leía. Este método es, literalmente, el cable que faltaba.
        """
        def _num(*claves):
            for clave in claves:
                valor = estado.get(clave)
                if valor:
                    return valor
            return None

        return cls(
            area_m2=float(_num("calc_area_m2", "plan_area_m2") or 120.0),
            perimetro_m=_num("calc_perimetro_m", "plan_perimetro_m"),
            altura_muro_m=_num("calc_altura_muro_m", "plan_altura_muro_m"),
            niveles=int(_num("calc_niveles", "plan_niveles") or 1),
        )

    def resumen(self) -> Dict[str, float]:
        """Diccionario plano para mostrar en la UI o adjuntar al PDF."""
        return {
            "area_construida_m2": round(self.area_m2, 2),
            "area_planta_m2": round(self.area_planta_m2, 2),
            "niveles": self.niveles,
            "perimetro_m": round(self.perimetro_efectivo_m, 2),
            "altura_muro_m": round(self.altura_efectiva_m, 2),
            "ml_muros_total": round(self.ml_muros_total, 2),
            "area_muros_m2": round(self.area_muros_m2, 2),
            "area_losa_azotea_m2": round(self.area_losa_azotea_m2, 2),
            "area_losa_entrepiso_m2": round(self.area_losa_entrepiso_m2, 2),
            "paneles_muro": self.n_paneles_muro,
            "paneles_losa": self.n_paneles_losa,
            "ventanas": self.n_ventanas,
            "puertas": self.n_puertas_total,
            "banos": self.n_banos,
        }
