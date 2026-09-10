"""Conteos detallados de instalaciones para el motor QTO."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any


@dataclass(frozen=True)
class InstalacionesDetalle:
    """Cantidades opcionales para sustituir el cálculo grueso por m²."""

    tableros: int = 1
    tomacorrientes: int = 0
    interruptores: int = 0
    luminarias: int = 0
    puntos_datos: int = 0
    camaras: int = 0
    ml_canalizacion_electrica: float = 0.0
    puntos_agua: int = 0
    puntos_sanitarios: int = 0
    registros_sanitarios: int = 0
    ml_tuberia_agua: float = 0.0
    ml_tuberia_sanitaria: float = 0.0
    puntos_gas: int = 0
    puntos_clima: int = 0

    @property
    def tiene_detalle(self) -> bool:
        """Indica si hay conteos reales además del tablero por defecto."""
        datos = self.a_dict()
        datos.pop("tableros", None)
        return any(float(v or 0) > 0 for v in datos.values())

    def a_dict(self) -> dict[str, int | float]:
        return asdict(self)

    @classmethod
    def desde_dict(cls, data: dict[str, Any] | None) -> "InstalacionesDetalle":
        if not data:
            return cls()

        validos = {f.name for f in fields(cls)}
        limpio: dict[str, int | float] = {}
        for clave, valor in data.items():
            if clave not in validos:
                continue
            try:
                if clave.startswith("ml_"):
                    limpio[clave] = max(0.0, float(valor))
                else:
                    limpio[clave] = max(0, int(round(float(valor))))
            except (TypeError, ValueError):
                continue
        return cls(**limpio)

