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

def render_integradora_vision_canvas(modelo_gemini):
    """Pestaña: Extracción Geométrica Avanzada y Visión Artificial."""
    st.subheader("📐 Extracción Geométrica Avanzada y Visión Artificial")
    col_izq, col_der = st.columns([1, 2])

    with col_izq:
        st.markdown("### 🛠️ Cargar Documento")
        archivo_plano = st.file_uploader(
            "Sube plano (PDF o Imagen)",
            type=["png", "jpg", "jpeg", "pdf"],
            key="uploader_v4"
        )

        imagen_pil = None
        if archivo_plano:
            if archivo_plano.name.lower().endswith(".pdf"):
                # Convertir primera página del PDF a imagen para el canvas
                with st.spinner("Convirtiendo PDF a imagen..."):
                    imagen_pil = pdf_first_page_to_image(archivo_plano.read(), dpi=150)
                if imagen_pil is None:
                    st.warning(
                        "No se pudo convertir el PDF. "
                        "Asegúrate de tener `PyMuPDF` instalado: `pip install pymupdf`"
                    )
                else:
                    st.success("✅ PDF convertido correctamente — primera página lista para analizar.")
            else:
                imagen_pil = Image.open(BytesIO(archivo_plano.read())).convert("RGB")

        if imagen_pil and modelo_gemini:
            if st.button("🧠 Analizar Estructura con Gemini IA", use_container_width=True):
                data_json, _ = analyze_plan_image_with_gemini(modelo_gemini, imagen_pil)
                if data_json:
                    st.json(data_json)
                    sincronizar_parametros_globales(data_json, "Gemini Vision API")
                else:
                    st.error("No se detectó una tabla de cotas legible en el gráfico.")

    with col_der:
        st.markdown("### ✏️ Calibración de Escala y Trazado de Polígonos")
        if imagen_pil:
            if st_canvas is None:
                st.error("Instale streamlit-drawable-canvas")
                return

            col_h1, col_h2 = st.columns(2)
            with col_h1:
                herramienta = st.selectbox("Modo de Dibujo", ["line", "polygon"])
            with col_h2:
                dist_real = st.number_input("Dimensión conocida de la línea (m)", min_value=0.1, value=1.0)

            # Ajuste dinámico de escala en pantalla
            w, h = imagen_pil.size
            ancho_ui = 680
            alto_ui = int((ancho_ui / w) * h)
            img_resize = imagen_pil.resize((ancho_ui, alto_ui))

            canvas_out = st_canvas(
                fill_color="rgba(30, 60, 114, 0.25)", stroke_width=3, stroke_color="#1e3c72",
                background_image=img_resize, height=alto_ui, width=ancho_ui,
                drawing_mode=herramienta, key="canvas_titanium"
            )

            if canvas_out.json_data and "objects" in canvas_out.json_data:
                objs = canvas_out.json_data["objects"]
                m_px = scale_from_canvas_line(objs, dist_real)
                if m_px:
                    st.caption(f"Factor de calibración: {m_px:.6f} m/px")
                    path_poligono = polygon_from_canvas(objs)
                    if path_poligono:
                        a_px2, p_px = polygon_area_perimeter(path_poligono)
                        real_a = a_px2 * (m_px ** 2)
                        real_p = p_px * m_px

                        st.metric("Área Calculada (Shoelace)", f"{real_a:.2f} m²")
                        if st.button("📥 Aplicar Mediciones del Canvas al Presupuesto", use_container_width=True):
                            sincronizar_parametros_globales(
                                {"area_m2": real_a, "perimetro_m": real_p},
                                "Canvas Interactivo"
                            )

