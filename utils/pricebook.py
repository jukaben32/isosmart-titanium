from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Dict, Tuple

from .storage import read_json, write_json_atomic

# ---------------------------------------------------------------------------
# Trazabilidad de precios
# ---------------------------------------------------------------------------
# El proveedor local en el que se basaba esta lista de precios operaba en
# efectivo, sin factura ni canal verificable, y esos números no se pueden
# defender ante un cliente. Mientras se establece un canal de precios
# auditable en Santo Domingo, dos partidas usan una fuente real —Covintec
# México, el mismo sistema constructivo (EPS + malla electrosoldada)— y
# quedan documentadas en utils/fuentes.py:
#
#   Panel_Muro (1,072 RD$/m²):
#     950 MXN/pieza (1.22 x 2.44 m) / 2.9768 m² x 3.36 DOP/MXN
#     Fuente: Materiales La Libertad (Puebla, México), precio de tienda.
#     https://materialeslibertad.com/products/panel-covintec-de-2-3-y-4
#
#   Malla_Electrosoldada (458 RD$/m²):
#     49.50 MXN/pieza (0.31 x 1.17 m) / 0.363 m² x 3.36 DOP/MXN
#     Fuente: Paneles y Plafones MG (México), precio de tienda.
#     https://plafonesmg.com/product-category/panel-constructivo/panel-covintec/
#
# Tipo de cambio: 3.36 DOP/MXN (Xe.com, 26 jul 2026). Ver utils/fuentes.py.
#
# El resto sigue en PRECIOS_POR_VERIFICAR: son estimaciones de ingeniería sin
# cotización real detrás, y así se lo advierte la interfaz al usuario.
# ---------------------------------------------------------------------------
DEFAULT_PRICEBOOK: dict[str, float] = {
    "Panel_Muro": 1072.00,      # antes: 925.00 (sin fuente conocida)
    "Panel_Techo": 1125.00,
    "H_3000_PSI": 7350.00,
    "H_3500_PSI": 7950.00,
    "Viga_H_kg": 105.00,
    "Acero_Varilla": 85.00,
    "Malla_Electrosoldada": 458.00,   # antes: 450.00 (coincide, ahora con fuente)
    "Poliestireno_EPS": 2800.00,
    "Fibra_Acero": 120.00,
    "Aditivo_Impermeabilizante": 850.00,
    "Cemento_Saco": 450.00,
    "Arena_m3": 1200.00,
    "Piedra_m3": 1100.00,
    "Ladrillo_unidad": 28.00,
    "Ceramica_m2": 450.00,
    "Porcelanato_m2": 850.00,
    "Pintura_galon": 1200.00,
    "Yeso_saco": 180.00,
    "Puerta_interior": 8500.00,
    "Ventana_aluminio_m2": 4500.00,
    "Griferia_bano": 3500.00,
    "Inodoro": 4200.00,
    "Lavamanos": 2800.00,
    "Ducha": 1800.00,
    "Fregadero_cocina": 6500.00,
    "Gabinete_cocina_ml": 12000.00,
    "Meson_granito_ml": 18000.00,

    # -----------------------------------------------------------------
    # Partidas incorporadas por la auditoría para completar el presupuesto.
    # El motor anterior solo usaba 9 de los 27 materiales; faltaban mortero,
    # mallas, instalaciones, impermeabilización y MANO DE OBRA, que son ~75%
    # del costo real de una vivienda.
    # -----------------------------------------------------------------
    "Mortero_saco": 380.00,
    "Microfibra_kg": 320.00,
    "Malla_zigzag_pieza": 95.00,
    # [doc] VERIFICADO con NotebookLM del usuario: son DOS productos
    # distintos, no una malla que se duplica -- malla esquinera interna
    # (10x10 o 14x14 cm x 2.40 m) y externa (20x20 cm x 2.40 m). Antes
    # había una sola clave "Malla_esquinera_pieza" tratando ambas caras
    # como el mismo producto.
    #
    # Sin cotización real que distinga el precio de cada una todavía
    # (ambas parten del mismo precio de referencia anterior, 180.00) --
    # ver PRECIOS_POR_VERIFICAR.
    "Malla_esquinera_interna_pieza": 180.00,
    "Malla_esquinera_externa_pieza": 180.00,
    "Malla_union_pieza": 145.00,
    "Polietileno_m2": 65.00,
    "Instalacion_electrica_m2": 1450.00,
    "Instalacion_sanitaria_m2": 1250.00,
    "Puerta_exterior": 22000.00,
    "Impermeabilizante_azotea_m2": 750.00,
    "Cielo_raso_m2": 950.00,
    "MO_jornal_dia": 1800.00,

    # -----------------------------------------------------------------
    # Sistemas de techo Isotex Dominicana (proveedor único del usuario).
    # Cotizados por m² INSTALADO (material + mano de obra + accesorios),
    # como el usuario confirmó que los ha visto cotizar en la práctica --
    # a diferencia de todo lo demás en este pricebook, no se descomponen
    # en materiales sueltos.
    #
    # EN CERO A PROPÓSITO, no un placeholder inventado: ningún sistema
    # tiene precio público (ni Isotex ni la competencia dominicana,
    # verificado con búsqueda web). Usar un precio de un producto
    # distinto habría arriesgado un orden de magnitud equivocado sin
    # ninguna base real. El total de cualquier presupuesto que use uno
    # de estos sistemas está INCOMPLETO hasta actualizar con la
    # cotización real -- ver la advertencia en la partida y en
    # LIMITACIONES_CONOCIDAS.
    "Techo_Termopanel_m2": 0.0,
    "Techo_Termolosa_m2": 0.0,
    "Techo_Isolosa_m2": 0.0,
    "Techo_Isofill_m2": 0.0,
}

# ---------------------------------------------------------------------------
# Precios que todavía son REFERENCIA, no cotización de proveedor.
#
# docs/BASE_TECNICA_EPS_ICF.md, sección 11: "Placeholder: precios de REFERENCIA
# Covintex convertidos a RD$ [...] NO inventar cifras". Marcarlos explícitamente
# permite que la interfaz y el PDF avisen en vez de presentarlos como firmes.
# ---------------------------------------------------------------------------
PRECIOS_POR_VERIFICAR = frozenset({
    "Mortero_saco", "Microfibra_kg", "Malla_zigzag_pieza",
    "Malla_esquinera_interna_pieza", "Malla_esquinera_externa_pieza",
    "Malla_union_pieza", "Polietileno_m2", "Instalacion_electrica_m2",
    "Instalacion_sanitaria_m2", "Puerta_exterior", "Impermeabilizante_azotea_m2",
    "Cielo_raso_m2", "MO_jornal_dia",
})

# Un escalón más fuerte que PRECIOS_POR_VERIFICAR: no son estimaciones de
# ingeniería con un número plausible pendiente de ajustar, son literalmente
# RD$0.00 porque no existe ningún precio público que citar. Un presupuesto
# que use alguno de estos sistemas de techo está incompleto -- ver la
# advertencia en utils/qto.py y LIMITACIONES_CONOCIDAS.
PRECIOS_SIN_COTIZAR = frozenset({
    "Techo_Termopanel_m2", "Techo_Termolosa_m2",
    "Techo_Isolosa_m2", "Techo_Isofill_m2",
})


@dataclass(frozen=True)
class Pricebook:
    path: str

    def load(self) -> dict[str, float]:
        data = read_json(self.path, default={})
        merged = copy.deepcopy(DEFAULT_PRICEBOOK)
        if isinstance(data, dict):
            for k, v in data.items():
                try:
                    merged[str(k)] = float(v)
                except Exception:
                    continue
        return merged

    def save(self, prices: dict[str, float]) -> None:
        normalized: dict[str, float] = {}
        for k, v in prices.items():
            try:
                normalized[str(k)] = float(v)
            except Exception:
                continue
        write_json_atomic(self.path, normalized)

    def diff_from_default(self, prices: dict[str, float]) -> dict[str, tuple[float, float]]:
        diff: dict[str, tuple[float, float]] = {}
        for k, default_v in DEFAULT_PRICEBOOK.items():
            current_v = prices.get(k, default_v)
            if float(current_v) != float(default_v):
                diff[k] = (float(default_v), float(current_v))
        return diff

