# -*- coding: utf-8 -*-
"""Página ⚡ Solar: sistema fotovoltaico según el tamaño y la demanda real."""
import pandas as pd
import streamlit as st

from ui_core import render_guard_sin_proyecto
from utils.energia import AnalisisEnergetico
from utils.estado import ProyectoState
from utils.estilos import encabezado, inyectar_css


def pagina_solar():
    """Punto de entrada de la página Solar."""
    inyectar_css()
    if not render_guard_sin_proyecto():
        return

    estado = ProyectoState.cargar()
    encabezado(
        "⚡ Solar",
        "Paneles, inversor y baterías dimensionados para tu vivienda y su zona.",
    )

    with st.expander("☀️ Ajustes del sistema solar", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            cobertura = st.slider("Cobertura del consumo mensual", 50, 100, 90, 5)
        with c2:
            incluir_baterias = st.checkbox("Incluir respaldo con baterías", value=True)
        with c3:
            costo_por_watt = st.slider("Costo instalado por watt (RD$)", 20, 90, 45, 5)

    solar = AnalisisEnergetico.calcular_sistema_solar_recomendado(
        estado.area_m2,
        sistema=estado.sistema,
        cobertura_pct=float(cobertura),
        incluir_baterias=incluir_baterias,
        costo_por_watt=float(costo_por_watt),
    )

    st.caption(
        f"Proyecto **{estado.area_m2:,.0f} m²** con cerramiento {estado.sistema}: "
        f"el consumo estimado ronda los **{solar['consumo_total_kwh_mes']:,.0f} kWh/mes**."
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🔆 Paneles", f"{solar['paneles_necesarios']} × {solar['potencia_panel_w']:.0f} W")
    c2.metric("⚡ Capacidad", f"{solar['capacidad_sistema_kw']:.2f} kW")
    c3.metric("🔌 Inversor", f"{solar['inversor_kw']:.0f} kW")
    c4.metric(
        "🔋 Baterías",
        f"{solar['baterias_necesarias']} ({solar['banco_baterias_kwh']:,.0f} kWh)"
        if incluir_baterias
        else "Sin respaldo",
    )

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("🌤️ Energía estimada", f"{solar['energia_mensual_kwh']:,.0f} kWh/mes")
    c6.metric("💸 Ahorro mensual", f"RD$ {solar['ahorro_solar_mensual_rd']:,.0f}")
    c7.metric("🏷️ Costo estimado", f"RD$ {solar['costo_estimado_rd']:,.0f}")
    c8.metric("🌱 CO₂ evitado", f"{solar['co2_evitable_solar_kg_anio']:,.0f} kg/año")

    if not solar["area_techo_suficiente"]:
        st.warning(
            f"⚠️ El sistema necesita **{solar['area_techo_requerida_m2']:,.0f} m²** de techo "
            f"y se estiman **{solar['area_techo_disponible_m2']:,.0f} m²** disponibles sin el "
            "plano de techo. Verifícalo en el dibujo antes de comprar."
        )
    else:
        st.success(
            f"✅ El techo estimado ({solar['area_techo_disponible_m2']:,.0f} m²) alcanza para "
            f"el sistema propuesto ({solar['area_techo_requerida_m2']:,.0f} m²)."
        )

    st.markdown("### 🧩 Componentes del sistema")
    st.dataframe(
        pd.DataFrame(solar["componentes"]),
        use_container_width=True,
        height=300,
        hide_index=True,
    )

    with st.expander("🔧 Previsiones eléctricas para tu plano", expanded=False):
        for prevision in solar["previsiones_electricas"]:
            st.markdown(f"- {prevision}")
        st.caption(
            "Estas previsiones se incluyen en el brief de la pestaña 📐 Plano "
            "cuando creas una orden CAD."
        )


if __name__ == "__main__":
    pagina_solar()