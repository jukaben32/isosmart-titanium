import json
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


# ===========================================================================
# Programa de ambientes (asistente Texto -> Diseño para captura de leads)
# ===========================================================================

def test_parser_extrae_programa_de_ambientes():
    """
    Antes: el parser solo extraía dimensiones agregadas (área, perímetro).
    Un lead que describe '3 dormitorios, 2 con baño' necesita que eso se
    capture como programa real, no se pierda en un área genérica.
    """
    respuesta = json.dumps({
        "area_m2": 165, "niveles": 2, "perimetro_m": 52,
        "dormitorios": 3, "dormitorios_con_bano": 2, "banos_comunes": 1,
        "tiene_cocina": True, "tiene_sala_estar": True, "tiene_comedor": True,
        "tiene_terraza_lavadero": True, "marquesina_autos": 2,
        "ambientes_adicionales": ["estudio"],
        "habitaciones": [
            {"tipo": "dormitorio", "nombre": "Dormitorio 1", "area_aprox_m2": 16},
        ],
    })
    params = parse_text_design_response(respuesta)

    assert params["dormitorios"] == 3
    assert params["dormitorios_con_bano"] == 2
    assert params["banos_comunes"] == 1
    assert params["marquesina_autos"] == 2
    assert params["ambientes_adicionales"] == ["estudio"]
    assert len(params["habitaciones"]) == 1
    assert params["habitaciones"][0]["nombre"] == "Dormitorio 1"


def test_parser_corrige_dormitorios_con_bano_inconsistente():
    """
    Defensivo: si el LLM alucina más baños privados que dormitorios totales
    (inconsistencia física imposible), se recorta en vez de propagar el error.
    """
    respuesta = json.dumps({"dormitorios": 2, "dormitorios_con_bano": 5})
    params = parse_text_design_response(respuesta)
    assert params["dormitorios_con_bano"] <= params["dormitorios"]


def test_parser_sin_programa_de_ambientes_no_revienta():
    """Retrocompatibilidad: una respuesta antigua (sin estos campos) sigue funcionando."""
    respuesta = json.dumps({"area_m2": 120, "niveles": 1, "perimetro_m": 44})
    params = parse_text_design_response(respuesta)
    assert params["dormitorios"] is None
    assert params["habitaciones"] == []
    assert params["marquesina_autos"] == 0


def test_parser_ignora_habitaciones_mal_formadas():
    """Un elemento de la lista que no es un dict no debe romper el parseo."""
    respuesta = json.dumps({"habitaciones": ["no es un dict", {"tipo": "sala", "nombre": "Sala"}]})
    params = parse_text_design_response(respuesta)
    assert len(params["habitaciones"]) == 1
    assert params["habitaciones"][0]["nombre"] == "Sala"


def test_prompt_pide_el_programa_de_ambientes():
    prompt = build_text_design_prompt("una casa cualquiera")
    assert "dormitorios_con_bano" in prompt
    assert "habitaciones" in prompt
    assert "marquesina_autos" in prompt
