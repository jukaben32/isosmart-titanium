from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional, Tuple

import streamlit as st

DEFAULT_TEXT_DESIGN_PARAMS: dict[str, Any] = {
    "area_m2": 120.0,
    "niveles": 1,
    "perimetro_m": 44.0,
    "altura_muro_m": 2.8,
    "espesor_muro_m": 0.12,
    "calidad_terminados": "media",
    "estilo_arquitectura": "",
    "observaciones": "",
}


def _extract_json(text: str) -> dict[str, Any] | None:
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


def _to_float(value: Any, default: float | None = None) -> float | None:
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


def parse_text_design_response(raw_text: str) -> dict[str, Any] | None:
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
    params["calidad_terminados"] = str(
        data.get("calidad_terminados") or params.get("calidad_terminados", "media")
    ).strip().lower()
    
    if params["calidad_terminados"] not in ["economica", "media", "alta", "lujo"]:
        params["calidad_terminados"] = "media"
        
    # El test tests/test_ai_text_design.py ya esperaba este campo (y fallaba con
    # KeyError desde hacía tiempo). Es útil además para alimentar el prompt del
    # render de fachada en Fal.ai, así que se implementa en vez de borrar el test.
    params["estilo_arquitectura"] = str(
        data.get("estilo_arquitectura") or data.get("estilo") or ""
    ).strip()

    params["observaciones"] = str(data.get("observaciones") or data.get("notas") or "").strip()

    return params


def build_text_design_prompt(descripcion: str) -> str:
    """Construye el prompt para pedirle a Gemini un JSON limpio y fácil de validar."""
    return f"""
Eres un ingeniero civil experto en optimización de planos y cubicación para el contexto de la República Dominicana.
Tu tarea es analizar la descripción en lenguaje natural dada por el usuario y extraer un objeto JSON estricto.

Analiza esta idea del cliente:
\"\"\"{descripcion}\"\"\"

Debes clasificar el proyecto dentro de una de las siguientes calidades de acabados ("economica", "media", "alta", "lujo")
siguiendo estas reglas de negocio dominicanas:
- Si el usuario menciona marquesinas simples, optimización de áreas o metrajes ajustados, clasifica como "economica".
- Si describe marquesinas dobles, estar familiar o 2.5 baños, clasifica como "media".
- Si describe cocinas frías/calientes, terrazas extensas, habitaciones con baños independientes o ubicaciones premium (Samaná, zonas turísticas de alta gama), clasifica como "alta" o "lujo".

El JSON de salida debe tener obligatoriamente esta estructura:
{{
  "area_m2": float,
  "niveles": int,
  "perimetro_m": float,
  "altura_muro_m": float,
  "espesor_muro_m": float,
  "calidad_terminados": "economica" | "media" | "alta" | "lujo",
  "estilo_arquitectura": string,
  "observaciones": string
}}

Reglas adicionales:
- Si el cliente no da medidas exactas, estima valores residenciales razonables.
- area_m2 debe ser el área total construida, incluyendo todos los niveles.
- perimetro_m debe ser el perímetro aproximado de la planta principal.
- niveles debe estar entre 1 y 20.
- altura_muro_m normalmente debe estar entre 2.6 y 3.2.
- espesor_muro_m normalmente debe estar entre 0.10 y 0.15.
- Usa observaciones para explicar supuestos importantes en una frase corta.

Responde SOLO un JSON válido, sin texto antes ni después y sin bloques de código.
"""


@st.cache_data(show_spinner=False, ttl=3600, hash_funcs={object: lambda _: "modelo_gemini"})
def analyze_text_design_with_gemini(_model: Any, descripcion: str) -> tuple[dict[str, Any] | None, str]:
    """
    Llama a Gemini y devuelve parámetros normalizados junto con la respuesta cruda.

    La llamada de red va envuelta en try/except: antes, un fallo de red o una
    cuota agotada mostraba el traceback crudo de Streamlit al cliente.
    """
    prompt = build_text_design_prompt(descripcion)
    try:
        resp = _model.generate_content(prompt)
    except Exception as exc:                       # red, cuota, API caída
        return None, f"[error] No se pudo consultar Gemini: {exc}"
    raw = getattr(resp, "text", "") or ""
    return parse_text_design_response(raw), raw
