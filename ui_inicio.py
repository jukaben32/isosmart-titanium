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

def pagina_inicio():
    """Página de inicio educativa y de marketing"""

    # Hero section
    st.markdown("""
    <div class="main-header">
        <h1 style="margin:0;">🏗️ IsoSmart Titanium</h1>
        <p style="margin:10px 0 0 0; font-size:1.3rem;">Construcción Inteligente con Poliestireno Expandido en República Dominicana</p>
        <p style="margin:5px 0 0 0; opacity:0.9;">Ahorra hasta 30% en costos y 40% en tiempo de construcción</p>
    </div>
    """, unsafe_allow_html=True)

    # Beneficios principales
    st.markdown("### 🌟 ¿Por Qué Construir con Poliestireno Expandido?")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown("""
        <div class="benefit-card">
            <div style="font-size:3rem;">💰</div>
            <h3>Menor Costo</h3>
            <p class="big-metric" style="color:#28a745;">-30%</p>
            <p>vs construcción tradicional</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="benefit-card">
            <div style="font-size:3rem;">⚡</div>
            <h3>Más Rápido</h3>
            <p class="big-metric" style="color:#28a745;">-40%</p>
            <p>tiempo de construcción</p>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown("""
        <div class="benefit-card">
            <div style="font-size:3rem;">🌡️</div>
            <h3>Térmico</h3>
            <p class="big-metric" style="color:#28a745;">-5°C</p>
            <p>interior más fresco</p>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown("""
        <div class="benefit-card">
            <div style="font-size:3rem;">🔊</div>
            <h3>Acústico</h3>
            <p class="big-metric" style="color:#28a745;">-45dB</p>
            <p>aislamiento sonoro</p>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # Información educativa
    st.markdown("### 📚 ¿Qué es el Sistema Isotex/ICF?")

    tab_info1, tab_info2, tab_info3 = st.tabs(["🏠 Sistema Isotex", "🧱 Bloques ICF", "❓ Preguntas Frecuentes"])

    with tab_info1:
        st.markdown("""
        #### Paneles Isotex - Construcción Moderna y Eficiente

        **El sistema Isotex** utiliza paneles prefabricados de poliestireno expandido (EPS) recubiertos con malla electrosoldada,
        que se llenan con concreto para formar muros y losas estructurales.

        ##### ✅ Ventajas:
        - **Peso reducido**: 70% menos peso que la construcción tradicional
        - **Aislamiento térmico**: Reduce el consumo de aire acondicionado
        - **Aislamiento acústico**: Hasta 45dB de reducción de ruido
        - **Resistencia sísmica**: Mayor flexibilidad ante movimientos
        - **Rapidez**: Hasta 3 veces más rápido que el ladrillo

        ##### 📋 Aplicaciones:
        - Viviendas unifamiliares
        - Edificios de apartamentos
        - Locales comerciales
        - Habitaciones de hotel
        """)

        st.image("https://images.unsplash.com/photo-1590059390239-03c9e7064e92?w=800",
                 caption="Panel Isotex durante instalación", use_container_width=True)

    with tab_info2:
        st.markdown("""
        #### Bloques ICF - Encofrado Concreto Aislante

        **ICF (Insulated Concrete Forms)** son bloques huecos de poliestireno que sirven como encofrado permanente.
        Se apilan como LEGO y se llenan de concreto, creando muros con aislamiento integrado.

        ##### ✅ Ventajas:
        - **Eficiencia energética**: Hasta 60% de ahorro en HVAC
        - **Resistencia estructural**: Muros de concreto reforzado
        - **Facilidad de instalación**: Sistema tipo LEGO
        - **Durabilidad**: No se pudre, no atrae termitas
        - **Ecológico**: Menor huella de carbono

        ##### 📋 Aplicaciones:
        - Sótanos y cimentaciones
        - Muros de contención
        - Edificios de varios pisos
        - Cámaras frigoríficas
        """)

    with tab_info3:
        st.markdown("""
        #### Preguntas Frecuentes

        **❓ ¿Es resistente a huracanes?**
        ✅ Sí, los muros de EPS con concreto tienen excelente resistencia a vientos huracanados.
        El sistema ha sido probado en zonas sísmicas y de huracanes.

        **❓ ¿Lo comen las termitas?**
        ✅ No, el poliestireno tratado no es alimento para termitas. Además, el concreto
        circundante crea una barrera física.

        **❓ ¿Qué duración tiene?**
        ✅ La vida útil es superior a 50 años. El concreto protegido por el EPS dura más
        porque no está expuesto directamente a los elementos.

        **❓ ¿Necesito mano de obra especializada?**
        ✅ Se requiere capacitación básica, pero cualquier albañil puede aprender en 1-2 días.
        Nuestro team ofrece capacitación y supervisión.

        **❓ ¿El precio incluye mano de obra?**
        ✅ Los cálculos mostrados son de materiales. Ofrecemos cotización de mano de obra
        por separado. Contáctanos para un presupuesto completo.

        **❓ ¿Dónde puedo comprar estos materiales en RD?**
        ✅ Trabajamos con proveedores locales. Isotex RD tiene distribución nacional.
        También importamos ICF de proveedores certificados.
        """)

    st.divider()

    # Comparativa rápida
    st.markdown("### 📊 Comparativa: Isotex vs Construcción Tradicional")

    st.markdown("""
    <div class="info-card">
    <strong>Para una vivienda de 120 m² en Santo Domingo:</strong>
    </div>
    """, unsafe_allow_html=True)

    # Carga precios para la comparación de demo
    pricebook_demo = Pricebook(path=os.path.join("data", "pricebook.json"))
    precios_demo = pricebook_demo.load()
    comparacion = BudgetCalculator.comparar_sistemas(120, precios_demo)

    col_comp1, col_comp2, col_comp3 = st.columns(3)

    with col_comp1:
        st.metric(
            label="💰 Costo Isotex",
            value=f"RD$ {comparacion['isotex']['costo_total']:,.0f}",
            delta=f"RD$ {comparacion['isotex']['costo_m2']:,.0f}/m²"
        )

    with col_comp2:
        st.metric(
            label="🏗️ Costo Tradicional",
            value=f"RD$ {comparacion['tradicional']['costo_total']:,.0f}",
            delta=f"RD$ {comparacion['tradicional']['costo_m2']:,.0f}/m²",
            delta_color="inverse"
        )

    with col_comp3:
        st.metric(
            label="✅ Ahorro Total",
            value=f"RD$ {comparacion['ahorro']['dinero']:,.0f}",
            delta=f"{comparacion['ahorro']['porcentaje']:.1f}% menos",
            delta_color="normal"
        )

    # Tabla comparativa
    st.markdown("""
    <table class="comparison-table" style="width:100%; margin:20px 0;">
        <tr style="background:#1e3c72; color:white;">
            <th>Característica</th>
            <th>Isotex/ICF</th>
            <th>Tradicional</th>
        </tr>
        <tr>
            <td><strong>Costo por m²</strong></td>
            <td class="highlight-green">RD$ {isotex_m2:,.0f}</td>
            <td>RD$ {trad_m2:,.0f}</td>
        </tr>
        <tr>
            <td><strong>Tiempo de construcción</strong></td>
            <td class="highlight-green">{isotex_t} días</td>
            <td>{trad_t} días</td>
        </tr>
        <tr>
            <td><strong>Peso de la estructura</strong></td>
            <td class="highlight-green">{isotex_p} kg</td>
            <td>{trad_p} kg</td>
        </tr>
        <tr>
            <td><strong>Aislamiento térmico</strong></td>
            <td class="highlight-green">Excelente</td>
            <td>Regular</td>
        </tr>
        <tr>
            <td><strong>Aislamiento acústico</strong></td>
            <td class="highlight-green">Hasta 45dB</td>
            <td>~20dB</td>
        </tr>
        <tr>
            <td><strong>Resistencia sísmica</strong></td>
            <td class="highlight-green">Alta (flexible)</td>
            <td>Media (rígido)</td>
        </tr>
    </table>
    """.format(
        isotex_m2=comparacion['isotex']['costo_m2'],
        trad_m2=comparacion['tradicional']['costo_m2'],
        isotex_t=int(comparacion['isotex']['tiempo_dias']),
        trad_t=int(comparacion['tradicional']['tiempo_dias']),
        isotex_p=int(comparacion['isotex']['peso_kg']),
        trad_p=int(comparacion['tradicional']['peso_kg'])
    ), unsafe_allow_html=True)

