# -*- coding: utf-8 -*-
"""Página 📐 Plano: recorrido de la idea de tu vivienda hasta el plano.

Tab 1 — Describe tu idea: asistente por texto (Gemini) que crea el programa
de ambientes, dibuja el esquema, cotiza y activa la orden CAD.
Tab 2 — Orden CAD para tu agente local: genera el brief OCS y lo descarga
para que tu agente local dibuje los planos DXF.
Tab 3 — Plano DXF y visor 3D: sube un DXF para medirlo y revisa el modelo.
"""
import json

import streamlit as st

from ui_core import render_guard_sin_proyecto, render_text_design_assistant
from ui_visor_bim import pagina_visor_bim
from utils.cad_jobs import brief_para_ocs_markdown, crear_cad_job, listar_cad_jobs
from utils.dxf_importer import analizar_dxf_bytes
from utils.energia import AnalisisEnergetico
from utils.estado import ProyectoState
from utils.estilos import caja_info, encabezado, inyectar_css

_ETIQUETAS_ESTADO_CAD = {
    "pendiente_ocs": "⏳ Pendiente de procesar",
    "en_proceso": "🔄 En proceso",
    "listo_para_ocs": "📤 Lista para tu agente",
    "completado": "✅ Completado",
    "error": "❌ Error",
}


def pagina_plano():
    """Punto de entrada de la página Plano."""
    inyectar_css()
    encabezado(
        "📐 Plano",
        "De la idea al plano: describe lo que quieres, genera una orden para "
        "tu agente local y revisa el resultado en 3D.",
    )

    p1, p2, p3 = st.tabs(
        ["💡 Describe tu idea", "🤖 Orden para tu agente local", "📂 Plano DXF y visor 3D"]
    )
    with p1:
        # El asistente por texto funciona desde cero: no exige proyecto previo.
        render_text_design_assistant("plano")
    with p2:
        _render_orden_cad()
    with p3:
        _render_dxf_y_visor()


def _render_orden_cad():
    """Crea y descarga órdenes CAD/OCS para el agente local del usuario."""
    estado = ProyectoState.cargar()
    if not (estado.origen_metricas or estado.habitaciones):
        caja_info(
            "Necesitas un proyecto activo para generar la orden CAD. "
            "Describe tu idea en la pestaña anterior o calcula en Inicio.",
            "Aún no hay proyecto",
        )
        return

    st.caption(
        "Genera una orden para tu agente local (Open CAD Studio): la procesa, "
        "dibuja los planos DXF y los deja listos para el visor 3D."
    )

    incluir_solar = st.checkbox("Incluir previsión del sistema solar", value=True)
    descripcion_guardada = st.session_state.get("descripcion_lead", "")
    descripcion = st.text_area(
        "Idea de la vivienda",
        value=descripcion_guardada or "Proyecto residencial EPS/ICF en República Dominicana",
        height=110,
        help="Este texto se envía tal cual a tu agente local como punto de partida.",
    )

    if st.button("🤖 Crear orden CAD", type="primary", use_container_width=True):
        solar = None
        if incluir_solar:
            with st.spinner("Calculando previsión solar para el plano..."):
                try:
                    solar = AnalisisEnergetico.calcular_sistema_solar_recomendado(estado.area_m2)
                except Exception:
                    solar = None
        with st.spinner("Creando orden para el agente local..."):
            job = crear_cad_job(descripcion.strip() or "Proyecto residencial EPS/ICF", estado, solar=solar)
        st.session_state["ultimo_cad_job_id"] = job["id"]
        st.success(f"Orden creada: `{job['id']}`. Descárgala abajo para tu agente.")

    st.divider()
    st.markdown("#### Órdenes recientes")
    jobs = listar_cad_jobs(limite=8)
    if not jobs:
        st.caption("Todavía no hay órdenes CAD guardadas.")
        return

    for job in jobs:
        etiqueta = _ETIQUETAS_ESTADO_CAD.get(job.get("status"), job.get("status", "?"))
        creada = str(job.get("created_at", ""))[:16]
        with st.expander(f"{etiqueta} · `{job['id']}` · {creada}"):
            st.write(job.get("descripcion", ""))
            c1, c2 = st.columns(2)
            c1.download_button(
                "📥 Brief para tu agente (.md)",
                data=brief_para_ocs_markdown(job).encode("utf-8"),
                file_name=f"brief_cad_{job['id']}.md",
                mime="text/markdown",
                key=f"desc_brief_{job['id']}",
                use_container_width=True,
            )
            c2.download_button(
                "📦 Orden completa (.json)",
                data=json.dumps(job, ensure_ascii=False, indent=2).encode("utf-8"),
                file_name=f"orden_cad_{job['id']}.json",
                mime="application/json",
                key=f"desc_json_{job['id']}",
                use_container_width=True,
            )


def _render_dxf_y_visor():
    """Sube un plano DXF para medirlo y revisa el modelo en 3D."""
    st.markdown("##### 1) Mide un plano DXF")
    archivo = st.file_uploader("Sube tu plano (formato .dxf ASCII)", type=["dxf"], key="plano_dxf_upload")
    medicion = None
    if archivo is not None:
        try:
            medicion = analizar_dxf_bytes(archivo.getvalue())
        except Exception as exc:  # pragma: no cover - depende del archivo
            st.error(f"No se pudo leer el DXF: {exc}")

    if medicion is not None:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Área", f"{medicion.area_m2:,.2f} m²")
        m2.metric("Perímetro", f"{medicion.perimetro_m:,.2f} m")
        m3.metric("Ventanas", f"{medicion.ventanas}")
        m4.metric("Baños", f"{medicion.banos}")
        for aviso in medicion.advertencias:
            st.warning(aviso)
        if st.button("✅ Usar estas medidas", type="primary", use_container_width=True):
            estado = ProyectoState.cargar()
            estado.aplicar_metricas(medicion.a_metricas(), origen="DXF del plano")
            st.rerun()

    st.markdown("##### 2) Visor 3D")
    if st.session_state.get("layers"):
        # Reutiliza el visor BIM existente (ya estilizado con su propio header).
        pagina_visor_bim()
    else:
        caja_info(
            "El visor 3D se activa cuando tu agente local procese la orden "
            "CAD y devuelva los layers con muros, puertas y ventanas.",
            "Todavía sin capas 3D",
        )


if __name__ == "__main__":
    pagina_plano()