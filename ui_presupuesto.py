"""Módulo de interfaz de IsoSmart Titanium (refactor de app.py, 2026-07-10)."""
import os

import pandas as pd
import streamlit as st

from ui_core import (
    get_gemini_api_key_from_config,
    initialize_gemini,
)

# Helpers compartidos desde ui_core
from ui_vision import render_integradora_vision_canvas
from utils.estado import ProyectoState
from utils.qto import CATEGORIAS_OBRA_GRIS, MotorQTO
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

    # Materiales que el motor QTO consume hoy (fuente única desde Fase 1). El
    # resto se muestra pero se marca honestamente como sin efecto sobre el
    # presupuesto: editarlos y ver "guardado" sin que cambie nada era una
    # promesa falsa de la interfaz.
    usados = MotorQTO.claves_precio_usadas()

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

    # ------------------------------------------------------------------
    # Motor de cálculo: MotorQTO (antes: BudgetCalculator, motor clásico).
    #
    # Esta pestaña mostraba solo la obra gris (ignoraba obra terminada en el
    # total), con sistema fijo en "Paneles Isotex" y sin usar el perímetro,
    # niveles o zona de riesgo que el usuario ya hubiera calibrado en la
    # pestaña "📐 Visión & Geometría" de este mismo Panel Operativo.
    # ------------------------------------------------------------------
    estado = ProyectoState.cargar()
    estado.area_m2 = area
    geo = estado.geometria()
    motor = MotorQTO(geo, precios, sistema=estado.sistema, calidad=estado.calidad,
                     zona_riesgo=estado.zona_riesgo)

    df_completo = motor.presupuesto()

    st.markdown("##### 🧱 Costos de Obra Gris Estructural")
    st.dataframe(df_completo[df_completo["categoria"].isin(CATEGORIAS_OBRA_GRIS)],
                use_container_width=True)

    st.metric("Total Neto Estructural (obra gris)", f"RD$ {motor.total_obra_gris():,.2f}")
    st.metric("Total General (gris + terminada)", f"RD$ {motor.total():,.2f}")

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



# ============================================================================
# PRESUPUESTO DETALLADO (motor QTO) — Fase 1 de la auditoría
# ============================================================================

def pagina_presupuesto_detallado():
    """
    Presupuesto por partidas con el motor `utils/qto.py`.

    A diferencia de la calculadora clásica, esta vista:
      - consume la geometría real (perímetro, altura, niveles) en vez de m²x2.2
      - incluye mortero, mallas, anclas, instalaciones, acabados y mano de obra
      - compara obra gris contra obra gris (27.5%), no gris contra terminada
    """
    from utils.geometria import Geometria
    from utils.qto import MotorQTO

    st.title("🧾 Presupuesto Detallado por Partidas")
    st.caption(
        "Motor basado en `docs/BASE_TECNICA_EPS_ICF.md`: espesores reales de mortero "
        "(2.5 cm/cara), mallas, cimentación completa y mano de obra."
    )

    with st.sidebar:
        st.markdown("### 📐 Geometría")
        area = st.number_input("Área construida total (m²)", min_value=20.0, max_value=5000.0,
                               value=float(st.session_state.get("calc_area_m2", 120.0)), step=10.0)
        perimetro = st.number_input("Perímetro de planta (m)", min_value=0.0, max_value=1000.0,
                                    value=float(st.session_state.get("calc_perimetro_m", 0.0) or 0.0),
                                    step=1.0,
                                    help="0 = estimar automáticamente con proporción 3:2")
        altura = st.number_input("Altura de muro (m)", min_value=2.2, max_value=6.0,
                                 value=float(st.session_state.get("calc_altura_muro_m", 2.8)), step=0.1)
        niveles = st.number_input("Niveles", min_value=1, max_value=20,
                                  value=int(st.session_state.get("calc_niveles", 1)))

        st.markdown("### ⚙️ Configuración")
        sistema = st.selectbox("Sistema", ["Paneles Isotex", "ICF Proform"])
        calidad = st.selectbox("Calidad de terminados", ["economica", "media", "alta", "lujo"], index=1)
        zona = st.selectbox("Zona de riesgo", ["Moderado (Base)", "Alto", "Muy Alto"])
        lanzadora = st.checkbox("Aplanado con lanzadora neumática", value=False,
                                help="60-70 m²/día frente a 15-20 m²/día manual")

        with st.expander("🪟 Dimensiones reales de vanos", expanded=False):
            st.caption(
                "La malla zigzag está calibrada para ventanas de 90x90 cm y puertas "
                "de 215x90 cm (docs/BASE_TECNICA_EPS_ICF.md). Si tus vanos son más "
                "grandes, indícalo aquí -- si no, la malla se queda corta sin avisar."
            )
            col_v1, col_v2 = st.columns(2)
            with col_v1:
                ancho_ventana = st.number_input("Ancho de ventana (m)", min_value=0.3, max_value=4.0,
                                                value=0.90, step=0.1)
                ancho_puerta = st.number_input("Ancho de puerta (m)", min_value=0.5, max_value=2.5,
                                               value=0.90, step=0.1)
            with col_v2:
                alto_ventana = st.number_input("Alto de ventana (m)", min_value=0.3, max_value=3.0,
                                               value=0.90, step=0.1)
                alto_puerta = st.number_input("Alto de puerta (m)", min_value=1.8, max_value=3.0,
                                              value=2.15, step=0.05)

    geo = Geometria(
        area_m2=area,
        perimetro_m=perimetro or None,
        altura_muro_m=altura,
        niveles=int(niveles),
        ancho_ventana_m=ancho_ventana,
        alto_ventana_m=alto_ventana,
        ancho_puerta_m=ancho_puerta,
        alto_puerta_m=alto_puerta,
    )
    precios = st.session_state.get("precios_sincronizados") or Pricebook(
        os.path.join("data", "pricebook.json")
    ).load()

    try:
        motor = MotorQTO(geo, precios, sistema=sistema, calidad=calidad,
                         zona_riesgo=zona, aplanado_mecanizado=lanzadora)
        df = motor.presupuesto()
    except (KeyError, ValueError) as e:
        st.error(f"No se pudo calcular el presupuesto: {e}")
        return

    # -- métricas ---------------------------------------------------------
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total", f"RD$ {motor.total():,.0f}")
    c2.metric("Costo por m²", f"RD$ {motor.costo_m2():,.0f}")
    c3.metric("Obra gris", f"RD$ {motor.total_obra_gris():,.0f}")
    c4.metric("Obra terminada", f"RD$ {motor.total_obra_terminada():,.0f}",
              f"{motor.total_obra_terminada()/motor.total()*100:.0f}% del total")

    # -- geometría derivada ----------------------------------------------
    with st.expander("📐 Geometría derivada del proyecto", expanded=False):
        st.caption(
            "Estos valores ya alimentan el cálculo. Antes se extraían del plano "
            "y no los leía nadie."
        )
        st.dataframe(pd.DataFrame([geo.resumen()]).T.rename(columns={0: "Valor"}),
                     use_container_width=True)

    # -- comparación gris vs gris ----------------------------------------
    comp = motor.comparar_con_tradicional()
    st.markdown("### ⚖️ Comparación con construcción tradicional")
    st.info(
        f"**Ahorro sobre obra gris: {comp['ahorro']['obra_gris_pct']:.1f}%** "
        f"(rango documentado: {comp['rango_ahorro_gris'][0]:.0f}–{comp['rango_ahorro_gris'][1]:.0f}%). "
        f"Sobre el **total** el ahorro es de **{comp['ahorro']['total_pct']:.1f}%**, "
        f"porque los acabados son iguales en ambos sistemas. "
        f"Ésta es la cifra que resiste una revisión técnica."
    )
    st.dataframe(pd.DataFrame({
        "Concepto": ["Obra gris", "Obra terminada", "TOTAL", "RD$/m²", "Plazo (días)"],
        "EPS / ICF": [comp["eps"]["obra_gris"], comp["eps"]["obra_terminada"],
                      comp["eps"]["costo_total"], comp["eps"]["costo_m2"], comp["eps"]["dias"]],
        "Tradicional": [comp["tradicional"]["obra_gris"], comp["tradicional"]["obra_terminada"],
                        comp["tradicional"]["costo_total"], comp["tradicional"]["costo_m2"],
                        comp["tradicional"]["dias"]],
    }).style.format({"EPS / ICF": "{:,.0f}", "Tradicional": "{:,.0f}"}),
        use_container_width=True)

    # -- desglose ---------------------------------------------------------
    st.markdown("### 📊 Desglose por categoría")
    st.dataframe(motor.resumen_por_categoria(), use_container_width=True)

    st.markdown("### 📋 Partidas")
    st.dataframe(df, use_container_width=True, height=420)

    # -- honestidad sobre los precios ------------------------------------
    por_verificar = motor.partidas_por_verificar()
    if not por_verificar.empty:
        monto = por_verificar["subtotal"].sum()
        st.warning(
            f"⚠️ **{len(por_verificar)} partidas (RD$ {monto:,.0f}, "
            f"{monto/motor.total()*100:.0f}% del presupuesto) usan precios de REFERENCIA**, "
            "no cotizaciones de proveedor. Sustitúyelos antes de entregar este "
            "presupuesto a un cliente."
        )
        with st.expander("Ver partidas con precio por verificar"):
            st.dataframe(por_verificar, use_container_width=True)

    # -- exportación ------------------------------------------------------
    st.download_button(
        "📥 Descargar presupuesto (CSV)",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=f"presupuesto_{int(area)}m2.csv",
        mime="text/csv",
        use_container_width=True,
    )
