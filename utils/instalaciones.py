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
    # --- desglose por diámetro y conductor (medido del plano) -----------
    ml_alambre_electrico: float = 0.0       # ml de cable THW (fase + neutro + tierra)
    ml_tuberia_agua_1_2: float = 0.0       # ramales de distribución (1/2")
    ml_tuberia_agua_3_4: float = 0.0       # alimentación principal (3/4")
    ml_tuberia_sanitaria_4: float = 0.0    # tubería sanitaria 4" (WC/drenaje)
    # --- acabados y equipamiento que requieren cantidad explícita --------
    lamparas: int = 0                       # lámparas/luminarias reales (suministro + instalación)
    kw_sistema_solar: float = 0.0           # sistema fotovoltaico (kW de paneles)
    pozo_septico: int = 0                   # pozos sépticos
    cisterna_m3: float = 0.0                # capacidad de cisterna en m³

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

