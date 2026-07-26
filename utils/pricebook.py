from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Dict, Tuple

from .storage import read_json, write_json_atomic

DEFAULT_PRICEBOOK: dict[str, float] = {
    "Panel_Muro": 925.00,
    "Panel_Techo": 1125.00,
    "H_3000_PSI": 7350.00,
    "H_3500_PSI": 7950.00,
    "Viga_H_kg": 105.00,
    "Acero_Varilla": 85.00,
    "Malla_Electrosoldada": 450.00,
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
    "Malla_esquinera_pieza": 180.00,
    "Malla_union_pieza": 145.00,
    "Polietileno_m2": 65.00,
    "Instalacion_electrica_m2": 1450.00,
    "Instalacion_sanitaria_m2": 1250.00,
    "Puerta_exterior": 22000.00,
    "Impermeabilizante_azotea_m2": 750.00,
    "Cielo_raso_m2": 950.00,
    "MO_jornal_dia": 1800.00,
}

# ---------------------------------------------------------------------------
# Precios que todavía son REFERENCIA, no cotización de proveedor.
#
# docs/BASE_TECNICA_EPS_ICF.md, sección 11: "Placeholder: precios de REFERENCIA
# Covintex convertidos a RD$ [...] NO inventar cifras". Marcarlos explícitamente
# permite que la interfaz y el PDF avisen en vez de presentarlos como firmes.
# ---------------------------------------------------------------------------
PRECIOS_POR_VERIFICAR = frozenset({
    "Mortero_saco", "Microfibra_kg", "Malla_zigzag_pieza", "Malla_esquinera_pieza",
    "Malla_union_pieza", "Polietileno_m2", "Instalacion_electrica_m2",
    "Instalacion_sanitaria_m2", "Puerta_exterior", "Impermeabilizante_azotea_m2",
    "Cielo_raso_m2", "MO_jornal_dia",
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

