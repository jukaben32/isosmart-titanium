# -*- coding: utf-8 -*-
"""
IsoSmart Titanium v4.5 - Professional Suite
Sistema Inteligente de Presupuestos, Visualización BIM y Marketing
para Construcción con Poliestireno Expandido en República Dominicana

Autor: jukaben32
Licencia: MIT
"""

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
from utils.calculador import BudgetCalculator as BudgetCalculatorLite

try:
    from streamlit_drawable_canvas import st_canvas
except Exception:
    st_canvas = None

# ============================================================================
# CONFIGURACIÓN DE PÁGINA Y ESTILOS
# ============================================================================

st.set_page_config(
    page_title="IsoSmart Titanium - Construcción Inteligente RD",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://github.com/jukaben32/isosmart-titanium',
        'Report a bug': 'https://github.com/jukaben32/isosmart-titanium/issues',
        'About': "# IsoSmart Titanium v4.5\nConstrucción con poliestireno expandido en República Dominicana"
    }
)

# CSS Personalizado
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
        padding: 2rem;
        border-radius: 15px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .info-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        padding: 1.5rem;
        border-radius: 15px;
        margin: 1rem 0;
        border-left: 5px solid #1e3c72;
    }
    .benefit-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        text-align: center;
        height: 100%;
    }
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        font-weight: bold;
        padding: 0.75rem 1rem;
    }
    .big-metric {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1e3c72;
    }
    .comparison-table td, .comparison-table th {
        padding: 12px;
        text-align: left;
    }
    .highlight-green {
        background-color: #d4edda;
        color: #155724;
        font-weight: bold;
    }
    .highlight-blue {
        background-color: #d1ecf1;
        color: #0c5460;
        font-weight: bold;
    }
    div[data-testid="stMetricValue"] {
        font-size: 2rem;
    }
    .team-card {
        background: white;
        padding: 2rem;
        border-radius: 15px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# INICIALIZACIÓN DE ESTADOS (PASO 1, 2 Y 3)
# ============================================================================

# Variables de cálculo y planificación (Paso 1 y 2)
_session_defaults = {
    "calc_area_m2": 120.0,
    "calc_perimetro_m": 45.0,
    "calc_niveles": 1,
    "calc_altura_muro_m": 2.80,
    "calc_espesor_muro_m": 0.12,
    "plan_area_m2": 120.0,
    "plan_niveles": 1,
    "plan_perimetro_m": 45.0,
    "plan_altura_muro_m": 2.80,
    "plan_espesor_muro_m": 0.12,
}

for _llave, _valor_defecto in _session_defaults.items():
    if _llave not in st.session_state:
        st.session_state[_llave] = _valor_defecto

# Inicializar precios sincronizados (Paso 3)
if "precios_sincronizados" not in st.session_state:
    _ruta = os.path.join("data", "pricebook.json")
    _precios_cargados = read_json(_ruta, default={})
    if not _precios_cargados:
        # Usar defaults si el archivo está vacío
        _precios_cargados = {
            "Panel_Muro": 925.00,
            "Panel_Techo": 1125.00,
            "H_3000_PSI": 7350.00,
            "H_3500_PSI": 7950.00,
            "Viga_H_kg": 105.00,
            "Acero_Varilla": 85.00,
            "Malla_Electrosoldada": 450.00,
            "Poliestireno_EPS": 2800.00,
            "Fibra_Acero": 120.00,
            "Aditivo_Impermeabilizante": 850.00,
            "Cemento_Saco": 450.00,
            "Arena_m3": 1200.00,
            "Piedra_m3": 1100.00,
            "Ladrillo_unidad": 28.00,
            "Ceramica_m2": 450.00,
            "Porcelanato_m2": 850.00,
            "Pintura_galon": 1200.00,
            "Yeso_saco": 180.00,
            "Puerta_interior": 8500.00,
            "Ventana_aluminio_m2": 4500.00,
            "Griferia_bano": 3500.00,
            "Inodoro": 4200.00,
            "Lavamanos": 2800.00,
            "Ducha": 1800.00,
            "Fregadero_cocina": 6500.00,
            "Gabinete_cocina_ml": 12000.00,
            "Meson_granito_ml": 18000.00,
        }
    st.session_state["precios_sincronizados"] = _precios_cargados

# Inicializar objeto Pricebook
if "pricebook_obj" not in st.session_state:
    try:
        _ruta = os.path.join("data", "pricebook.json")
        st.session_state["pricebook_obj"] = Pricebook(_ruta)
    except Exception as e:
        st.warning(f"⚠️ No se pudo inicializar el módulo Pricebook: {e}")
        st.session_state["pricebook_obj"] = None

# ============================================================================
# CLASES Y UTILIDADES
# ============================================================================

class ProjectManager:
    """Gestor de proyectos con persistencia local"""

    def __init__(self, base_dir: str = "data"):
        self.base_dir = base_dir
        self.storage_file = os.path.join(self.base_dir, "projects_db.json")
        self.leads_file = os.path.join(self.base_dir, "leads_db.json")
        self.projects = self._load_projects()
        self.leads = self._load_leads()

    def _load_projects(self) -> Dict:
        return read_json(self.storage_file, default={})

    def _load_leads(self) -> List:
        return read_json(self.leads_file, default=[])

    def save_lead(self, lead_data: Dict):
        """Guarda un lead interesado"""
        lead_data['fecha'] = datetime.now().isoformat()
        lead_data['id'] = hashlib.md5(
            f"{lead_data['nombre']}{lead_data['fecha']}".encode()
        ).hexdigest()[:8]
        self.leads.append(lead_data)
        write_json_atomic(self.leads_file, self.leads)

    def save_project(self, project_id: str, data: Dict):
        self.projects[project_id] = {
            **data,
            'updated_at': datetime.now().isoformat()
        }
        write_json_atomic(self.storage_file, self.projects)

    def get_project(self, project_id: str) -> Optional[Dict]:
        return self.projects.get(project_id)

    def list_projects(self) -> List[Dict]:
        return list_dict_values(self.projects)

    def delete_project(self, project_id: str):
        if project_id in self.projects:
            del self.projects[project_id]
            write_json_atomic(self.storage_file, self.projects)


# ============================================================================
# PASO 3: MOTOR DE CÁLCULO DILUIDO CON PRICEBOOK DINÁMICO
# ============================================================================

class BudgetCalculator:
    """Motor de cálculo de presupuestos optimizado con precios dinámicos desde JSON"""

    FACTORES_RENDIMIENTO = {
        "desperdicio_panel": 0.05,
        "desperdicio_hormigon": 0.08,
        "factor_conversion_m3": 1.10,
    }

    @classmethod
    def calcular_area_muros(cls, area_construida: float, factor: float = 2.2) -> float:
        return area_construida * factor

    @classmethod
    def calcular_area_techo(cls, area_construida: float, factor: float = 1.10) -> float:
        return area_construida * factor

    @classmethod
    def calcular_volumen_hormigon(cls, area_muros: float, espesor: float = 0.12) -> float:
        return area_muros * espesor

    @classmethod
    def calcular_acero_refuerzo(cls, area_construida: float, tipo: str = "varilla") -> Tuple[float, float]:
        if tipo == "varilla":
            kg_m2 = 8.5
        else:
            kg_m2 = 6.0
        total_kg = area_construida * kg_m2
        total_barras = total_kg / 12
        return total_kg, total_barras

    @classmethod
    def calcular_obra_grisa(cls, m2: float, sistema: str, precios: dict, incluir_vigas: bool = True) -> pd.DataFrame:
        """Calcula costos de obra gris utilizando el diccionario dinámico de precios"""
        area_muros = cls.calcular_area_muros(m2)
        area_techo = cls.calcular_area_techo(m2)
        desperdicio_p = cls.FACTORES_RENDIMIENTO["desperdicio_panel"]
        desperdicio_h = cls.FACTORES_RENDIMIENTO["desperdicio_hormigon"]

        data = []

        if sistema == "Paneles Isotex":
            total_muros = area_muros * (1 + desperdicio_p)
            data.append({
                "Categoria": "Estructura",
                "Material": "Paneles Isotex (Muros)",
                "Detalle": "Panel estructural EPS con malla electrosoldada",
                "Cantidad": round(total_muros, 2),
                "Unidad": "m²",
                "P_Unitario": precios.get("Panel_Muro", 925.0),
                "Subtotal": total_muros * precios.get("Panel_Muro", 925.0)
            })

            total_techo = area_techo * (1 + desperdicio_p)
            data.append({
                "Categoria": "Estructura",
                "Material": "Paneles Isotex (Techo)",
                "Detalle": "Panel aligerado para losa",
                "Cantidad": round(total_techo, 2),
                "Unidad": "m²",
                "P_Unitario": precios.get("Panel_Techo", 1125.0),
                "Subtotal": total_techo * precios.get("Panel_Techo", 1125.0)
            })

            # Corrección del bug silencioso: ahora usa desperdicio_h (0.08)
            vol_hormigon = cls.calcular_volumen_hormigon(area_muros + area_techo)
            vol_hormigon *= (1 + desperdicio_h)
            data.append({
                "Categoria": "Hormigón",
                "Material": "Hormigón Cemex 3000 PSI",
                "Detalle": "Concreto premezclado para llenado",
                "Cantidad": round(vol_hormigon, 2),
                "Unidad": "m³",
                "P_Unitario": precios.get("H_3000_PSI", 7350.0),
                "Subtotal": vol_hormigon * precios.get("H_3000_PSI", 7350.0)
            })

        else:  # ICF
            data.append({
                "Categoria": "Estructura",
                "Material": "Bloques ICF Proform",
                "Detalle": "Bloques de poliestireno para encofrado",
                "Cantidad": round(area_muros * 0.85, 2),
                "Unidad": "m²",
                "P_Unitario": precios.get("Panel_Muro", 925.0) * 1.15,
                "Subtotal": area_muros * 0.85 * (precios.get("Panel_Muro", 925.0) * 1.15)
            })

            vol_hormigon = area_muros * 0.15
            data.append({
                "Categoria": "Hormigón",
                "Material": "Hormigón Cemex 3500 PSI",
                "Detalle": "Concreto de alta resistencia para ICF",
                "Cantidad": round(vol_hormigon, 2),
                "Unidad": "m³",
                "P_Unitario": precios.get("H_3500_PSI", 7950.0),
                "Subtotal": vol_hormigon * precios.get("H_3500_PSI", 7950.0)
            })

        vol_cimentacion = m2 * 0.15
        data.append({
            "Categoria": "Cimentación",
            "Material": "Cimentación Armada",
            "Detalle": "Zapatas y vigas de fundación",
            "Cantidad": round(vol_cimentacion, 2),
            "Unidad": "m³",
            "P_Unitario": precios.get("H_3000_PSI", 7350.0) * 1.2,
            "Subtotal": vol_cimentacion * (precios.get("H_3000_PSI", 7350.0) * 1.2)
        })

        if incluir_vigas:
            kg_vigas = m2 * 25
            data.append({
                "Categoria": "Acero",
                "Material": "Vigas H Estructurales",
                "Detalle": "Perfil de acero A36 para estructura",
                "Cantidad": round(kg_vigas, 2),
                "Unidad": "kg",
                "P_Unitario": precios.get("Viga_H_kg", 105.0),
                "Subtotal": kg_vigas * precios.get("Viga_H_kg", 105.0)
            })

        kg_acero, barras = cls.calcular_acero_refuerzo(m2)
        data.append({
            "Categoria": "Acero",
            "Material": "Acero de Refuerzo",
            "Detalle": f"Varillas corrugadas (~{int(barras)} barras)",
            "Cantidad": round(kg_acero, 2),
            "Unidad": "kg",
            "P_Unitario": precios.get("Acero_Varilla", 85.0),
            "Subtotal": kg_acero * precios.get("Acero_Varilla", 85.0)
        })

        return pd.DataFrame(data)

    @classmethod
    def calcular_obra_terminada(cls, m2: float, area_muros: float, precios: dict, calidad: str = "media") -> pd.DataFrame:
        """Calcula costos de obra terminada utilizando el diccionario dinámico de precios"""
        factores = {"economica": 0.8, "media": 1.0, "alta": 1.5, "lujo": 2.5}
        factor = factores.get(calidad, 1.0)

        data = []
        area_piso = m2 * 0.9
        data.append({
            "Categoria": "Pisos",
            "Material": "Cerámica/Porcelanato",
            "Detalle": f"Piso calidad {calidad}",
            "Cantidad": round(area_piso, 2),
            "Unidad": "m²",
            "P_Unitario": precios.get("Ceramica_m2", 450.0) * factor,
            "Subtotal": area_piso * precios.get("Ceramica_m2", 450.0) * factor
        })

        galones_pintura = area_muros / 12
        data.append({
            "Categoria": "Pintura",
            "Material": "Pintura Interior/Exterior",
            "Detalle": "Pintura vinílica premium (3 manos)",
            "Cantidad": round(galones_pintura, 1),
            "Unidad": "gal",
            "P_Unitario": precios.get("Pintura_galon", 1200.0) * factor,
            "Subtotal": galones_pintura * precios.get("Pintura_galon", 1200.0) * factor
        })

        num_puertas = max(4, int(m2 / 15))
        data.append({
            "Categoria": "Carpintería",
            "Material": "Puertas Interiores",
            "Detalle": f"{num_puertas} puertas de madera con marcos",
            "Cantidad": num_puertas,
            "Unidad": "ud",
            "P_Unitario": precios.get("Puerta_interior", 8500.0),
            "Subtotal": num_puertas * precios.get("Puerta_interior", 8500.0)
        })

        return pd.DataFrame(data)

    @classmethod
    def calcular_presupuesto_completo(cls, m2: float, sistema: str, precios: dict, incluir_vigas: bool = True, calidad_terminados: str = "media") -> Tuple[pd.DataFrame, pd.DataFrame]:
        obra_gris = cls.calcular_obra_grisa(m2, sistema, precios, incluir_vigas)
        area_muros = cls.calcular_area_muros(m2)
        obra_terminada = cls.calcular_obra_terminada(m2, area_muros, precios, calidad_terminados)
        return obra_gris, obra_terminada

    @classmethod
    def comparar_sistemas(cls, m2: float, precios: dict, sistema: str = "Paneles Isotex", usar_vigas: bool = False, calidad: str = "media") -> Dict:
        """Compara Isotex vs Construcción Tradicional con precios dinámicos"""
        # Costos Isotex
        isotex_gris, isotex_term = cls.calcular_presupuesto_completo(m2, sistema, precios, usar_vigas, calidad)
        total_isotex = isotex_gris['Subtotal'].sum() + isotex_term['Subtotal'].sum()

        # Costos Tradicional (matriz dinámica según calidad)
        matriz_tradicional = {
            "economica": {"gris": 22000.00, "terminado": 16000.00},
            "media":     {"gris": 35000.00, "terminado": 25000.00},
            "alta":      {"gris": 52000.00, "terminado": 38000.00},
            "lujo":      {"gris": 75000.00, "terminado": 60000.00}
        }
        
        costos_trad = matriz_tradicional.get(calidad, matriz_tradicional["media"])
        tradicional_gris = m2 * costos_trad["gris"]
        tradicional_term = m2 * costos_trad["terminado"]
        total_tradicional = tradicional_gris + tradicional_term

        # Indicadores de Rendimiento
        tiempo_isotex = m2 * (1.1 if usar_vigas else 1.5)
        tiempo_tradicional = m2 * 2.5
        peso_tradicional = m2 * 850
        peso_isotex = m2 * (220 if sistema == "Paneles Isotex" else 380)

        return {
            'isotex': {
                'costo_total': total_isotex,
                'costo_m2': total_isotex / m2,
                'tiempo_dias': tiempo_isotex,
                'peso_kg': peso_isotex
            },
            'tradicional': {
                'costo_total': total_tradicional,
                'costo_m2': total_tradicional / m2,
                'tiempo_dias': tiempo_tradicional,
                'peso_kg': peso_tradicional
            },
            'ahorro': {
                'dinero': total_tradicional - total_isotex,
                'porcentaje': ((total_tradicional - total_isotex) / total_tradicional) * 100,
                'tiempo_dias': tiempo_tradicional - tiempo_isotex,
                'peso_kg': peso_tradicional - peso_isotex
            }
        }


class PDFGenerator:
    """Generador de documentos PDF profesionales"""

    def __init__(self):
        self.pdf = FPDF()
        self.pdf.set_auto_page_break(auto=True, margin=15)

    def generar_propuesta(self, cliente: str, datos_proyecto: Dict,
                         presupuesto_df: pd.DataFrame, total: float) -> bytes:
        self.pdf.add_page()

        # Encabezado
        self.pdf.set_fill_color(30, 60, 114)
        self.pdf.rect(0, 0, 210, 40, 'F')

        self.pdf.set_font('Arial', 'B', 20)
        self.pdf.set_text_color(255, 255, 255)
        self.pdf.cell(190, 15, 'IsoSmart Titanium', ln=True, align='C')

        self.pdf.set_font('Arial', '', 12)
        self.pdf.cell(190, 10, 'Propuesta Técnica Comercial', ln=True, align='C')

        self.pdf.ln(20)

        # Información del cliente
        self.pdf.set_font('Arial', 'B', 12)
        self.pdf.set_text_color(0, 0, 0)
        self.pdf.cell(95, 10, 'INFORMACIÓN DEL CLIENTE', ln=False)
        self.pdf.cell(95, 10, 'DETALLES DEL PROYECTO', ln=True)

        self.pdf.set_font('Arial', '', 10)
        self.pdf.cell(95, 8, f'Cliente: {cliente}', ln=False)
        self.pdf.cell(95, 8, f'Fecha: {date.today().strftime("%d/%m/%Y")}', ln=True)

        self.pdf.cell(95, 8, f'Área: {datos_proyecto.get("area", 0):.2f} m²', ln=False)
        self.pdf.cell(95, 8, f'Sistema: {datos_proyecto.get("sistema", "N/A")}', ln=True)

        self.pdf.ln(10)

        # Tabla de presupuesto
        self.pdf.set_font('Arial', 'B', 10)
        self.pdf.set_fill_color(240, 240, 240)

        col_widths = [50, 70, 25, 45]
        headers = ['Material', 'Descripción', 'Cant.', 'Subtotal']

        for i, header in enumerate(headers):
            self.pdf.cell(col_widths[i], 10, header, border=1, fill=True, align='C')
        self.pdf.ln()

        self.pdf.set_font('Arial', '', 9)

        for _, row in presupuesto_df.iterrows():
            self.pdf.cell(col_widths[0], 8, str(row['Material'])[:30], border=1)
            self.pdf.cell(col_widths[1], 8, str(row['Detalle'])[:45], border=1)
            self.pdf.cell(col_widths[2], 8, f"{row['Cantidad']} {row['Unidad']}", border=1, align='C')
            self.pdf.cell(col_widths[3], 8, f"RD$ {row['Subtotal']:,.2f}", border=1, align='R')
            self.pdf.ln()

        # Total
        self.pdf.ln(5)
        self.pdf.set_font('Arial', 'B', 12)
        self.pdf.set_fill_color(200, 220, 255)
        self.pdf.cell(145, 10, '', border=0)
        self.pdf.cell(45, 10, 'TOTAL:', border=1, fill=True, align='R')
        self.pdf.cell(20, 10, f"RD$ {total:,.2f}", border=1, fill=True, align='R', ln=True)

        # Notas
        self.pdf.ln(10)
        self.pdf.set_font('Arial', 'I', 8)
        self.pdf.set_text_color(100, 100, 100)
        self.pdf.multi_cell(190, 5,
            'Nota: Esta cotización es estimada y puede variar según especificaciones finales. '
            'Precios válidos por 15 días. No incluye mano de obra ni transporte.')

        return self.pdf.output(dest='S').encode('latin-1')


def create_download_link(pdf_content: bytes, filename: str, button_text: str = "📥 Descargar PDF") -> str:
    b64 = base64.b64encode(pdf_content).decode()
    return f'''
    <a href="data:application/pdf;base64,{b64}" download="{filename}">
        <button style="width:100%; border-radius:10px; background-color:#28a745;
                       color:white; padding:15px; border:none; cursor:pointer;
                       font-size:16px; font-weight:bold;">{button_text}</button>
    </a>
    '''

def initialize_gemini(api_key: str) -> Optional[any]:
    if not api_key:
        return None
    try:
        genai.configure(api_key=api_key)
        return genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        st.error(f"Error configurando Gemini: {e}")
        return None


def get_gemini_api_key_from_config() -> str:
    # Prioridad: secrets.toml -> env var -> vacío
    try:
        k = st.secrets.get("gemini", {}).get("api_key", "")
        if k:
            return str(k)
    except Exception:
        pass
    return os.getenv("GEMINI_API_KEY", "") or ""

def get_fal_key_from_config() -> str:
    try:
        k = st.secrets.get("fal", {}).get("api_key", "")
        if k:
            return str(k)
    except Exception:
        pass
    return os.getenv("FAL_KEY", "") or ""

def get_luma_key_from_config() -> str:
    try:
        k = st.secrets.get("luma", {}).get("api_key", "")
        if k:
            return str(k)
    except Exception:
        pass
    return os.getenv("LUMA_API_KEY", "") or ""

def init_text_design_state():
    """Inicializa valores seguros para el asistente Text-to-Design."""
    if "text_design_params" not in st.session_state:
        st.session_state["text_design_params"] = dict(DEFAULT_TEXT_DESIGN_PARAMS)
    if "text_design_raw" not in st.session_state:
        st.session_state["text_design_raw"] = ""
    if "url_imagen" not in st.session_state:
        st.session_state["url_imagen"] = None
    if "url_video" not in st.session_state:
        st.session_state["url_video"] = None


def render_text_design_assistant(context_key: str):
    """
    Renderiza el asistente de texto libre.

    El asistente solo prellena parámetros; no modifica las fórmulas de cálculo.
    """
    init_text_design_state()
    api_key_default = get_gemini_api_key_from_config()
    fal_key_default = get_fal_key_from_config()
    luma_key_default = get_luma_key_from_config()

    with st.expander("✨ ¿No tienes planos? Diseña el concepto con IA", expanded=False):
        st.caption("Describe la vivienda y la IA estimará parámetros editables para el presupuesto, además de generar un render 3D y video si provees las claves de Fal y Luma.")
        descripcion = st.text_area(
            "Describe tu idea de vivienda",
            placeholder="Ej: Casa moderna de 2 niveles en Samaná, 3 habitaciones, terraza, ventanales amplios...",
            key=f"text_design_desc_{context_key}",
        )
        
        col_keys1, col_keys2, col_keys3 = st.columns(3)
        with col_keys1:
            api_key = st.text_input("Gemini API Key (Requerido)", value=api_key_default, type="password", key=f"text_design_api_key_{context_key}")
        with col_keys2:
            fal_key = st.text_input("Fal.ai Key (Para Imagen)", value=fal_key_default, type="password", key=f"text_design_fal_key_{context_key}")
        with col_keys3:
            luma_key = st.text_input("Luma AI Key (Para Video)", value=luma_key_default, type="password", key=f"text_design_luma_key_{context_key}")

        if st.button("Generar Concepto y Medios Visuales", key=f"text_design_btn_{context_key}", use_container_width=True):
            if not descripcion.strip():
                st.warning("Escribe una descripción corta de la vivienda.")
                return
            if not api_key:
                st.warning("Configura tu Gemini API Key en Streamlit Secrets o pégala aquí.")
                return

            # 1. Extraer dimensiones con Gemini
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel("gemini-1.5-flash")
                with st.spinner("🧠 Interpretando tu idea y calculando dimensiones..."):
                    params, raw = analyze_text_design_with_gemini(model, descripcion)
                st.session_state["text_design_raw"] = raw
            except Exception as e:
                st.error(f"No pude consultar Gemini: {e}")
                return

            if not params:
                st.warning("La IA no devolvió un JSON confiable. Ajusta la descripción e intenta otra vez.")
                return

            # Actualizar estado para la app
            st.session_state["text_design_params"] = params
            st.session_state["calc_area_m2"] = float(params["area_m2"])
            st.session_state["plan_area_m2"] = float(params["area_m2"])
            st.session_state["plan_niveles"] = int(params["niveles"])
            st.session_state["plan_perimetro_m"] = float(params["perimetro_m"])
            st.session_state["plan_altura_muro_m"] = float(params["altura_muro_m"])
            st.session_state["plan_espesor_muro_m"] = float(params["espesor_muro_m"])
            st.session_state["calidad_terminados"] = params.get("calidad_terminados", "media")
            st.session_state["plan_params"] = {
                "area_m2": params["area_m2"],
                "niveles": params["niveles"],
                "perimetro_m": params["perimetro_m"],
                "altura_muro_m": params["altura_muro_m"],
                "espesor_muro_m": params["espesor_muro_m"],
                "calidad_terminados": params.get("calidad_terminados", "media"),
                "observaciones": params.get("observaciones", ""),
            }
            
            # 2. Generar Imagen con Fal.ai
            if fal_key:
                with st.spinner("🖼️ Generando render de fachada fotorrealista..."):
                    image_url = generate_facade_image_fal(descripcion, fal_key)
                    if image_url:
                        st.session_state["url_imagen"] = image_url
                        
                        # 3. Generar Video con Luma si hay imagen y llave de Luma
                        if luma_key:
                            with st.spinner("🎥 Generando recorrido virtual en video (puede tomar un par de minutos)..."):
                                video_url = generate_video_luma(image_url, descripcion, luma_key)
                                if video_url:
                                    st.session_state["url_video"] = video_url
                                else:
                                    st.warning("No se pudo generar el video cinematográfico.")
                    else:
                        st.warning("No se pudo generar el render de fachada.")

            st.success("¡Concepto generado con éxito! Revisa los resultados a continuación.")

    # Mostrar medios generados fuera del expander
    if st.session_state.get("url_imagen") or st.session_state.get("url_video"):
        st.subheader("✨ Visualización del Concepto IA")
        col_media1, col_media2 = st.columns(2)
        with col_media1:
            if st.session_state.get("url_imagen"):
                st.image(st.session_state["url_imagen"], caption="Render de Fachada (Fal.ai)", use_column_width=True)
        with col_media2:
            if st.session_state.get("url_video"):
                st.video(st.session_state["url_video"])


def estimate_build_time_days(area_m2: float, productividad_m2_dia: float, min_days: float = 1.0) -> float:
    if productividad_m2_dia <= 0:
        return float("nan")
    return max(min_days, area_m2 / productividad_m2_dia)


def estimate_foundation_volume_m3(area_m2: float, metodo: str) -> float:
    """
    Estimación rápida para comparar métodos.
    - Tradicional suele requerir mayor cimentación por peso.
    """
    base = area_m2 * 0.15
    metodo = (metodo or "").lower()
    if "tradicional" in metodo:
        return base * 1.15
    if "vigas h" in metodo or "isotex" in metodo or "icf" in metodo:
        return base * 1.00
    return base


def calc_h_beams_kg(area_m2: float, perimetro_m: float, beam_spacing_m: float, kg_per_m: float) -> float:
    """
    Modelo paramétrico simple: longitud total de vigas ≈ (perímetro) + (2 * área/espaciamiento).
    Es una aproximación razonable para una retícula básica.
    """
    if beam_spacing_m <= 0 or kg_per_m <= 0:
        return 0.0
    total_len_m = max(0.0, float(perimetro_m)) + 2.0 * (float(area_m2) / float(beam_spacing_m))
    return max(0.0, total_len_m * float(kg_per_m))


# ============================================================================
# RENDERIZADO DEL ENTORNO WEB INTERACTIVO
# ============================================================================

def sincronizar_parametros_globales(datos: dict, origen: str):
    """Sincroniza métricas extraídas (canvas o Gemini) al estado global de la sesión."""
    if not datos:
        return
    st.success(f"🔄 Sincronizando métricas desde: {origen}")
    if datos.get("area_m2"):
        st.session_state["calc_area_m2"] = float(datos["area_m2"])
    if datos.get("perimetro_m"):
        st.session_state["calc_perimetro_m"] = float(datos["perimetro_m"])


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
    df_gris, df_term = BudgetCalculatorLite.calcular_presupuesto_completo(area, "Paneles Isotex", precios)

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


def pagina_team():
    """Página de presentación del team constructor"""

    st.markdown("""
    <div class="main-header">
        <h1 style="margin:0;">👷 Nuestro Team de Construcción</h1>
        <p style="margin:10px 0 0 0; font-size:1.2rem;">Expertos en Construcción con Poliestireno Expandido en República Dominicana</p>
    </div>
    """, unsafe_allow_html=True)

    # Información del team
    col_team1, col_team2 = st.columns([2, 1])

    with col_team1:
        st.markdown("""
        <div class="team-card">
        <h3>🏆 Experiencia y Profesionalismo</h3>
        <p>Somos un equipo de constructores dominicanos con experiencia en el sistema de
        poliestireno expandido. Entendemos las necesidades específicas de construcción
        en nuestro país y ofrecemos soluciones adaptadas al clima y condiciones de RD.</p>

        <h4>✅ Nuestros Servicios:</h4>
        <ul>
            <li>Asesoría técnica personalizada</li>
            <li>Cálculo estructural y de materiales</li>
            <li>Supervisión de obra</li>
            <li>Capacitación a albañiles y maestros</li>
            <li>Ejecución completa de proyectos</li>
        </ul>
        </div>
        """, unsafe_allow_html=True)

    with col_team2:
        st.markdown("""
        <div class="team-card" style="text-align:center;">
            <div style="font-size:4rem;">📞</div>
            <h4>Contáctanos</h4>
            <p><strong>Teléfono:</strong><br>809-XXX-XXXX</p>
            <p><strong>Email:</strong><br>info@tuempresa.com</p>
            <p><strong>Ubicación:</strong><br>Santo Domingo, RD</p>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # Galería de proyectos
    st.markdown("### 🏠 Proyectos Realizados")

    col_gal1, col_gal2, col_gal3 = st.columns(3)

    with col_gal1:
        st.image("https://images.unsplash.com/photo-1590059390239-03c9e7064e92?w=400",
                 caption="Vivienda Unifamiliar - 150m²", use_container_width=True)

    with col_gal2:
        st.image("https://images.unsplash.com/photo-1582268611958-ebfd161ef9cf?w=400",
                 caption="Edificio de Apartamentos", use_container_width=True)

    with col_gal3:
        st.image("https://images.unsplash.com/photo-1503387762-592deb58ef4e?w=400",
                 caption="Local Comercial", use_container_width=True)

    st.divider()

    # Testimonios (placeholder)
    st.markdown("### 💬 Lo Que Dicen Nuestros Clientes")

    st.markdown("""
    <div class="info-card">
        <em>"Construí mi vivienda con el sistema Isotex y estoy muy satisfecho. La casa quedó
        más fresca y el ahorro en el aire acondicionado es notable. El team fue muy profesional."</em>
        <br><strong>- Juan P., Santo Domingo</strong>
    </div>

    <div class="info-card">
        <em>"Como ingeniero, estaba escéptico al principio. Pero después de ver los resultados
        y los cálculos estructurales, quedé convencido. Es un sistema válido y eficiente."</em>
        <br><strong>- Arq. María G., Santiago</strong>
    </div>
    """, unsafe_allow_html=True)
# ============================================================================
# PASO 1: INTEGRACIÓN DE CANVAS GEOMÉTRICO Y VISIÓN IA
# ============================================================================

def sincronizar_parametros_globales(datos: dict, origen: str):
    """
    Inyecta de forma segura las dimensiones detectadas o calculadas
    en el session_state para que el calculador de presupuestos las use.
    """
    if not datos:
        return

    st.success(f"🔄 Parámetros actualizados automáticamente desde: **{origen}**")
    
    # Mapeo seguro con fallback para evitar sobreescritura con None
    if datos.get("area_m2") is not None:
        st.session_state["calc_area_m2"] = float(datos["area_m2"])
    if datos.get("perimetro_m") is not None:
        st.session_state["calc_perimetro_m"] = float(datos["perimetro_m"])
    if datos.get("niveles") is not None:
        st.session_state["calc_niveles"] = int(datos["niveles"])
    if datos.get("altura_muro_m") is not None:
        st.session_state["calc_altura_muro_m"] = float(datos["altura_muro_m"])
    if datos.get("espesor_muro_m") is not None:
        st.session_state["calc_espesor_muro_m"] = float(datos["espesor_muro_m"])


def render_modulo_vision_y_canvas(modelo_gemini):
    """
    Pestaña interactiva de análisis de planos y dibujo geométrico.
    """
    st.subheader("📐 Extracción Geométrica Avanzada y Visión Artificial")
    
    col_izq, col_der = st.columns([1, 2])
    
    with col_izq:
        st.markdown("### 🛠️ Cargar Documento")
        archivo_plano = st.file_uploader(
            "Sube el plano del proyecto (PDF o Imagen)", 
            type=["png", "jpg", "jpeg", "pdf"],
            key="uploader_planos"
        )
        
        imagen_pil = None
        if archivo_plano:
            bytes_data = archivo_plano.read()
            if archivo_plano.name.lower().endswith(".pdf"):
                with st.spinner("📄 Convirtiendo primera página del PDF a imagen..."):
                    imagen_pil = pdf_first_page_to_image(bytes_data, dpi=150)
            else:
                imagen_pil = Image.open(BytesIO(bytes_data)).convert("RGB")
        
        # Botón para activar análisis de Gemini 1.5
        if imagen_pil and modelo_gemini:
            if st.button("🧠 Analizar Estructura con Gemini IA", use_container_width=True):
                with st.spinner("Consultando especificaciones del plano..."):
                    # Forzamos las reglas e inferencia limpia
                    data_json, raw_text = analyze_plan_image_with_gemini(modelo_gemini, imagen_pil)
                    
                    if data_json:
                        st.json(data_json)
                        sincronizar_parametros_globales(data_json, origen="Gemini Vision IA")
                    else:
                        st.warning("La IA no detectó cotas o escalas explícitas en el plano. Proceda con la calibración manual.")
                        if raw_text:
                            with st.expander("Ver diagnóstico crudo de la IA"):
                                st.text(raw_text)

    with col_der:
        st.markdown("### ✏️ Calibración de Escala y Trazado de Polígonos")
        
        if imagen_pil:
            if st_canvas is None:
                st.error("El componente `streamlit-drawable-canvas` no está instalado.")
                return
                
            st.caption("1. Dibuja una línea sobre una cota conocida para calibrar. 2. Traza el polígono perimetral.")
            
            col_cota1, col_cota2 = st.columns(2)
            with col_cota1:
                herramienta = st.selectbox("Herramienta", ["line", "polygon"], index=0, key="canvas_tool")
            with col_cota2:
                longitud_real_m = st.number_input("Longitud real de la línea de calibración (m)", min_value=0.1, value=1.0, step=0.5)

            # Renderizado del lienzo interactivo
            ancho_pantalla = 700
            w, h = imagen_pil.size
            alto_proporcional = int((ancho_pantalla / w) * h)
            imagen_redimensionada = imagen_pil.resize((ancho_pantalla, alto_proporcional))

            canvas_result = st_canvas(
                fill_color="rgba(30, 60, 114, 0.3)",
                stroke_width=3,
                stroke_color="#1e3c72",
                background_image=imagen_redimensionada,
                height=alto_proporcional,
                width=ancho_pantalla,
                drawing_mode=herramienta,
                key="canvas_planos",
                update_streamlit=True
            )

            # Procesamiento matemático de las geometrías dibujadas
            if canvas_result.json_data and "objects" in canvas_result.json_data:
                objetos = canvas_result.json_data["objects"]
                
                # Calcular escala en metros/píxel (m/px) usando la primera línea dibujada
                m_por_px = scale_from_canvas_line(objetos, longitud_real_m)
                
                if m_por_px:
                    st.info(f"📐 Factor de escala calculado: **{m_por_px:.5f} m/px**")
                    
                    # Extraer el primer polígono dibujado por el usuario
                    puntos_poligono = polygon_from_canvas(objetos)
                    
                    if puntos_poligono:
                        area_px2, perimetro_px = polygon_area_perimeter(puntos_poligono)
                        
                        # Conversión métrica real usando el factor de escala
                        area_m2_real = area_px2 * (m_por_px ** 2)
                        perimetro_m_real = perimetro_px * m_por_px
                        
                        st.metric("Área Calculada (Shoelace)", f"{area_m2_real:.2f} m²")
                        st.metric("Perímetro Calculado", f"{perimetro_m_real:.2f} m")
                        
                        # Guardar temporalmente en un botón para confirmación del ingeniero
                        if st.button("📥 Aplicar Mediciones del Canvas al Presupuesto", use_container_width=True):
                            datos_geometria = {
                                "area_m2": area_m2_real,
                                "perimetro_m": perimetro_m_real
                            }
                            sincronizar_parametros_globales(datos_geometria, origen="Trazado Geométrico Manual")
        else:
            st.info("Por favor, cargue un plano arquitectónico en el panel izquierdo para habilitar el Canvas de medición.")


def pagina_calculadora():
    """Página principal de cálculo de presupuestos"""

    st.markdown("""
    <div class="main-header">
        <h1 style="margin:0;">🧮 Calculadora de Presupuesto</h1>
        <p style="margin:10px 0 0 0;">Obra Gris + Obra Terminada con Precios de República Dominicana</p>
    </div>
    """, unsafe_allow_html=True)

    api_key_default = get_gemini_api_key_from_config()
    modelo_gemini = initialize_gemini(api_key_default)
    render_modulo_vision_y_canvas(modelo_gemini)

    st.divider()

    # Barra lateral de configuración
    with st.sidebar:
        st.markdown("### 📋 Datos del Proyecto")
        render_text_design_assistant("calculadora")
        text_design_params = st.session_state.get("text_design_params", DEFAULT_TEXT_DESIGN_PARAMS)

        cliente = st.text_input("👤 Nombre del Cliente", "Proyecto Residencial")
        
        area_default = st.session_state.get("calc_area_m2", float(text_design_params.get("area_m2", 120.0)))
        m2_in = st.number_input(
            "📐 Área (m²)",
            value=area_default,
            min_value=10.0,
            max_value=10000.0,
        )
        st.session_state["calc_area_m2"] = m2_in

        st.subheader("Configuración Estructural del Proyecto")

        sistema_seleccionado = st.selectbox(
            "Sistema Constructivo de Cerramiento", 
            ["Paneles Isotex", "ICF Proform"],
            key="sistema_seleccionado"
        )

        # Variable Opcional Clave Consensusada: Vigas H como alternativa recomendada
        usar_vigas_h = st.toggle(
            "💡 Incorporar Pórticos en Vigas H (Acero A36)",
            value=False,
            key="usar_vigas_h",
            help="Habilita una estructura combinada de vigas de acero estructural con cerramientos de EPS. Incrementa velocidad de obra gris y reduce peso en cimientos."
        )

        calidad_terminados = st.select_slider(
            "Clase Social / Nivel de Acabados",
            options=["economica", "media", "alta", "lujo"],
            value="media",
            key="calidad_terminados",
            format_func=lambda x: {"economica": "Baja (Económica)", "media": "Media (Residencial)", "alta": "Alta (Premium)", "lujo": "Lujo / Exclusivo"}[x]
        )

        zona_riesgo = st.selectbox(
            "🌪️ Zona de Riesgo Estructural (Sismo/Huracán RD)",
            ["Moderado (Base)", "Alto (Falla Septentrional/Suroeste)", "Muy Alto (Ruta Huracanes Este)"],
            help="Ajusta la densidad de acero y dimensionamiento de cimientos según el código sísmico y de vientos de la República Dominicana."
        )

        st.divider()

        st.markdown("### 💲 Precios (Pricebook)")
        pricebook = Pricebook(path=os.path.join("data", "pricebook.json"))
        precios_actuales = pricebook.load()
        with st.expander("Editar precios", expanded=False):
            st.caption("Estos precios se guardan localmente en `data/pricebook.json`.")
            df_prices = (
                pd.DataFrame(
                    [{"Clave": k, "Precio_RD$": float(v)} for k, v in precios_actuales.items()]
                )
                .sort_values("Clave")
                .reset_index(drop=True)
            )
            edited = st.data_editor(
                df_prices,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Clave": st.column_config.TextColumn(disabled=True),
                    "Precio_RD$": st.column_config.NumberColumn(min_value=0.0, step=1.0, format="%.2f"),
                },
            )
            col_p1, col_p2 = st.columns(2)
            with col_p1:
                if st.button("💾 Guardar precios", use_container_width=True):
                    nuevos = {row["Clave"]: float(row["Precio_RD$"]) for _, row in edited.iterrows()}
                    pricebook.save(nuevos)
                    st.success("✅ Precios guardados")
                    st.rerun()
            with col_p2:
                if st.button("↩️ Restablecer a default", use_container_width=True):
                    pricebook.save(precios_actuales)  # asegura archivo; luego se borra abajo
                    try:
                        if os.path.exists(pricebook.path):
                            os.remove(pricebook.path)
                    except Exception:
                        pass
                    st.success("✅ Restablecido (se usará el default)")
                    st.rerun()

        st.divider()
        st.markdown("### ⏱️ Productividad (m²/día)")
        prod_trad = st.number_input("Tradicional", min_value=1.0, max_value=500.0, value=12.0, step=1.0)
        prod_eps = st.number_input("EPS/Isotex/ICF", min_value=1.0, max_value=800.0, value=25.0, step=1.0)

        st.divider()

        # Gestión
        st.markdown("### 📁 Gestión")
        project_manager = ProjectManager()

        if st.button("💾 Guardar Proyecto"):
            project_data = {
                'cliente': cliente,
                'area': m2_in,
                'calidad': calidad_terminados,
                'sistema': sistema_seleccionado,
                'opcion_vigas': usar_vigas_h,
                'zona_riesgo': zona_riesgo
            }
            project_id = hashlib.md5(f"{cliente}{datetime.now().isoformat()}".encode()).hexdigest()[:8]
            project_manager.save_project(project_id, project_data)
            st.success("✅ Proyecto guardado correctamente en la base de datos.")

    # Calcular presupuestos
    # Inyecta el pricebook (editable) al motor de cálculo.
    obra_gris_df, obra_terminada_df = BudgetCalculator.calcular_presupuesto_completo(
        m2=m2_in,
        sistema=sistema_seleccionado,
        precios=precios_actuales,
        incluir_vigas=usar_vigas_h,
        calidad_terminados=calidad_terminados,
        zona_riesgo=zona_riesgo
    )

    total_obra_gris = obra_gris_df['Subtotal'].sum()
    total_obra_terminada = obra_terminada_df['Subtotal'].sum()
    total_general = total_obra_gris + total_obra_terminada

    # Métricas
    st.markdown("### 💰 Resumen de Costos")

    col_m1, col_m2, col_m3, col_m4 = st.columns(4)

    with col_m1:
        st.metric(
            label="Obra Gris",
            value=f"RD$ {total_obra_gris:,.2f}",
            delta=f"RD$ {total_obra_gris/m2_in:,.0f}/m²"
        )

    with col_m2:
        st.metric(
            label="Obra Terminada",
            value=f"RD$ {total_obra_terminada:,.2f}",
            delta=f"RD$ {total_obra_terminada/m2_in:,.0f}/m²"
        )

    with col_m3:
        st.metric(
            label="Total General",
            value=f"RD$ {total_general:,.2f}",
            delta=f"RD$ {total_general/m2_in:,.0f}/m²"
        )

    with col_m4:
        comparacion = BudgetCalculator.comparar_sistemas(m2_in, precios_actuales, sistema_seleccionado, usar_vigas_h, calidad_terminados)
        ahorro_pct = comparacion['ahorro']['porcentaje']
        st.metric(
            label="Ahorro vs Tradicional",
            value=f"{ahorro_pct:.1f}%",
            delta=f"RD$ {comparacion['ahorro']['dinero']:,.0f}"
        )

    st.markdown("### ⏱️ Tiempo estimado (productividad)")
    col_t1, col_t2, col_t3 = st.columns(3)
    with col_t1:
        st.metric("Tradicional", f"{estimate_build_time_days(m2_in, prod_trad):.1f} días", f"{prod_trad:.0f} m²/día")
    with col_t2:
        st.metric("Sistema EPS/ICF", f"{estimate_build_time_days(m2_in, prod_eps):.1f} días", f"{prod_eps:.0f} m²/día")
    with col_t3:
        delta_days = estimate_build_time_days(m2_in, prod_trad) - estimate_build_time_days(m2_in, prod_eps)
        st.metric("Ahorro de tiempo", f"{max(0.0, delta_days):.1f} días", "más rápido")

    st.divider()

    # Tablas de presupuesto
    tab_gris, tab_term, tab_comp = st.tabs(["🏗️ Obra Gris", "🎨 Obra Terminada", "📊 Comparativa"])

    with tab_gris:
        st.markdown("##### Materiales de Obra Gris")

        df_display = obra_gris_df.copy()
        df_display['P_Unitario'] = df_display['P_Unitario'].apply(lambda x: f"RD$ {x:,.2f}")
        df_display['Subtotal'] = df_display['Subtotal'].apply(lambda x: f"RD$ {x:,.2f}")

        st.dataframe(df_display, use_container_width=True, hide_index=True)

        # Gráfico
        fig_pie = go.Figure(data=[go.Pie(
            labels=obra_gris_df.groupby('Categoria')['Subtotal'].sum().index,
            values=obra_gris_df.groupby('Categoria')['Subtotal'].sum().values,
            hole=0.4
        )])
        fig_pie.update_layout(title='Distribución Obra Gris', height=400)
        st.plotly_chart(fig_pie, use_container_width=True)

    with tab_term:
        st.markdown("##### Materiales de Obra Terminada")

        df_display = obra_terminada_df.copy()
        df_display['P_Unitario'] = df_display['P_Unitario'].apply(lambda x: f"RD$ {x:,.2f}")
        df_display['Subtotal'] = df_display['Subtotal'].apply(lambda x: f"RD$ {x:,.2f}")

        st.dataframe(df_display, use_container_width=True, hide_index=True)

    with tab_comp:
        st.markdown("##### Comparativa Isotex vs Tradicional")

        comparacion = BudgetCalculator.comparar_sistemas(m2_in, precios_actuales, sistema_seleccionado, usar_vigas_h, calidad_terminados)

        col_c1, col_c2 = st.columns(2)

        with col_c1:
            st.markdown(f"""
            #### Isotex/ICF
            - **Costo Total:** RD$ {comparacion['isotex']['costo_total']:,.0f}
            - **Costo/m²:** RD$ {comparacion['isotex']['costo_m2']:,.0f}
            - **Tiempo:** {comparacion['isotex']['tiempo_dias']:.0f} días
            - **Peso:** {comparacion['isotex']['peso_kg']:,.0f} kg
            """)

        with col_c2:
            st.markdown(f"""
            #### Tradicional
            - **Costo Total:** RD$ {comparacion['tradicional']['costo_total']:,.0f}
            - **Costo/m²:** RD$ {comparacion['tradicional']['costo_m2']:,.0f}
            - **Tiempo:** {comparacion['tradicional']['tiempo_dias']:.0f} días
            - **Peso:** {comparacion['tradicional']['peso_kg']:,.0f} kg
            """)

    # Módulo de Financiamiento
    st.divider()
    st.markdown("### 🏦 Opciones de Financiamiento")
    
    col_fin1, col_fin2, col_fin3 = st.columns(3)
    with col_fin1:
        plazo_anos = st.slider("Plazo del Préstamo (Años)", min_value=1, max_value=30, value=20)
    with col_fin2:
        tasa_interes = st.slider("Tasa de Interés Anual (%)", min_value=1.0, max_value=25.0, value=12.0, step=0.5)
    with col_fin3:
        inicial_pct = st.slider("Inicial (%)", min_value=10, max_value=50, value=20, step=5)
    
    monto_financiar = total_general * (1 - inicial_pct/100)
    resultado_fin = AnalisisFinanciero.calcular_costo_financiamiento(
        monto=monto_financiar, 
        tasa_anual=tasa_interes/100, 
        plazo_meses=plazo_anos*12
    )
    
    col_res1, col_res2, col_res3 = st.columns(3)
    col_res1.metric("Inicial Requerido", f"RD$ {total_general * (inicial_pct/100):,.0f}")
    col_res2.metric("Monto a Financiar", f"RD$ {monto_financiar:,.0f}")
    col_res3.metric("Cuota Mensual Estimada", f"RD$ {resultado_fin['cuota_mensual']:,.0f}")

    # Bloque WOW + Lead Capture
    st.info("💡 **¿Listo para construir?** Déjanos tus datos y un asesor te contactará para llevar este proyecto a la realidad.")
    with st.expander("📝 Solicitud de Asesoría"):
        with st.form("lead_presupuesto"):
            nombre_l = st.text_input("Nombre Completo")
            celular_l = st.text_input("Celular")
            if st.form_submit_button("Enviar Solicitud"):
                st.success(f"Gracias {nombre_l}, te contactaremos pronto.")

    # Exportación
    st.divider()
    st.markdown("##### 📥 Exportar y Compartir")

    col_exp1, col_exp2, col_exp3 = st.columns(3)

    with col_exp1:
        if st.button("📄 Generar PDF Completo", use_container_width=True):
            pdf_gen = PDFGenerator()
            datos = {'area': m2_in, 'sistema': sistema_seleccionado, 'cliente': cliente}
            pdf_bytes = pdf_gen.generar_propuesta(cliente, datos, obra_gris_df, total_general)
            st.markdown(
                create_download_link(pdf_bytes, f"Presupuesto_{cliente.replace(' ', '_')}.pdf"),
                unsafe_allow_html=True
            )

    with col_exp2:
        from urllib.parse import quote
        wa_text = (
            f"Hola, soy {cliente}.\n\n"
            f"Solicito información sobre mi presupuesto:\n"
            f"  📐 Sistema: {sistema_seleccionado}\n"
            f"  📏 Área: {m2_in:.0f} m²\n"
            f"  💰 Costo Total: RD$ {total_general:,.0f}\n"
            f"  🏦 Cuota mensual estimada: RD$ {resultado_fin['cuota_mensual']:,.0f}\n\n"
            f"Generado por IsoSmart Titanium."
        )
        wa_url = f"https://api.whatsapp.com/send?text={quote(wa_text)}"
        st.markdown(
            f'<a href="{wa_url}" target="_blank">'
            f'<button style="width:100%; border-radius:10px; background-color:#25D366; color:white; '
            f'padding:15px; border:none; cursor:pointer; font-size:16px; font-weight:bold;">'
            f'💬 Enviar por WhatsApp</button></a>',
            unsafe_allow_html=True
        )

    with col_exp3:
        if st.button("📊 Exportar Excel", use_container_width=True):
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                obra_gris_df.to_excel(writer, sheet_name='Obra Gris', index=False)
                obra_terminada_df.to_excel(writer, sheet_name='Obra Terminada', index=False)
            output.seek(0)
            b64 = base64.b64encode(output.getvalue()).decode()
            st.markdown(
                f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" '
                f'download="Presupuesto_Completo_{cliente.replace(" ", "_")}.xlsx">'
                f'<button style="width:100%; border-radius:10px; background-color:#27ae60; color:white; '
                f'padding:15px; border:none; cursor:pointer; font-size:16px; font-weight:bold;">'
                f'📊 Descargar Excel</button></a>',
                unsafe_allow_html=True
            )

    st.markdown("##### 📧 Enviar por Correo Electrónico")
    email_dest = st.text_input("Correo electrónico del cliente", placeholder="cliente@ejemplo.com", key="email_input")
    if st.button("✉️ Enviar Presupuesto PDF", use_container_width=True):
        if email_dest:
            import requests
            pdf_gen = PDFGenerator()
            datos = {'area': m2_in, 'sistema': sistema_seleccionado, 'cliente': cliente}
            pdf_bytes = pdf_gen.generar_propuesta(cliente, datos, obra_gris_df, total_general)
            
            resend_api_key = os.environ.get("RESEND_API_KEY", "")
            if resend_api_key:
                try:
                    b64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
                    headers = {
                        "Authorization": f"Bearer {resend_api_key}",
                        "Content-Type": "application/json"
                    }
                    payload = {
                        "from": "onboarding@resend.dev",
                        "to": [email_dest],
                        "subject": f"Presupuesto de Construcción - {cliente}",
                        "html": f"<p>Hola {cliente},</p><p>Adjunto encontrará su presupuesto estimado para la construcción con sistema {sistema_sel}.</p>",
                        "attachments": [
                            {
                                "filename": f"Presupuesto_{cliente}.pdf",
                                "content": b64_pdf
                            }
                        ]
                    }
                    response = requests.post("https://api.resend.com/emails", json=payload, headers=headers)
                    if response.status_code == 200:
                        st.success("✅ Correo enviado exitosamente.")
                    else:
                        st.error(f"❌ Error al enviar: {response.text}")
                except Exception as e:
                    st.error(f"❌ Excepción: {e}")
            else:
                st.warning("⚠️ Falta configurar RESEND_API_KEY en las variables de entorno.")
        else:
            st.error("Por favor ingrese un correo válido.")


def pagina_contacto():
    """Formulario de contacto y captura de leads"""

    st.markdown("""
    <div class="main-header">
        <h1 style="margin:0;">📞 Contáctanos</h1>
        <p style="margin:10px 0 0 0;">Solicita tu cotización o asesoría gratuita</p>
    </div>
    """, unsafe_allow_html=True)

    project_manager = ProjectManager()

    col_form1, col_form2 = st.columns([2, 1])

    with col_form1:
        with st.form("contacto_form", clear_on_submit=False):
            st.markdown("### 📝 Formulario de Contacto")

            nombre = st.text_input("Nombre Completo *")
            email = st.text_input("Email *")
            telefono = st.text_input("Teléfono")
            ubicacion = st.selectbox(
                "Ubicación del Proyecto",
                ["Santo Domingo", "Santiago", "Punta Cana", "La Romana",
                 "Puerto Plata", "San Pedro", "La Vega", "Otro"]
            )
            tipo_proyecto = st.selectbox(
                "Tipo de Proyecto",
                ["Vivienda Unifamiliar", "Apartamento", "Local Comercial",
                 "Edificio", "Remodelación", "Otro"]
            )
            area_estimada = st.number_input("Área Estimada (m²)", min_value=0, max_value=10000, step=10)
            mensaje = st.text_area("Mensaje o Detalles Adicionales")

            submit = st.form_submit_button("🚀 Enviar Solicitud", use_container_width=True)

            if submit:
                if nombre and email:
                    lead_data = {
                        'nombre': nombre,
                        'email': email,
                        'telefono': telefono,
                        'ubicacion': ubicacion,
                        'tipo_proyecto': tipo_proyecto,
                        'area_estimada': area_estimada,
                        'mensaje': mensaje
                    }
                    project_manager.save_lead(lead_data)
                    st.success("✅ ¡Gracias por tu mensaje! Nos pondremos en contacto pronto.")
                else:
                    st.error("❌ Por favor completa nombre y email")

    with col_form2:
        st.markdown("""
        ### 📍 Información de Contacto

        **📞 Teléfono:**
        809-XXX-XXXX

        **📧 Email:**
        info@tuempresa.com

        **📌 Ubicación:**
        Santo Domingo, República Dominicana

        **⏰ Horario:**
        Lunes - Viernes: 8:00 AM - 6:00 PM
        Sábados: 8:00 AM - 12:00 PM

        ---

        ### 🔗 Redes Sociales

        - [Facebook](#)
        - [Instagram](#)
        - [YouTube](#)
        - [LinkedIn](#)
        """)

    st.divider()

    # Mapa (placeholder)
    st.markdown("### 🗺️ Nuestra Ubicación")
    st.map([{"lat": 18.4861, "lon": -69.9312}])  # Santo Domingo


def render_pestana_configuracion_precios():
    """Pestaña administrativa para actualizar costos de materiales en tiempo real."""
    st.subheader("⚙️ Panel de Control del Libro de Precios RD")
    st.caption("Modifica los costos básicos del mercado dominicano. Los cambios afectarán los nuevos cálculos de presupuesto de forma inmediata.")

    # Instanciación del Pricebook (Usa el tuyo propio de utils.pricebook)
    ruta_preciobook = os.path.join("data", "pricebook.json")
    
    # Asegurar directorio data existente
    os.makedirs("data", exist_ok=True)
    
    # Cargamos el estado actual
    if "pricebook_obj" not in st.session_state:
        # Si tu clase Pricebook requiere inicialización con dict, adaptamos:
        st.session_state["pricebook_obj"] = Pricebook(ruta_preciobook)
    
    pb = st.session_state["pricebook_obj"]
    
    # Intentar leer los precios desde el archivo o usar fallback si está vacío
    precios_actuales = pb.get_all_prices() if hasattr(pb, 'get_all_prices') else read_json(ruta_preciobook, default={})
    
    if not precios_actuales:
        # Fallback de seguridad con tus datos por defecto si el JSON no existe
        precios_actuales = {
            "Panel_Muro": 925.00, "Panel_Techo": 1125.00, "H_3000_PSI": 7350.00,
            "H_3500_PSI": 7950.00, "Viga_H_kg": 105.00, "Acero_Varilla": 85.00,
            "Ceramica_m2": 450.00, "Pintura_galon": 1200.00, "Puerta_interior": 8500.00
        }
        write_json_atomic(ruta_preciobook, precios_actuales)

    # UI dividida por categorías de insumos para que sea cómoda de leer
    tab_cat1, tab_cat2 = st.tabs(["🏗️ Estructura y Obra Gris", "🎨 Terminaciones y Acabados"])
    
    nuevos_precios = precios_actuales.copy()
    
    with tab_cat1:
        st.markdown("#### Materiales Base e Insumos Críticos")
        col1, col2 = st.columns(2)
        with col1:
            nuevos_precios["Panel_Muro"] = st.number_input("Panel Isotex / Bloque Muro (RD$/m²)", min_value=1.0, value=float(precios_actuales.get("Panel_Muro", 925.0)))
            nuevos_precios["Panel_Techo"] = st.number_input("Panel Isotex Losa / Techo (RD$/m²)", min_value=1.0, value=float(precios_actuales.get("Panel_Techo", 1125.0)))
            nuevos_precios["Acero_Varilla"] = st.number_input("Acero de Varilla Corrugada (RD$/kg)", min_value=1.0, value=float(precios_actuales.get("Acero_Varilla", 85.0)))
        with col2:
            nuevos_precios["H_3000_PSI"] = st.number_input("Hormigón Premezclado 3000 PSI (RD$/m³)", min_value=1.0, value=float(precios_actuales.get("H_3000_PSI", 7350.0)))
            nuevos_precios["H_3500_PSI"] = st.number_input("Hormigón Premezclado 3500 PSI (RD$/m³)", min_value=1.0, value=float(precios_actuales.get("H_3500_PSI", 7950.0)))
            nuevos_precios["Viga_H_kg"] = st.number_input("Perfil de Acero Viga H (RD$/kg)", min_value=1.0, value=float(precios_actuales.get("Viga_H_kg", 105.0)))

    with tab_cat2:
        st.markdown("#### Elementos de Obra Terminada")
        col3, col4 = st.columns(2)
        with col3:
            nuevos_precios["Ceramica_m2"] = st.number_input("Revestimiento Cerámica Base (RD$/m²)", min_value=1.0, value=float(precios_actuales.get("Ceramica_m2", 450.0)))
            nuevos_precios["Pintura_galon"] = st.number_input("Pintura Vinílica Premium (RD$/galón)", min_value=1.0, value=float(precios_actuales.get("Pintura_galon", 1200.0)))
        with col4:
            nuevos_precios["Puerta_interior"] = st.number_input("Puerta Interior estándar con herraje (RD$/ud)", min_value=1.0, value=float(precios_actuales.get("Puerta_interior", 8500.0)))

    st.markdown("---")
    if st.button("💾 Guardar y Sincronizar Libro de Precios", use_container_width=True, type="primary"):
        # Guardar de forma atómica usando tus utilitarios compartidos
        if hasattr(pb, 'save_prices'):
            pb.save_prices(nuevos_precios)
        else:
            write_json_atomic(ruta_preciobook, nuevos_precios)
            
        st.session_state["precios_sincronizados"] = nuevos_precios
        st.success("¡Libro de precios actualizado con éxito! Los cambios se guardaron de forma segura en la base de datos atómica.")

    # Guardamos siempre en session_state para que el calculador lo lea sin re-leer el disco cada segundo
    if "precios_sincronizados" not in st.session_state:
        st.session_state["precios_sincronizados"] = nuevos_precios


def pagina_plano_estructura():
    """Plano -> parámetros -> estructura (vigas H) + cerramiento + comparativas"""
    st.markdown("""
    <div class="main-header">
        <h1 style="margin:0;">📐 Plano → Estructura</h1>
        <p style="margin:10px 0 0 0;">Sube un plano (imagen) y genera un modelo paramétrico para vigas H + EPS/ICF</p>
    </div>
    """, unsafe_allow_html=True)

    st.info("MVP: el análisis del plano se convierte en parámetros editables. Mientras más claras sean las cotas/escala, mejor.")

    params_default = {
        **DEFAULT_TEXT_DESIGN_PARAMS,
        "observaciones": "",
    }
    render_text_design_assistant("plano")

    with st.sidebar:
        st.markdown("### 🤖 IA (opcional)")
        api_key_default = get_gemini_api_key_from_config()
        api_key = st.text_input("Gemini API Key", value=api_key_default, type="password")
        model_vision = None
        if api_key:
            try:
                genai.configure(api_key=api_key)
                # Modelo con visión (si está disponible en tu cuenta)
                model_vision = genai.GenerativeModel("gemini-1.5-flash")
            except Exception as e:
                st.warning(f"No pude inicializar el modelo con visión: {e}")

    upload = st.file_uploader("Sube plano (PNG/JPG/PDF).", type=["png", "jpg", "jpeg", "pdf"])

    img = None
    if upload is not None and upload.type == "application/pdf":
        pdf_bytes = upload.getvalue()
        img = pdf_first_page_to_image(pdf_bytes, dpi=150)
        if img is None:
            st.error("No pude convertir el PDF a imagen. Verifica que `PyMuPDF` esté instalado y que el PDF no esté corrupto.")
    elif upload is not None:
        img = Image.open(upload).convert("RGB")

    if img is not None:
        st.image(img, caption="Plano cargado", use_container_width=True)

        if model_vision and st.button("🧠 Analizar plano con IA", use_container_width=True):
            with st.spinner("Analizando plano..."):
                data, raw = analyze_plan_image_with_gemini(model_vision, img)
            st.session_state["plan_raw"] = raw
            if isinstance(data, dict):
                st.session_state["plan_params"] = {**params_default, **{k: v for k, v in data.items() if v is not None}}
                st.success("✅ Parámetros sugeridos por IA (revisa/ajusta abajo).")
            else:
                st.warning("No pude extraer un JSON confiable. Usa los parámetros manuales.")

        st.divider()
        st.markdown("### ✍️ Trazado sobre el plano (Opción B)")
        if st_canvas is None:
            st.error("Falta dependencia `streamlit-drawable-canvas`. Ejecuta `pip install -r requirements.txt` y reinicia la app.")
        else:
            st.caption("Paso 1: dibuja una línea sobre una medida conocida para calibrar la escala. Paso 2: dibuja un polígono del perímetro.")

            col_can1, col_can2 = st.columns(2)
            with col_can1:
                st.markdown("#### 1) Escala")
                real_len = st.number_input("Longitud real de la línea (m)", min_value=0.1, max_value=500.0, value=5.0, step=0.1)
                scale_canvas = st_canvas(
                    background_image=img,
                    height=500,
                    width=700,
                    drawing_mode="line",
                    stroke_width=3,
                    stroke_color="#00A3FF",
                    fill_color="rgba(0,0,0,0)",
                    update_streamlit=True,
                    key="scale_canvas",
                )
                objects_scale = (scale_canvas.json_data or {}).get("objects", []) if scale_canvas else []
                m_per_px = scale_from_canvas_line(objects_scale, real_len) if objects_scale else None
                if m_per_px:
                    st.success(f"Escala estimada: {m_per_px:.6f} m/px")
                else:
                    st.warning("Dibuja una línea para calcular la escala.")

            with col_can2:
                st.markdown("#### 2) Perímetro")
                per_canvas = st_canvas(
                    background_image=img,
                    height=500,
                    width=700,
                    drawing_mode="polygon",
                    stroke_width=2,
                    stroke_color="#28a745",
                    fill_color="rgba(40,167,69,0.10)",
                    update_streamlit=True,
                    key="perimeter_canvas",
                )
                objects_per = (per_canvas.json_data or {}).get("objects", []) if per_canvas else []
                poly = polygon_from_canvas(objects_per) if objects_per else None
                if poly and m_per_px:
                    area_px2, per_px = polygon_area_perimeter(poly)
                    area_m2 = area_px2 * (m_per_px ** 2)
                    per_m = per_px * m_per_px
                    st.success(f"Área (planta) ≈ {area_m2:,.2f} m² | Perímetro ≈ {per_m:,.2f} m")
                    if st.button("⬇️ Usar estos valores en el modelo", use_container_width=True):
                        merged = dict(st.session_state.get("plan_params", params_default))
                        merged["area_m2"] = float(area_m2)
                        merged["perimetro_m"] = float(per_m)
                        st.session_state["plan_params"] = merged
                        st.success("✅ Parámetros actualizados desde el trazado.")
                        st.rerun()
                elif poly and not m_per_px:
                    st.warning("Primero calibra la escala con una línea.")

            st.divider()
            st.markdown("### 🧱 Capas reales (desde tu trazado)")
            if m_per_px:
                col_layer1, col_layer2 = st.columns(2)
                with col_layer1:
                    st.markdown("#### Muros interiores (líneas)")
                    walls_canvas = st_canvas(
                        background_image=img,
                        height=500,
                        width=700,
                        drawing_mode="line",
                        stroke_width=3,
                        stroke_color="#10B981",
                        fill_color="rgba(0,0,0,0)",
                        update_streamlit=True,
                        key="walls_canvas",
                    )
                    wall_objs = (walls_canvas.json_data or {}).get("objects", []) if walls_canvas else []
                    wall_segs = extract_line_segments(wall_objs)
                    wall_len_m = sum((((a[0]-b[0])**2 + (a[1]-b[1])**2) ** 0.5) for a, b in wall_segs) * m_per_px
                    st.write(f"Longitud total muros interiores (aprox): **{wall_len_m:,.2f} m**")

                with col_layer2:
                    st.markdown("#### Puntos eléctricos / hidrosanitarios (círculos)")
                    st.caption("Dibuja círculos pequeños como marcadores (tomas, interruptores, puntos de agua).")
                    fixtures_canvas = st_canvas(
                        background_image=img,
                        height=500,
                        width=700,
                        drawing_mode="circle",
                        stroke_width=2,
                        stroke_color="#F59E0B",
                        fill_color="rgba(245,158,11,0.25)",
                        update_streamlit=True,
                        key="fixtures_canvas",
                    )
                    fix_objs = (fixtures_canvas.json_data or {}).get("objects", []) if fixtures_canvas else []
                    pts = extract_points(fix_objs)
                    st.write(f"Marcadores detectados: **{len(pts)}**")

                if st.button("💾 Guardar capas del plano en sesión", use_container_width=True):
                    st.session_state["layers"] = {
                        "m_per_px": float(m_per_px),
                        "walls_segments_px": [((float(a[0]), float(a[1])), (float(b[0]), float(b[1]))) for a, b in wall_segs],
                        "fixture_points_px": [(float(x), float(y)) for x, y in pts],
                    }
                    st.success("✅ Capas guardadas. Abre `🧱 Visor BIM 3D` para verlas.")
            else:
                st.info("Calibra primero la escala para poder convertir capas a metros.")

    params = st.session_state.get("plan_params", params_default)

    st.markdown("### 🧩 Parámetros del modelo (editables)")
    c1, c2, c3 = st.columns(3)
    with c1:
        area_m2 = st.number_input("Área construida (m²)", min_value=10.0, max_value=100000.0, value=float(params.get("area_m2") or 120.0), step=10.0)
        niveles = st.number_input("Niveles", min_value=1, max_value=20, value=int(params.get("niveles") or 1), step=1)
    with c2:
        perimetro_m = st.number_input("Perímetro estimado (m)", min_value=10.0, max_value=5000.0, value=float(params.get("perimetro_m") or 44.0), step=1.0)
        altura_muro_m = st.number_input("Altura de muro (m)", min_value=2.2, max_value=6.0, value=float(params.get("altura_muro_m") or 2.8), step=0.1)
    with c3:
        sistema = st.selectbox("Cerramiento", ["EPS", "ICF"], index=0)
        espesor_muro_m = st.number_input("Espesor muro (m)", min_value=0.08, max_value=0.30, value=float(params.get("espesor_muro_m") or 0.12), step=0.01)

    st.markdown("### 🏗️ Estructura con Vigas H (modelo paramétrico)")
    colb1, colb2, colb3 = st.columns(3)
    with colb1:
        beam_spacing = st.number_input("Espaciamiento retícula (m)", min_value=1.5, max_value=8.0, value=3.0, step=0.25)
    with colb2:
        kg_per_m = st.number_input("Peso viga (kg/m)", min_value=5.0, max_value=200.0, value=18.0, step=1.0)
    with colb3:
        prod_trad = st.number_input("Productividad tradicional (m²/día)", min_value=1.0, max_value=500.0, value=12.0, step=1.0)
        prod_eps = st.number_input("Productividad EPS/ICF (m²/día)", min_value=1.0, max_value=800.0, value=25.0, step=1.0)

    pricebook = Pricebook(path=os.path.join("data", "pricebook.json"))
    precios = pricebook.load()

    vigas_kg = calc_h_beams_kg(area_m2 * niveles, perimetro_m, beam_spacing, kg_per_m)
    costo_vigas = vigas_kg * float(precios.get("Viga_H_kg", 105.0))

    area_muros = perimetro_m * altura_muro_m * niveles
    st.metric("Acero en vigas H (estimado)", f"{vigas_kg:,.0f} kg", f"RD$ {costo_vigas:,.0f}")

    st.markdown("### 🧱 Cerramiento (EPS/ICF) + Cimientos + Comparativa")
    c_f1, c_f2, c_f3 = st.columns(3)
    with c_f1:
        vol_found_trad = estimate_foundation_volume_m3(area_m2 * niveles, "tradicional")
        st.metric("Cimientos (Tradicional)", f"{vol_found_trad:.2f} m³", "estimado")
    with c_f2:
        vol_found_sys = estimate_foundation_volume_m3(area_m2 * niveles, "vigas h + eps/icf")
        st.metric("Cimientos (EPS/ICF)", f"{vol_found_sys:.2f} m³", "estimado")
    with c_f3:
        t_trad = estimate_build_time_days(area_m2 * niveles, prod_trad)
        t_sys = estimate_build_time_days(area_m2 * niveles, prod_eps)
        st.metric("Tiempo (Tradicional vs EPS/ICF)", f"{t_trad:.1f} → {t_sys:.1f} días", f"{max(0.0, t_trad - t_sys):.1f} días menos")

    st.markdown("#### Detalle rápido del cerramiento")
    if sistema == "EPS":
        panel_m2 = area_muros * 1.05
        costo_panel = panel_m2 * float(precios.get("Panel_Muro", 925.0))
        st.write(f"- Área de muros estimada: **{area_muros:,.1f} m²**")
        st.write(f"- Paneles EPS/Isotex para cerramiento (con 5%): **{panel_m2:,.1f} m²**")
        st.write(f"- Costo estimado cerramiento: **RD$ {costo_panel:,.0f}**")
    else:
        bloques_m2 = area_muros * 0.85
        costo_icf = bloques_m2 * float(precios.get("Panel_Muro", 925.0)) * 1.15
        st.write(f"- Área de muros estimada: **{area_muros:,.1f} m²**")
        st.write(f"- Bloques ICF (equivalente m²): **{bloques_m2:,.1f} m²**")
        st.write(f"- Costo estimado cerramiento: **RD$ {costo_icf:,.0f}**")

    with st.expander("Ver respuesta cruda de IA (si aplica)", expanded=False):
        st.markdown("**Text-to-Design**")
        st.code(st.session_state.get("text_design_raw", "") or "(sin análisis por texto)")
        st.markdown("**Análisis de plano**")
        st.code(st.session_state.get("plan_raw", "") or "(sin análisis de plano)")


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
