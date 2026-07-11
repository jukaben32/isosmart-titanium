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
from ui_vision import render_integradora_vision_canvas

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
        +809 561 5599

        **📧 Email:**
        info@grupoisotex.net

        **📌 Ubicación:**
        Parque Industrial Duarte, Autopista Duarte Km 22 1/2, Santo Domingo

        **⏰ Horario:**
        Lunes - Viernes: 8:00 AM - 6:00 PM
        Sábados: 8:00 AM - 12:00 PM

        **🌐 Web:**
        [isotexdominicana.com](https://isotexdominicana.com/)

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

