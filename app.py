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

# Configuracion de la pagina (debe ser la PRIMERA llamada a Streamlit)
st.set_page_config(
    page_title="IsoSmart Titanium",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

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

# Módulos de interfaz (refactor de app.py, 2026-07-10)
from ui_core import sincronizar_parametros_globales, ProjectManager, PDFGenerator, create_download_link
from ui_vision import render_integradora_vision_canvas
from ui_presupuesto import render_pestana_pricebook, render_vista_presupuesto_y_roi, pagina_panel_operativo
from ui_inicio import pagina_inicio
from ui_team import pagina_team
from ui_calculadora import (
    render_modulo_vision_y_canvas,
    pagina_calculadora,
    pagina_contacto,
    render_pestana_configuracion_precios,
    pagina_plano_estructura,
)
from ui_visor_bim import pagina_visor_bim

try:
    from streamlit_drawable_canvas import st_canvas
except Exception:
    st_canvas = None

def main():
    # Menú de navegación
    with st.sidebar:
        st.image("https://img.icons8.com/color/96/construction.png", width=80)
        st.markdown("### 🏗️ IsoSmart Titanium")

        menu = st.radio(
            "Navegación",
            ["🏠 Inicio", "👷 Nuestro Team", "🧮 Calculadora", "📐 Plano → Estructura", "🧱 Visor BIM 3D", "🎛️ Panel Operativo", "📞 Contacto"],
            label_visibility="collapsed"
        )

        st.divider()

        # Información rápida
        st.markdown("""
        <div style="background:#f0f2f6; padding:15px; border-radius:10px;">
            <strong>💡 ¿Sabías qué?</strong><br>
            El poliestireno expandido puede reducir hasta 30% los costos de construcción
            comparado con el método tradicional.
        </div>
        """, unsafe_allow_html=True)

    # Router de páginas
    if menu == "🏠 Inicio":
        pagina_inicio()
    elif menu == "👷 Nuestro Team":
        pagina_team()
    elif menu == "🧮 Calculadora":
        pagina_calculadora()
    elif menu == "📐 Plano → Estructura":
        pagina_plano_estructura()
    elif menu == "🧱 Visor BIM 3D":
        pagina_visor_bim()
    elif menu == "🎛️ Panel Operativo":
        pagina_panel_operativo()
    elif menu == "📞 Contacto":
        pagina_contacto()


# ============================================================================
# PUNTO DE ENTRADA
# ============================================================================

if __name__ == "__main__":
    main()
