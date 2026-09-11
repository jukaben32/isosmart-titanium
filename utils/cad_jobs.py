"""
utils/cad_jobs.py
-----------------
Cola simple de trabajos CAD para conectar la idea del usuario con un worker OCS.

Streamlit Cloud no puede controlar directamente Open CAD Studio en la PC del
usuario. Esta cola crea una orden estructurada que un proceso local puede tomar
y convertir en plano DXF/PDF/ZIP usando OCS.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .estado import ProyectoState
from .repositorio import leer_config_supabase
from .storage import read_json, write_json_atomic

DEFAULT_CAD_QUEUE_DIR = Path("data") / "cad_jobs"

ESTADOS_CAD = {
    "pendiente_ocs",
    "procesando",
    "listo_para_ocs",
    "generado",
    "error",
}

LAYERS_CAD_BASE = [
    "A-MUROS",
    "A-PUERTAS",
    "A-VENTANAS",
    "A-MOBILIARIO",
    "A-TEXTOS",
    "S-CIMENTACION",
    "S-MUROS-EPS",
    "S-LOSAS",
    "I-ELECTRICA-ILUMINACION",
    "I-ELECTRICA-TOMAS",
    "I-ELECTRICA-TABLERO",
    "I-HIDRAULICA-AGUA-FRIA",
    "I-HIDRAULICA-AGUA-CALIENTE",
    "I-SANITARIA-DRENAJE",
    "I-SOLAR-PANELES",
    "I-SOLAR-DC",
    "I-SOLAR-AC",
    "I-SOLAR-BATERIAS",
    "I-DATOS",
    "I-CLIMATIZACION",
    "L-JARDINERIA",
    "L-ILUMINACION-EXTERIOR",
]


def _ahora_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _ruta_job(job_id: str, cola_dir: str | Path = DEFAULT_CAD_QUEUE_DIR) -> Path:
    return Path(cola_dir) / f"{job_id}.json"


def _usar_supabase(cola_dir: str | Path) -> bool:
    """Usa Supabase solo para la cola por defecto; tests pueden pasar tmp_path."""
    return Path(cola_dir) == DEFAULT_CAD_QUEUE_DIR and leer_config_supabase() is not None


def _headers_supabase(config: dict[str, str]) -> dict[str, str]:
    key = config.get("service_role_key") or config.get("anon_key") or ""
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _crear_cad_job_supabase(job: dict[str, Any]) -> dict[str, Any]:
    import requests

    config = leer_config_supabase()
    if not config:
        raise RuntimeError("Supabase no está configurado")
    resp = requests.post(
        f"{config['url'].rstrip('/')}/rest/v1/cad_jobs",
        headers=_headers_supabase(config),
        json=job,
        timeout=10,
    )
    resp.raise_for_status()
    return job


def _obtener_cad_job_supabase(job_id: str) -> dict[str, Any] | None:
    import requests

    config = leer_config_supabase()
    if not config:
        return None
    resp = requests.get(
        f"{config['url'].rstrip('/')}/rest/v1/cad_jobs",
        headers=_headers_supabase(config),
        params={"select": "*", "id": f"eq.{job_id}", "limit": "1"},
        timeout=10,
    )
    resp.raise_for_status()
    filas = resp.json()
    return filas[0] if filas else None


def _listar_cad_jobs_supabase(limite: int = 20) -> list[dict[str, Any]]:
    import requests

    config = leer_config_supabase()
    if not config:
        return []
    resp = requests.get(
        f"{config['url'].rstrip('/')}/rest/v1/cad_jobs",
        headers=_headers_supabase(config),
        params={"select": "*", "order": "created_at.desc", "limit": str(limite)},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def _actualizar_cad_job_supabase(job_id: str, cambios: dict[str, Any]) -> dict[str, Any]:
    import requests

    config = leer_config_supabase()
    if not config:
        raise RuntimeError("Supabase no está configurado")
    resp = requests.patch(
        f"{config['url'].rstrip('/')}/rest/v1/cad_jobs",
        headers=_headers_supabase(config),
        params={"id": f"eq.{job_id}"},
        json={**cambios, "updated_at": _ahora_iso()},
        timeout=10,
    )
    resp.raise_for_status()
    job = _obtener_cad_job_supabase(job_id)
    if not job:
        raise FileNotFoundError(f"No existe el job CAD {job_id}")
    return job


def estado_a_payload(estado: ProyectoState) -> dict[str, Any]:
    """Convierte ProyectoState en un payload estable para el worker CAD."""
    return {
        "area_m2": estado.area_m2,
        "niveles": estado.niveles,
        "perimetro_m": estado.perimetro_m,
        "altura_muro_m": estado.altura_muro_m,
        "espesor_muro_m": estado.espesor_muro_m,
        "sistema": estado.sistema,
        "calidad": estado.calidad,
        "zona_riesgo": estado.zona_riesgo,
        "dormitorios": estado.n_dormitorios,
        "banos": estado.n_banos,
        "puertas_interiores": estado.n_puertas_interiores,
        "puertas_exteriores": estado.n_puertas_exteriores,
        "ventanas": estado.n_ventanas,
        "ml_cocina": estado.ml_cocina,
        "habitaciones": estado.habitaciones,
    }


def construir_brief_cad(
    descripcion: str,
    proyecto: dict[str, Any],
    solar: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Construye el brief técnico que viajará al worker OCS.

    El brief no intenta ser plano final; es la especificación inicial para que
    el agente CAD genere una planta tentativa con layers e instalaciones.
    """
    habitaciones = proyecto.get("habitaciones") or []
    solar = solar or {}
    return {
        "tipo": "vivienda_ecologica_eps",
        "descripcion_usuario": descripcion.strip(),
        "objetivo": "plano_tentativo_cad_con_layers",
        "proyecto": proyecto,
        "habitaciones": habitaciones,
        "sistema_solar": {
            "activo": bool(solar),
            "paneles_necesarios": solar.get("paneles_necesarios"),
            "potencia_panel_w": solar.get("potencia_panel_w"),
            "capacidad_sistema_kw": solar.get("capacidad_sistema_kw"),
            "inversor_kw": solar.get("inversor_kw"),
            "baterias_necesarias": solar.get("baterias_necesarias"),
            "banco_baterias_kwh": solar.get("banco_baterias_kwh"),
            "area_techo_requerida_m2": solar.get("area_techo_requerida_m2"),
            "previsiones_electricas": solar.get("previsiones_electricas", []),
        },
        "layers_requeridos": list(LAYERS_CAD_BASE),
        "entregables": [
            "planta_arquitectonica_tentativa.dxf",
            "planta_instalaciones_electricas.dxf",
            "planta_hidrosanitaria.dxf",
            "planta_solar_fotovoltaica.dxf",
            "paquete_planos.zip",
        ],
        "criterios_diseno": [
            "Separar zona social, zona privada y servicios.",
            "Reservar cuarto tecnico para inversor, baterias y tablero solar.",
            "Prever ducto/canalizacion vertical para DC solar desde techo.",
            "Ubicar tablero principal en punto accesible y ventilado.",
            "Dejar recorridos hidrosanitarios cortos hacia baños, cocina y lavado.",
            "Usar fachada moderna de lujo como intención estética.",
        ],
    }


def crear_cad_job(
    descripcion: str,
    estado: ProyectoState,
    solar: dict[str, Any] | None = None,
    cola_dir: str | Path = DEFAULT_CAD_QUEUE_DIR,
) -> dict[str, Any]:
    """Crea y guarda una orden CAD pendiente para el worker local."""
    if not descripcion.strip():
        raise ValueError("descripcion no puede estar vacía")

    job_id = uuid4().hex[:12]
    ahora = _ahora_iso()
    proyecto = estado_a_payload(estado)
    brief = construir_brief_cad(descripcion, proyecto, solar=solar)
    job = {
        "id": job_id,
        "status": "pendiente_ocs",
        "created_at": ahora,
        "updated_at": ahora,
        "descripcion": descripcion.strip(),
        "brief": brief,
        "resultado": {},
        "error": "",
    }
    if _usar_supabase(cola_dir):
        return _crear_cad_job_supabase(job)
    write_json_atomic(str(_ruta_job(job_id, cola_dir)), job)
    return job


def obtener_cad_job(job_id: str, cola_dir: str | Path = DEFAULT_CAD_QUEUE_DIR) -> dict[str, Any] | None:
    """Lee un job por id."""
    if _usar_supabase(cola_dir):
        return _obtener_cad_job_supabase(job_id)
    ruta = _ruta_job(job_id, cola_dir)
    job = read_json(str(ruta), None)
    return job if isinstance(job, dict) else None


def listar_cad_jobs(cola_dir: str | Path = DEFAULT_CAD_QUEUE_DIR, limite: int = 20) -> list[dict[str, Any]]:
    """Lista los jobs más recientes."""
    if _usar_supabase(cola_dir):
        return _listar_cad_jobs_supabase(limite)
    ruta = Path(cola_dir)
    if not ruta.exists():
        return []
    jobs = []
    for archivo in ruta.glob("*.json"):
        job = read_json(str(archivo), None)
        if isinstance(job, dict):
            jobs.append(job)
    jobs.sort(key=lambda j: j.get("created_at", ""), reverse=True)
    return jobs[:limite]


def actualizar_cad_job(
    job_id: str,
    cambios: dict[str, Any],
    cola_dir: str | Path = DEFAULT_CAD_QUEUE_DIR,
) -> dict[str, Any]:
    """Actualiza un job existente conservando sus campos previos."""
    job = obtener_cad_job(job_id, cola_dir)
    if not job:
        raise FileNotFoundError(f"No existe el job CAD {job_id}")
    status = cambios.get("status")
    if status and status not in ESTADOS_CAD:
        raise ValueError(f"Estado CAD inválido: {status}")
    if _usar_supabase(cola_dir):
        return _actualizar_cad_job_supabase(job_id, cambios)
    job.update(cambios)
    job["updated_at"] = _ahora_iso()
    write_json_atomic(str(_ruta_job(job_id, cola_dir)), job)
    return job


def brief_para_ocs_markdown(job: dict[str, Any]) -> str:
    """Genera una guía legible para que el worker/agente CAD ejecute en OCS."""
    brief = job["brief"]
    layers = "\n".join(f"- {layer}" for layer in brief["layers_requeridos"])
    ambientes = "\n".join(
        f"- {h.get('nombre', 'Ambiente')}: {h.get('area_aprox_m2', '?')} m²"
        for h in brief.get("habitaciones", [])
    ) or "- Sin ambientes detallados"
    solar = brief.get("sistema_solar", {})
    previsiones = "\n".join(f"- {p}" for p in solar.get("previsiones_electricas", [])) or "- No aplica"
    return f"""# Trabajo CAD {job['id']}

## Idea del usuario
{brief['descripcion_usuario']}

## Proyecto
{brief['proyecto']}

## Ambientes
{ambientes}

## Layers requeridos
{layers}

## Sistema solar
- Paneles: {solar.get('paneles_necesarios')}
- Potencia panel: {solar.get('potencia_panel_w')} W
- Capacidad: {solar.get('capacidad_sistema_kw')} kW
- Inversor: {solar.get('inversor_kw')} kW
- Baterías: {solar.get('baterias_necesarias')}
- Área de techo requerida: {solar.get('area_techo_requerida_m2')} m²

## Previsiones eléctricas
{previsiones}

## Entregables esperados
{chr(10).join(f"- {e}" for e in brief['entregables'])}
"""
