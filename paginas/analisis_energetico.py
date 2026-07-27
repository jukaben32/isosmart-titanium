"""
IsoSmart Titanium - Módulo de Ahorro Energético
Análisis de carga térmica, consumo de AC y beneficios del aislamiento
"""

import os
import sys

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.energia import AnalisisEnergetico
from utils.estilos import inyectar_css, tarjeta_metrica  # noqa: E402

# Configuración de página
# st.set_page_config() lo llama app.py: solo puede invocarse una vez por sesión.
# Este módulo ahora se importa desde el router unificado, no se ejecuta suelto.

# CSS personalizado
inyectar_css()   # hoja de estilos única: .streamlit/estilos.css


def format_rd(value: float) -> str:
    return f"RD$ {value:,.2f}"


def format_kwh(value: float) -> str:
    return f"{value:,.2f} kWh"


def format_kg(value: float) -> str:
    return f"{value:,.2f} kg"


def render_energy_card(label: str, value: str, subtext: str = "", card_class: str = ""):
    """Delegado a utils.estilos (antes era render_metric_card copiada con otro nombre)."""
    tarjeta_metrica(label, value, subtext, card_class, clase_base="energy-card")


def grafico_carga_termica_comparativa(area: float) -> go.Figure:
    """Gráfico de barras de carga térmica por sistema"""
    sistemas = ['Tradicional', 'ISOTEX', 'ICF']
    cargas_btu = []
    cargas_kw = []

    for sis in ['tradicional', 'isotex', 'icf']:
        carga = AnalisisEnergetico.calcular_carga_termica(area, sistema=sis)
        cargas_btu.append(carga['carga_termica_btu_h'])
        cargas_kw.append(carga['carga_termica_kw'])

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(go.Bar(
        name="Carga BTU/h",
        x=sistemas,
        y=cargas_btu,
        marker_color=['#f5576c', '#4facfe', '#38ef7d'],
        text=[f"{b:,.0f} BTU/h" for b in cargas_btu],
        textposition='outside'
    ))

    fig.update_layout(
        title=f"Carga Térmica de Refrigeración - Área: {area}m²",
        xaxis_title="Sistema Constructivo",
        yaxis_title="BTU/h",
        template="plotly_white",
        height=400,
        showlegend=False
    )

    return fig


def grafico_consumo_mensual(area: float) -> go.Figure:
    """Gráfico de consumo mensual por sistema"""
    sistemas = ['Tradicional', 'ISOTEX', 'ICF']
    consumos_kwh = []
    consumos_rd = []

    for sis in ['tradicional', 'isotex', 'icf']:
        carga = AnalisisEnergetico.calcular_carga_termica(area, sistema=sis)
        seer = 16 if sis == 'tradicional' else 20
        consumo = AnalisisEnergetico.calcular_consumo_mensual(carga['carga_termica_btu_h'], seer)
        consumos_kwh.append(consumo['consumo_mensual_kwh'])
        consumos_rd.append(consumo['consumo_mensual_rd'])

    fig = go.Figure()

    fig.add_trace(go.Bar(
        name="Consumo kWh",
        x=sistemas,
        y=consumos_kwh,
        marker_color=['#f5576c', '#4facfe', '#38ef7d'],
        text=[f"{k:,.0f} kWh" for k in consumos_kwh],
        textposition='outside'
    ))

    fig.update_layout(
        title=f"Consumo Mensual de Energía - Área: {area}m²",
        xaxis_title="Sistema Constructivo",
        yaxis_title="kWh/mes",
        template="plotly_white",
        height=400,
        showlegend=False
    )

    return fig


def grafico_proyeccion_ahorro(df_proyeccion: pd.DataFrame) -> go.Figure:
    """Gráfico de proyección de ahorro a lo largo del tiempo"""
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Ahorro anual
    fig.add_trace(go.Bar(
        name="Ahorro Anual",
        x=df_proyeccion['Anio'],
        y=df_proyeccion['Ahorro_Anual_RD'],
        marker_color='#38ef7d',
        opacity=0.7,
        text=[f"RD${a:,.0f}" for a in df_proyeccion['Ahorro_Anual_RD']],
        textposition='outside'
    ))

    # Ahorro acumulado
    fig.add_trace(go.Scatter(
        name="Ahorro Acumulado",
        x=df_proyeccion['Anio'],
        y=df_proyeccion['Ahorro_Acumulado_RD'],
        yaxis='y2',
        line=dict(color='#11998e', width=3),
        fill='tozeroy',
        fillcolor='rgba(17, 153, 142, 0.2)'
    ))

    fig.update_layout(
        title="Proyección de Ahorro Energético a 20 Años",
        xaxis_title="Año",
        yaxis_title="Ahorro Anual (RD$)",
        yaxis2=dict(title="Ahorro Acumulado (RD$)", overlaying='y', side='right'),
        template="plotly_white",
        height=450,
        hovermode="x unified"
    )

    return fig


def grafico_pastel_consumo(df_comparativa: pd.DataFrame, sistema: str) -> go.Figure:
    """Gráfico de pastel del consumo por calidad de equipo"""
    df_filtrado = df_comparativa[df_comparativa['Sistema'] == sistema]

    fig = go.Figure(data=[go.Pie(
        labels=[f"{row['Calidad_Equipo']} ({row['SEER']} SEER)" for _, row in df_filtrado.iterrows()],
        values=df_filtrado['Consumo_mensual_kWh'],
        hole=0.4,
        textinfo='label+percent+value',
        marker=dict(colors=px.colors.qualitative.Set2)
    )])

    fig.update_layout(
        title=f"Consumo por Calidad de Equipo - {sistema}",
        height=350,
        template="plotly_white"
    )

    return fig


def grafico_equipo_recomendado(tamano_ac: dict) -> go.Figure:
    """Gráfico de capacidades de equipos de AC"""
    btu_labels = [e['nombre'] for e in tamano_ac['equipos_sugeridos']]
    btu_values = [e['btu'] for e in tamano_ac['equipos_sugeridos']]

    fig = go.Figure(data=[go.Bar(
        name="BTU/h",
        x=btu_labels,
        y=btu_values,
        marker_color='#4facfe',
        text=[f"{b:,} BTU" for b in btu_values],
        textposition='outside'
    )])

    fig.add_hline(
        y=tamano_ac['btu_por_unidad'],
        line_dash="dash",
        line_color="red",
        annotation_text=f"Recomendado: {tamano_ac['btu_por_unidad']:,.0f} BTU",
        annotation_position="top"
    )

    fig.update_layout(
        title="Equipos de AC Recomendados",
        xaxis_title="Tipo de Equipo",
        yaxis_title="Capacidad (BTU/h)",
        template="plotly_white",
        height=350,
        showlegend=False
    )

    return fig


def main():
    st.markdown("""
    <div style="background: linear-gradient(90deg, #11998e 0%, #38ef7d 100%); padding: 2rem; border-radius: 15px; margin-bottom: 2rem;">
        <h1 style="color: white; margin: 0;">⚡ Análisis de Ahorro Energético</h1>
        <p style="color: white; opacity: 0.9; margin: 10px 0 0 0;">
            Cálculo de carga térmica, consumo de aire acondicionado y beneficios del aislamiento ISOTEX
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Sidebar - Configuración
    with st.sidebar:
        st.markdown("### ⚙️ Configuración")

        area = st.slider("📐 Área de Construcción (m²)", 30, 500, 120, step=10)

        sistema_analisis = st.selectbox("🏗️ Sistema a Analizar", ["isotex", "icf"])

        calidad_equipo = st.selectbox("❄️ Calidad Equipo AC",
                                       ["economico", "standard", "inverter", "premium"],
                                       format_func=lambda x: x.capitalize())

        st.divider()

        st.markdown("### 📊 Parámetros")

        temp_exterior = st.number_input("🌡️ Temp. Exterior (°C)", value=34.0, min_value=25.0, max_value=45.0)

        st.divider()

        # ANTES: texto fijo "reducen la carga térmica hasta 55%", que citaba
        # una constante muerta (FACTOR_REDUCCION_ISOTEX, nunca usada por el
        # cálculo real). El cálculo real da 44.4% para isotex y 51.1% para
        # ICF -- ahora se muestra el número que realmente se está calculando.
        reduccion_pct = AnalisisEnergetico.reduccion_carga_termica_pct(sistema_analisis)
        st.markdown(f"""
        <div style="background: #f0f2f6; padding: 15px; border-radius: 10px; font-size: 0.9rem;">
            <strong>💡 Beneficios del Aislamiento:</strong><br>
            El sistema {sistema_analisis.upper()} reduce la carga térmica en {reduccion_pct:.1f}%
            frente a construcción tradicional (estimación de ingeniería, ver
            <code>utils/energia.py</code>), lo que permite equipos de AC más pequeños.
        </div>
        """, unsafe_allow_html=True)

    # Calcular análisis
    analisis = AnalisisEnergetico.calcular_ahorro_energetico(area, sistema_analisis, calidad_equipo)
    carga = AnalisisEnergetico.calcular_carga_termica(area, sistema='isotex')
    tamano_ac = AnalisisEnergetico.calcular_tamano_ac_recomendado(area, sistema_analisis)
    df_proyeccion = AnalisisEnergetico.generar_proyeccion_ahorro(area)
    df_comparativa = AnalisisEnergetico.generar_tabla_comparativa_consumos(area)
    sistema_solar = AnalisisEnergetico.calcular_sistema_solar_recomendado(area)

    # ===== SECCIÓN 1: Resumen de Ahorros =====
    st.markdown('<h2 class="section-header">💚 Resumen de Beneficios Energéticos</h2>', unsafe_allow_html=True)

    col_s1, col_s2, col_s3, col_s4 = st.columns(4)

    with col_s1:
        render_energy_card(
            "Ahorro Mensual",
            format_rd(analisis.ahorro_mensual_rd),
            f"{analisis.ahorro_mensual_kwh:,.0f} kWh",
            "green"
        )

    with col_s2:
        render_energy_card(
            "Ahorro Anual",
            format_rd(analisis.ahorro_anual_rd),
            "En aire acondicionado",
            "blue"
        )

    with col_s3:
        render_energy_card(
            "CO₂ Evitado",
            format_kg(analisis.co2_evitado_kg_anio),
            "Por año",
            "purple"
        )

    with col_s4:
        render_energy_card(
            "ROI Energético",
            f"{analisis.roi_energetico_anios:.1f} años",
            "Recuperación inversión",
            "orange"
        )

    # ===== SECCIÓN 2: Comparativa de Sistemas =====
    st.markdown('<h2 class="section-header">📊 Comparativa de Sistemas Constructivos</h2>', unsafe_allow_html=True)

    col_c1, col_c2 = st.columns(2)

    with col_c1:
        fig_carga = grafico_carga_termica_comparativa(area)
        st.plotly_chart(fig_carga, use_container_width=True)

    with col_c2:
        fig_consumo = grafico_consumo_mensual(area)
        st.plotly_chart(fig_consumo, use_container_width=True)

    # ===== SECCIÓN 3: Detalle de Carga Térmica =====
    st.markdown(f"""
    <div style="background: #f8f9fa; padding: 1.5rem; border-radius: 10px; margin: 1rem 0;">
        <h3>🌡️ Detalle de Carga Térmica - Sistema {sistema_analisis.upper()}</h3>
        <p>Para una construcción de <strong>{area} m²</strong> con techo de 2.7m de altura:</p>
    </div>
    """, unsafe_allow_html=True)

    col_d1, col_d2, col_d3, col_d4 = st.columns(4)

    with col_d1:
        st.metric("Carga Térmica", f"{carga['carga_termica_btu_h']:,.0f} BTU/h")

    with col_d2:
        st.metric("Equivalente", f"{carga['carga_termica_kw']:.2f} kW")

    with col_d3:
        st.metric("Toneladas Ref.", f"{carga['carga_toneladas_refrigeracion']:.2f} Ton")

    with col_d4:
        st.metric("Volumen", f"{carga['volumen_m3']:.0f} m³")

    # ===== SECCIÓN 4: Comparativa de Consumos =====
    st.markdown('<h2 class="section-header">❄️ Tabla Comparativa de Consumos por Configuración</h2>', unsafe_allow_html=True)

    # Selector de sistema
    sis_selector = st.selectbox("Ver consumo por sistema:", ['Todos', 'Tradicional', 'ISOTEX', 'ICF'])

    if sis_selector != 'Todos':
        df_mostrar = df_comparativa[df_comparativa['Sistema'] == sis_selector]
    else:
        df_mostrar = df_comparativa

    # Formatear para mostrar
    df_display = df_mostrar.copy()
    df_display['Carga_Termica_BTU_h'] = df_display['Carga_Termica_BTU_h'].apply(lambda x: f"{x:,.0f}")
    df_display['Consumo_mensual_kWh'] = df_display['Consumo_mensual_kWh'].apply(lambda x: f"{x:,.1f}")
    df_display['Costo_Mensual_RD'] = df_display['Costo_Mensual_RD'].apply(lambda x: format_rd(x))
    df_display['Costo_Anual_RD'] = df_display['Costo_Anual_RD'].apply(lambda x: format_rd(x))

    st.dataframe(
        df_display[['Sistema', 'Calidad_Equipo', 'SEER', 'Carga_Termica_BTU_h', 'Consumo_mensual_kWh', 'Costo_Mensual_RD', 'Costo_Anual_RD']],
        use_container_width=True,
        hide_index=True
    )

    # ===== SECCIÓN 5: Proyección de Ahorro =====
    st.markdown('<h2 class="section-header">📈 Proyección de Ahorro a 20 Años</h2>', unsafe_allow_html=True)

    col_p1, col_p2 = st.columns([2, 1])

    with col_p1:
        fig_proyeccion = grafico_proyeccion_ahorro(df_proyeccion)
        st.plotly_chart(fig_proyeccion, use_container_width=True)

    with col_p2:
        st.markdown("##### 📋 Resumen de Proyección")

        total_ahorro = df_proyeccion['Ahorro_Anual_RD'].sum()
        total_co2 = df_proyeccion['CO2_Evitado_kg'].iloc[-1]

        st.metric("Ahorro Total 20 años", format_rd(total_ahorro))
        st.metric("CO₂ Evitado Total", f"{total_co2:,.0f} kg")

        st.divider()

        st.markdown("##### 📅 Primeros 5 años")
        df_5 = df_proyeccion.head(5).copy()
        df_5['Ahorro_Anual_RD'] = df_5['Ahorro_Anual_RD'].apply(lambda x: format_rd(x))
        st.dataframe(df_5[['Anio', 'Ahorro_Anual_RD', 'Factor_Crecimiento']],
                    use_container_width=True, hide_index=True)

    # ===== SECCIÓN 6: Tamaño de AC Recomendado =====
    st.markdown('<h2 class="section-header">❄️ Dimensionamiento de Aire Acondicionado</h2>', unsafe_allow_html=True)

    col_ac1, col_ac2 = st.columns([1, 1])

    with col_ac1:
        st.markdown(f"""
        ### Equipo Recomendado para {area}m²

        **Carga térmica calculada:** {tamano_ac['carga_termica_btu_h']:,.0f} BTU/h

        **Capacidad total necesaria:** {tamano_ac['toneladas_recomendadas']:.2f} Toneladas de refrigeración

        **Número de unidades recomendadas:** {tamano_ac['num_unidades_recomendado']}

        **Capacidad por unidad:** {tamano_ac['btu_por_unidad']:,.0f} BTU/h
        """)

        if tamano_ac['equipos_sugeridos']:
            st.markdown("##### 🔧 Equipos Sugeridos:")
            for eq in tamano_ac['equipos_sugeridos']:
                st.markdown(f"- **{eq['nombre']}**: {eq['btu']:,} BTU ({eq['kw']} kW)")

    with col_ac2:
        fig_equipos = grafico_equipo_recomendado(tamano_ac)
        st.plotly_chart(fig_equipos, use_container_width=True)

    # ===== SECCIÓN 7: Sistema Solar (Opcional) =====
    st.markdown('<h2 class="section-header">☀️ Complemento Solar Fotovoltaico</h2>', unsafe_allow_html=True)

    col_sol1, col_sol2, col_sol3, col_sol4 = st.columns(4)

    with col_sol1:
        st.metric("Paneles Necesarios", f"{sistema_solar['paneles_necesarios']} uds",
                 f"{sistema_solar['capacidad_sistema_kw']} kW")

    with col_sol2:
        st.metric("Generación Mensual", f"{sistema_solar['energia_mensual_kwh']:,.0f} kWh",
                 f"{sistema_solar['autoconsumo_pct']:.0f}% autoconsumo")

    with col_sol3:
        st.metric("Costo Estimado", format_rd(sistema_solar['costo_estimado_rd']),
                 f"~{format_rd(sistema_solar['costo_por_panel_rd'])}/panel")

    with col_sol4:
        st.metric("Ahorro Solar", format_rd(sistema_solar['ahorro_solar_mensual_rd']) + "/mes",
                 "Estimado")

    st.info("💡 El sistema solar fotovoltaico puede compensar parte del consumo eléctrico剩余. "
           "Consulte con un proveedor local para una cotización exacta.")

    # ===== SECCIÓN 8: Beneficios Ambientales =====
    st.markdown('<h2 class="section-header">🌍 Impacto Ambiental</h2>', unsafe_allow_html=True)

    col_eco1, col_eco2, col_eco3 = st.columns(3)

    with col_eco1:
        # Árboles equivalentes
        arboles_equivalentes = analisis.co2_evitado_kg_anio / 21  # ~21 kg CO2/árbol/año
        st.metric("🌳 Árboles Equivalentes", f"{arboles_equivalentes:.0f}",
                 "Por año de operación")

    with col_eco2:
        km_auto_equivalente = analisis.co2_evitado_kg_anio / 0.192  # ~192 g/km
        st.metric("🚗 km de Auto Equivalentes", f"{km_auto_equivalente:,.0f}",
                 "Por año de operación")

    with col_eco3:
        st.metric("♻️ Reducción vs Tradicional", f"{55}%",
                 "En huella de carbono")

    # ===== FOOTER =====
    st.divider()
    st.markdown("""
    <div style="text-align: center; color: #666; font-size: 0.9rem;">
        <p><strong>IsoSmart Titanium</strong> - Módulo de Análisis Energético</p>
        <p>Nota: Los cálculos son estimaciones basadas en condiciones climáticas de Santo Domingo, República Dominicana.
        Los resultados reales pueden variar según orientación, materiales y uso del edificio.</p>
    </div>
    """, unsafe_allow_html=True)


