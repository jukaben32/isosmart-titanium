"""Módulo de interfaz de IsoSmart Titanium (refactor de app.py, 2026-07-10)."""
import os
from io import BytesIO

import pandas as pd
import streamlit as st

from ui_core import (
    PDFGenerator,
    get_gemini_api_key_from_config,
    initialize_gemini,
)

# Helpers compartidos desde ui_core
from ui_vision import render_integradora_vision_canvas
from utils.estado import ProyectoState
from utils.dxf_importer import analizar_dxf_bytes
from utils.escenarios import calcular_escenarios
from utils.qto import CATEGORIAS_OBRA_GRIS, MotorQTO
from utils.financiera import AnalisisFinancieroRD
from utils.instalaciones import InstalacionesDetalle
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

    estado_guardado = ProyectoState.cargar()

    with st.sidebar:
        st.markdown("### 📥 Importar DXF")
        archivo_dxf = st.file_uploader(
            "Plano CAD (.dxf)",
            type=["dxf"],
            help="Lee capas como A-MUROS, A-PUERTAS, A-VENTANAS e I-* para alimentar el presupuesto.",
        )
        if archivo_dxf is not None:
            try:
                mediciones = analizar_dxf_bytes(archivo_dxf.getvalue())
                st.success(
                    f"Detectado: {mediciones.area_m2:,.2f} m², "
                    f"{mediciones.perimetro_m:,.2f} ml, "
                    f"{mediciones.ventanas} ventanas, "
                    f"{mediciones.puertas_interiores + mediciones.puertas_exteriores} puertas."
                )
                if mediciones.advertencias:
                    for advertencia in mediciones.advertencias:
                        st.warning(advertencia)
                if st.button("Usar mediciones del DXF", use_container_width=True):
                    estado_dxf = ProyectoState.cargar()
                    estado_dxf.aplicar_metricas(mediciones.a_metricas(), origen=f"DXF: {archivo_dxf.name}")
                    estado_dxf.guardar()
                    st.rerun()
            except Exception as e:
                st.error(f"No pude leer este DXF: {e}")

        st.divider()
        st.markdown("### 📐 Geometría")
        area = st.number_input("Área construida total (m²)", min_value=20.0, max_value=5000.0,
                               value=float(estado_guardado.area_m2), step=10.0)
        perimetro = st.number_input("Perímetro de planta (m)", min_value=0.0, max_value=1000.0,
                                    value=float(estado_guardado.perimetro_m or 0.0),
                                    step=1.0,
                                    help="0 = estimar automáticamente con proporción 3:2")
        altura = st.number_input("Altura de muro (m)", min_value=2.2, max_value=6.0,
                                 value=float(estado_guardado.altura_muro_m), step=0.1)
        niveles = st.number_input("Niveles", min_value=1, max_value=20,
                                  value=int(estado_guardado.niveles))
        # Antes ausente de la interfaz: una casa en L (6 esquinas típicas,
        # 4 convexas + 2 cóncavas) se calculaba siempre con 4 esquinas por
        # defecto, sin manera de corregirlo. Verificado con NotebookLM del
        # usuario: esquinas entrantes y salientes reciben el mismo
        # tratamiento (una tira interna + una externa cada una), así que
        # solo hace falta el conteo total, no distinguir el tipo.
        esquinas = st.number_input("Número de esquinas", min_value=4, max_value=20,
                                   value=int(estado_guardado.esquinas or 4),
                                   help="4 para una planta rectangular simple. Una casa en L "
                                        "típica tiene 6 (4 convexas + 2 cóncavas); ambos tipos "
                                        "llevan el mismo tratamiento de malla esquinera.")

        with st.expander("Programa real de ambientes", expanded=False):
            ventanas = st.number_input("Ventanas", min_value=0, max_value=500,
                                       value=int(estado_guardado.n_ventanas or 0),
                                       help="0 = estimación automática por área")
            puertas_interiores = st.number_input("Puertas interiores", min_value=0, max_value=500,
                                                 value=int(estado_guardado.n_puertas_interiores or 0),
                                                 help="0 = estimación automática por área")
            puertas_exteriores = st.number_input("Puertas exteriores", min_value=0, max_value=100,
                                                 value=int(estado_guardado.n_puertas_exteriores or 0),
                                                 help="0 = estimación automática de la app")
            banos = st.number_input("Baños", min_value=0, max_value=100,
                                    value=int(estado_guardado.n_banos or 0),
                                    help="0 = estimación automática por área")
            ml_cocina = st.number_input("Cocina (metros lineales)", min_value=0.0, max_value=200.0,
                                        value=float(estado_guardado.ml_cocina or 0.0), step=0.5,
                                        help="0 = estimación automática por área")

        st.markdown("### ⚙️ Configuración")
        sistema = st.selectbox("Sistema", ["Paneles Isotex", "ICF Proform"])
        calidad = st.selectbox("Calidad de terminados", ["economica", "media", "alta", "lujo"], index=1)
        zona = st.selectbox("Zona de riesgo", ["Moderado (Base)", "Alto", "Muy Alto"])
        lanzadora = st.checkbox("Aplanado con lanzadora neumática", value=False,
                                help="60-70 m²/día frente a 15-20 m²/día manual")

        sistema_techo_label = st.selectbox(
            "Sistema de techo",
            ["Genérico (panel + concreto, tipo Qualylosa)", "Termopanel®", "Termolosa®",
             "Isolosa®", "Isofill® (bovedilla)"],
            help="Termopanel/Termolosa/Isolosa/Isofill son productos reales de Isotex "
                 "Dominicana, cotizados por m² instalado. NINGUNO tiene precio público "
                 "todavía -- el total quedará incompleto hasta que actualices el precio."
        )
        sistema_techo = {
            "Genérico (panel + concreto, tipo Qualylosa)": None,
            "Termopanel®": "termopanel",
            "Termolosa®": "termolosa",
            "Isolosa®": "isolosa",
            "Isofill® (bovedilla)": "isofill",
        }[sistema_techo_label]
        if sistema_techo:
            st.caption(
                f"⚠️ RD$0.00 hasta que actualices el precio de "
                f"`Techo_{sistema_techo.capitalize()}_m2` con la cotización real."
            )

        with st.expander("🪟 Dimensiones reales de vanos", expanded=False):
            st.caption(
                "La malla zigzag está calibrada para ventanas de 90x90 cm y puertas "
                "de 215x90 cm (docs/BASE_TECNICA_EPS_ICF.md). Si tus vanos son más "
                "grandes, indícalo aquí -- si no, la malla se queda corta sin avisar."
            )
            col_v1, col_v2 = st.columns(2)
            with col_v1:
                ancho_ventana = st.number_input("Ancho de ventana (m)", min_value=0.3, max_value=4.0,
                                                value=float(estado_guardado.ancho_ventana_m), step=0.1)
                ancho_puerta = st.number_input("Ancho de puerta (m)", min_value=0.5, max_value=2.5,
                                               value=float(estado_guardado.ancho_puerta_m), step=0.1)
            with col_v2:
                alto_ventana = st.number_input("Alto de ventana (m)", min_value=0.3, max_value=3.0,
                                               value=float(estado_guardado.alto_ventana_m), step=0.1)
                alto_puerta = st.number_input("Alto de puerta (m)", min_value=1.8, max_value=3.0,
                                              value=float(estado_guardado.alto_puerta_m), step=0.05)

        detalle_guardado = InstalacionesDetalle.desde_dict(estado_guardado.instalaciones_detalle)
        with st.expander("🔌 Instalaciones detalladas", expanded=False):
            st.caption("Si dejas todo en 0, la app usa el cálculo grueso por m².")
            tomacorrientes = st.number_input("Tomacorrientes", min_value=0, max_value=1000,
                                             value=detalle_guardado.tomacorrientes)
            interruptores = st.number_input("Interruptores", min_value=0, max_value=1000,
                                            value=detalle_guardado.interruptores)
            luminarias = st.number_input("Luminarias", min_value=0, max_value=1000,
                                         value=detalle_guardado.luminarias)
            puntos_datos = st.number_input("Puntos de datos", min_value=0, max_value=500,
                                           value=detalle_guardado.puntos_datos)
            camaras = st.number_input("Cámaras", min_value=0, max_value=500,
                                      value=detalle_guardado.camaras)
            ml_electrica = st.number_input("Canalización eléctrica (ml)", min_value=0.0, max_value=10000.0,
                                           value=float(detalle_guardado.ml_canalizacion_electrica), step=1.0)
            puntos_agua = st.number_input("Puntos de agua", min_value=0, max_value=1000,
                                          value=detalle_guardado.puntos_agua)
            puntos_sanitarios = st.number_input("Puntos sanitarios", min_value=0, max_value=1000,
                                                value=detalle_guardado.puntos_sanitarios)
            registros_sanitarios = st.number_input("Registros sanitarios", min_value=0, max_value=500,
                                                   value=detalle_guardado.registros_sanitarios)
            ml_agua = st.number_input("Tubería de agua (ml)", min_value=0.0, max_value=10000.0,
                                      value=float(detalle_guardado.ml_tuberia_agua), step=1.0)
            ml_sanitaria = st.number_input("Tubería sanitaria (ml)", min_value=0.0, max_value=10000.0,
                                           value=float(detalle_guardado.ml_tuberia_sanitaria), step=1.0)
            puntos_gas = st.number_input("Puntos de gas", min_value=0, max_value=100,
                                         value=detalle_guardado.puntos_gas)
            puntos_clima = st.number_input("Puntos de clima", min_value=0, max_value=500,
                                           value=detalle_guardado.puntos_clima)

    geo = Geometria(
        area_m2=area,
        perimetro_m=perimetro or None,
        altura_muro_m=altura,
        niveles=int(niveles),
        esquinas=int(esquinas),
        ventanas=int(ventanas) or None,
        puertas_interiores=int(puertas_interiores) or None,
        puertas_exteriores=int(puertas_exteriores) or None,
        banos=int(banos) or None,
        ml_cocina=float(ml_cocina) or None,
        ancho_ventana_m=ancho_ventana,
        alto_ventana_m=alto_ventana,
        ancho_puerta_m=ancho_puerta,
        alto_puerta_m=alto_puerta,
    )
    instalaciones = InstalacionesDetalle(
        tomacorrientes=int(tomacorrientes),
        interruptores=int(interruptores),
        luminarias=int(luminarias),
        puntos_datos=int(puntos_datos),
        camaras=int(camaras),
        ml_canalizacion_electrica=float(ml_electrica),
        puntos_agua=int(puntos_agua),
        puntos_sanitarios=int(puntos_sanitarios),
        registros_sanitarios=int(registros_sanitarios),
        ml_tuberia_agua=float(ml_agua),
        ml_tuberia_sanitaria=float(ml_sanitaria),
        puntos_gas=int(puntos_gas),
        puntos_clima=int(puntos_clima),
    )

    estado_actualizado = ProyectoState.cargar()
    estado_actualizado.area_m2 = float(area)
    estado_actualizado.perimetro_m = float(perimetro) or None
    estado_actualizado.altura_muro_m = float(altura)
    estado_actualizado.niveles = int(niveles)
    estado_actualizado.esquinas = int(esquinas)
    estado_actualizado.n_ventanas = int(ventanas) or None
    estado_actualizado.n_puertas_interiores = int(puertas_interiores) or None
    estado_actualizado.n_puertas_exteriores = int(puertas_exteriores) or None
    estado_actualizado.n_banos = int(banos) or None
    estado_actualizado.ml_cocina = float(ml_cocina) or None
    estado_actualizado.ancho_ventana_m = float(ancho_ventana)
    estado_actualizado.alto_ventana_m = float(alto_ventana)
    estado_actualizado.ancho_puerta_m = float(ancho_puerta)
    estado_actualizado.alto_puerta_m = float(alto_puerta)
    estado_actualizado.instalaciones_detalle = instalaciones.a_dict() if instalaciones.tiene_detalle else {}
    estado_actualizado.guardar()

    precios = st.session_state.get("precios_sincronizados") or Pricebook(
        os.path.join("data", "pricebook.json")
    ).load()

    try:
        motor = MotorQTO(geo, precios, sistema=sistema, calidad=calidad,
                         zona_riesgo=zona, aplanado_mecanizado=lanzadora,
                         sistema_techo=sistema_techo, instalaciones=instalaciones)
        df = motor.presupuesto()
    except (KeyError, ValueError) as e:
        st.error(f"No se pudo calcular el presupuesto: {e}")
        return

    # -- métricas ---------------------------------------------------------
    if sistema_techo and motor._precio(f"Techo_{sistema_techo.capitalize()}_m2") == 0.0:
        st.error(
            f"🔴 **Este presupuesto está INCOMPLETO**: el sistema de techo "
            f"({sistema_techo_label}) no tiene precio cotizado (RD$0.00/m²). "
            f"Actualiza `Techo_{sistema_techo.capitalize()}_m2` en el pricebook "
            f"con la cotización real de Isotex Dominicana antes de entregar este "
            f"presupuesto a un cliente."
        )

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

    if instalaciones.tiene_detalle:
        with st.expander("🔌 Instalaciones usadas por el cálculo", expanded=False):
            st.dataframe(pd.DataFrame([instalaciones.a_dict()]).T.rename(columns={0: "Cantidad"}),
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

    st.markdown("### 🧭 Escenarios rápidos")
    escenarios_df = calcular_escenarios(geo, precios, instalaciones=instalaciones)
    st.dataframe(
        escenarios_df.style.format({
            "total": "RD$ {:,.0f}",
            "costo_m2": "RD$ {:,.0f}",
            "obra_gris": "RD$ {:,.0f}",
            "obra_terminada": "RD$ {:,.0f}",
            "ahorro_total_pct": "{:.1f}%",
        }),
        use_container_width=True,
    )
    if escenarios_df["incompleto"].any():
        st.warning(
            "Los escenarios con techo Isotex real aparecen como incompletos si su precio "
            "por m² sigue en RD$0.00. Esa parte queda pendiente hasta tener cotización."
        )

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

    # -- honestidad sobre condiciones de proyecto no modeladas ------------
    with st.expander("⚠️ Condiciones de proyecto que este motor NO calcula", expanded=False):
        st.caption(
            "Verificado con el NotebookLM del usuario: estos refuerzos existen en las "
            "fuentes técnicas pero no están modelados todavía. Si tu proyecto tiene "
            "alguna de estas condiciones, presupuéstala aparte."
        )
        for limitacion in MotorQTO.limitaciones_conocidas():
            st.markdown(f"- {limitacion}")

    # -- exportación ------------------------------------------------------
    st.download_button(
        "📥 Descargar presupuesto (CSV)",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=f"presupuesto_{int(area)}m2.csv",
        mime="text/csv",
        use_container_width=True,
    )

    col_desc1, col_desc2 = st.columns(2)
    with col_desc1:
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

    with col_desc2:
        pdf = PDFGenerator().generar_propuesta(
            "Proyecto Residencial",
            {
                "area": area,
                "sistema": sistema,
                "calidad": calidad,
                "zona_riesgo": zona,
            },
            motor.presupuesto_formato_legado(),
            motor.total(),
        )
        st.download_button(
            "📄 Descargar PDF comercial",
            data=pdf,
            file_name=f"propuesta_comercial_{int(area)}m2.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
