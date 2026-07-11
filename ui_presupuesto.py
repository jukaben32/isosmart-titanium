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

def render_pestana_pricebook():
    """Pestaña: Panel de Control del Libro de Precios RD."""
    st.subheader("⚙️ Panel de Control del Libro de Precios RD")
    ruta = os.path.join("data", "pricebook.json")
    os.makedirs("data", exist_ok=True)

    # Precios base por defecto (Costo Mercado Dominicano 2026)
    precios = {
        "Panel_Muro":     925.0,
        "Panel_Techo":   1125.0,
        "H_3000_PSI":    7350.0,
        "H_3500_PSI":    7950.0,
        "Viga_H_kg":      105.0,
        "Acero_Varilla":   85.0,
        "Ceramica_m2":    450.0,
        "Pintura_galon": 1200.0,
    }

    if os.path.exists(ruta):
        try:
            with open(ruta, "r") as f:
                precios.update(json.load(f))
        except Exception:
            pass

    col1, col2 = st.columns(2)
    with col1:
        precios["Panel_Muro"]    = st.number_input("Costo Muro EPS (RD$/m²)",      value=float(precios["Panel_Muro"]))
        precios["Panel_Techo"]   = st.number_input("Costo Techo EPS (RD$/m²)",     value=float(precios["Panel_Techo"]))
        precios["H_3000_PSI"]    = st.number_input("Hormigón 3000 PSI (RD$/m³)",   value=float(precios["H_3000_PSI"]))
    with col2:
        precios["Acero_Varilla"] = st.number_input("Varilla de Acero (RD$/kg)",    value=float(precios["Acero_Varilla"]))
        precios["Ceramica_m2"]   = st.number_input("Porcelanato/Cerámica (RD$/m²)", value=float(precios["Ceramica_m2"]))
        precios["Pintura_galon"] = st.number_input("Pintura Insumo (RD$/gal)",     value=float(precios["Pintura_galon"]))

    if st.button("💾 Guardar y Sincronizar Libro de Precios", use_container_width=True, type="primary"):
        with open(ruta, "w") as f:
            json.dump(precios, f, indent=4)
        st.session_state["precios_sincronizados"] = precios
        st.success("¡Libro de precios sincronizado en el archivo local de configuración!")

    if st.session_state.get("precios_sincronizados") is None:
        st.session_state["precios_sincronizados"] = precios


def render_vista_presupuesto_y_roi():
    """Pestaña: Análisis de Cotización & Retorno Energético."""
    st.subheader("📊 Análisis de Cotización & Retorno Energético")
    area   = st.session_state.get("calc_area_m2", 120.0)
    precios = st.session_state.get("precios_sincronizados", {})

    if not precios:
        st.warning("Configure el libro de precios antes de procesar el presupuesto.")
        return

    st.markdown(f"#### 📐 Proyecto Actual Evaluado: **{area:.2f} m²**")

    # Ejecutar cálculos de obra gris y acabados
    df_gris, df_term = BudgetCalculator.calcular_presupuesto_completo(area, "Paneles Isotex", precios)

    st.markdown("##### 🧱 Costos de Obra Gris Estructural")
    st.dataframe(df_gris, use_container_width=True)

    total_gris = df_gris["Subtotal"].sum()
    st.metric("Total Neto Estructural", f"RD$ {total_gris:,.2f}")

    # Retorno de Inversión Térmica con tarifa BTS2
    st.divider()
    st.markdown("#### ⚡ Simulación de Ahorro Eléctrico (Tarifa BTS2 - RD)")
    horas = st.slider("Uso diario promedio del Aire Acondicionado (Horas)", 2.0, 24.0, 8.0)

    roi = AnalisisFinancieroRD.simular_ahorro_termico(area, horas)

    c1, c2 = st.columns(2)
    with c1:
        st.metric("Ahorro Mensual en Factura", f"RD$ {roi['ahorro_mensual_rds']:,.2f}")
    with c2:
        st.metric("Ahorro Anual Proyectado",   f"RD$ {roi['ahorro_anual_rds']:,.2f}")


def pagina_panel_operativo():
    """Panel Operativo que integra visión artificial, precios y ROI."""
    st.title("🎛️ Panel Operativo")
    st.markdown("Gestión integrada de cotizaciones, precios y visión geométrica.")
    
    t1, t2, t3 = st.tabs(["📐 Visión & Geometría", "⚙️ Libro de Precios", "📊 Presupuesto & ROI"])
    
    with t1:
        api_key = get_gemini_api_key_from_config()
        modelo = initialize_gemini(api_key)
        render_integradora_vision_canvas(modelo)
    
    with t2:
        render_pestana_pricebook()
        
    with t3:
        render_vista_presupuesto_y_roi()

# ============================================================================
# PÁGINAS DE LA APLICACIÓN
# ============================================================================

