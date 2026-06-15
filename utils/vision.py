# -*- coding: utf-8 -*-
"""
utils/vision.py
---------------
Capa de Visión Artificial para IsoSmart Titanium.

Módulo de prompts optimizados para procesar esquemas arquitectónicos
mediante modelos masivos de lenguaje con visión (Gemini 1.5 Flash).

Convierte imágenes de planos en datos JSON estructurados listos para
los módulos de cálculo y presupuesto.
"""

import json


# ============================================================================
# EXTRACTOR MULTIMODAL (GEMINI IA)
# ============================================================================

def analyze_plan_image_with_gemini(model, image_pil):
    """
    Fuerza a Gemini a comportarse como un transcriptor geométrico puro,
    evitando alucinaciones textuales no deseadas.

    Args:
        model: Instancia del modelo Gemini con capacidad de visión.
        image_pil: Imagen PIL del plano arquitectónico a analizar.

    Returns:
        tuple: (dict_datos | None, texto_respuesta_completa)
            - dict_datos: Diccionario con las dimensiones extraídas o None si falla.
            - texto_respuesta: Texto completo devuelto por la IA.
    """
    prompt = """
    Eres un ingeniero estructural experto en sistemas de paneles EPS. Analiza este plano arquitectónico.
    Debes extraer las siguientes dimensiones métricas explícitas. Si una dimensión no es visible en el plano,
    deja el valor como null en el JSON. No inventes aproximaciones si no hay una escala clara.

    Devuelve ÚNICAMENTE un objeto JSON válido al final de tu respuesta con este formato exacto:
    {
      "area_m2": float_o_null,
      "perimetro_m": float_o_null,
      "niveles": int_o_null,
      "altura_muro_m": float_o_null,
      "espesor_muro_m": float_o_null
    }
    """
    try:
        response = model.generate_content([prompt, image_pil])
        text_response = response.text

        # Buscar el bloque JSON en la respuesta de la IA
        start = text_response.find("{")
        end = text_response.rfind("}") + 1
        if start != -1 and end != -1:
            json_str = text_response[start:end]
            return json.loads(json_str), text_response
        return None, text_response
    except Exception as e:
        return None, f"Error en API Gemini: {str(e)}"
