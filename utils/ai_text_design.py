from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional, Tuple


DEFAULT_TEXT_DESIGN_PARAMS: Dict[str, Any] = {
    "area_m2": 120.0,
    "niveles": 1,
    "perimetro_m": 44.0,
    "altura_muro_m": 2.8,
    "espesor_muro_m": 0.12,
    "estilo_arquitectura": "Moderna",
    "observaciones": "",
}


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Extrae el primer JSON válido aunque venga dentro de ```json ... ```."""
    candidates = []
    fenced = re.findall(r"```(?:json)?\s*([\s\S]*?)```", text, flags=re.IGNORECASE)
    candidates.extend(fenced)
    candidates.append(text)

    for cand in candidates:
        cand = cand.strip()
        if not cand:
            continue

        start = cand.find("{")
        end = cand.rfind("}")
        if start == -1 or end == -1 or end <= start:
            continue

        try:
            return json.loads(cand[start : end + 1])
        except Exception:
            continue

    return None


def _to_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    """Convierte valores de Gemini a float sin romper si vienen vacíos o como texto."""
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int) -> int:
    """Convierte valores de Gemini a entero con mínimo 1."""
    try:
        return max(1, int(round(float(value))))
    except (TypeError, ValueError):
        return default


def _clamp(value: float, min_value: float, max_value: float) -> float:
    """Mantiene un número dentro de un rango seguro para los inputs de Streamlit."""
    return max(min_value, min(max_value, value))


def parse_text_design_response(raw_text: str) -> Optional[Dict[str, Any]]:
    """
    Normaliza la respuesta IA a los parámetros que ya usa IsoSmart.

    Soporta dos formatos:
    - El formato interno de la app: area_m2, perimetro_m, niveles.
    - El formato del PDF: largo_muros, ancho_muros, niveles.
    """
    data = _extract_json(raw_text)
    if not isinstance(data, dict):
        return None

    params = dict(DEFAULT_TEXT_DESIGN_PARAMS)
    niveles = _to_int(data.get("niveles"), params["niveles"])

    largo = _to_float(data.get("largo_muros"))
    ancho = _to_float(data.get("ancho_muros"))

    area_m2 = _to_float(data.get("area_m2"))
    perimetro_m = _to_float(data.get("perimetro_m"))

    # Si Gemini responde con largo/ancho como pide el PDF, lo convertimos al modelo actual.
    if largo and ancho:
        area_m2 = largo * ancho * niveles
        perimetro_m = 2 * (largo + ancho)

    if area_m2:
        params["area_m2"] = round(_clamp(area_m2, 10.0, 100000.0), 2)
    if perimetro_m:
        params["perimetro_m"] = round(_clamp(perimetro_m, 10.0, 5000.0), 2)

    params["niveles"] = min(20, niveles)
    params["altura_muro_m"] = round(
        _clamp(_to_float(data.get("altura_muro_m"), params["altura_muro_m"]), 2.2, 6.0),
        2,
    )
    params["espesor_muro_m"] = round(
        _clamp(_to_float(data.get("espesor_muro_m"), params["espesor_muro_m"]), 0.08, 0.30),
        2,
    )
    params["estilo_arquitectura"] = str(
        data.get("estilo_arquitectura") or data.get("estilo") or params["estilo_arquitectura"]
    ).strip()
    params["observaciones"] = str(data.get("observaciones") or data.get("notas") or "").strip()

    return params


def build_text_design_prompt(descripcion: str) -> str:
    """Construye el prompt para pedirle a Gemini un JSON limpio y fácil de validar."""
    return f"""
Eres un asistente técnico para presupuestos de viviendas con sistemas EPS/ICF en República Dominicana.

Analiza esta idea del cliente:
\"\"\"{descripcion}\"\"\"

Devuelve SOLO un JSON válido, sin markdown ni explicación adicional, con estas claves:
{{
  "area_m2": number,
  "niveles": integer,
  "perimetro_m": number,
  "altura_muro_m": number,
  "espesor_muro_m": number,
  "estilo_arquitectura": string,
  "observaciones": string
}}

Reglas:
- Si el cliente no da medidas exactas, estima valores residenciales razonables.
- area_m2 debe ser el área total construida, incluyendo todos los niveles.
- perimetro_m debe ser el perímetro aproximado de la planta principal.
- niveles debe estar entre 1 y 20.
- altura_muro_m normalmente debe estar entre 2.6 y 3.2.
- espesor_muro_m normalmente debe estar entre 0.10 y 0.15.
- Usa observaciones para explicar supuestos importantes en una frase corta.
"""


def analyze_text_design_with_gemini(model: Any, descripcion: str) -> Tuple[Optional[Dict[str, Any]], str]:
    """Llama a Gemini y devuelve parámetros normalizados junto con la respuesta cruda."""
    prompt = build_text_design_prompt(descripcion)
    resp = model.generate_content(prompt)
    raw = getattr(resp, "text", "") or ""
    return parse_text_design_response(raw), raw
