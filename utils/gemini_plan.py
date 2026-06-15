# -*- coding: utf-8 -*-
"""
utils/gemini_plan.py
--------------------
MÓDULO DE COMPATIBILIDAD — re-exporta desde utils/vision.py.

La lógica real vive en utils/vision.py (fuente única).
Este archivo existe solo para no romper imports anteriores.

    from utils.gemini_plan import analyze_plan_image_with_gemini  ← sigue funcionando
"""

from utils.vision import (       # noqa: F401  (re-exportación intencional)
    PlanParams,
    _extract_json,
    analyze_plan_image_with_gemini,
)

__all__ = ["PlanParams", "_extract_json", "analyze_plan_image_with_gemini"]
