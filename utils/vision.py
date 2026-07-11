# -*- coding: utf-8 -*-
"""
utils/vision.py
---------------
Capa de Visión Artificial para IsoSmart Titanium.  FUENTE ÚNICA.

Módulo consolidado que reemplaza utils/gemini_plan.py como punto de
entrada para todo análisis multimodal de planos arquitectónicos con
Gemini.  gemini_plan.py re-exporta desde aquí para mantener
compatibilidad con imports existentes.

Incluye:
    - PlanParams          : dataclass con los campos del plano
    - analyze_plan_image_with_gemini() : extractor principal (imagen)
    - _extract_json()     : parser JSON robusto (soporta bloques ```json```)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from PIL import Image


# ============================================================================
# MODELO DE DATOS
# ============================================================================

@dataclass(frozen=True)
class PlanParams:
    """Parámetros geométricos extraídos de un plano arquitectónico."""
    area_m2:            float
    niveles:            int
    perimetro_m:        float
    altura_muro_m:      float
    espesor_muro_m:     float
    sistema_cerramiento: str   # "EPS" | "ICF" | "N/A"
    notas:              str = ""


# ============================================================================
# PARSER JSON ROBUSTO
# ============================================================================

def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    """
    Extrae el primer bloque JSON válido de la respuesta de Gemini.
    Soporta respuestas con bloques ```json ... ``` y texto adicional.
    """
    candidates = []

    # 1. Bloques delimitados con comillas de código (Gemini los usa frecuentemente)
    fenced = re.findall(r"```(?:json)?\s*([\s\S]*?)```", text, flags=re.IGNORECASE)
    candidates.extend(fenced)

    # 2. Texto completo como fallback
    candidates.append(text)

    for cand in candidates:
        cand = cand.strip()
        if not cand:
            continue
        start = cand.find("{")
        end   = cand.rfind("}")
        if start == -1 or end == -1 or end <= start:
            continue
        snippet = cand[start : end + 1]
        try:
            return json.loads(snippet)
        except Exception:
            continue
    return None


# ============================================================================
import streamlit as st


@st.cache_data(show_spinner=False, hash_funcs={
    object: lambda _: "modelo_gemini",
    Image.Image: lambda img: img.tobytes(),
})
def analyze_plan_image_with_gemini(
    model: Any,
    image: Image.Image,
) -> Tuple[Optional[Dict[str, Any]], str]:
    """
    Fuerza a Gemini a comportarse como un transcriptor geométrico puro,
    evitando alucinaciones textuales no deseadas.

    Ingeniería del prompt optimizada para:
      - Sistemas de paneles EPS (Isotex / ICF)
      - Clima y normativa de República Dominicana
      - Rechazo explícito de valores inventados

    Args:
        model: Instancia del modelo Gemini con capacidad de visión.
        image: Imagen PIL del plano arquitectónico a analizar.

    Returns:
        tuple: (dict_datos | None, texto_respuesta_completa)
            - dict_datos : dimensiones extraídas o None si falla el parseo.
            - raw_text   : texto completo devuelto por la IA (para depuración).
    """
    prompt = """
Eres un ingeniero estructural experto en sistemas de paneles EPS (Isotex e ICF)
para construcción en República Dominicana.  Analiza este plano arquitectónico.

Extrae ÚNICAMENTE las dimensiones métricas que sean explícitamente visibles.
Si una dimensión no aparece con claridad, devuelve null — nunca inventes valores.

Devuelve SOLO un objeto JSON válido con este formato exacto:
{
  "area_m2":        <número o null>,
  "perimetro_m":    <número o null>,
  "niveles":        <entero o null>,
  "altura_muro_m":  <número o null>,
  "espesor_muro_m": <número o null>,
  "observaciones":  <string o null>
}

Reglas estrictas:
- No inventes valores con falsa precisión.
- Si hay cota de escala o dimensiones, úsalas; si no, marca null.
- Responde SOLO con el JSON, sin texto adicional antes ni después.
"""
    resp = model.generate_content([prompt, image])
    raw  = getattr(resp, "text", "") or ""
    data = _extract_json(raw)
    return data, raw
