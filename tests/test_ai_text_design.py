import sys

sys.path.append(".")

from utils.ai_text_design import (
    DEFAULT_TEXT_DESIGN_PARAMS,
    build_text_design_prompt,
    parse_text_design_response,
)


def test_parse_text_design_response_normalizes_existing_plan_fields():
    """Convierte un JSON de Gemini a parámetros técnicos usados por la app."""
    raw = """
    ```json
    {
      "area_m2": 180,
      "niveles": 2,
      "perimetro_m": 58,
      "altura_muro_m": 3,
      "espesor_muro_m": 0.14,
      "estilo_arquitectura": "moderna tropical",
      "observaciones": "Terraza frontal y ventanales amplios"
    }
    ```
    """

    data = parse_text_design_response(raw)

    assert data["area_m2"] == 180.0
    assert data["niveles"] == 2
    assert data["perimetro_m"] == 58.0
    assert data["altura_muro_m"] == 3.0
    assert data["espesor_muro_m"] == 0.14
    assert data["estilo_arquitectura"] == "moderna tropical"
    assert "Terraza" in data["observaciones"]


def test_parse_text_design_response_maps_largo_ancho_from_pdf_schema():
    """Acepta el esquema del PDF y calcula área/perímetro para Streamlit."""
    raw = '{"largo_muros": 14.5, "ancho_muros": 9, "niveles": 2, "estilo": "Moderna"}'

    data = parse_text_design_response(raw)

    assert data["area_m2"] == 261.0
    assert data["perimetro_m"] == 47.0
    assert data["niveles"] == 2
    assert data["altura_muro_m"] == DEFAULT_TEXT_DESIGN_PARAMS["altura_muro_m"]
    assert data["estilo_arquitectura"] == "Moderna"


def test_parse_text_design_response_returns_none_for_invalid_json():
    """No rompe la interfaz cuando Gemini responde texto no estructurado."""
    assert parse_text_design_response("no hay json aqui") is None


def test_build_text_design_prompt_contains_required_schema_fields():
    """El prompt exige las claves que la app necesita para prellenar formularios."""
    prompt = build_text_design_prompt("Casa moderna de 2 niveles")

    assert "area_m2" in prompt
    assert "perimetro_m" in prompt
    assert "estilo_arquitectura" in prompt
    assert "SOLO un JSON" in prompt


def run_all_tests():
    test_parse_text_design_response_normalizes_existing_plan_fields()
    test_parse_text_design_response_maps_largo_ancho_from_pdf_schema()
    test_parse_text_design_response_returns_none_for_invalid_json()
    test_build_text_design_prompt_contains_required_schema_fields()
    print("Todas las pruebas de Text-to-Design pasaron [OK]")


if __name__ == "__main__":
    run_all_tests()
