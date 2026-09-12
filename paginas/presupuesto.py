# -*- coding: utf-8 -*-
"""Página 🧮 Presupuesto: partidas exactas EPS/ICF desde el proyecto activo."""
import os
from io import BytesIO

import pandas as pd
import streamlit as st

from ui_core import PDFGenerator, render_guard_sin_proyecto
from utils.escenarios import calcular_escenarios
from utils.estado import ProyectoState
from utils.estilos import encabezado, inyectar_css
from utils.pricebook import Pricebook
from utils.qto import CATEGORIAS_OBRA_GRIS, MotorQTO


def _cargar_precios():
    """Precios sincronizados en sesión, o el pricebook local como respaldo."""
    precio_guardado = st.session_state.get("precios_sincronizados")
    if precio_guardado is not None:
        return precio_guardado
    return Pricebook(os.path.join("data", "pricebook.json")).load()


def pagina_presupuesto():
    """Punto de entrada de la página Presupuesto."""
    inyectar_css()
    if not render_guard_sin_proyecto():
        return

    estado = ProyectoState.cargar()
    encabezado(
        "🧮 Presupuesto",
        "Partidas exactas de materiales y mano de obra para tu vivienda EPS/ICF.",
    )
    st.caption(
        f"Proyecto: **{estado.area_m2:,.0f} m²** · {estado.niveles} nivel(es) · "
        f"{estado.sistema} · calidad {estado.calidad}"
    )

    precios = _cargar_precios()
    geo = estado.geometria()
    motor = MotorQTO(
        geo,
        precios,
        sistema=estado.sistema,
        calidad=estado.calidad,
        zona_riesgo=estado.zona_riesgo,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Total", f"RD$ {motor.total():,.0f}")
    c2.metric("Por m²", f"RD$ {motor.costo_m2():,.0f}")
    c3.metric("🏗️ Obra gris", f"RD$ {motor.total_obra_gris():,.0f}")
    c4.metric("✨ Obra terminada", f"RD$ {motor.total_obra_terminada():,.0f}")

    comp = motor.comparar_con_tradicional()
    st.info(
        f"**Misma vivienda en obra gris tradicional:** RD$ "
        f"{comp['tradicional']['costo_total']:,.0f} "
        f"({comp['tradicional']['costo_m2']:,.0f} RD$/m²). Es un punto de "
        "referencia; el valor real de EPS se ve en la pestaña 💰 Finanzas."
    )

    df = motor.presupuesto()
    escenarios_df = calcular_escenarios(geo, precios)
    por_verificar = motor.partidas_por_verificar()

    _render_exportacion(estado, df, motor, escenarios_df, por_verificar)

    st.markdown("### 🧭 Escenarios rápidos")
    st.dataframe(
        escenarios_df.style.format(
            {
                "total": "RD$ {:,.0f}",
                "costo_m2": "RD$ {:,.0f}",
                "obra_gris": "RD$ {:,.0f}",
                "obra_terminada": "RD$ {:,.0f}",
                "ahorro_total_pct": "{:.1f}%",
            }
        ),
        use_container_width=True,
        height=220,
    )
    if escenarios_df["incompleto"].any():
        st.warning(
            "Los escenarios con techo Isotex real aparecen como incompletos si su "
            "precio por m² sigue en RD$0.00. Esa parte queda pendiente hasta tener "
            "cotización."
        )

    st.markdown("### 📊 Desglose por categoría")
    st.dataframe(motor.resumen_por_categoria(), use_container_width=True)

    # Partidas separadas entre obra gris y obra terminada (mismo criterio del PDF).
    obra_gris_df = df[df["categoria"].isin(CATEGORIAS_OBRA_GRIS)].reset_index(drop=True)
    obra_terminada_df = df[~df["categoria"].isin(CATEGORIAS_OBRA_GRIS)].reset_index(drop=True)
    con_gris, con_ter = st.tabs(["🏗️ Obra gris", "✨ Obra terminada"])
    with con_gris:
        st.dataframe(obra_gris_df, use_container_width=True, height=360)
    with con_ter:
        st.dataframe(obra_terminada_df, use_container_width=True, height=360)

    # Honestidad: precios que aún son referencia, no cotización.
    por_verificar = motor.partidas_por_verificar()
    if not por_verificar.empty:
        monto = por_verificar["subtotal"].sum()
        st.warning(
            f"⚠️ **{len(por_verificar)} partidas (RD$ {monto:,.0f}, "
            f"{monto / motor.total() * 100:.0f}% del presupuesto) usan precios de "
            "REFERENCIA**, no cotizaciones de proveedor."
        )
        with st.expander("Ver partidas con precio por verificar"):
            st.dataframe(por_verificar, use_container_width=True)

    with st.expander("⚠️ Condiciones que este motor NO calcula", expanded=False):
        st.caption("Si tu proyecto tiene alguna de estas condiciones, presupuéstala aparte.")
        for limitacion in MotorQTO.limitaciones_conocidas():
            st.markdown(f"- {limitacion}")


def _render_exportacion(estado, df, motor, escenarios_df, por_verificar):
    """Botones CSV / Excel / PDF con el nombre de archivo basado en el área."""
    area = estado.area_m2
    st.markdown("### 📥 Exportar")
    with st.expander("Descargar exportaciones (PDF, Excel, CSV)", expanded=True):
        pdf = PDFGenerator().generar_propuesta(
            "Proyecto Residencial",
            {
                "area": area,
                "sistema": estado.sistema,
                "calidad": estado.calidad,
                "zona_riesgo": estado.zona_riesgo,
            },
            df,
            motor.total(),
        )
        st.download_button(
            f"📄 Descargar PDF con presupuesto total (RD$ {motor.total():,.0f})",
            data=pdf,
            file_name=f"propuesta_comercial_{int(area)}m2.pdf",
            mime="application/pdf",
            use_container_width=True,
            type="primary",
        )

        st.download_button(
            "📥 Descargar presupuesto (CSV)",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name=f"presupuesto_{int(area)}m2.csv",
            mime="text/csv",
            use_container_width=True,
        )

        excel = BytesIO()
        with pd.ExcelWriter(excel, engine="xlsxwriter") as writer:
            df.to_excel(writer, sheet_name="Partidas", index=False)
            motor.resumen_por_categoria().to_excel(writer, sheet_name="Resumen", index=False)
            por_verificar.to_excel(writer, sheet_name="Precios por verificar", index=False)
            escenarios_df.to_excel(writer, sheet_name="Escenarios", index=False)
        st.download_button(
            "📊 Descargar Excel completo",
            data=excel.getvalue(),
            file_name=f"presupuesto_detallado_{int(area)}m2.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )


if __name__ == "__main__":
    pagina_presupuesto()