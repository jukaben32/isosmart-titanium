# -*- coding: utf-8 -*-
"""Módulo de interfaz de IsoSmart Titanium (refactor de app.py, 2026-07-10)."""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import google.generativeai as genai
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, date
from fpdf import FPDF
import base64
import json
import os
from io import BytesIO
from typing import Dict, List, Optional, Tuple
import hashlib
import time

from utils.pricebook import Pricebook
from utils.storage import list_dict_values, read_json, write_json_atomic
from utils.gemini_plan import analyze_plan_image_with_gemini
from utils.plan_geometry import (
    polygon_area_perimeter,
    polygon_from_canvas,
    scale_from_canvas_line,
    extract_line_segments,
    extract_points,
)
from utils.pdf_utils import pdf_first_page_to_image
from utils.catalog import Catalog
from utils.ai_text_design import DEFAULT_TEXT_DESIGN_PARAMS, analyze_text_design_with_gemini
from utils.ai_media import generate_facade_image_fal, generate_video_luma
from utils.financiera import AnalisisFinanciero, AnalisisFinancieroRD
from utils.calculador import BudgetCalculator
from utils.energia import AnalisisEnergetico

# Helpers compartidos desde ui_core
from ui_core import (
    sincronizar_parametros_globales,
    ProjectManager,
    PDFGenerator,
    create_download_link,
    initialize_gemini,
    get_gemini_api_key_from_config,
    get_fal_key_from_config,
    get_luma_key_from_config,
    init_text_design_state,
    render_text_design_assistant,
    estimate_build_time_days,
    estimate_foundation_volume_m3,
    calc_h_beams_kg,
)

def _mesh_box(x0, x1, y0, y1, z0, z1):
    # Devuelve puntos para un cubo/ prisma rectangular en plotly Mesh3d
    x = [x0, x1, x1, x0, x0, x1, x1, x0]
    y = [y0, y0, y1, y1, y0, y0, y1, y1]
    z = [z0, z0, z0, z0, z1, z1, z1, z1]
    i = [0, 0, 0, 1, 1, 2, 4, 4, 4, 5, 5, 6]
    j = [1, 2, 3, 2, 5, 3, 5, 6, 7, 6, 1, 2]
    k = [2, 3, 1, 5, 4, 7, 6, 7, 5, 1, 0, 3]
    return x, y, z, i, j, k


def pagina_visor_bim():
    """Visor 3D por capas (conceptual) para atraer al cliente."""
    st.markdown("""
    <div class="main-header">
        <h1 style="margin:0;">🧱 Visor BIM 3D (Capas)</h1>
        <p style="margin:10px 0 0 0;">Estructura, cerramiento, techo e instalaciones (eléctrica/hidrosanitaria) por capas</p>
    </div>
    """, unsafe_allow_html=True)

    st.caption("Visor conceptual: pensado para explicar al cliente el sistema y sus capas. No sustituye un modelado estructural final.")

    # Fuente de parámetros: si vienes del trazado, úsalo; si no, defaults.
    params = st.session_state.get("plan_params", {
        "area_m2": 120.0,
        "niveles": 1,
        "perimetro_m": 44.0,
        "altura_muro_m": 2.8,
    })
    layers = st.session_state.get("layers", None)

    with st.sidebar:
        st.markdown("### 🧩 Parámetros del modelo")
        area_m2 = st.number_input("Área planta (m²)", min_value=10.0, max_value=100000.0, value=float(params.get("area_m2") or 120.0), step=10.0)
        niveles = st.number_input("Niveles", min_value=1, max_value=20, value=int(params.get("niveles") or 1), step=1)
        perimetro_m = st.number_input("Perímetro (m)", min_value=10.0, max_value=5000.0, value=float(params.get("perimetro_m") or 44.0), step=1.0)
        altura_muro = st.number_input("Altura de muro (m)", min_value=2.2, max_value=6.0, value=float(params.get("altura_muro_m") or 2.8), step=0.1)

        st.divider()
        st.markdown("### 🧱 Sistema")
        sistema = st.selectbox("Sistema", ["Sin vigas H (panel estructural)", "Vigas H + Cerramiento EPS", "Vigas H + Cerramiento ICF"])

        st.divider()
        st.markdown("### 🧩 Capas")
        show_structure = st.checkbox("Estructura (vigas/columnas)", True)
        show_enclosure = st.checkbox("Cerramiento (muros/paneles)", True)
        show_roof = st.checkbox("Techo", True)
        show_electrical = st.checkbox("Instalación eléctrica", True)
        show_hydrosan = st.checkbox("Instalación hidrosanitaria", True)

        st.divider()
        st.markdown("### 🧾 Catálogo")
        catalog = Catalog(path=os.path.join("data", "catalog_isotex.json"))
        cat = catalog.load()
        prods = catalog.list_products()
        _ = st.selectbox(
            "Producto de muro (referencia)",
            [p["name"] for p in prods if p.get("category") == "muros"] or ["(sin catálogo)"],
        )
        _ = st.selectbox(
            "Producto de techo (referencia)",
            [p["name"] for p in prods if p.get("category") == "techos"] or ["(sin catálogo)"],
        )
        st.caption(f"Proveedor: {cat.get('provider', {}).get('name', 'N/A')}")

    # Derivar dimensiones aproximadas (rectángulo equivalente) desde área/perímetro.
    # Para un MVP visual: asumimos planta rectangular.
    P = float(perimetro_m)
    A = float(area_m2)
    # Resolver a,b: 2(a+b)=P y ab=A -> b = P/2 - a -> a(P/2 - a)=A
    # a^2 - (P/2)a + A = 0
    disc = max(0.0, (P / 2) ** 2 - 4 * A)
    a = ((P / 2) + (disc ** 0.5)) / 2 if disc >= 0 else (P / 4)
    b = max(1.0, A / a) if a > 0 else (P / 4)
    length = float(max(a, b))
    width = float(min(a, b))

    # Coordenadas: (0..L, 0..W) y altura por nivel.
    total_h = altura_muro * niveles
    wall_th = 0.12
    beam_th = 0.20

    fig = go.Figure()

    # Estructura: columnas + vigas (conceptual)
    if show_structure and ("Vigas H" in sistema):
        # Columnas en esquinas
        col_size = 0.18
        for (x0, y0) in [(0, 0), (length, 0), (length, width), (0, width)]:
            x, y, z, i, j, k = _mesh_box(x0 - col_size / 2, x0 + col_size / 2, y0 - col_size / 2, y0 + col_size / 2, 0, total_h)
            fig.add_trace(go.Mesh3d(x=x, y=y, z=z, i=i, j=j, k=k, color="#4B5563", opacity=0.55, name="Columnas"))

        # Vigas perimetrales arriba
        z0 = total_h - beam_th
        # 4 vigas (prismas delgados)
        beams = [
            (0, length, -beam_th / 2, beam_th / 2),               # borde y=0
            (0, length, width - beam_th / 2, width + beam_th / 2),# borde y=W
            (-beam_th / 2, beam_th / 2, 0, width),               # borde x=0
            (length - beam_th / 2, length + beam_th / 2, 0, width),# borde x=L
        ]
        for bx0, bx1, by0, by1 in beams:
            x, y, z, i, j, k = _mesh_box(bx0, bx1, by0, by1, z0, total_h)
            fig.add_trace(go.Mesh3d(x=x, y=y, z=z, i=i, j=j, k=k, color="#111827", opacity=0.65, name="Vigas H"))

    # Cerramiento: muros perimetrales
    if show_enclosure:
        z0, z1 = 0, total_h
        wall_color = "#22C55E" if "EPS" in sistema or "panel" in sistema.lower() else "#0EA5E9"
        # 4 muros delgados
        walls = [
            (0, length, 0, wall_th),  # y=0
            (0, length, width - wall_th, width),  # y=W
            (0, wall_th, 0, width),  # x=0
            (length - wall_th, length, 0, width),  # x=L
        ]
        for wx0, wx1, wy0, wy1 in walls:
            x, y, z, i, j, k = _mesh_box(wx0, wx1, wy0, wy1, z0, z1)
            fig.add_trace(go.Mesh3d(x=x, y=y, z=z, i=i, j=j, k=k, color=wall_color, opacity=0.22, name="Muros/Paneles"))

    # Techo: losa/panel superior
    if show_roof:
        x, y, z, i, j, k = _mesh_box(0, length, 0, width, total_h, total_h + 0.10)
        fig.add_trace(go.Mesh3d(x=x, y=y, z=z, i=i, j=j, k=k, color="#93C5FD", opacity=0.25, name="Techo"))

    # Eléctrica: rutas simples (líneas)
    if show_electrical:
        if layers and layers.get("fixture_points_px") and layers.get("m_per_px"):
            # Renderiza marcadores reales (proyección 2D → 3D) en un plano intermedio.
            z = total_h * 0.65
            m_per_px = float(layers["m_per_px"])
            pts = layers["fixture_points_px"]
            # Normalizamos a caja del modelo: tomamos min/max de puntos px para mapear a [0..L]/[0..W]
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            minx, maxx = min(xs), max(xs)
            miny, maxy = min(ys), max(ys)
            def mapx(x):
                return (x - minx) / (maxx - minx + 1e-9) * length
            def mapy(y):
                return (y - miny) / (maxy - miny + 1e-9) * width
            fig.add_trace(go.Scatter3d(
                x=[mapx(p[0]) for p in pts],
                y=[mapy(p[1]) for p in pts],
                z=[z for _ in pts],
                mode="markers",
                marker=dict(color="#F59E0B", size=5),
                name="Eléctrica (marcadores)",
            ))
        else:
            z = total_h * 0.65
            fig.add_trace(go.Scatter3d(
                x=[length * 0.1, length * 0.9, length * 0.9],
                y=[width * 0.15, width * 0.15, width * 0.85],
                z=[z, z, z],
                mode="lines",
                line=dict(color="#F59E0B", width=6),
                name="Eléctrica",
            ))

    # Hidrosanitaria: rutas simples (líneas)
    if show_hydrosan:
        z = total_h * 0.35
        fig.add_trace(go.Scatter3d(
            x=[length * 0.2, length * 0.2, length * 0.8],
            y=[width * 0.8, width * 0.2, width * 0.2],
            z=[z, z, z],
            mode="lines",
            line=dict(color="#06B6D4", width=6),
            name="Hidrosanitaria",
        ))

    # Muros interiores desde trazado (líneas reales)
    if layers and show_enclosure and layers.get("walls_segments_px"):
        segs = layers["walls_segments_px"]
        xs = [p[0] for seg in segs for p in seg]
        ys = [p[1] for seg in segs for p in seg]
        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)
        def mapx(x):
            return (x - minx) / (maxx - minx + 1e-9) * length
        def mapy(y):
            return (y - miny) / (maxy - miny + 1e-9) * width
        # Dibujamos cada segmento como línea vertical extruida en Z (de 0 a total_h)
        for (a, b) in segs[:300]:  # límite de seguridad visual
            fig.add_trace(go.Scatter3d(
                x=[mapx(a[0]), mapx(b[0])],
                y=[mapy(a[1]), mapy(b[1])],
                z=[0, 0],
                mode="lines",
                line=dict(color="#16A34A", width=6),
                name="Muros interiores",
                showlegend=False,
            ))
        # una leyenda única
        fig.add_trace(go.Scatter3d(
            x=[None], y=[None], z=[None],
            mode="lines",
            line=dict(color="#16A34A", width=6),
            name="Muros interiores (trazado)",
        ))

    fig.update_layout(
        height=700,
        scene=dict(
            xaxis_title="X (m)",
            yaxis_title="Y (m)",
            zaxis_title="Z (m)",
            aspectmode="data",
        ),
        legend=dict(orientation="h"),
        margin=dict(l=10, r=10, t=10, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### 🔍 Qué sigue para que sea realmente “BIM-like”")
    st.write("- Dibujar muros interiores y ejes de vigas desde el trazado (no solo perímetro).")
    st.write("- Colocar puntos de tomas/interruptores y aparatos sanitarios y autorutar MEP.")
    st.write("- Vincular cada capa a partidas del presupuesto (catálogo Isotex + mano de obra).")


# ============================================================================
# NAVEGACIÓN PRINCIPAL
# ============================================================================

