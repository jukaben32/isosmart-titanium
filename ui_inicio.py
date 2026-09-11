# -*- coding: utf-8 -*-
"""
ui_inicio.py
------------
Página de inicio.

REESCRITURA POR TRAZABILIDAD (2026-07-26)
==========================================
La versión anterior mostraba nueve cifras y tres afirmaciones de texto sin
ninguna fuente:

  - Los números (RD$ 1,178,009 / RD$ 7,200,000 / 83.6% / 180-300 días /
    26,400-102,000 kg) salían de `BudgetCalculator.comparar_sistemas()`, el
    motor CLÁSICO que la Fase 1 de la auditoría reemplazó por `utils/qto.py`
    en el resto de la app. Esta página nunca se migró.
  - "-30%", "-40%", "-5°C", "70% menos peso", "3 veces más rápido" en el hero
    y las tarjetas de beneficio eran texto fijo sin cálculo ni cita.
  - "Excelente/Regular", "Hasta 45dB/~20dB", "Alta (flexible)/Media (rígido)"
    en la tabla comparativa eran texto fijo en el HTML.

Principio de esta reescritura: **todo dato que se muestra en pantalla declara
su fuente** (`utils/fuentes.py`). Un dato sin fuente defendible no se muestra
como cifra: se retira o se marca explícitamente como no disponible.
"""

import os

import streamlit as st

from utils.comparativa_inicio import calcular_comparativa_area
from utils.estado import AREA_UI_MAX_M2, AREA_UI_MIN_M2, AREA_UI_STEP_M2, ProyectoState, limitar_area_ui
from utils.estilos import caja_info, encabezado, inyectar_css, tarjeta_metrica
from utils.fuentes import (
    COSTO_TRADICIONAL_RD_M2,
    FICHA_COVINTEC,
    SIN_FUENTE_CONOCIDA,
    TIPO_CAMBIO_FECHA,
    TIPO_CAMBIO_FUENTE,
    TIPO_CAMBIO_MXN_DOP,
    TIPO_CAMBIO_URL,
)
from utils.pricebook import PRECIOS_POR_VERIFICAR, Pricebook


def _footnote(fuente) -> None:
    """Pie de página con la cita de una `Fuente`, bajo cualquier dato mostrado."""
    st.markdown(fuente.html_footnote(), unsafe_allow_html=True)


def pagina_inicio():
    """Página de inicio: educativa, con cada cifra trazada a su fuente."""
    inyectar_css()

    # -- hero --------------------------------------------------------------
    encabezado(
        "🏗️ IsoSmart Titanium",
        "Construcción con poliestireno expandido (EPS/ICF) en República Dominicana",
    )

    st.divider()

    # -- comparativa real, calculada con el motor QTO -----------------------
    estado = ProyectoState.cargar()
    precios = Pricebook(os.path.join("data", "pricebook.json")).load()
    area_base = int(round(limitar_area_ui(estado.area_m2)))
    if "inicio_area_m2" in st.session_state:
        st.session_state["inicio_area_m2"] = int(round(limitar_area_ui(st.session_state["inicio_area_m2"])))

    area_inicio = st.slider(
        "Área de construcción (m²)",
        min_value=AREA_UI_MIN_M2,
        max_value=AREA_UI_MAX_M2,
        value=area_base,
        step=AREA_UI_STEP_M2,
        key="inicio_area_m2",
    )
    area_previa = st.session_state.get("_inicio_area_m2_previa")
    area_cambio = area_previa is not None and float(area_inicio) != float(area_previa)
    st.session_state["_inicio_area_m2_previa"] = float(area_inicio)
    if area_cambio:
        estado.area_m2 = float(area_inicio)
        # Si el visitante mueve la barra, esa área tentativa pasa a ser la
        # referencia viva para las demás páginas.
        estado.perimetro_m = None
        estado.origen_metricas = "Inicio - area tentativa"
        estado.guardar()

    datos = calcular_comparativa_area(
        area_inicio,
        precios=precios,
        sistema=estado.sistema,
        calidad=estado.calidad,
        niveles=estado.niveles,
        altura_muro_m=estado.altura_muro_m,
    )
    comp = datos["comparativa"]

    st.markdown(f"### 📊 Comparativa para una vivienda de {area_inicio:,.0f} m²")
    st.caption(
        "Calculado en vivo con `utils/qto.py` (motor de cantidades), no con cifras fijas. "
        "La barra recalcula el presupuesto tentativo según el área del proyecto."
    )

    col_area, col_accion = st.columns([2, 1])
    with col_area:
        st.caption(
            f"Estimación rápida: {datos['geometria']['perimetro_m']:,.1f} ml de perímetro, "
            f"{datos['geometria']['banos']} baños y {datos['geometria']['ventanas']} ventanas."
        )
    with col_accion:
        if st.button("Usar esta área", type="secondary", use_container_width=True):
            estado.area_m2 = float(area_inicio)
            # Si el area cambia manualmente, el perimetro anterior de un DXF ya no
            # representa esta nueva opcion tentativa.
            estado.perimetro_m = None
            estado.origen_metricas = "Inicio - area tentativa"
            estado.guardar()
            st.success("Área aplicada al presupuesto detallado.")

    c1, c2, c3 = st.columns(3)
    with c1:
        tarjeta_metrica("Costo EPS/ICF", f"RD$ {comp['eps']['costo_total']:,.0f}",
                        f"RD$ {comp['eps']['costo_m2']:,.0f}/m²", variante="green")
    with c2:
        tarjeta_metrica("Costo Tradicional", f"RD$ {comp['tradicional']['costo_total']:,.0f}",
                        f"RD$ {comp['tradicional']['costo_m2']:,.0f}/m²", variante="orange")
    with c3:
        tarjeta_metrica("Ahorro Total", f"RD$ {comp['ahorro']['total_rd']:,.0f}",
                        f"{comp['ahorro']['total_pct']:.1f}% menos", variante="blue")

    st.caption(
        f"El {comp['ahorro']['obra_gris_pct']:.1f}% de ahorro se aplica solo a la "
        f"**obra gris**; los acabados son iguales en ambos sistemas. Antes esta "
        f"página mostraba 83.6% comparando obra gris EPS contra obra **terminada** "
        f"tradicional — peras con manzanas. Ver `docs/BASE_TECNICA_EPS_ICF.md`."
    )

    if datos["monto_por_verificar"] > 0:
        monto = datos["monto_por_verificar"]
        st.warning(
            f"⚠️ RD$ {monto:,.0f} de este presupuesto ({datos['pct_por_verificar']:.0f}% del "
            f"total) usa precios de **referencia**, no cotizaciones de proveedor local. "
            f"Ver la sección de fuentes al final de esta página."
        )

    # -- tabla técnica, con cita por fila ------------------------------------
    st.markdown("### 🔧 Características técnicas")
    st.caption("Cada fila cita su fuente. Lo que no tiene fuente defendible no aparece.")

    filas = [
        ("Peso del panel (sin aplanar)", FICHA_COVINTEC["peso_panel_sin_aplanar_kg_m2"]),
        ("Peso de losa terminada (azotea)", FICHA_COVINTEC["peso_losa_azotea_kg_m2"]),
        ("Resistencia térmica de la losa", FICHA_COVINTEC["resistencia_termica_r"]),
        ("Aislamiento acústico", FICHA_COVINTEC["aislamiento_acustico_db"]),
        ("Reducción de acero estructural", FICHA_COVINTEC["reduccion_acero_pct"]),
    ]
    for etiqueta, fuente in filas:
        col_a, col_b = st.columns([2, 3])
        with col_a:
            st.markdown(f"**{etiqueta}**")
            st.markdown(f"### {fuente.valor}")
        with col_b:
            st.caption(fuente.etiqueta)
            _footnote(fuente)
        st.divider()

    with st.expander("❓ Datos que esta app YA NO afirma, por falta de fuente"):
        st.caption(
            "Estas afirmaciones aparecían en versiones anteriores sin ningún respaldo. "
            "Se retiraron en vez de dejarlas como texto fijo."
        )
        for clave, fuente in SIN_FUENTE_CONOCIDA.items():
            st.markdown(f"- **{clave.replace('_', ' ')}**: {fuente.cita}")

    st.divider()

    # -- información educativa ------------------------------------------------
    st.markdown("### 📚 ¿Qué es el sistema Isotex/ICF?")

    tab1, tab2, tab3 = st.tabs(["🏠 Sistema Isotex", "🧱 Bloques ICF", "❓ Preguntas frecuentes"])

    with tab1:
        st.markdown(
            "**El sistema Isotex** usa paneles prefabricados de poliestireno "
            "expandido (EPS) recubiertos con malla electrosoldada, que se rellenan "
            "con concreto para formar muros y losas estructurales."
        )
        st.caption(
            "Descripción del sistema constructivo, sin cifras de rendimiento "
            "comparativo (ver la tabla de arriba para las que sí tienen fuente)."
        )

    with tab2:
        st.markdown(
            "**ICF (Insulated Concrete Forms)** son bloques huecos de poliestireno "
            "que sirven como encofrado permanente. Se apilan y se rellenan de "
            "concreto, creando muros con aislamiento integrado."
        )

    with tab3:
        st.markdown("#### Preguntas frecuentes")
        st.markdown(
            "**¿El precio incluye mano de obra?** Sí: el motor de cantidades "
            "(`🧾 Presupuesto Detallado`) incluye jornales de montaje, aplanado, "
            "cimentación y losa, según los rendimientos de `docs/BASE_TECNICA_EPS_ICF.md`."
        )
        st.markdown(
            "**¿Dónde se compran los materiales en RD?** Ese canal de proveedor "
            "todavía no está establecido con precios verificables. Mientras tanto, "
            "esta app usa precios de referencia de Covintec México para las "
            "partidas donde existe una fuente citable — ver más abajo."
        )
        st.caption(
            "Las preguntas sobre resistencia sísmica, vida útil y resistencia a "
            "termitas se retiraron de esta sección hasta contar con un informe de "
            "ingeniería o una norma que las respalde para el sistema y la zona "
            "específicos de este proyecto."
        )

    st.divider()

    # -- fuentes y metodología ------------------------------------------------
    with st.expander("📎 Fuentes y metodología", expanded=False):
        st.markdown(
            "Todas las cifras técnicas de esta página citan una fuente pública. "
            "Ninguna es una medición local en República Dominicana: son datos del "
            "fabricante del mismo sistema constructivo (Covintec, México) o índices "
            "oficiales dominicanos, usados como referencia mientras se establece "
            "un canal de precios local verificable."
        )

        st.markdown("**Costo de construcción tradicional en RD**")
        _footnote(COSTO_TRADICIONAL_RD_M2)

        st.markdown("**Tipo de cambio usado para convertir precios de Covintec México**")
        st.markdown(
            f"1 MXN = {TIPO_CAMBIO_MXN_DOP} DOP · {TIPO_CAMBIO_FECHA.strftime('%d/%m/%Y')} · "
            f'<a href="{TIPO_CAMBIO_URL}" target="_blank">{TIPO_CAMBIO_FUENTE}</a>',
            unsafe_allow_html=True,
        )

        st.markdown("**Fichas técnicas citadas**")
        for etiqueta, fuente in FICHA_COVINTEC.items():
            st.markdown(f"- {etiqueta.replace('_', ' ')}: {fuente.cita}")
            if fuente.url:
                st.caption(fuente.url)

        if PRECIOS_POR_VERIFICAR:
            st.markdown(
                f"**{len(PRECIOS_POR_VERIFICAR)} partidas del pricebook** todavía usan "
                f"estimaciones de ingeniería sin cotización real: "
                + ", ".join(sorted(k.replace('_', ' ') for k in PRECIOS_POR_VERIFICAR))
            )

        caja_info(
            "Si algo en esta app te parece incorrecto o sin fuente, repórtalo: "
            "el objetivo es que cada número sea verificable, no solo plausible.",
            "💬 ¿Ves algo sin fuente?",
        )
