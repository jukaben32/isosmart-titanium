# -*- coding: utf-8 -*-
"""Página 💰 Finanzas: ROI, VAN, TIR y comparativa desde el proyecto activo."""
import os

import pandas as pd
import streamlit as st

from ui_core import render_guard_sin_proyecto
from utils.estado import ProyectoState
from utils.estilos import encabezado, inyectar_css
from utils.pricebook import Pricebook
from utils.qto import MotorQTO


def _cargar_precios():
    """Precios sincronizados en sesión, o el pricebook local como respaldo."""
    precio_guardado = st.session_state.get("precios_sincronizados")
    if precio_guardado is not None:
        return precio_guardado
    return Pricebook(os.path.join("data", "pricebook.json")).load()


def pagina_finanzas():
    """Punto de entrada de la página Finanzas."""
    inyectar_css()
    if not render_guard_sin_proyecto():
        return

    # Imports diferidos: el dashboard llama a inyectar_css() al importarse y
    # solo debe ocurrir con Streamlit ejecutándose (no en tests).
    from paginas.dashboard_financiero import (  # noqa: PLC0415
        format_pct,
        format_rd,
        grafico_barras_comparativa,
        grafico_roi_tiempo,
    )
    from utils.financiera import AnalisisFinanciero  # noqa: PLC0415

    estado = ProyectoState.cargar()
    encabezado(
        "💰 Finanzas",
        "ROI, VAN y comparativa de inversión de tu vivienda EPS/ICF frente "
        "a la construcción tradicional.",
    )
    st.caption(
        f"Proyecto **{estado.area_m2:,.0f} m²** con cerramiento {estado.sistema} "
        f"y calidad {estado.calidad}."
    )

    with st.expander("📅 Ajustes del análisis", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            horizonte = st.slider("Horizonte de inversión (años)", 5, 30, 10)
        with c2:
            tasa_descuento = st.slider("Tasa de descuento (%)", 5, 25, 12) / 100.0

    precios = _cargar_precios()
    geo = estado.geometria()
    motor = MotorQTO(geo, precios, sistema=estado.sistema, calidad=estado.calidad)
    comp = motor.comparar_con_tradicional()
    total_eps = comp["eps"]["costo_total"]
    total_trad = comp["tradicional"]["costo_total"]

    roi = AnalisisFinanciero.calcular_roi(
        area_m2=estado.area_m2,
        costo_total_isotex=total_eps,
        costo_tradicional=total_trad,
        horizonte_anios=int(horizonte),
        tasa_descuento=tasa_descuento,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📈 ROI total", format_pct(roi.roi_nominal))
    c2.metric("ROI anualizado", format_pct(roi.roi_anualizado))
    c3.metric("⏱️ Payback", f"{roi.payback_anios:.1f} años" if roi.payback_anios else "—")
    c4.metric("💹 VAN", format_rd(roi.van))

    c5, c6 = st.columns(2)
    c5.metric("Inversión EPS/ICF", format_rd(total_eps))
    c6.metric("Obra gris tradicional", format_rd(total_trad))

    st.markdown("### 📊 Proyección")
    g1, g2 = st.columns(2)
    with g1:
        st.plotly_chart(
            grafico_roi_tiempo(roi.flujo_caja, int(horizonte)),
            use_container_width=True,
        )
    with g2:
        st.plotly_chart(
            grafico_barras_comparativa(estado.area_m2),
            use_container_width=True,
        )

    with st.expander("Cuadro comparativo detallado", expanded=False):
        df_comp = pd.DataFrame(
            {
                "Concepto": ["Obra gris", "Obra terminada", "TOTAL", "RD$/m²"],
                "EPS / ICF": [
                    comp["eps"]["obra_gris"],
                    comp["eps"]["obra_terminada"],
                    comp["eps"]["costo_total"],
                    comp["eps"]["costo_m2"],
                ],
                "Tradicional": [
                    comp["tradicional"]["obra_gris"],
                    comp["tradicional"]["obra_terminada"],
                    comp["tradicional"]["costo_total"],
                    comp["tradicional"]["costo_m2"],
                ],
            }
        ).style.format({"EPS / ICF": "{:,.0f}", "Tradicional": "{:,.0f}"})
        st.dataframe(df_comp, use_container_width=True, hide_index=True)

    st.caption(
        "El ROI parte del ahorro energético y de climatización. Es tu vivienda "
        "concreta, no un promedio genérico."
    )


if __name__ == "__main__":
    pagina_finanzas()