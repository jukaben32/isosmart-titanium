# -*- coding: utf-8 -*-
"""
Tests de utils/gemini_client.py -- la migración del SDK de Gemini.

CONTEXTO: `google-generativeai` (el SDK viejo) llegó a su fin de soporte
permanente el 30 de noviembre de 2025. El modelo que usaba toda la app
("gemini-1.5-flash") es de una generación anterior a Gemini 2.0 Flash, que a
su vez se apagó el 1 de junio de 2026 -- con alta probabilidad las llamadas
a Gemini de la app en producción ya no respondían en absoluto antes de esta
migración.

⚠️ Estos tests verifican la ESTRUCTURA de la migración (qué se llama, con
qué argumentos, que la respuesta se pasa correctamente) usando un cliente
simulado -- no hay forma de probar contra la API real de Gemini desde este
entorno, sin una API key. Alguien con una API key real debe verificar al
menos una llamada real (Texto -> Diseño o Análisis de plano) antes de
confiar en esto en producción.

    pytest tests/test_gemini_client.py
"""

import sys

sys.path.insert(0, ".")

from utils.gemini_client import (  # noqa: E402
    MODELO_GEMINI_DEFAULT,
    ModeloGemini,
    crear_modelo_gemini,
)


class _ClienteFalso:
    """
    Simula `google.genai.Client` lo justo para verificar que `ModeloGemini`
    llama `client.models.generate_content(model=..., contents=...)` con los
    argumentos correctos -- la forma exacta documentada por Google para el
    SDK nuevo, verificada por búsqueda web antes de implementar la migración.
    """

    def __init__(self):
        self.llamadas = []
        self.models = self  # el SDK real expone .models.generate_content

    def generate_content(self, model, contents):
        self.llamadas.append({"model": model, "contents": contents})
        return f"respuesta simulada para: {contents!r}"


def test_modelo_gemini_delega_al_cliente_con_el_nombre_correcto():
    """
    Verificado contra la documentación del SDK nuevo (ai.google.dev/gemini-api/docs/migrate):
    `client.models.generate_content(model=nombre, contents=...)`, no
    `model.generate_content(...)` como en el SDK viejo.
    """
    cliente = _ClienteFalso()
    modelo = ModeloGemini(cliente, model_name="gemini-3.6-flash")

    resultado = modelo.generate_content("hola")

    assert len(cliente.llamadas) == 1
    assert cliente.llamadas[0]["model"] == "gemini-3.6-flash"
    assert cliente.llamadas[0]["contents"] == "hola"
    assert "respuesta simulada" in resultado


def test_modelo_gemini_preserva_la_interfaz_generate_content():
    """
    Diseño central de la migración: `utils/vision.py` y
    `utils/ai_text_design.py` llaman `_model.generate_content(contents)` --
    la interfaz del SDK VIEJO. `ModeloGemini` debe exponer exactamente esa
    misma interfaz para que esos llamadores no necesiten cambiar.
    """
    modelo = ModeloGemini(_ClienteFalso())
    assert hasattr(modelo, "generate_content")
    assert callable(modelo.generate_content)


def test_modelo_gemini_acepta_contenido_multimodal_como_lista():
    """
    Verificado contra la documentación (ai.google.dev/api/generate-content):
    `contents=[prompt, imagen_PIL]` funciona igual en el SDK nuevo que en el
    viejo -- sin necesidad de `client.files.upload()` para una sola imagen.
    Esto es lo que usa utils/vision.py para analizar planos.
    """
    cliente = _ClienteFalso()
    modelo = ModeloGemini(cliente)

    contenido_multimodal = ["Describe este plano", "objeto-imagen-simulado"]
    modelo.generate_content(contenido_multimodal)

    assert cliente.llamadas[0]["contents"] == contenido_multimodal


def test_crear_modelo_gemini_sin_api_key_devuelve_none():
    """Mismo contrato que la función anterior (`initialize_gemini`): sin key, None."""
    assert crear_modelo_gemini("") is None
    assert crear_modelo_gemini(None) is None


def test_modelo_por_defecto_no_es_una_generacion_apagada():
    """
    "gemini-1.5-flash" (el modelo anterior) es de una generación previa a
    Gemini 2.0 Flash, que se apagó el 1 de junio de 2026 -- con alta
    probabilidad ya no respondía. El modelo por defecto no debe ser ninguna
    de las variantes de generación 1.x o 2.0 conocidas como apagadas.
    """
    assert not MODELO_GEMINI_DEFAULT.startswith("gemini-1.")
    assert MODELO_GEMINI_DEFAULT != "gemini-2.0-flash"
    assert MODELO_GEMINI_DEFAULT != "gemini-2.0-flash-lite"


def test_nombre_de_modelo_centralizado_en_un_solo_lugar():
    """
    Antes: "gemini-1.5-flash" estaba repetido sin fuente única en
    ui_core.py (x2) y ui_calculadora.py. Verifica que ya no hay ningún
    nombre de modelo hardcodeado fuera de este módulo (los comentarios que
    mencionan el modelo viejo como contexto histórico no cuentan).
    """
    from pathlib import Path

    for archivo in ("ui_core.py", "ui_calculadora.py"):
        codigo = Path(archivo).read_text(encoding="utf-8")
        cuerpo = "\n".join(ln for ln in codigo.splitlines() if not ln.strip().startswith("#"))
        assert "gemini-1.5-flash" not in cuerpo, f"{archivo} sigue con el modelo apagado"
        assert 'GenerativeModel("gemini' not in cuerpo
        assert "GenerativeModel('gemini" not in cuerpo
