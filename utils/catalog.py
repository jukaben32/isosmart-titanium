from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from .storage import read_json, write_json_atomic


DEFAULT_CATALOG: Dict[str, Any] = {
    "provider": {
        "name": "Isotex Dominicana",
        "source_pages": [
            "https://isotexdominicana.com/paredes/mpanel/",
            "https://isotexdominicana.com/techos/termopanel/",
        ],
    },
    "products": [
        {
            "sku": "MPANEL",
            "name": "Panel de malla MPanel®",
            "category": "muros",
            "unit": "m2",
            "notes": "Panel EPS + mallas electrosoldadas. Usado en paredes estructurales y cerramiento.",
            "specs": {
                "ancho_util_m": 1.2,
                "eps_espesor_mm_min": 40,
                "eps_espesor_mm_max": 200,
                "pared_terminada_mm_min": 90,
                "pared_terminada_mm_max": 270,
            },
            "price_key": "Panel_Muro",
        },
        {
            "sku": "TERMOPANEL",
            "name": "Panel sándwich para techos Termopanel®",
            "category": "techos",
            "unit": "m2",
            "notes": "Panel sándwich (acero + EPS).",
            "specs": {
                "ancho_util_mm": 1000,
                "largo_max_m": 12,
                "espesores_nominales_mm": [75, 100],
            },
            "price_key": "Panel_Techo",
        },
    ],
}


@dataclass(frozen=True)
class Catalog:
    path: str

    def load(self) -> Dict[str, Any]:
        data = read_json(self.path, default={})
        if isinstance(data, dict) and data.get("products"):
            return data
        return DEFAULT_CATALOG

    def save(self, catalog: Dict[str, Any]) -> None:
        write_json_atomic(self.path, catalog)

    def list_products(self) -> List[Dict[str, Any]]:
        cat = self.load()
        prods = cat.get("products", [])
        return [p for p in prods if isinstance(p, dict)]

