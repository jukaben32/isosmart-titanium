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
from utils.geometria import Geometria
from utils.pricebook import PRECIOS_POR_VERIFICAR, Pricebook
from utils.qto import MotorQTO


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
    st.markdown("### 📊 Comparativa para una vivienda de 120 m²")
    st.caption(
        "Calculado en vivo con `utils/qto.py` (motor de cantidades), no con cifras fijas. "
        "Cambia el área en **🧾 Presupuesto Detallado** para ver cómo varía."
    )

    precios = Pricebook(os.path.join("data", "pricebook.json")).load()
    geo = Geometria(area_m2=120.0, perimetro_m=44.0, altura_muro_m=2.8, niveles=1)
    motor = MotorQTO(geo, precios, sistema="Paneles Isotex", calidad="media")
    comp = motor.comparar_con_tradicional()

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

    por_verificar = motor.partidas_por_verificar()
    if not por_verificar.empty:
        monto = por_verificar["subtotal"].sum()
        st.warning(
            f"⚠️ RD$ {monto:,.0f} de este presupuesto ({monto/motor.total()*100:.0f}% del "
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
