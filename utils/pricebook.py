from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Dict, Tuple

from .storage import read_json, write_json_atomic


DEFAULT_PRICEBOOK: Dict[str, float] = {
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
    "Ladrillounidad": 28.00,
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
}


@dataclass(frozen=True)
class Pricebook:
    path: str

    def load(self) -> Dict[str, float]:
        data = read_json(self.path, default={})
        merged = copy.deepcopy(DEFAULT_PRICEBOOK)
        if isinstance(data, dict):
            for k, v in data.items():
                try:
                    merged[str(k)] = float(v)
                except Exception:
                    continue
        return merged

    def save(self, prices: Dict[str, float]) -> None:
        normalized: Dict[str, float] = {}
        for k, v in prices.items():
            try:
                normalized[str(k)] = float(v)
            except Exception:
                continue
        write_json_atomic(self.path, normalized)

    def diff_from_default(self, prices: Dict[str, float]) -> Dict[str, Tuple[float, float]]:
        diff: Dict[str, Tuple[float, float]] = {}
        for k, default_v in DEFAULT_PRICEBOOK.items():
            current_v = prices.get(k, default_v)
            if float(current_v) != float(default_v):
                diff[k] = (float(default_v), float(current_v))
        return diff

