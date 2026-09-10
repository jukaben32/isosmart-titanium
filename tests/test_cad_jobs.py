import sys

import pytest

sys.path.insert(0, ".")

from utils.cad_jobs import (  # noqa: E402
    LAYERS_CAD_BASE,
    actualizar_cad_job,
    brief_para_ocs_markdown,
    construir_brief_cad,
    crear_cad_job,
    listar_cad_jobs,
    obtener_cad_job,
)
from utils.energia import AnalisisEnergetico  # noqa: E402
from utils.estado import ProyectoState  # noqa: E402


def test_crear_cad_job_guarda_brief_con_layers_y_solar(tmp_path):
    estado = ProyectoState(area_m2=180, niveles=2, n_dormitorios=3, n_banos=3)
    estado.habitaciones = [{"tipo": "dormitorio", "nombre": "Dormitorio 1", "area_aprox_m2": 14}]
    solar = AnalisisEnergetico.calcular_sistema_solar_recomendado(180)

    job = crear_cad_job("Casa moderna ecológica de dos niveles", estado, solar=solar, cola_dir=tmp_path)
    guardado = obtener_cad_job(job["id"], cola_dir=tmp_path)

    assert guardado is not None
    assert guardado["status"] == "pendiente_ocs"
    assert "I-SOLAR-PANELES" in guardado["brief"]["layers_requeridos"]
    assert "I-HIDRAULICA-AGUA-FRIA" in guardado["brief"]["layers_requeridos"]
    assert guardado["brief"]["sistema_solar"]["paneles_necesarios"] == solar["paneles_necesarios"]
    assert len(listar_cad_jobs(tmp_path)) == 1


def test_actualizar_cad_job_valida_estado(tmp_path):
    estado = ProyectoState(area_m2=120)
    job = crear_cad_job("Casa compacta con paneles solares", estado, cola_dir=tmp_path)

    actualizado = actualizar_cad_job(job["id"], {"status": "procesando"}, cola_dir=tmp_path)
    assert actualizado["status"] == "procesando"

    with pytest.raises(ValueError, match="Estado CAD"):
        actualizar_cad_job(job["id"], {"status": "inventado"}, cola_dir=tmp_path)


def test_brief_para_ocs_markdown_incluye_entregables():
    brief = construir_brief_cad(
        "Vivienda eco con tres habitaciones",
        {"area_m2": 140, "niveles": 1, "habitaciones": []},
        solar={"paneles_necesarios": 6, "previsiones_electricas": ["Canalización DC"]},
    )
    job = {"id": "abc123", "brief": brief}
    md = brief_para_ocs_markdown(job)

    assert "Trabajo CAD abc123" in md
    assert "planta_solar_fotovoltaica.dxf" in md
    assert "Canalización DC" in md
    assert set(["I-SOLAR-DC", "I-ELECTRICA-TABLERO"]).issubset(set(LAYERS_CAD_BASE))
