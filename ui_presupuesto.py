# -*- coding: utf-8 -*-
"""Módulo de interfaz de IsoSmart Titanium (refactor de app.py, 2026-07-10)."""
import os

import streamlit as st

from ui_core import (
    get_gemini_api_key_from_config,
    initialize_gemini,
)

# Helpers compartidos desde ui_core
from ui_vision import render_integradora_vision_canvas
from utils.calculador import BudgetCalculator
from utils.financiera import AnalisisFinancieroRD
from utils.pricebook import Pricebook


def render_pestana_pricebook():
    """
    Pestaña: Panel de Control del Libro de Precios RD.

    FUENTE ÚNICA: ahora usa la clase `Pricebook` (escritura atómica + merge con
    los 27 materiales por defecto). Antes esta función tenía su propio
    diccionario de 8 precios hardcodeados y escribía el JSON con `open(w)`
    directo, ignorando `write_json_atomic` y sin `encoding="utf-8"`.
    """
    st.subheader("⚙️ Panel de Control del Libro de Precios RD")
    st.caption(
        "Precios de REFERENCIA (Covintex convertidos a RD$). "
        "Sustituir por precios reales de proveedor antes de emitir cotizaciones."
    )

    libro = Pricebook(os.path.join("data", "pricebook.json"))
    precios = libro.load()

    # Materiales que el motor de cálculo consume hoy. El resto se muestra pero
    # se marca honestamente como sin efecto sobre el presupuesto: editarlos y
    # ver "guardado" sin que cambie nada era una promesa falsa de la interfaz.
    usados = BudgetCalculator.claves_precio_usadas()

    activos = {k: v for k, v in precios.items() if k in usados}
    inactivos = {k: v for k, v in precios.items() if k not in usados}

    st.markdown("#### ✅ Materiales que afectan el presupuesto")
    cols = st.columns(3)
    for i, clave in enumerate(sorted(activos)):
        with cols[i % 3]:
            precios[clave] = st.number_input(
                clave.replace("_", " "),
                value=float(precios[clave]),
                min_value=0.0,
                step=25.0,
                key=f"pb_act_{clave}",
            )

    with st.expander(
        f"⚠️ {len(inactivos)} materiales aún NO conectados al motor de cálculo",
        expanded=False,
    ):
        st.warning(
            "Estos precios se guardan, pero todavía no entran en ninguna partida "
            "del presupuesto (instalaciones, baños, cocina, ventanas, mallas...). "
            "Se conectan en la migración al motor de partidas `utils/qto.py`."
        )
        cols2 = st.columns(3)
        for i, clave in enumerate(sorted(inactivos)):
            with cols2[i % 3]:
                precios[clave] = st.number_input(
                    clave.replace("_", " "),
                    value=float(precios[clave]),
                    min_value=0.0,
                    step=25.0,
                    key=f"pb_ina_{clave}",
                )

    if st.button("💾 Guardar y Sincronizar Libro de Precios",
                 use_container_width=True, type="primary"):
        libro.save(precios)                       # escritura atómica + utf-8
        st.session_state["precios_sincronizados"] = precios
        st.success("¡Libro de precios sincronizado!")

    st.session_state.setdefault("precios_sincronizados", precios)


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
    df_gris, df_term = BudgetCalculator.calcular_presupuesto_completo(area, "Paneles Isotex", precios)

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

