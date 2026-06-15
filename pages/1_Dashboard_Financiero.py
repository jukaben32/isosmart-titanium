# -*- coding: utf-8 -*-
"""
IsoSmart Titanium - Dashboard Financiero
Análisis avanzado de ROI, VAN, TIR, sensibilidad y proyecciones
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import sys
import os

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.financiera import AnalisisFinanciero, calcular_costo_unitario_por_sistema
from app import BudgetCalculator

# Configuración de página
st.set_page_config(
    page_title="Dashboard Financiero - IsoSmart Titanium",
    page_icon="📊",
    layout="wide"
)

# CSS personalizado
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 15px;
        color: white;
        text-align: center;
        margin: 0.5rem 0;
    }
    .metric-card.green {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
    }
    .metric-card.orange {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
    }
    .metric-card.blue {
        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
    }
    .metric-value {
        font-size: 2.5rem;
        font-weight: bold;
        margin: 0;
    }
    .metric-label {
        font-size: 1rem;
        opacity: 0.9;
        margin: 5px 0 0 0;
    }
    .section-header {
        background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
        padding: 1rem 1.5rem;
        border-radius: 10px;
        color: white;
        margin: 2rem 0 1rem 0;
    }
</style>
""", unsafe_allow_html=True)


def format_rd(value: float) -> str:
    """Formatea número como moneda RD$"""
    return f"RD$ {value:,.2f}"


def format_pct(value: float) -> str:
    """Formatea número como porcentaje"""
    return f"{value:.2f}%"


def render_metric_card(label: str, value: str, subtext: str = "", card_class: str = ""):
    """Renderiza una tarjeta de métrica estilizada"""
    card_class_css = f"metric-card {card_class}"
    st.markdown(f"""
    <div class="{card_class_css}">
        <p class="metric-value">{value}</p>
        <p class="metric-label">{label}</p>
        {f'<p style="font-size:0.8rem; opacity:0.8;">{subtext}</p>' if subtext else ''}
    </div>
    """, unsafe_allow_html=True)


def grafico_roi_tiempo(flujos: list, horizonte: int) -> go.Figure:
    """Genera gráfico de ROI a lo largo del tiempo"""
    anios = list(range(horizonte + 1))
    acumulado = []
    running = 0
    for i, flujo in enumerate(flujos):
        if i == 0:
            running = flujo
        else:
            running = acumulado[-1] + flujo if acumulado else flujo
        acumulado.append(running)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=anios,
        y=acumulado,
        mode='lines+markers',
        name='Acumulado',
        line=dict(color='#11998e', width=3),
        fill='tozeroy',
        fillcolor='rgba(17, 153, 142, 0.2)'
    ))

    # Línea de break-even
    fig.add_hline(y=0, line_dash="dash", line_color="gray", annotation_text="Punto de equilibrio")

    fig.update_layout(
        title="Proyección de Ahorro Acumulado",
        xaxis_title="Años",
        yaxis_title="RD$ Acumulado",
        hovermode="x unified",
        template="plotly_white",
        height=400
    )

    return fig


def grafico_sensibilidad_area(df_sensibilidad: pd.DataFrame) -> go.Figure:
    """Genera gráfico de sensibilidad por área"""
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Costo Isotex
    fig.add_trace(
        go.Scatter(x=df_sensibilidad['Area_m2'], y=df_sensibilidad['Costo_Isotex_RD'],
                   name="Costo Isotex", line=dict(color='#4facfe', width=3))
    )

    # Costo Tradicional
    fig.add_trace(
        go.Scatter(x=df_sensibilidad['Area_m2'], y=df_sensibilidad['Costo_Tradicional_RD'],
                   name="Costo Tradicional", line=dict(color='#f5576c', width=3))
    )

    # Porcentaje de ahorro (eje secundario)
    fig.add_trace(
        go.Scatter(x=df_sensibilidad['Area_m2'], y=df_sensibilidad['Ahorro_Pct'],
                   name="Ahorro %", line=dict(color='#38ef7d', width=2, dash='dot'),
                   yaxis='y2')
    )

    fig.update_layout(
        title="Sensibilidad de Costos según Área de Construcción",
        xaxis_title="Área (m²)",
        yaxis_title="Costo Total (RD$)",
        yaxis2=dict(title="Ahorro (%)", overlaying='y', side='right'),
        hovermode="x unified",
        template="plotly_white",
        height=450
    )

    return fig


def grafico_costo_por_categoria(area_m2: float, sistema: str) -> go.Figure:
    """Genera gráfico de costos por categoría"""
    costos = calcular_costo_unitario_por_sistema(area_m2)
    data = costos[sistema]

    categorias = list(data['categorias_obra_gris'].keys()) + list(data['categorias_obra_terminada'].keys())
    valores = list(data['categorias_obra_gris'].values()) + list(data['categorias_obra_terminada'].values())

    fig = go.Figure(data=[go.Pie(
        labels=categorias,
        values=valores,
        hole=0.4,
        textinfo='label+percent',
        marker=dict(colors=px.colors.qualitative.Set3)
    )])

    fig.update_layout(
        title=f"Distribución de Costos - {sistema}",
        height=400,
        template="plotly_white"
    )

    return fig


def grafico_barras_comparativa(area_m2: float) -> go.Figure:
    """Genera gráfico de barras comparativo"""
    costos = calcular_costo_unitario_por_sistema(area_m2)

    sistemas = list(costos.keys())
    obra_gris = [costos[s]['obra_gris_total'] for s in sistemas]
    obra_terminada = [costos[s]['obra_terminada_total'] for s in sistemas]

    fig = go.Figure()
    fig.add_trace(go.Bar(name='Obra Gris', x=sistemas, y=obra_gris, marker_color='#4facfe'))
    fig.add_trace(go.Bar(name='Obra Terminada', x=sistemas, y=obra_terminada, marker_color='#38ef7d'))

    fig.update_layout(
        title=f"Comparativa de Costos por Sistema (Área: {area_m2}m²)",
        xaxis_title="Sistema",
        yaxis_title="Costo (RD$)",
        barmode='stack',
        template="plotly_white",
        height=400
    )

    return fig


def grafico_flujo_caja(df_flujo: pd.DataFrame) -> go.Figure:
    """Genera gráfico de flujo de caja"""
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Flujo neto
    fig.add_trace(go.Bar(
        x=df_flujo['Anio'],
        y=df_flujo['Flujo_Neto_RD'],
        name="Flujo Neto Anual",
        marker_color='#4facfe',
        opacity=0.7
    ))

    # Acumulado
    fig.add_trace(
        go.Scatter(x=df_flujo['Anio'], y=df_flujo['Acumulado_Nominal'],
                   name="Ahorro Acumulado", yaxis='y2',
                   line=dict(color='#11998e', width=3))
    )

    fig.update_layout(
        title="Proyección de Flujo de Caja (20 años)",
        xaxis_title="Año",
        yaxis_title="Flujo Neto Anual (RD$)",
        yaxis2=dict(title="Ahorro Acumulado (RD$)", overlaying='y', side='right'),
        hovermode="x unified",
        template="plotly_white",
        height=450
    )

    return fig


def grafico_comparativa_densidades(df_densidades: pd.DataFrame) -> go.Figure:
    """Genera gráfico comparativo de densidades"""
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=df_densidades['Densidad_Panel'],
        y=df_densidades['Costo_m2_RD'],
        name="Costo/m²",
        marker_color='#4facfe',
        text=df_densidades['Costo_m2_RD'].apply(lambda x: f"RD${x:,.0f}"),
        textposition='outside'
    ))

    fig.add_trace(go.Scatter(
        x=df_densidades['Densidad_Panel'],
        y=df_densidades['Ahorro_Pct'],
        name="Ahorro %",
        yaxis='y2',
        mode='lines+markers',
        line=dict(color='#38ef7d', width=3)
    ))

    fig.update_layout(
        title="Comparativa de Densidades de Panel ISOTEX",
        xaxis_title="Densidad del Panel",
        yaxis_title="Costo por m² (RD$)",
        yaxis2=dict(title="Ahorro vs Tradicional (%)", overlaying='y', side='right'),
        template="plotly_white",
        height=400
    )

    return fig


def main():
    st.markdown("""
    <div style="background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%); padding: 2rem; border-radius: 15px; margin-bottom: 2rem;">
        <h1 style="color: white; margin: 0;">📊 Dashboard Financiero</h1>
        <p style="color: white; opacity: 0.9; margin: 10px 0 0 0;">
            Análisis completo de ROI,VAN, TIR y comparativas de inversión
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Sidebar - Configuración
    with st.sidebar:
        st.markdown("### ⚙️ Configuración")

        area = st.slider("📐 Área de Construcción (m²)", 50, 500, 120, step=10)

        sistema = st.selectbox("🏗️ Sistema", ["Paneles Isotex", "ICF Proform"])

        calidad = st.selectbox("🎨 Calidad", ["económica", "media", "alta", "lujo"])

        st.divider()

        st.markdown("### 📅 Análisis")

        horizonte = st.slider("Horizonte de Inversión (años)", 5, 30, 10)

        tasa_descuento = st.slider("Tasa de Descuento (%)", 5, 25, 12) / 100

        st.divider()

        st.markdown("""
        <div style="background: #f0f2f6; padding: 15px; border-radius: 10px; font-size: 0.9rem;">
            <strong>💡 Nota:</strong><br>
            Este análisis compara el costo total de propiedad a lo largo del tiempo,
            incluyendo ahorro energético y mantenimiento.
        </div>
        """, unsafe_allow_html=True)

    # Calcular datos base
    budget = BudgetCalculator()
    obra_gris, obra_terminada = budget.calcular_presupuesto_completo(
        m2=area,
        sistema=sistema,
        usar_vigas_h=True,
        calidad_terminados=calidad
    )

    total_isotex = obra_gris['Subtotal'].sum() + obra_terminada['Subtotal'].sum()
    comparacion = budget.comparar_sistemas(area)
    total_tradicional = comparacion['tradicional']['costo_total']

    # Análisis ROI
    resultado_roi = AnalisisFinanciero.calcular_roi(
        area_m2=area,
        costo_total_isotex=total_isotex,
        costo_tradicional=total_tradicional,
        horizonte_anios=horizonte,
        tasa_descuento=tasa_descuento
    )

    # ===== SECCIÓN 1: Métricas Principales =====
    st.markdown('<h2 class="section-header">📈 Métricas de Rentabilidad</h2>', unsafe_allow_html=True)

    col_m1, col_m2, col_m3, col_m4 = st.columns(4)

    with col_m1:
        render_metric_card(
            "ROI Nominal",
            format_pct(resultado_roi.roi_nominal),
            f"A {horizonte} años",
            "green"
        )

    with col_m2:
        render_metric_card(
            "ROI Anualizado",
            format_pct(resultado_roi.roi_anualizado),
            "Tasa compuesta",
            "blue"
        )

    with col_m3:
        render_metric_card(
            "Payback",
            f"{resultado_roi.payback_anios:.1f} años",
            "Recuperación inversión",
            "orange"
        )

    with col_m4:
        render_metric_card(
            "VAN",
            format_rd(resultado_roi.van),
            f"Tasa {tasa_descuento*100:.0f}%",
            "green"
        )

    # ===== SECCIÓN 2: Comparativa de Costos =====
    st.markdown('<h2 class="section-header">💰 Comparativa de Costos</h2>', unsafe_allow_html=True)

    col_c1, col_c2, col_c3 = st.columns(3)

    with col_c1:
        st.metric(
            label="Costo Construcción Isotex",
            value=format_rd(total_isotex),
            delta=format_rd(total_isotex / area) + "/m²"
        )

    with col_c2:
        st.metric(
            label="Costo Construcción Tradicional",
            value=format_rd(total_tradicional),
            delta=format_rd(total_tradicional / area) + "/m²",
            delta_color="inverse"
        )

    with col_c3:
        ahorro = total_tradicional - total_isotex
        st.metric(
            label="Ahorro Total",
            value=format_rd(ahorro),
            delta=f"{(ahorro/total_tradicional)*100:.1f}% menos",
            delta_color="normal"
        )

    # ===== SECCIÓN 3: Gráficos Principales =====
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.markdown("##### 📊 Proyección de Ahorro Acumulado")
        fig_roi = grafico_roi_tiempo(resultado_roi.flujo_caja, horizonte)
        st.plotly_chart(fig_roi, use_container_width=True)

    with col_g2:
        st.markdown("##### 🏗️ Costos por Sistema Constructivo")
        fig_barras = grafico_barras_comparativa(area)
        st.plotly_chart(fig_barras, use_container_width=True)

    # ===== SECCIÓN 4: Análisis de Sensibilidad =====
    st.markdown('<h2 class="section-header">🔍 Análisis de Sensibilidad</h2>', unsafe_allow_html=True)

    tab_sens1, tab_sens2, tab_sens3 = st.tabs([
        "📐 Por Área",
        "📦 Por Materiales",
        "⚖️ Por Densidad"
    ])

    with tab_sens1:
        st.markdown("##### Sensibilidad de Costos según Área de Construcción")
        df_sens_area = AnalisisFinanciero.analizar_sensibilidad_area(
            area_min=50, area_max=500, paso=50, sistema="isotex"
        )
        fig_sens_area = grafico_sensibilidad_area(df_sens_area)
        st.plotly_chart(fig_sens_area, use_container_width=True)

        st.markdown("##### Tabla de Sensibilidad por Área")
        df_display = df_sens_area.copy()
        df_display['Costo_Isotex_RD'] = df_display['Costo_Isotex_RD'].apply(format_rd)
        df_display['Costo_Tradicional_RD'] = df_display['Costo_Tradicional_RD'].apply(format_rd)
        df_display['Ahorro_RD'] = df_display['Ahorro_RD'].apply(format_rd)
        df_display['Ahorro_Pct'] = df_display['Ahorro_Pct'].apply(lambda x: f"{x:.1f}%")
        st.dataframe(df_display[['Area_m2', 'Costo_Isotex_RD', 'Costo_Tradicional_RD', 'Ahorro_RD', 'Ahorro_Pct']],
                    use_container_width=True, hide_index=True)

    with tab_sens2:
        st.markdown("##### Impacto de Variación de Precios de Materiales")
        df_sens_mat = AnalisisFinanciero.analizar_sensibilidad_precio_materiales(area)
        st.dataframe(df_sens_mat, use_container_width=True, hide_index=True)

        # Gráfico de sensibilidad
        fig_sens_mat = go.Figure()
        fig_sens_mat.add_trace(go.Bar(
            x=df_sens_mat['Variacion_Pct'],
            y=df_sens_mat['Costo_Ajustado_RD'],
            marker_color='#4facfe',
            text=df_sens_mat['Costo_Ajustado_RD'].apply(lambda x: format_rd(x)),
            textposition='outside'
        ))
        fig_sens_mat.update_layout(
            title="Costo Total según Variación de Precios",
            xaxis_title="Variación (%)",
            yaxis_title="Costo Total (RD$)",
            template="plotly_white",
            height=400
        )
        st.plotly_chart(fig_sens_mat, use_container_width=True)

    with tab_sens3:
        st.markdown("##### Comparativa de Densidades de Panel ISOTEX")
        df_densidades = AnalisisFinanciero.comparar_financiero_densidades(area)
        fig_dens = grafico_comparativa_densidades(df_densidades)
        st.plotly_chart(fig_dens, use_container_width=True)

        st.dataframe(df_densidades, use_container_width=True, hide_index=True)

    # ===== SECCIÓN 5: Proyección de Flujo de Caja =====
    st.markdown('<h2 class="section-header">💵 Proyección de Flujo de Caja</h2>', unsafe_allow_html=True)

    df_flujo = AnalisisFinanciero.generar_proyeccion_flujo_caja(
        area_m2=area,
        costo_total=total_isotex,
        horizonte_anios=20,
        tasa_crecimiento_energia=0.05,
        tasa_descuento=tasa_descuento
    )

    col_f1, col_f2 = st.columns([2, 1])

    with col_f1:
        fig_flujo = grafico_flujo_caja(df_flujo)
        st.plotly_chart(fig_flujo, use_container_width=True)

    with col_f2:
        st.markdown("##### Resumen de Proyección (20 años)")

        total_ahorro = df_flujo['Flujo_Neto_RD'].sum()
        van_final = df_flujo['Valor_Presente_RD'].sum()

        st.metric("Ahorro Total Nominal", format_rd(total_ahorro))
        st.metric("Valor Presente Neto", format_rd(van_final))
        st.metric("Flujo Promedio Anual", format_rd(total_ahorro / 20))

        st.divider()

        # Tabla de primeros años
        st.markdown("##### Primeros 5 años")
        df_5anios = df_flujo.head(5).copy()
        df_5anios['Flujo_Neto_RD'] = df_5anios['Flujo_Neto_RD'].apply(format_rd)
        st.dataframe(df_5anios[['Anio', 'Flujo_Neto_RD', 'Acumulado_Nominal']],
                    use_container_width=True, hide_index=True)

    # ===== SECCIÓN 6: Costos de Financiamiento =====
    st.markdown('<h2 class="section-header">🏦 Análisis de Financiamiento</h2>', unsafe_allow_html=True)

    col_fin1, col_fin2, col_fin3 = st.columns(3)

    with col_fin1:
        tasa_banco = st.slider("Tasa de Interés Anual (%)", 8, 25, 15) / 100

    with col_fin2:
        plazo_meses = st.select_slider("Plazo", options=[12, 24, 36, 48, 60, 72, 84, 120], value=60)

    with col_fin3:
        porcentaje_financiar = st.slider("Porcentaje a Financiar (%)", 50, 100, 80) / 100

    monto_financiar = total_isotex * porcentaje_financiar
    financiamiento = AnalisisFinanciero.calcular_costo_financiamiento(
        monto=monto_financiar,
        tasa_anual=tasa_banco,
        plazo_meses=plazo_meses
    )

    col_fm1, col_fm2, col_fm3, col_fm4 = st.columns(4)

    with col_fm1:
        st.metric("Monto del Préstamo", format_rd(financiamiento['monto_prestamo']))

    with col_fm2:
        st.metric("Cuota Mensual", format_rd(financiamiento['cuota_mensual']))

    with col_fm3:
        st.metric("Total Intereses", format_rd(financiamiento['total_intereses']))

    with col_fm4:
        st.metric("Total a Pagar", format_rd(financiamiento['total_pagado']))

    # ===== SECCIÓN 7: Costo Total de Propiedad =====
    st.markdown('<h2 class="section-header">📋 Costo Total de Propiedad (TCO)</h2>', unsafe_allow_html=True)

    # Comparación TCO Isotex vs Tradicional
    col_tco1, col_tco2 = st.columns(2)

    with col_tco1:
        st.markdown(f"""
        ### 🏠 ISOTEX ({area}m²)
        - **Costo inicial:** {format_rd(total_isotex)}
        - **Mantenimiento (20 años):** {format_rd(total_isotex * 0.015 * 20)}
        - **Seguro (20 años):** {format_rd(total_isotex * 0.005 * 20)}
        - **TCO:** **{format_rd(resultado_roi.tco)}**
        """)

    with col_tco2:
        tco_trad = comparacion['tradicional']['costo_total']
        mantenimiento_trad = tco_trad * 0.02 * 20
        seguro_trad = tco_trad * 0.008 * 20
        tco_trad_total = tco_trad + mantenimiento_trad + seguro_trad

        st.markdown(f"""
        ### 🧱 Tradicional ({area}m²)
        - **Costo inicial:** {format_rd(tco_trad)}
        - **Mantenimiento (20 años):** {format_rd(mantenimiento_trad)}
        - **Seguro (20 años):** {format_rd(seguro_trad)}
        - **TCO:** **{format_rd(tco_trad_total)}**
        """)

    # Gráfico TCO comparativo
    fig_tco = go.Figure()

    categorias_tco = ['Costo Inicial', 'Mantenimiento (20a)', 'Seguro (20a)', 'Energía (20a)']
    isotex_tco = [
        total_isotex,
        total_isotex * 0.015 * 20,
        total_isotex * 0.005 * 20,
        AnalisisFinanciero.calcular_ahorro_energia_mensual(area, "isotex")["ahorro_rd_mes"] * 12 * 20
    ]
    trad_tco = [
        tco_trad,
        tco_trad * 0.02 * 20,
        tco_trad * 0.008 * 20,
        0  # Sin ahorro energético
    ]

    fig_tco.add_trace(go.Bar(name='ISOTEX', x=categorias_tco, y=isotex_tco, marker_color='#4facfe'))
    fig_tco.add_trace(go.Bar(name='Tradicional', x=categorias_tco, y=trad_tco, marker_color='#f5576c'))

    fig_tco.update_layout(
        title="Comparativa TCO - 20 Años",
        xaxis_title="Categoría",
        yaxis_title="Costo (RD$)",
        barmode='group',
        template="plotly_white",
        height=400
    )

    st.plotly_chart(fig_tco, use_container_width=True)

    # ===== FOOTER =====
    st.divider()
    st.markdown("""
    <div style="text-align: center; color: #666; font-size: 0.9rem;">
        <p><strong>IsoSmart Titanium</strong> - Sistema de Análisis Financiero</p>
        <p>Nota: Los cálculos son estimaciones basadas en precios promedio del mercado chileno.
        Consulte con su proveedor para cotizaciones exactas.</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
