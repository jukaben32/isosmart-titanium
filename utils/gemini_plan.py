from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from PIL import Image


@dataclass(frozen=True)
class PlanParams:
    area_m2: float
    niveles: int
    perimetro_m: float
    altura_muro_m: float
    espesor_muro_m: float
    sistema_cerramiento: str  # "EPS" | "ICF" | "N/A"
    notas: str = ""


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    # Intenta extraer el primer bloque JSON válido que aparezca en el texto.
    # Gemini a veces envuelve JSON en ```json ... ```
    candidates = []
    fenced = re.findall(r"```(?:json)?\s*([\s\S]*?)```", text, flags=re.IGNORECASE)
    candidates.extend(fenced)
    candidates.append(text)

    for cand in candidates:
        cand = cand.strip()
        if not cand:
            continue
        # Busca una llave inicial/final para recortar si viene con texto adicional
        start = cand.find("{")
        end = cand.rfind("}")
        if start == -1 or end == -1 or end <= start:
            continue
        snippet = cand[start : end + 1]
        try:
            return json.loads(snippet)
        except Exception:
            continue
    return None


def analyze_plan_image_with_gemini(
    model: Any,
    image: Image.Image,
) -> Tuple[Optional[Dict[str, Any]], str]:
    """
    Devuelve (data, raw_text).

    data intenta ser un JSON con parámetros del plano. raw_text conserva la respuesta completa.
    """
    prompt = """
Eres un asistente de ingeniería y presupuestos. Analiza el plano (imagen) y devuelve SOLO un JSON válido
con estas claves (si no puedes inferir algo, pon null):

{
  "area_m2": number|null,
  "niveles": integer|null,
  "perimetro_m": number|null,
  "altura_muro_m": number|null,
  "espesor_muro_m": number|null,
  "observaciones": string|null
}

Reglas:
- No inventes valores con falsa precisión. Si no es visible, usa null.
- Si hay cota de escala o dimensiones, úsala; si no, asume que NO hay escala y marca null.
"""
    resp = model.generate_content([prompt, image])
    raw = getattr(resp, "text", "") or ""
    data = _extract_json(raw)
    return data, raw

