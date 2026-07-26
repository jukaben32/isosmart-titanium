# -*- coding: utf-8 -*-
"""
utils/dominio.py
----------------
Vocabulario del dominio: sistema constructivo, calidad de terminados y zona de
riesgo, con normalización y validación estricta.

MOTIVO
======
El código anterior comparaba strings crudos contra literales y usaba
``dict.get(valor, default)``. Eso convertía cualquier desalineación en un
**número plausible y equivocado, sin traza**:

    pages/1_Dashboard_Financiero.py -> "económica"   (con tilde)
    utils/calculador.py             -> "economica"   (sin tilde)
    factores.get("económica", 1.0)  -> 1.0           (¡el factor de "media"!)

Resultado: seleccionar "económica" cotizaba exactamente igual que "media".

Aquí la normalización es explícita (ignora tildes, mayúsculas y espacios) y un
valor realmente desconocido **lanza ValueError** en vez de degradarse en
silencio.
"""

from __future__ import annotations

import unicodedata
from enum import Enum
from typing import Iterable


def _slug(texto: object) -> str:
    """Minúsculas, sin tildes, sin espacios sobrantes."""
    s = str(texto).strip().lower()
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


class Calidad(str, Enum):
    ECONOMICA = "economica"
    MEDIA = "media"
    ALTA = "alta"
    LUJO = "lujo"


class Sistema(str, Enum):
    ISOTEX = "isotex"
    ICF = "icf"
    TRADICIONAL = "tradicional"


class ZonaRiesgo(str, Enum):
    MODERADO = "moderado"
    ALTO = "alto"
    MUY_ALTO = "muy_alto"


# Sinónimos aceptados desde la interfaz y desde respuestas de la IA.
_ALIAS_SISTEMA = {
    "isotex": Sistema.ISOTEX,
    "paneles isotex": Sistema.ISOTEX,
    "panel isotex": Sistema.ISOTEX,
    "eps": Sistema.ISOTEX,
    "covintec": Sistema.ISOTEX,
    "icf": Sistema.ICF,
    "icf proform": Sistema.ICF,
    "proform": Sistema.ICF,
    "tradicional": Sistema.TRADICIONAL,
    "bloque": Sistema.TRADICIONAL,
    "block": Sistema.TRADICIONAL,
    "convencional": Sistema.TRADICIONAL,
}

_ALIAS_ZONA = {
    "moderado": ZonaRiesgo.MODERADO,
    "moderado (base)": ZonaRiesgo.MODERADO,
    "base": ZonaRiesgo.MODERADO,
    "alto": ZonaRiesgo.ALTO,
    "alto (falla septentrional)": ZonaRiesgo.ALTO,
    "muy alto": ZonaRiesgo.MUY_ALTO,
    "muy_alto": ZonaRiesgo.MUY_ALTO,
    "muy alto (ruta de huracanes)": ZonaRiesgo.MUY_ALTO,
}


def _resolver(valor: object, alias: dict, enum_cls, etiqueta: str):
    slug = _slug(valor)
    if slug in alias:
        return alias[slug]
    for miembro in enum_cls:
        if slug == miembro.value:
            return miembro
    validos: Iterable[str] = sorted({*alias.keys(), *(m.value for m in enum_cls)})
    raise ValueError(
        f"{etiqueta} no reconocido: {valor!r}. Valores válidos: {', '.join(validos)}"
    )


def normalizar_calidad(valor: object) -> Calidad:
    """'Económica' / 'ECONOMICA' / ' economica ' -> Calidad.ECONOMICA."""
    slug = _slug(valor)
    for miembro in Calidad:
        if slug == miembro.value:
            return miembro
    raise ValueError(
        f"Calidad no reconocida: {valor!r}. "
        f"Valores válidos: {', '.join(m.value for m in Calidad)}"
    )


def normalizar_sistema(valor: object) -> Sistema:
    """'Paneles Isotex' / 'EPS' / 'icf proform' -> Sistema.*"""
    return _resolver(valor, _ALIAS_SISTEMA, Sistema, "Sistema constructivo")


def normalizar_zona_riesgo(valor: object) -> ZonaRiesgo:
    """'Moderado (Base)' / 'Muy Alto' -> ZonaRiesgo.*"""
    return _resolver(valor, _ALIAS_ZONA, ZonaRiesgo, "Zona de riesgo")
