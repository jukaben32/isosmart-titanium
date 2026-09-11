"""Módulo de interfaz de IsoSmart Titanium (refactor de app.py, 2026-07-10)."""
import base64
import hashlib
import html
import os
from datetime import datetime
from io import BytesIO

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from PIL import Image

from ui_core import (
    PDFGenerator,
    ProjectManager,
    create_download_link,
    estimate_build_time_days,
    get_gemini_api_key_from_config,
    initialize_gemini,
    render_text_design_assistant,
    sincronizar_parametros_globales,
    st_canvas,
)
from utils.ai_text_design import DEFAULT_TEXT_DESIGN_PARAMS
from utils.dxf_importer import analizar_dxf_bytes
from utils.estado import ProyectoState

# Helpers compartidos desde ui_core
from utils.estilos import boton_enlace  # noqa: E402
from utils.financiera import AnalisisFinanciero
from utils.gemini_client import crear_modelo_gemini
from utils.gemini_plan import analyze_plan_image_with_gemini
from utils.pdf_utils import pdf_first_page_to_image
from utils.plan_geometry import (
    contar_lineas_calibracion,
    contar_poligonos,
    extract_line_segments,
    extract_points,
    polygon_area_perimeter,
    polygon_from_canvas,
    scale_from_canvas_line,
)
from utils.pricebook import Pricebook
from utils.qto import CATEGORIAS_OBRA_GRIS, MotorQTO


def _mostrar_mediciones_dxf(archivo_dxf, origen: str) -> bool:
    """Lee un DXF subido y permite guardar sus mediciones en el proyecto."""
    try:
        mediciones = analizar_dxf_bytes(archivo_dxf.getvalue())
    except Exception as e:
        st.error(f"No pude leer este DXF: {e}")
        return False

    st.success(
        f"DXF detectado: {mediciones.area_m2:,.2f} m², "
        f"{mediciones.perimetro_m:,.2f} ml, "
        f"{mediciones.ventanas} ventanas, "
        f"{mediciones.puertas_interiores + mediciones.puertas_exteriores} puertas."
    )
    for advertencia in mediciones.advertencias:
        st.warning(advertencia)

    if st.button("Usar mediciones del DXF", key=f"usar_dxf_{origen}", use_container_width=True):
        estado_dxf = ProyectoState.cargar()
        estado_dxf.aplicar_metricas(mediciones.a_metricas(), origen=f"DXF: {archivo_dxf.name}")
        estado_dxf.guardar()
        st.rerun()

    return True


def render_modulo_vision_y_canvas(modelo_gemini):
    """
    Pestaña interactiva de análisis de planos y dibujo geométrico.
    """
    st.subheader("📐 Extracción Geométrica Avanzada y Visión Artificial")
    
    col_izq, col_der = st.columns([1, 2])
    
    with col_izq:
        st.markdown("### 🛠️ Cargar Documento")
        archivo_plano = st.file_uploader(
            "Sube el plano del proyecto (DXF, PDF o Imagen)",
            type=["dxf", "png", "jpg", "jpeg", "pdf"],
            key="uploader_planos"
        )
        
        imagen_pil = None
        if archivo_plano:
            nombre_archivo = archivo_plano.name.lower()
            if nombre_archivo.endswith(".dxf"):
                _mostrar_mediciones_dxf(archivo_plano, "vision")
            elif nombre_archivo.endswith(".pdf"):
                bytes_data = archivo_plano.getvalue()
                with st.spinner("📄 Convirtiendo primera página del PDF a imagen..."):
                    imagen_pil = pdf_first_page_to_image(bytes_data, dpi=150)
            else:
                bytes_data = archivo_plano.getvalue()
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
        
        if archivo_plano and archivo_plano.name.lower().endswith(".dxf"):
            st.info(
                "El DXF se procesa directamente desde sus capas CAD. "
                "Para usar el canvas de medición, sube un PDF o una imagen."
            )
        elif imagen_pil:
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
                    n_lineas = contar_lineas_calibracion(objetos)
                    if n_lineas > 1:
                        st.warning(
                            f"⚠️ Se detectaron {n_lineas} líneas dibujadas; se usó la "
                            f"PRIMERA para calibrar. Borra las líneas sobrantes si no "
                            f"era la que querías usar."
                        )
                    st.info(f"📐 Factor de escala calculado: **{m_por_px:.5f} m/px**")

                    # Extraer el primer polígono dibujado por el usuario
                    puntos_poligono = polygon_from_canvas(objetos)
                    n_poligonos = contar_poligonos(objetos)
                    if n_poligonos > 1:
                        st.warning(
                            f"⚠️ Se detectaron {n_poligonos} polígonos trazados; se usó "
                            f"el PRIMERO. Si el área mostrada no es la que esperabas, "
                            f"borra los polígonos sobrantes y traza solo el perímetro."
                        )

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
    estado_calculo = ProyectoState.cargar()

    # Barra lateral de configuración
    with st.sidebar:
        st.markdown("### 📋 Datos del Proyecto")
        render_text_design_assistant("calculadora")
        text_design_params = st.session_state.get("text_design_params", DEFAULT_TEXT_DESIGN_PARAMS)

        cliente = st.text_input("👤 Nombre del Cliente", "Proyecto Residencial")
        
        area_default = float(estado_calculo.area_m2 or text_design_params.get("area_m2", 120.0))
        area_default = max(20.0, min(5000.0, area_default))
        area_key = "calc_area_slider_m2"
        area_base_key = "_calc_area_estado_base_m2"
        area_llego_de_otra_pagina = (
            st.session_state.get(area_base_key) is not None
            and float(st.session_state.get(area_base_key)) != float(area_default)
        )
        if area_key not in st.session_state or area_llego_de_otra_pagina:
            st.session_state[area_key] = area_default
            st.session_state[area_base_key] = area_default
        else:
            st.session_state[area_key] = max(20.0, min(5000.0, float(st.session_state[area_key])))

        m2_in = st.slider(
            "📐 Área de construcción (m²)",
            min_value=20.0,
            max_value=5000.0,
            step=10.0,
            key=area_key,
            help=(
                "Esta barra alimenta el resumen, las tablas de materiales, "
                "la comparativa, el PDF y las demás páginas del proyecto."
            ),
        )
        # Antes: `st.session_state["calc_area_m2"] = m2_in` aquí mismo --
        # redundante con `estado_proyecto.guardar()` unas líneas más abajo
        # en esta misma función, que ya sincroniza esta clave a través de
        # ProyectoState (la única fuente de escritura que debe tocarla).

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

    # ------------------------------------------------------------------
    # Motor de cálculo: MotorQTO (antes: BudgetCalculator, motor clásico)
    #
    # Esta es LA página que genera el PDF que recibe un cliente real. Seguía
    # en el motor clásico después de que la Fase 1 de la auditoría migró el
    # resto de la app al motor de cantidades — el usuario podía calibrar el
    # canvas, trazar el polígono, dejar que Gemini leyera el plano... y esta
    # página seguía calculando con `m2 * 2.2`, sin usar nada de eso.
    #
    # Además el PDF recibía solo `obra_gris_df` pero el total impreso incluía
    # obra gris + terminada: las filas nunca sumaban el total mostrado en el
    # documento que firma el cliente. `presupuesto_formato_legado()` corrige
    # ambas cosas a la vez.
    # ------------------------------------------------------------------
    estado_proyecto = ProyectoState.cargar()
    estado_proyecto.area_m2 = m2_in
    estado_proyecto.sistema = sistema_seleccionado
    estado_proyecto.calidad = calidad_terminados
    estado_proyecto.zona_riesgo = zona_riesgo
    estado_proyecto.guardar()
    # La barra de Inicio usa otra key de widget. En esta página no existe ese
    # widget, así que podemos mantenerla alineada para la próxima visita.
    st.session_state["inicio_area_m2"] = float(m2_in)
    st.session_state["_inicio_area_m2_previa"] = float(m2_in)
    st.session_state["_calc_area_estado_base_m2"] = float(m2_in)

    geo = estado_proyecto.geometria()
    motor = MotorQTO(geo, precios_actuales, sistema=sistema_seleccionado,
                     calidad=calidad_terminados, zona_riesgo=zona_riesgo)

    if usar_vigas_h:
        st.sidebar.warning(
            "⚠️ Los pórticos de vigas H aún no están modelados en el motor QTO. "
            "Esta opción no afecta el presupuesto mostrado."
        )

    presupuesto_legado = motor.presupuesto_formato_legado()
    obra_gris_df = presupuesto_legado[presupuesto_legado["Categoria"].isin(CATEGORIAS_OBRA_GRIS)].reset_index(drop=True)
    obra_terminada_df = presupuesto_legado[~presupuesto_legado["Categoria"].isin(CATEGORIAS_OBRA_GRIS)].reset_index(drop=True)

    total_obra_gris = motor.total_obra_gris()
    total_obra_terminada = motor.total_obra_terminada()
    total_general = motor.total()

    por_verificar = motor.partidas_por_verificar()
    if not por_verificar.empty:
        monto_ref = por_verificar["subtotal"].sum()
        st.info(
            f"📎 RD$ {monto_ref:,.0f} ({monto_ref/total_general*100:.0f}% del total) usa "
            f"precios de **referencia** (Covintec México, convertidos a DOP), no "
            f"cotizaciones de proveedor local. Ver `utils/fuentes.py`."
        )

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
        comparacion = motor.comparar_con_tradicional()
        ahorro_pct = comparacion['ahorro']['total_pct']
        st.metric(
            label="Ahorro vs Tradicional",
            value=f"{ahorro_pct:.1f}%",
            delta=f"RD$ {comparacion['ahorro']['total_rd']:,.0f}"
        )
        st.caption(
            f"{comparacion['ahorro']['obra_gris_pct']:.1f}% sobre obra gris; "
            f"los acabados son iguales en ambos sistemas."
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
        st.markdown("##### Comparativa EPS/ICF vs Tradicional (obra gris vs obra gris)")
        st.caption(
            f"El ahorro ({comparacion['ahorro']['obra_gris_pct']:.1f}%) se aplica solo a la "
            f"obra gris; los acabados son idénticos en ambos sistemas. Antes esta pestaña "
            f"comparaba obra gris EPS contra obra **terminada** tradicional — peras con "
            f"manzanas — y mostraba peso y tiempo de construcción sin ninguna fuente."
        )

        col_c1, col_c2 = st.columns(2)

        with col_c1:
            st.markdown(f"""
            #### EPS/ICF
            - **Costo Total:** RD$ {comparacion['eps']['costo_total']:,.0f}
            - **Costo/m²:** RD$ {comparacion['eps']['costo_m2']:,.0f}
            - **Obra gris:** RD$ {comparacion['eps']['obra_gris']:,.0f}
            - **Obra terminada:** RD$ {comparacion['eps']['obra_terminada']:,.0f}
            """)

        with col_c2:
            st.markdown(f"""
            #### Tradicional
            - **Costo Total:** RD$ {comparacion['tradicional']['costo_total']:,.0f}
            - **Costo/m²:** RD$ {comparacion['tradicional']['costo_m2']:,.0f}
            - **Obra gris:** RD$ {comparacion['tradicional']['obra_gris']:,.0f}
            - **Obra terminada:** RD$ {comparacion['tradicional']['obra_terminada']:,.0f}
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
            pdf_bytes = pdf_gen.generar_propuesta(
                cliente, datos, presupuesto_legado, total_general
            )  # antes: solo obra_gris_df -> las filas no sumaban el total impreso
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
        boton_enlace(wa_url, "💬 Enviar por WhatsApp", variante="whatsapp")

    with col_exp3:
        if st.button("📊 Exportar Excel", use_container_width=True):
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                obra_gris_df.to_excel(writer, sheet_name='Obra Gris', index=False)
                obra_terminada_df.to_excel(writer, sheet_name='Obra Terminada', index=False)
            output.seek(0)
            b64 = base64.b64encode(output.getvalue()).decode()
            nombre_archivo = f"Presupuesto_Completo_{cliente.replace(' ', '_')}.xlsx"
            st.markdown(
                f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" '
                f'download="{html.escape(nombre_archivo, quote=True)}">'
                f'<button class="iso-btn iso-btn--excel">📊 Descargar Excel</button></a>',
                unsafe_allow_html=True
            )

    st.markdown("##### 📧 Enviar por Correo Electrónico")
    email_dest = st.text_input("Correo electrónico del cliente", placeholder="cliente@ejemplo.com", key="email_input")
    if st.button("✉️ Enviar Presupuesto PDF", use_container_width=True):
        if email_dest:
            import requests
            pdf_gen = PDFGenerator()
            datos = {'area': m2_in, 'sistema': sistema_seleccionado, 'cliente': cliente}
            pdf_bytes = pdf_gen.generar_propuesta(
                cliente, datos, presupuesto_legado, total_general
            )  # antes: solo obra_gris_df -> las filas no sumaban el total impreso
            
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
                        "html": (
                            f"<p>Hola {html.escape(str(cliente))},</p>"
                            f"<p>Adjunto encontrará su presupuesto estimado para la "
                            f"construcción con sistema {html.escape(str(sistema_seleccionado))}.</p>"
                        ),
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

        - [Facebook](https://www.facebook.com/IsotexRD/)
        - [Instagram](https://www.instagram.com/isotexrd/)
        - [Twitter/X](https://twitter.com/IsotexD)
        """)

    st.divider()

    # Mapa (placeholder)
    st.markdown("### 🗺️ Nuestra Ubicación")
    st.map([{"lat": 18.4861, "lon": -69.9312}])  # Santo Domingo


# ============================================================================
# NOTA (revisión de pantallas, 2026-07-26): existía aquí
# `render_pestana_configuracion_precios()`, un tercer panel de precios,
# completamente inalcanzable -- ninguna pantalla la llamaba, ni siquiera un
# test. Solo cubría 9 de los 39 materiales y su fallback usaba
# `Panel_Muro: 925.00`, el precio sin fuente que ya se corrigió a 1,072
# (Covintec México, ver utils/pricebook.py). Además llamaba a
# `pb.get_all_prices()` / `pb.save_prices()`, métodos que no existen en la
# clase `Pricebook` actual (son `load()` / `save()`).
#
# El panel de precios real y con las 39 partidas está en
# `ui_presupuesto.py::render_pestana_pricebook()`. Se retira el duplicado en
# vez de mantenerlo como código muerto: a diferencia de utils/calculations.py
# (que se conservó marcado por si sus fórmulas resultan útiles), aquí no hay
# ninguna fórmula que rescatar, solo una copia obsoleta de la interfaz.
# ============================================================================


def pagina_plano_estructura():
    """Plano -> parámetros -> estructura (vigas H) + cerramiento + comparativas"""
    st.markdown("""
    <div class="main-header">
        <h1 style="margin:0;">📐 Plano → Estructura</h1>
        <p style="margin:10px 0 0 0;">Sube un plano (imagen) y genera un modelo paramétrico para vigas H + EPS/ICF</p>
    </div>
    """, unsafe_allow_html=True)

    st.info(
        "Sube un plano para calibrar escala y extraer dimensiones -- las medidas "
        "que extraigas aquí alimentan el presupuesto real de la app."
    )

    render_text_design_assistant("plano")

    with st.sidebar:
        st.markdown("### 🤖 IA (opcional)")
        api_key_default = get_gemini_api_key_from_config()
        api_key = st.text_input("Gemini API Key", value=api_key_default, type="password")
        model_vision = None
        if api_key:
            try:
                # Migrado al SDK nuevo (google-genai) -- ver
                # utils/gemini_client.py. Gemini 3.6 Flash acepta imagen
                # como input multimodal igual que el modelo viejo.
                model_vision = crear_modelo_gemini(api_key)
            except Exception as e:
                st.warning(f"No pude inicializar el modelo con visión: {e}")

    upload = st.file_uploader("Sube plano (DXF/PNG/JPG/PDF).", type=["dxf", "png", "jpg", "jpeg", "pdf"])

    img = None
    if upload is not None:
        nombre_upload = upload.name.lower()
        if nombre_upload.endswith(".dxf"):
            _mostrar_mediciones_dxf(upload, "plano")
        elif nombre_upload.endswith(".pdf"):
            pdf_bytes = upload.getvalue()
            img = pdf_first_page_to_image(pdf_bytes, dpi=150)
            if img is None:
                st.error("No pude convertir el PDF a imagen. Verifica que `PyMuPDF` esté instalado y que el PDF no esté corrupto.")
        else:
            img = Image.open(upload).convert("RGB")

    if img is not None:
        st.image(img, caption="Plano cargado", use_container_width=True)

        if model_vision and st.button("🧠 Analizar plano con IA", use_container_width=True):
            with st.spinner("Analizando plano..."):
                data, raw = analyze_plan_image_with_gemini(model_vision, img)
            st.session_state["plan_raw"] = raw
            if isinstance(data, dict):
                # ANTES: `st.session_state["plan_params"] = {...}` -- un flujo
                # paralelo que nunca pasaba por ProyectoState. El resultado
                # nunca llegaba al motor QTO real. Ahora usa el mismo camino
                # que el resto de la app (ver sincronizar_parametros_globales
                # en ui_core.py).
                sincronizar_parametros_globales(
                    {k: v for k, v in data.items() if v is not None},
                    "Análisis de plano (IA)"
                )
            else:
                st.warning("No pude extraer un JSON confiable. Usa el trazado manual abajo.")

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
                    if contar_lineas_calibracion(objects_scale) > 1:
                        st.warning(
                            f"⚠️ Hay {contar_lineas_calibracion(objects_scale)} líneas dibujadas; "
                            f"se calibró con la primera."
                        )
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
                    if contar_poligonos(objects_per) > 1:
                        st.warning(
                            f"⚠️ Hay {contar_poligonos(objects_per)} polígonos trazados; "
                            f"se usó el primero."
                        )
                    area_px2, per_px = polygon_area_perimeter(poly)
                    area_m2 = area_px2 * (m_per_px ** 2)
                    per_m = per_px * m_per_px
                    st.success(f"Área (planta) ≈ {area_m2:,.2f} m² | Perímetro ≈ {per_m:,.2f} m")
                    if st.button("⬇️ Usar estos valores en el modelo", use_container_width=True):
                        # ANTES: escribía a `st.session_state["plan_params"]`
                        # directo, sin pasar por ProyectoState -- ver la nota
                        # equivalente arriba, en el análisis con IA.
                        sincronizar_parametros_globales(
                            {"area_m2": float(area_m2), "perimetro_m": float(per_m)},
                            "Trazado sobre plano (canvas)"
                        )
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

    # ------------------------------------------------------------------
    # ANTES: aquí seguía un "modelo paramétrico" completo (vigas H,
    # cimientos, cerramiento) con su PROPIO cálculo desconectado del motor
    # QTO real -- fórmulas propias (`calc_h_beams_kg`,
    # `estimate_foundation_volume_m3`), su propio pricebook fallback con
    # `Panel_Muro: 925.00` (el precio SIN FUENTE que se corrigió a 1,072 en
    # todo el resto de la app hace varias rondas), y un 5%/15% de
    # desperdicio plano -- exactamente el patrón que se eliminó del motor
    # real reemplazándolo por modulación a 1.22 m.
    #
    # Ese bloque nunca llegaba a ningún presupuesto real, a ningún PDF, ni
    # se guardaba con el lead: era un número que aparecía en pantalla y no
    # iba a ningún lado, calculado con un precio de hace meses. Se retira
    # en vez de mantenerlo -- la calculadora real está a un clic.
    # ------------------------------------------------------------------
    estado_actual = ProyectoState.cargar()
    st.divider()
    st.markdown("### 🧾 Presupuesto real")
    st.info(
        f"Área actual del proyecto: **{estado_actual.area_m2:,.0f} m²**"
        + (f" (desde: {estado_actual.origen_metricas})" if estado_actual.origen_metricas else "")
        + ". El presupuesto completo -- con el motor de cantidades real, no una "
          "estimación paramétrica aparte -- está en **🧾 Presupuesto Detallado**."
    )

    with st.expander("Ver respuesta cruda de IA (si aplica)", expanded=False):
        st.markdown("**Text-to-Design**")
        st.code(st.session_state.get("text_design_raw", "") or "(sin análisis por texto)")
        st.markdown("**Análisis de plano**")
        st.code(st.session_state.get("plan_raw", "") or "(sin análisis de plano)")

