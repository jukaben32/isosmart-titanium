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
# CLASES Y UTILIDADES
# ============================================================================

class ProjectManager:
    """Gestor de proyectos con persistencia local"""

    def __init__(self, storage_file: str = "projects_db.json"):
        self.storage_file = storage_file
        self.projects = self._load_projects()
        self.leads = self._load_leads()

    def _load_projects(self) -> Dict:
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _load_leads(self) -> List:
        leads_file = "leads_db.json"
        if os.path.exists(leads_file):
            try:
                with open(leads_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
        return []

    def save_lead(self, lead_data: Dict):
        """Guarda un lead interesado"""
        lead_data['fecha'] = datetime.now().isoformat()
        lead_data['id'] = hashlib.md5(
            f"{lead_data['nombre']}{lead_data['fecha']}".encode()
        ).hexdigest()[:8]
        self.leads.append(lead_data)
        with open("leads_db.json", 'w', encoding='utf-8') as f:
            json.dump(self.leads, f, indent=2, ensure_ascii=False)

    def save_project(self, project_id: str, data: Dict):
        self.projects[project_id] = {
            **data,
            'updated_at': datetime.now().isoformat()
        }
        with open(self.storage_file, 'w', encoding='utf-8') as f:
            json.dump(self.projects, f, indent=2, ensure_ascii=False)

    def get_project(self, project_id: str) -> Optional[Dict]:
        return self.projects.get(project_id)

    def list_projects(self) -> List[Dict]:
        return [
            {'id': k, **v} for k, v in self.projects.items()
        ]

    def delete_project(self, project_id: str):
        if project_id in self.projects:
            del self.projects[project_id]
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(self.projects, f, indent=2, ensure_ascii=False)


class BudgetCalculator:
    """Motor de cálculo de presupuestos con precios actualizables"""

    PRECIOS_BASE = {
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
        # Obra gris adicional
        "Cemento_Saco": 450.00,
        "Arena_m3": 1200.00,
        "Piedra_m3": 1100.00,
        "Ladrillounidad": 28.00,
        # Obra terminada
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
    def calcular_obra_grisa(cls, m2: float, sistema: str, incluir_vigas: bool = True) -> pd.DataFrame:
        """Calcula costos de obra gris"""
        precios = cls.PRECIOS_BASE
        area_muros = cls.calcular_area_muros(m2)
        area_techo = cls.calcular_area_techo(m2)
        desperdicio = cls.FACTORES_RENDIMIENTO["desperdicio_panel"]

        data = []

        if sistema == "Paneles Isotex":
            # Paneles
            total_muros = area_muros * (1 + desperdicio)
            data.append({
                "Categoria": "Estructura",
                "Material": "Paneles Isotex (Muros)",
                "Detalle": "Panel estructural EPS con malla electrosoldada",
                "Cantidad": round(total_muros, 2),
                "Unidad": "m²",
                "P_Unitario": precios["Panel_Muro"],
                "Subtotal": total_muros * precios["Panel_Muro"]
            })

            total_techo = area_techo * (1 + desperdicio)
            data.append({
                "Categoria": "Estructura",
                "Material": "Paneles Isotex (Techo)",
                "Detalle": "Panel aligerado para losa",
                "Cantidad": round(total_techo, 2),
                "Unidad": "m²",
                "P_Unitario": precios["Panel_Techo"],
                "Subtotal": total_techo * precios["Panel_Techo"]
            })

            # Hormigón
            vol_hormigon = cls.calcular_volumen_hormigon(area_muros + area_techo)
            vol_hormigon *= cls.FACTORES_RENDIMIENTO["desperdicio_hormigon"]
            data.append({
                "Categoria": "Hormigón",
                "Material": "Hormigón Cemex 3000 PSI",
                "Detalle": "Concreto premezclado para llenado",
                "Cantidad": round(vol_hormigon, 2),
                "Unidad": "m³",
                "P_Unitario": precios["H_3000_PSI"],
                "Subtotal": vol_hormigon * precios["H_3000_PSI"]
            })

        else:  # ICF
            data.append({
                "Categoria": "Estructura",
                "Material": "Bloques ICF Proform",
                "Detalle": "Bloques de poliestireno para encofrado",
                "Cantidad": round(area_muros * 0.85, 2),
                "Unidad": "m²",
                "P_Unitario": precios["Panel_Muro"] * 1.15,
                "Subtotal": area_muros * 0.85 * precios["Panel_Muro"] * 1.15
            })

            vol_hormigon = area_muros * 0.15
            data.append({
                "Categoria": "Hormigón",
                "Material": "Hormigón Cemex 3500 PSI",
                "Detalle": "Concreto de alta resistencia para ICF",
                "Cantidad": round(vol_hormigon, 2),
                "Unidad": "m³",
                "P_Unitario": precios["H_3500_PSI"],
                "Subtotal": vol_hormigon * precios["H_3500_PSI"]
            })

        # Cimentación (estimada)
        vol_cimentacion = m2 * 0.15  # 0.15 m³ por m² de construcción
        data.append({
            "Categoria": "Cimentación",
            "Material": "Cimentación Armada",
            "Detalle": "Zapatas y vigas de fundación",
            "Cantidad": round(vol_cimentacion, 2),
            "Unidad": "m³",
            "P_Unitario": precios["H_3000_PSI"] * 1.2,  # Incluye acero adicional
            "Subtotal": vol_cimentacion * precios["H_3000_PSI"] * 1.2
        })

        # Vigas estructurales
        if incluir_vigas:
            kg_vigas = m2 * 25
            data.append({
                "Categoria": "Acero",
                "Material": "Vigas H Estructurales",
                "Detalle": "Perfil de acero A36 para estructura",
                "Cantidad": round(kg_vigas, 2),
                "Unidad": "kg",
                "P_Unitario": precios["Viga_H_kg"],
                "Subtotal": kg_vigas * precios["Viga_H_kg"]
            })

        # Acero de refuerzo
        kg_acero, barras = cls.calcular_acero_refuerzo(m2)
        data.append({
            "Categoria": "Acero",
            "Material": "Acero de Refuerzo",
            "Detalle": f"Varillas corrugadas (~{int(barras)} barras)",
            "Cantidad": round(kg_acero, 2),
            "Unidad": "kg",
            "P_Unitario": precios["Acero_Varilla"],
            "Subtotal": kg_acero * precios["Acero_Varilla"]
        })

        return pd.DataFrame(data)

    @classmethod
    def calcular_obra_terminada(cls, m2: float, area_muros: float, calidad: str = "media") -> pd.DataFrame:
        """Calcula costos de obra terminada"""
        precios = cls.PRECIOS_BASE

        # Factores según calidad
        factores = {
            "economica": 0.8,
            "media": 1.0,
            "alta": 1.5,
            "lujo": 2.5
        }
        factor = factores.get(calidad, 1.0)

        data = []

        # Pisos
        area_piso = m2 * 0.9  # 90% del área tiene piso (el resto son muros)
        data.append({
            "Categoria": "Pisos",
            "Material": "Cerámica/Porcelanato",
            "Detalle": f"Piso calidad {calidad} (incluye pegamento y fragüe)",
            "Cantidad": round(area_piso, 2),
            "Unidad": "m²",
            "P_Unitario": precios["Ceramica_m2"] * factor,
            "Subtotal": area_piso * precios["Ceramica_m2"] * factor
        })

        # Pintura
        galones_pintura = area_muros / 12  # 1 galón rinde ~12 m² (3 manos)
        data.append({
            "Categoria": "Pintura",
            "Material": "Pintura Interior/Exterior",
            "Detalle": "Pintura vinílica calidad premium (3 manos)",
            "Cantidad": round(galones_pintura, 1),
            "Unidad": "gal",
            "P_Unitario": precios["Pintura_galon"] * factor,
            "Subtotal": galones_pintura * precios["Pintura_galon"] * factor
        })

        # Puertas
        num_puertas = max(4, int(m2 / 15))  # 1 puerta cada ~15 m²
        data.append({
            "Categoria": "Carpintería",
            "Material": "Puertas Interiores",
            "Detalle": f"{num_puertas} puertas de madera (incluye marcos y herrajes)",
            "Cantidad": num_puertas,
            "Unidad": "ud",
            "P_Unitario": precios["Puerta_interior"],
            "Subtotal": num_puertas * precios["Puerta_interior"]
        })

        # Ventanas
        area_ventanas = m2 * 0.15  # 15% del área en ventanas
        data.append({
            "Categoria": "Carpintería",
            "Material": "Ventanas de Aluminio",
            "Detalle": "Ventanas con vidrio templado",
            "Cantidad": round(area_ventanas, 1),
            "Unidad": "m²",
            "P_Unitario": precios["Ventana_aluminio_m2"],
            "Subtotal": area_ventanas * precios["Ventana_aluminio_m2"]
        })

        # Baños (asumir 1 baño cada 30 m²)
        num_banos = max(1, int(m2 / 30))
        data.append({
            "Categoria": "Baños",
            "Material": "Equipamiento de Baños",
            "Detalle": f"{num_banos} baños completos (inodoro, lavamanos, ducha, grifería)",
            "Cantidad": num_banos,
            "Unidad": "ud",
            "P_Unitario": (precios["Inodoro"] + precios["Lavamanos"] + precios["Ducha"] + precios["Griferia_bano"]) * factor,
            "Subtotal": num_banos * (precios["Inodoro"] + precios["Lavamanos"] + precios["Ducha"] + precios["Griferia_bano"]) * factor
        })

        # Cocina
        ml_gabinete = max(3, m2 / 20)  # Metros lineales de gabinete
        data.append({
            "Categoria": "Cocina",
            "Material": "Gabinetes de Cocina",
            "Detalle": f"{ml_gabinete:.1f} metros lineales de gabinetes",
            "Cantidad": round(ml_gabinete, 1),
            "Unidad": "ml",
            "P_Unitario": precios["Gabinete_cocina_ml"] * factor,
            "Subtotal": ml_gabinete * precios["Gabinete_cocina_ml"] * factor
        })

        data.append({
            "Categoria": "Cocina",
            "Material": "Mesón de Granito",
            "Detalle": "Mesón para cocina y baños",
            "Cantidad": round(ml_gabinete * 0.6, 1),
            "Unidad": "ml",
            "P_Unitario": precios["Meson_granito_ml"],
            "Subtotal": ml_gabinete * 0.6 * precios["Meson_granito_ml"]
        })

        return pd.DataFrame(data)

    @classmethod
    def calcular_presupuesto_completo(cls, m2: float, sistema: str, incluir_vigas: bool = True,
                                      calidad_terminados: str = "media") -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Retorna presupuesto de obra gris y obra terminada"""
        obra_gris = cls.calcular_obra_grisa(m2, sistema, incluir_vigas)
        area_muros = cls.calcular_area_muros(m2)
        obra_terminada = cls.calcular_obra_terminada(m2, area_muros, calidad_terminados)
        return obra_gris, obra_terminada

    @classmethod
    def comparar_sistemas(cls, m2: float) -> Dict:
        """Compara Isotex vs Construcción Tradicional"""
        # Costos Isotex
        isotex_gris, isotex_term = cls.calcular_presupuesto_completo(m2, "Paneles Isotex")
        total_isotex = isotex_gris['Subtotal'].sum() + isotex_term['Subtotal'].sum()

        # Costos Tradicional (estimado: 35-40% más caro en estructura)
        tradicional_gris = m2 * 35000  # RD$ por m² obra gris tradicional
        tradicional_term = m2 * 25000  # RD$ por m² obra terminada
        total_tradicional = tradicional_gris + tradicional_term

        # Tiempo de construcción
        tiempo_isotex = m2 * 1.5  # días por m²
        tiempo_tradicional = m2 * 2.5  # días por m²

        # Ahorro de peso (Isotex pesa ~70% menos)
        peso_tradicional = m2 * 800  # kg/m²
        peso_isotex = m2 * 250  # kg/m²

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
        return genai.GenerativeModel('gemini-pro')
    except Exception as e:
        st.error(f"Error configurando Gemini: {e}")
        return None


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

    comparacion = BudgetCalculator.comparar_sistemas(120)

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


def pagina_calculadora():
    """Página principal de cálculo de presupuestos"""

    st.markdown("""
    <div class="main-header">
        <h1 style="margin:0;">🧮 Calculadora de Presupuesto</h1>
        <p style="margin:10px 0 0 0;">Obra Gris + Obra Terminada con Precios de República Dominicana</p>
    </div>
    """, unsafe_allow_html=True)

    # Barra lateral de configuración
    with st.sidebar:
        st.markdown("### 📋 Datos del Proyecto")

        cliente = st.text_input("👤 Nombre del Cliente", "Proyecto Residencial")
        col1, col2 = st.columns(2)
        with col1:
            m2_in = st.number_input("📐 Área (m²)", value=120.0, min_value=10.0, max_value=10000.0)
        with col2:
            calidad = st.selectbox("🎨 Calidad Terminados",
                                   ["económica", "media", "alta", "lujo"])

        sistema_sel = st.selectbox(
            "🏗️ Sistema Constructivo",
            ["Paneles Isotex", "ICF Proform"],
            help="Isotex: Paneles de EPS con malla. ICF: Encofrado aislante permanente"
        )

        incluir_vigas = st.checkbox("Incluir Vigas H", value=True)

        st.divider()

        # IA
        st.markdown("### 🤖 Inteligencia Artificial")
        api_key = st.text_input("Gemini API Key", type="password")

        st.divider()

        # Gestión
        st.markdown("### 📁 Gestión")
        project_manager = ProjectManager()

        if st.button("💾 Guardar Proyecto"):
            project_data = {
                'cliente': cliente,
                'area': m2_in,
                'calidad': calidad,
                'sistema': sistema_sel,
                'opcion_vigas': incluir_vigas
            }
            project_id = hashlib.md5(f"{cliente}{datetime.now().isoformat()}".encode()).hexdigest()[:8]
            project_manager.save_project(project_id, project_data)
            st.success("✅ Proyecto guardado")

    # Calcular presupuestos
    budget_calc = BudgetCalculator()
    obra_gris_df, obra_terminada_df = budget_calc.calcular_presupuesto_completo(
        m2=m2_in,
        sistema=sistema_sel,
        incluir_vigas=incluir_vigas,
        calidad_terminados=calidad
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
        comparacion = budget_calc.comparar_sistemas(m2_in)
        ahorro_pct = comparacion['ahorro']['porcentaje']
        st.metric(
            label="Ahorro vs Tradicional",
            value=f"{ahorro_pct:.1f}%",
            delta=f"RD$ {comparacion['ahorro']['dinero']:,.0f}"
        )

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

        comparacion = budget_calc.comparar_sistemas(m2_in)

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

    # Exportación
    st.divider()
    st.markdown("##### 📥 Exportar Presupuesto")

    col_exp1, col_exp2 = st.columns(2)

    with col_exp1:
        if st.button("📄 Generar PDF Completo", use_container_width=True):
            pdf_gen = PDFGenerator()
            datos = {'area': m2_in, 'sistema': sistema_sel, 'cliente': cliente}
            pdf_bytes = pdf_gen.generar_propuesta(cliente, datos, obra_gris_df, total_general)
            st.markdown(
                create_download_link(pdf_bytes, f"Presupuesto_{cliente.replace(' ', '_')}.pdf"),
                unsafe_allow_html=True
            )

    with col_exp2:
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
            ["🏠 Inicio", "👷 Nuestro Team", "🧮 Calculadora", "📞 Contacto"],
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
    elif menu == "📞 Contacto":
        pagina_contacto()


# ============================================================================
# PUNTO DE ENTRADA
# ============================================================================

if __name__ == "__main__":
    main()
