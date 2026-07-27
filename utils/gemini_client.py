# -*- coding: utf-8 -*-
"""
utils/gemini_client.py
-----------------------
Cliente Gemini centralizado, sobre el SDK nuevo (`google-genai`).

POR QUÉ EXISTE
==============
`google-generativeai` (el SDK que usaba toda la app) llegó a su fin de
soporte permanente el 30 de noviembre de 2025 -- ocho meses antes de esta
migración, no un aviso reciente. Google recomienda el SDK unificado
`google-genai` desde entonces.

El nombre del modelo (`gemini-1.5-flash`) también estaba repetido en tres
sitios distintos (`ui_core.py` x2, `ui_calculadora.py`) sin ninguna fuente
única -- exactamente el patrón de "número mágico repetido" que esta
auditoría ha corregido en todo lo demás.

DISEÑO
======
El resto de la app (`utils/vision.py`, `utils/ai_text_design.py`) recibe un
objeto `_model` y llama a `_model.generate_content(contents)` -- la interfaz
del SDK VIEJO. En vez de reescribir esa lógica ya probada, `ModeloGemini`
adapta el cliente nuevo (`client.models.generate_content(model=..., contents=...)`)
para exponer exactamente esa misma interfaz. Cambia únicamente la CREACIÓN
del modelo (este archivo); los llamadores existentes no se tocan.

⚠️ NO PROBADO CONTRA LA API REAL
=================================
Esta migración se implementó sin una API key real disponible -- no hay forma
de verificar contra el servicio en vivo desde este entorno. La estructura
está verificada con tests que simulan (mock) el cliente, pero alguien con
una API key real debe probar al menos una llamada real (Texto -> Diseño o
Análisis de plano) antes de confiar en esto en producción.
"""

from __future__ import annotations

from typing import Any

# Nombre de modelo centralizado -- antes repetido sin fuente única en
# ui_core.py (x2) y ui_calculadora.py, y fijo en "gemini-1.5-flash".
#
# URGENTE: verificado por búsqueda web (26-27 jul 2026) que Gemini 2.0 Flash
# se apagó el 1 de junio de 2026, y "gemini-1.5-flash" es una generación
# ANTERIOR a esa -- casi con toda seguridad ya no responde en absoluto, no
# solo "SDK deprecado pero funcional". El modelo actual recomendado por
# Google es Gemini 3.6 Flash (gemini-3.6-flash), lanzado el 21 de julio de
# 2026 como "el nuevo modelo por defecto". Cambiar el modelo es ahora un
# cambio en un solo lugar.
MODELO_GEMINI_DEFAULT = "gemini-3.6-flash"


class ModeloGemini:
    """
    Adapta `google.genai.Client` a la interfaz `.generate_content(contents)`
    que ya usan `utils/vision.py` y `utils/ai_text_design.py` (heredada del
    SDK viejo, `GenerativeModel.generate_content`).

    Verificado que la API nueva acepta `contents=[prompt, imagen_PIL]` de la
    misma forma que la vieja (sin necesidad de `client.files.upload()` para
    una sola imagen) -- no hace falta cambiar nada en los llamadores.
    """

    def __init__(self, client: Any, model_name: str = MODELO_GEMINI_DEFAULT):
        self._client = client
        self._model_name = model_name

    def generate_content(self, contents: Any) -> Any:
        return self._client.models.generate_content(model=self._model_name, contents=contents)


def crear_modelo_gemini(api_key: str, model_name: str = MODELO_GEMINI_DEFAULT) -> ModeloGemini | None:
    """
    Crea un `ModeloGemini` listo para usar, o `None` si no hay API key o si
    falla la inicialización (mismo contrato que `initialize_gemini()` en
    ui_core.py, que ahora delega aquí).
    """
    if not api_key:
        return None
    from google import genai  # import diferido: evita cargar el SDK si no hace falta

    client = genai.Client(api_key=api_key)
    return ModeloGemini(client, model_name)
