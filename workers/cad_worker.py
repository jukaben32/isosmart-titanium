"""
Worker local para trabajos CAD/OCS.

Uso recomendado en la PC donde está instalado Open CAD Studio:

    python workers/cad_worker.py --once
    python workers/cad_worker.py --watch

Esta primera versión prepara el brief que debe consumir el agente/OCS y cambia
el estado del job a `listo_para_ocs`. La llamada directa al MCP/API de OCS se
conecta encima de esta cola sin tocar la interfaz de Streamlit.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.cad_jobs import (  # noqa: E402
    DEFAULT_CAD_QUEUE_DIR,
    actualizar_cad_job,
    brief_para_ocs_markdown,
    listar_cad_jobs,
)


def procesar_pendientes(cola_dir: str | Path = DEFAULT_CAD_QUEUE_DIR) -> int:
    """Prepara archivos markdown para los jobs pendientes de OCS."""
    procesados = 0
    for job in listar_cad_jobs(cola_dir=cola_dir, limite=200):
        if job.get("status") != "pendiente_ocs":
            continue

        actualizar_cad_job(job["id"], {"status": "procesando"}, cola_dir=cola_dir)
        salida = Path(cola_dir) / f"{job['id']}_brief_ocs.md"
        salida.parent.mkdir(parents=True, exist_ok=True)
        salida.write_text(brief_para_ocs_markdown(job), encoding="utf-8")
        actualizar_cad_job(
            job["id"],
            {
                "status": "listo_para_ocs",
                "resultado": {
                    "brief_ocs_md": str(salida),
                    "mensaje": "Brief preparado. Ejecutar generación CAD en Open CAD Studio.",
                },
            },
            cola_dir=cola_dir,
        )
        procesados += 1
    return procesados


def main() -> int:
    parser = argparse.ArgumentParser(description="Worker local para solicitudes CAD/OCS")
    parser.add_argument("--queue", default=str(DEFAULT_CAD_QUEUE_DIR), help="Carpeta de cola CAD")
    parser.add_argument("--once", action="store_true", help="Procesa una vez y termina")
    parser.add_argument("--watch", action="store_true", help="Escucha la cola continuamente")
    parser.add_argument("--interval", type=float, default=5.0, help="Segundos entre revisiones")
    args = parser.parse_args()

    if not args.once and not args.watch:
        args.once = True

    while True:
        procesados = procesar_pendientes(args.queue)
        print(f"Jobs CAD preparados: {procesados}")
        if args.once:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
