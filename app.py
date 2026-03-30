# -*- coding: utf-8 -*-
"""
IsoSmart Titanium v4.0 - Executive Suite
Sistema Inteligente de Presupuestos y Visualización BIM
para Construcción con Poliestireno Expandido

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

# ============================================================================
# CONFIGURACIÓN DE PÁGINA Y ESTILOS
# ============================================================================

st.set_page_config(
    page_title="IsoSmart Titanium v4.0",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://github.com/jukaben32/isosmart-titanium',
        'Report a bug': 'https://github.com/jukaben32/isosmart-titanium/issues',
        'About': "# IsoSmart Titanium v4.0\nSistema profesional para construcción con poliestireno expandido"
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
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        font-weight: bold;
        padding: 0.75rem 1rem;
    }
    .download-button {
        background-color: #28a745;
        color: white;
        border: none;
        padding: 10px 20px;
        border-radius: 5px;
        cursor: pointer;
        font-size: 16px;
    }
    div[data-testid="stMetricValue"] {
        font-size: 2rem;
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

    def _load_projects(self) -> Dict:
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}

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
    }

    FACTORES_RENDIMIENTO = {
        "desperdicio_panel": 0.05,
        "desperdicio_hormigon": 0.08,
        "factor_conversion_m3": 1.10,
    }

    @classmethod
    def calcular_area_muros(cls, area_construida: float, factor: float = 2.2) -> float:
        """Calcula área de muros basada en área construida"""
        return area_construida * factor

    @classmethod
    def calcular_area_techo(cls, area_construida: float, factor: float = 1.10) -> float:
        """Calcula área de techo con factor de voladizos"""
        return area_construida * factor

    @classmethod
    def calcular_volumen_hormigon(cls, area_muros: float, espesor: float = 0.12) -> float:
        """Calcula volumen de hormigón necesario"""
        return area_muros * espesor

    @classmethod
    def calcular_acero_refuerzo(cls, area_construida: float, tipo: str = "varilla") -> Tuple[float, float]:
        """Calcula cantidad de acero de refuerzo"""
        if tipo == "varilla":
            kg_m2 = 8.5  # kg por m²
        else:  # malla
            kg_m2 = 6.0

        total_kg = area_construida * kg_m2
        total_barras = total_kg / 12  # Barras de 12kg aprox

        return total_kg, total_barras

    @classmethod
    def calcular_presupuesto(cls, m2: float, sistema: str, incluir_vigas: bool = True,
                            precios_personalizados: Optional[Dict] = None) -> pd.DataFrame:
        """Genera presupuesto detallado del proyecto"""

        precios = {**cls.PRECIOS_BASE}
        if precios_personalizados:
            precios.update(precios_personalizados)

        area_muros = cls.calcular_area_muros(m2)
        area_techo = cls.calcular_area_techo(m2)
        desperdicio = cls.FACTORES_RENDIMIENTO["desperdicio_panel"]

        data = []

        if sistema == "Paneles Isotex":
            # Paneles para muros
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

            # Paneles para techo
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

            # Hormigón para llenado
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

        else:  # ICF Proform
            # Bloques ICF
            data.append({
                "Categoria": "Estructura",
                "Material": "Bloques ICF Proform",
                "Detalle": "Bloques de poliestireno para encofrado",
                "Cantidad": round(area_muros * 0.85, 2),  # 0.85 bloques por m²
                "Unidad": "m²",
                "P_Unitario": precios["Panel_Muro"] * 1.15,
                "Subtotal": area_muros * 0.85 * precios["Panel_Muro"] * 1.15
            })

            # Hormigón
            vol_hormigon = cls.calcular_volumen_hormigon(area_muros, 0.15)
            data.append({
                "Categoria": "Hormigón",
                "Material": "Hormigón Cemex 3500 PSI",
                "Detalle": "Concreto de alta resistencia para ICF",
                "Cantidad": round(vol_hormigon, 2),
                "Unidad": "m³",
                "P_Unitario": precios["H_3500_PSI"],
                "Subtotal": vol_hormigon * precios["H_3500_PSI"]
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

        # Aditivos
        data.append({
            "Categoria": "Aditivos",
            "Material": "Aditivo Impermeabilizante",
            "Detalle": "Aditivo para concreto",
            "Cantidad": round(m2 * 0.02, 2),
            "Unidad": "gal",
            "P_Unitario": precios["Aditivo_Impermeabilizante"],
            "Subtotal": m2 * 0.02 * precios["Aditivo_Impermeabilizante"]
        })

        df = pd.DataFrame(data)
        return df


class PDFGenerator:
    """Generador de documentos PDF profesionales"""

    def __init__(self):
        self.pdf = FPDF()
        self.pdf.set_auto_page_break(auto=True, margin=15)

    def generar_propuesta(self, cliente: str, datos_proyecto: Dict,
                         presupuesto_df: pd.DataFrame, total: float) -> bytes:
        """Genera propuesta comercial en PDF"""

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
    """Crea enlace de descarga para PDF"""
    b64 = base64.b64encode(pdf_content).decode()
    return f'''
    <a href="data:application/pdf;base64,{b64}" download="{filename}">
        <button style="width:100%; border-radius:10px; background-color:#28a745;
                       color:white; padding:15px; border:none; cursor:pointer;
                       font-size:16px; font-weight:bold;">{button_text}</button>
    </a>
    '''


def initialize_gemini(api_key: str) -> Optional[any]:
    """Inicializa cliente de Gemini API"""
    if not api_key:
        return None
    try:
        genai.configure(api_key=api_key)
        return genai.GenerativeModel('gemini-pro')
    except Exception as e:
        st.error(f"Error configurando Gemini: {e}")
        return None


# ============================================================================
# INTERFAZ PRINCIPAL
# ============================================================================

def main():
    # Inicializar gestores
    project_manager = ProjectManager()
    budget_calculator = BudgetCalculator()
    pdf_generator = PDFGenerator()

    # Estado de sesión
    if 'project_id' not in st.session_state:
        st.session_state.project_id = hashlib.md5(
            datetime.now().isoformat().encode()
        ).hexdigest()[:8]

    # Encabezado principal
    st.markdown("""
    <div class="main-header">
        <h1 style="margin:0;">🏗️ IsoSmart Titanium v4.0</h1>
        <p style="margin:5px 0 0 0; opacity:0.9;">Sistema Ejecutivo de Presupuestos y Visualización BIM</p>
    </div>
    """, unsafe_allow_html=True)

    # Barra lateral
    with st.sidebar:
        st.image("https://img.icons8.com/color/96/construction.png", width=80)
        st.markdown("### 📋 Centro de Gestión")

        # Información del proyecto
        cliente = st.text_input("👤 Nombre del Cliente", "Proyecto Residencial")
        col1, col2 = st.columns(2)
        with col1:
            m2_in = st.number_input("📐 Área (m²)", value=120.0, min_value=10.0, max_value=10000.0)
        with col2:
            habitaciones = st.number_input("🛏️ Habitaciones", value=3, min_value=1, max_value=10)

        sistema_sel = st.selectbox(
            "🏗️ Sistema Constructivo",
            ["Paneles Isotex", "ICF Proform"],
            help="Isotex: Paneles de EPS con malla. ICF: Encofrado aislante permanente"
        )

        st.markdown("##### ⚙️ Opciones")
        incluir_vigas = st.checkbox("Incluir Vigas H", value=True)
        ver_elec = st.checkbox("Ver Capa Eléctrica", value=True)
        ver_san = st.checkbox("Ver Capa Sanitaria", value=True)

        st.divider()

        # Configuración de IA
        st.markdown("##### 🤖 Inteligencia Artificial")
        api_key = st.text_input("Gemini API Key", type="password",
                               help="Obtén tu key en: makersuite.google.com")

        st.divider()

        # Gestión de proyectos
        st.markdown("##### 📁 Gestión de Proyectos")
        if st.button("💾 Guardar Proyecto"):
            project_data = {
                'cliente': cliente,
                'area': m2_in,
                'habitaciones': habitaciones,
                'sistema': sistema_sel,
                'opcion_vigas': incluir_vigas
            }
            project_manager.save_project(st.session_state.project_id, project_data)
            st.success("✅ Proyecto guardado")

        if st.button("📂 Cargar Proyecto Guardado"):
            projects = project_manager.list_projects()
            if projects:
                project_options = {f"{p['cliente']} - {p.get('area', 0)}m²": p for p in projects}
                selected = st.selectbox("Selecciona proyecto", list(project_options.keys()))
                if selected:
                    proj = project_options[selected]
                    st.session_state.loaded_project = proj

        # Cargar proyecto si existe
        if hasattr(st.session_state, 'loaded_project') and st.session_state.loaded_project:
            proj = st.session_state.loaded_project
            cliente = proj.get('cliente', cliente)
            m2_in = proj.get('area', m2_in)
            sistema_sel = proj.get('sistema', sistema_sel)
            incluir_vigas = proj.get('opcion_vigas', incluir_vigas)
            del st.session_state.loaded_project

        st.divider()

        # Información
        with st.expander("ℹ️ Acerca de"):
            st.markdown("""
            **IsoSmart Titanium v4.0**

            Sistema profesional para:
            - Cálculo de presupuestos
            - Visualización BIM 3D
            - Asistencia con IA

            [GitHub Repository](https://github.com/jukaben32/isosmart-titanium)
            """)

    # Pestañas principales
    tab_bim, tab_ia, tab_presu, tab_config = st.tabs([
        "🏠 VISOR BIM 3D",
        "🤖 ASISTENTE IA",
        "💰 PRESUPUESTO",
        "⚙️ CONFIGURACIÓN"
    ])

    # ==========================================================================
    # PESTAÑA 1: VISOR BIM 3D
    # ==========================================================================
    with tab_bim:
        st.markdown("### 🏗️ Visualizador BIM Interactivo")

        # Calcular dimensiones
        ancho = m2_in ** 0.5
        alto = 3.0  # Altura estándar

        # Crear figura 3D
        fig = make_subplots(
            rows=1, cols=1,
            specs=[[{'type': 'scatter3d'}]]
        )

        # Muros estructurales (transparentes)
        x_coords = [0, ancho, ancho, 0, 0, ancho, ancho, 0]
        y_coords = [0, 0, ancho, ancho, 0, 0, ancho, ancho]
        z_coords = [0, 0, 0, 0, alto, alto, alto, alto]

        fig.add_trace(go.Mesh3d(
            x=x_coords, y=y_coords, z=z_coords,
            i=[7,0,0,0,4,4,6,6,4,0,3,2],
            j=[3,4,1,2,5,6,5,2,0,1,6,3],
            k=[0,7,2,3,6,7,1,1,5,5,7,6],
            color='rgba(100,150,200,0.3)',
            opacity=0.5,
            name="Muros Estructurales",
            showscale=False
        ))

        # Techo
        fig.add_trace(go.Mesh3d(
            x=[0, ancho, ancho, 0],
            y=[0, 0, ancho, ancho],
            z=[alto, alto, alto, alto],
            color='rgba(150,100,100,0.6)',
            name="Losa de Techo",
            showscale=False
        ))

        # Capa eléctrica
        if ver_elec:
            # Trayecto eléctrico en paredes
            elec_path_x = [0, ancho/2, ancho, ancho]
            elec_path_y = [alto-0.3, alto-0.3, alto-0.3, ancho/2]
            elec_path_z = [0, 0, 0, 0]

            fig.add_trace(go.Scatter3d(
                x=elec_path_x, y=elec_path_y, z=elec_path_z,
                mode='lines+markers',
                line=dict(color='yellow', width=8),
                marker=dict(size=4, color='yellow'),
                name="⚡ Instalación Eléctrica"
            ))

        # Capa sanitaria
        if ver_san:
            # Tubería sanitaria
            san_path_x = [ancho/2, ancho/2, ancho/4]
            san_path_y = [0, ancho/2, ancho/4]
            san_path_z = [0.1, 0.1, 0.1]

            fig.add_trace(go.Scatter3d(
                x=san_path_x, y=san_path_y, z=san_path_z,
                mode='lines+markers',
                line=dict(color='blue', width=10),
                marker=dict(size=5, color='blue'),
                name="💧 Instalación Sanitaria"
            ))

        # Pisos
        fig.add_trace(go.Mesh3d(
            x=[0, ancho, ancho, 0],
            y=[0, 0, ancho, ancho],
            z=[0, 0, 0, 0],
            color='rgba(180,180,180,0.8)',
            name="Planta Baja",
            showscale=False
        ))

        # Actualizar layout
        fig.update_layout(
            scene=dict(
                xaxis_title='Largo (m)',
                yaxis_title='Ancho (m)',
                zaxis_title='Altura (m)',
                aspectmode='data',
                bgcolor='rgba(240,240,240,0.5)'
            ),
            margin=dict(l=0, r=0, b=0, t=50),
            height=600
        )

        st.plotly_chart(fig, use_container_width=True)

        # Controles adicionales
        col_viz1, col_viz2, col_viz3 = st.columns(3)
        with col_viz1:
            if st.button("🔄 Vista Isométrica"):
                st.rerun()
        with col_viz2:
            if st.button("📐 Mostrar Dimensiones"):
                st.info(f"Dimensiones: {ancho:.2f}m x {ancho:.2f}m x {alto}m")
        with col_viz3:
            if st.button("📸 Capturar Vista"):
                st.success("✅ Vista capturada (funcionalidad en desarrollo)")

    # ==========================================================================
    # PESTAÑA 2: ASISTENTE IA
    # ==========================================================================
    with tab_ia:
        st.markdown("### 🤖 Asistente Inteligente de Construcción")

        if not api_key:
            st.warning("⚠️ Ingresa tu API Key de Gemini en la barra lateral para usar el asistente IA")

            # Mostrar información de ejemplo
            st.info("""
            **El asistente IA puede ayudarte con:**
            - 📐 Cálculos estructurales y de materiales
            - 🏗️ Recomendaciones sobre sistemas constructivos
            - 📋 Normativas y mejores prácticas
            - 💡 Optimización de costos y diseños

            Para obtener una API Key gratuita, visita:
            [Google AI Studio](https://makersuite.google.com/app/apikey)
            """)
        else:
            # Inicializar modelo
            model = initialize_gemini(api_key)

            if model:
                # Contexto del proyecto
                contexto = f"""
                Eres un experto en construcción con sistemas de poliestireno expandido (EPS).
                El proyecto actual es:
                - Cliente: {cliente}
                - Área: {m2_in} m²
                - Sistema: {sistema_sel}
                - Habitaciones: {habitaciones}

                Responde de forma técnica pero accesible, en español.
                """

                # Chat interface
                if 'chat_history' not in st.session_state:
                    st.session_state.chat_history = []

                # Mostrar historial
                for msg in st.session_state.chat_history:
                    with st.chat_message(msg['role']):
                        st.markdown(msg['content'])

                # Input del usuario
                if prompt := st.chat_input("Haz una pregunta sobre tu proyecto..."):
                    st.session_state.chat_history.append({'role': 'user', 'content': prompt})

                    with st.chat_message('user'):
                        st.markdown(prompt)

                    with st.chat_message('assistant'):
                        with st.spinner('🤔 Analizando consulta...'):
                            try:
                                full_prompt = f"{contexto}\n\nPregunta del usuario: {prompt}"
                                response = model.generate_content(full_prompt)
                                respuesta = response.text
                                st.markdown(respuesta)
                                st.session_state.chat_history.append({
                                    'role': 'assistant',
                                    'content': respuesta
                                })
                            except Exception as e:
                                st.error(f"Error: {e}")

                # Botones de acción rápida
                st.divider()
                st.markdown("##### 💡 Consultas rápidas:")

                col_q1, col_q2, col_q3 = st.columns(3)
                with col_q1:
                    if st.button("📊 Calcular materiales exactos"):
                        st.session_state.chat_history.append({
                            'role': 'user',
                            'content': 'Calcula la lista exacta de materiales necesarios para este proyecto'
                        })
                        st.rerun()
                with col_q2:
                    if st.button("💰 Optimizar costos"):
                        st.session_state.chat_history.append({
                            'role': 'user',
                            'content': '¿Cómo puedo optimizar los costos de este proyecto sin comprometer la calidad?'
                        })
                        st.rerun()
                with col_q3:
                    if st.button("🏗️ Comparar sistemas"):
                        st.session_state.chat_history.append({
                            'role': 'user',
                            'content': 'Compara las ventajas y desventajas de Isotex vs ICF para este proyecto'
                        })
                        st.rerun()

    # ==========================================================================
    # PESTAÑA 3: PRESUPUESTO
    # ==========================================================================
    with tab_presu:
        st.markdown(f"### 💰 Presupuesto Detallado - {cliente}")

        # Calcular presupuesto
        df_presupuesto = budget_calculator.calcular_presupuesto(
            m2=m2_in,
            sistema=sistema_sel,
            incluir_vigas=incluir_vigas
        )

        # Métricas clave
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)

        total_obra = df_presupuesto['Subtotal'].sum()
        costo_m2 = total_obra / m2_in if m2_in > 0 else 0

        with col_m1:
            st.metric(
                label="Inversión Total",
                value=f"RD$ {total_obra:,.2f}",
                delta=f"RD$ {costo_m2:,.0f}/m²"
            )
        with col_m2:
            subtotal_materiales = df_presupuesto[df_presupuesto['Categoria'] == 'Estructura']['Subtotal'].sum()
            st.metric(
                label="Estructura",
                value=f"RD$ {subtotal_materiales:,.2f}",
                delta=f"{(subtotal_materiales/total_obra*100):.1f}%"
            )
        with col_m3:
            subtotal_hormigon = df_presupuesto[df_presupuesto['Categoria'] == 'Hormigón']['Subtotal'].sum()
            st.metric(
                label="Hormigón",
                value=f"RD$ {subtotal_hormigon:,.2f}",
                delta=f"{(subtotal_hormigon/total_obra*100):.1f}%"
            )
        with col_m4:
            subtotal_acero = df_presupuesto[df_presupuesto['Categoria'] == 'Acero']['Subtotal'].sum()
            st.metric(
                label="Acero",
                value=f"RD$ {subtotal_acero:,.2f}",
                delta=f"{(subtotal_acero/total_obra*100):.1f}%"
            )

        st.divider()

        # Tabla de presupuesto
        st.markdown("##### 📋 Desglose de Materiales")

        # Formatear tabla para visualización
        df_display = df_presupuesto.copy()
        df_display['P_Unitario'] = df_display['P_Unitario'].apply(lambda x: f"RD$ {x:,.2f}")
        df_display['Subtotal'] = df_display['Subtotal'].apply(lambda x: f"RD$ {x:,.2f}")

        st.dataframe(
            df_display[['Categoria', 'Material', 'Detalle', 'Cantidad', 'Unidad', 'P_Unitario', 'Subtotal']],
            use_container_width=True,
            hide_index=True
        )

        # Gráficos
        st.divider()
        st.markdown("##### 📊 Análisis de Costos")

        col_g1, col_g2 = st.columns(2)

        with col_g1:
            # Gráfico de dona por categoría
            df_pie = df_presupuesto.groupby('Categoria')['Subtotal'].sum().reset_index()

            fig_pie = go.Figure(data=[go.Pie(
                labels=df_pie['Categoria'],
                values=df_pie['Subtotal'],
                hole=0.4,
                marker=dict(colors=['#3498db', '#e74c3c', '#2ecc71', '#f39c12', '#9b59b6'])
            )])
            fig_pie.update_layout(
                title='Distribución de Costos por Categoría',
                height=400,
                showlegend=True
            )
            st.plotly_chart(fig_pie, use_container_width=True)

        with col_g2:
            # Gráfico de barras
            fig_bar = go.Figure(data=[go.Bar(
                x=df_presupuesto['Material'],
                y=df_presupuesto['Subtotal'],
                marker=dict(color='#3498db'),
                text=df_presupuesto['Subtotal'].apply(lambda x: f"RD$ {x:,.0f}"),
                textposition='auto'
            )])
            fig_bar.update_layout(
                title='Costos por Material',
                xaxis_title='Material',
                yaxis_title='Costo (RD$)',
                height=400,
                xaxis={'tickangle': -45}
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        # Acciones de exportación
        st.divider()
        st.markdown("##### 📥 Exportar Presupuesto")

        col_exp1, col_exp2, col_exp3 = st.columns(3)

        with col_exp1:
            # Generar PDF
            if st.button("📄 Generar PDF", use_container_width=True):
                datos_proyecto = {
                    'area': m2_in,
                    'sistema': sistema_sel,
                    'cliente': cliente
                }
                pdf_bytes = pdf_generator.generar_propuesta(
                    cliente=cliente,
                    datos_proyecto=datos_proyecto,
                    presupuesto_df=df_presupuesto,
                    total=total_obra
                )
                st.markdown(
                    create_download_link(pdf_bytes, f"Cotizacion_{cliente.replace(' ', '_')}.pdf"),
                    unsafe_allow_html=True
                )

        with col_exp2:
            # Generar Excel
            if st.button("📊 Exportar Excel", use_container_width=True):
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_presupuesto.to_excel(writer, sheet_name='Presupuesto', index=False)

                    # Formatear
                    workbook = writer.book
                    worksheet = writer.sheets['Presupuesto']

                    # Formato de moneda
                    money_format = workbook.add_format({'num_format': 'RD$ #,##0.00'})
                    worksheet.set_column('F:G', 15, money_format)

                output.seek(0)
                b64 = base64.b64encode(output.getvalue()).decode()
                st.markdown(
                    f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" '
                    f'download="Presupuesto_{cliente.replace(" ", "_")}.xlsx">'
                    f'<button style="width:100%; border-radius:10px; background-color:#27ae60; color:white; '
                    f'padding:15px; border:none; cursor:pointer; font-size:16px; font-weight:bold;">'
                    f'📊 Descargar Excel</button></a>',
                    unsafe_allow_html=True
                )

        with col_exp3:
            # Imprimir
            if st.button("🖨️ Imprimir", use_container_width=True):
                st.info("Funcionalidad de impresión - Usa Ctrl+P de tu navegador")

    # ==========================================================================
    # PESTAÑA 4: CONFIGURACIÓN
    # ==========================================================================
    with tab_config:
        st.markdown("### ⚙️ Configuración del Sistema")

        # Configuración de precios
        st.markdown("##### 💲 Precios Unitarios")
        st.info("Modifica los precios según tu proveedor local")

        col_conf1, col_conf2 = st.columns(2)

        with col_conf1:
            nuevo_panel_muro = st.number_input(
                "Panel Muro (RD$/m²)",
                value=BudgetCalculator.PRECIOS_BASE["Panel_Muro"],
                step=50.0
            )
            nuevo_panel_techo = st.number_input(
                "Panel Techo (RD$/m²)",
                value=BudgetCalculator.PRECIOS_BASE["Panel_Techo"],
                step=50.0
            )
            nuevo_h3000 = st.number_input(
                "Hormigón 3000 PSI (RD$/m³)",
                value=BudgetCalculator.PRECIOS_BASE["H_3000_PSI"],
                step=100.0
            )

        with col_conf2:
            nuevo_h3500 = st.number_input(
                "Hormigón 3500 PSI (RD$/m³)",
                value=BudgetCalculator.PRECIOS_BASE["H_3500_PSI"],
                step=100.0
            )
            nueva_viga = st.number_input(
                "Viga H (RD$/kg)",
                value=BudgetCalculator.PRECIOS_BASE["Viga_H_kg"],
                step=5.0
            )
            nuevo_acero = st.number_input(
                "Acero Varilla (RD$/kg)",
                value=BudgetCalculator.PRECIOS_BASE["Acero_Varilla"],
                step=5.0
            )

        # Guardar configuración
        if st.button("💾 Guardar Precios Personalizados"):
            st.session_state.precios_personalizados = {
                "Panel_Muro": nuevo_panel_muro,
                "Panel_Techo": nuevo_panel_techo,
                "H_3000_PSI": nuevo_h3000,
                "H_3500_PSI": nuevo_h3500,
                "Viga_H_kg": nueva_viga,
                "Acero_Varilla": nuevo_acero
            }
            st.success("✅ Precios actualizados para esta sesión")

        st.divider()

        # Información del sistema
        st.markdown("##### ℹ️ Información del Sistema")

        col_info1, col_info2 = st.columns(2)

        with col_info1:
            st.markdown("""
            **Factores de Cálculo**
            - Factor muro: 2.2 × área construida
            - Factor techo: 1.10 × área construida
            - Espesor hormigón: 12cm (Isotex) / 15cm (ICF)
            - Desperdicio panel: 5%
            - Desperdicio hormigón: 8%
            """)

        with col_info2:
            st.markdown("""
            **Rendimientos**
            - Acero de refuerzo: 8.5 kg/m²
            - Aditivo impermeabilizante: 0.02 gal/m²
            - Vigas estructurales: 25 kg/m²
            """)

        st.divider()

        # Acerca de
        st.markdown("##### 📖 Acerca de IsoSmart Titanium")

        with st.expander("Ver información de la aplicación"):
            st.markdown("""
            **Versión:** 4.0.0

            **Características:**
            - ✅ Cálculo automático de presupuestos
            - ✅ Visualización BIM 3D interactiva
            - ✅ Asistente IA con Gemini
            - ✅ Generación de PDF y Excel
            - ✅ Gestión de proyectos
            - ✅ Precios personalizables

            **Tecnologías:**
            - Streamlit (Frontend)
            - Plotly (Visualización 3D)
            - Google Gemini (IA)
            - FPDF / ReportLab (Documentos)
            - Pandas (Datos)

            **Licencia:** MIT

            **Autor:** jukaben32

            [🔗 Repositorio GitHub](https://github.com/jukaben32/isosmart-titanium)
            """)


# ============================================================================
# PUNTO DE ENTRADA
# ============================================================================

if __name__ == "__main__":
    main()
