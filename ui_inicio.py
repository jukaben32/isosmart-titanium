# -*- coding: utf-8 -*-
"""
ui_inicio.py
------------
Entrada principal de IsoSmart Titanium.

La pantalla inicial debe funcionar como un cotizador guiado, no como una hoja
de cálculos abierta. El visitante ve resultados solo después de elegir una
entrada concreta: metros cuadrados, plano DXF o pedido por voz/texto para CAD.
"""

from __future__ import annotations

import os

import streamlit as st

from utils.cad_jobs import crear_cad_job
from utils.comparativa_inicio import calcular_comparativa_area
from utils.dxf_importer import analizar_dxf_bytes
from utils.energia import AnalisisEnergetico
from utils.estado import (
    AREA_UI_MAX_M2,
    AREA_UI_MIN_M2,
    AREA_UI_STEP_M2,
    ProyectoState,
    limitar_area_ui,
)
from utils.estilos import caja_info, inyectar_css, tarjeta_metrica
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
    """Pie de página con la cita de una fuente."""
    st.markdown(fuente.html_footnote(), unsafe_allow_html=True)


def _ir_a(seccion: str) -> None:
    """Pide al router principal navegar a otra sección en el siguiente rerun."""
    st.session_state["_nav_destino"] = seccion
    st.rerun()


def _sincronizar_area_visual(area_m2: float) -> None:
    """Alinea barras entre páginas sin fallar si el widget ya fue creado."""
    area = limitar_area_ui(area_m2)
    for key, value in {
        "inicio_area_m2": int(round(area)),
        "calc_area_slider_m2": float(area),
    }.items():
        try:
            st.session_state[key] = value
        except Exception:
            pass
    st.session_state["_inicio_area_m2_previa"] = float(area)
    st.session_state["_calc_area_estado_base_m2"] = float(area)


def _guardar_area_tentativa(area_m2: float, origen: str) -> ProyectoState:
    """Guarda un área manual y limpia geometría que ya no corresponda."""
    estado = ProyectoState.cargar()
    estado.area_m2 = float(area_m2)
    estado.perimetro_m = None
    estado.origen_metricas = origen
    estado.guardar()
    _sincronizar_area_visual(area_m2)
    st.session_state["inicio_resultado_activo"] = True
    return estado


def _guardar_mediciones_dxf(archivo_dxf) -> bool:
    """Procesa un DXF y lo convierte en el proyecto activo."""
    try:
        mediciones = analizar_dxf_bytes(archivo_dxf.getvalue())
    except Exception as e:
        st.error(f"No pude leer este DXF: {e}")
        return False

    st.success(
        f"Detectado: {mediciones.area_m2:,.2f} m², "
        f"{mediciones.perimetro_m:,.2f} ml, "
        f"{mediciones.ventanas} ventanas y "
        f"{mediciones.puertas_interiores + mediciones.puertas_exteriores} puertas."
    )
    for advertencia in mediciones.advertencias:
        st.warning(advertencia)

    if st.button("Usar este DXF para calcular", use_container_width=True, type="primary"):
        estado = ProyectoState.cargar()
        estado.aplicar_metricas(mediciones.a_metricas(), origen=f"DXF: {archivo_dxf.name}")
        estado.guardar()
        _sincronizar_area_visual(estado.area_m2)
        st.session_state["inicio_resultado_activo"] = True
        st.rerun()
    return True


def _render_resultado(estado: ProyectoState, precios: dict[str, float]) -> None:
    """Muestra el presupuesto tentativo solo cuando el usuario ya dio una entrada."""
    datos = calcular_comparativa_area(
        estado.area_m2,
        precios=precios,
        sistema=estado.sistema,
        calidad=estado.calidad,
        niveles=estado.niveles,
        altura_muro_m=estado.altura_muro_m,
    )
    comp = datos["comparativa"]

    st.markdown(f"### Resumen tentativo para {estado.area_m2:,.0f} m²")
    if estado.origen_metricas:
        st.caption(f"Dimensiones tomadas desde: {estado.origen_metricas}")

    c1, c2, c3 = st.columns(3)
    with c1:
        tarjeta_metrica(
            "Costo EPS/ICF",
            f"RD$ {comp['eps']['costo_total']:,.0f}",
            f"RD$ {comp['eps']['costo_m2']:,.0f}/m²",
            variante="green",
        )
    with c2:
        tarjeta_metrica(
            "Costo Tradicional",
            f"RD$ {comp['tradicional']['costo_total']:,.0f}",
            f"RD$ {comp['tradicional']['costo_m2']:,.0f}/m²",
            variante="orange",
        )
    with c3:
        tarjeta_metrica(
            "Ahorro Total",
            f"RD$ {comp['ahorro']['total_rd']:,.0f}",
            f"{comp['ahorro']['total_pct']:.1f}% menos",
            variante="blue",
        )

    col_a, col_b = st.columns([2, 1])
    with col_a:
        st.caption(
            f"Base geométrica: {datos['geometria']['perimetro_m']:,.1f} ml, "
            f"{datos['geometria']['banos']} baños y "
            f"{datos['geometria']['ventanas']} ventanas estimadas."
        )
        st.caption(
            f"El ahorro de {comp['ahorro']['obra_gris_pct']:.1f}% aplica a obra gris; "
            "los acabados se comparan iguales en ambos sistemas."
        )
    with col_b:
        if st.button("Abrir calculadora avanzada", use_container_width=True):
            _ir_a("🧮 Calculadora Avanzada")

    if datos["monto_por_verificar"] > 0:
        monto = datos["monto_por_verificar"]
        st.info(
            f"RD$ {monto:,.0f} ({datos['pct_por_verificar']:.0f}% del total) usa "
            "precios de referencia, no cotización local de proveedor."
        )


def _render_entrada_por_area() -> None:
    """Camino 1: el usuario solo conoce los metros cuadrados."""
    estado = ProyectoState.cargar()
    area_base = int(round(limitar_area_ui(estado.area_m2)))
    if "inicio_area_m2" not in st.session_state:
        st.session_state["inicio_area_m2"] = area_base
    else:
        st.session_state["inicio_area_m2"] = int(
            round(limitar_area_ui(st.session_state["inicio_area_m2"]))
        )

    area = st.slider(
        "Área de construcción estimada (m²)",
        min_value=AREA_UI_MIN_M2,
        max_value=AREA_UI_MAX_M2,
        step=AREA_UI_STEP_M2,
        key="inicio_area_m2",
    )
    niveles = st.number_input(
        "Niveles",
        min_value=1,
        max_value=20,
        value=int(estado.niveles),
        step=1,
    )
    calidad = st.select_slider(
        "Nivel de acabados",
        options=["economica", "media", "alta", "lujo"],
        value=estado.calidad,
        format_func=lambda x: {
            "economica": "Económica",
            "media": "Media",
            "alta": "Alta",
            "lujo": "Lujo",
        }[x],
    )

    if st.button("Calcular con estos datos", use_container_width=True, type="primary"):
        nuevo = _guardar_area_tentativa(area, "Inicio - metros cuadrados")
        nuevo.niveles = int(niveles)
        nuevo.calidad = calidad
        nuevo.guardar()
        st.rerun()


def _render_entrada_por_plano() -> None:
    """Camino 2: plano DXF directo o salto a medición de PDF/imagen."""
    archivo = st.file_uploader(
        "Sube plano CAD DXF",
        type=["dxf"],
        help="El DXF permite extraer área, perímetro, vanos e instalaciones desde capas CAD.",
    )
    if archivo is not None:
        _guardar_mediciones_dxf(archivo)

    st.divider()
    st.caption("Para PDF o imagen, usa la herramienta de medición con canvas.")
    if st.button("Ir a medición de PDF/imagen", use_container_width=True):
        _ir_a("📐 Planos y CAD")


def _render_entrada_por_pedido() -> None:
    """Camino 3: pedido libre para crear una orden CAD/OCS."""
    estado = ProyectoState.cargar()
    st.caption("Describe o dicta la vivienda. Con texto suficiente se crea una solicitud CAD/OCS.")

    if hasattr(st, "audio_input"):
        audio = st.audio_input("Grabar pedido de voz")
        if audio is not None:
            st.info(
                "Audio recibido. Para convertirlo automáticamente a texto falta conectar "
                "un servicio de transcripción; por ahora escribe abajo el resumen del pedido."
            )
    else:
        st.info("La versión actual de Streamlit no expone grabación de voz nativa en este entorno.")

    descripcion = st.text_area(
        "Pedido de vivienda",
        placeholder=(
            "Ej: Casa moderna de lujo, 2 niveles, 3 habitaciones, 3 baños, "
            "marquesina para 2 vehículos, cocina abierta, terraza y sistema solar."
        ),
        key="inicio_pedido_cad",
    )
    area = st.number_input(
        "Área aproximada si la conoces (m²)",
        min_value=0,
        max_value=AREA_UI_MAX_M2,
        value=int(round(limitar_area_ui(estado.area_m2))),
        step=AREA_UI_STEP_M2,
    )
    incluir_solar = st.checkbox("Incluir previsión solar e instalaciones ecológicas", value=True)

    if st.button("Crear solicitud CAD", use_container_width=True, type="primary"):
        if not descripcion.strip():
            st.warning("Escribe una descripción mínima para poder crear la solicitud CAD.")
            return

        if area > 0:
            estado.area_m2 = float(area)
            estado.perimetro_m = None
            estado.origen_metricas = "Pedido libre para CAD"
            estado.guardar()
            _sincronizar_area_visual(estado.area_m2)
            st.session_state["inicio_resultado_activo"] = True

        solar = (
            AnalisisEnergetico.calcular_sistema_solar_recomendado(estado.area_m2)
            if incluir_solar else None
        )
        job = crear_cad_job(descripcion, estado, solar=solar)
        st.session_state["ultimo_cad_job_id"] = job["id"]
        st.success(f"Solicitud CAD creada: {job['id']}")

    ultimo = st.session_state.get("ultimo_cad_job_id")
    if ultimo:
        st.caption(f"Última solicitud CAD: `{ultimo}`")


def _render_fuentes_y_tecnica() -> None:
    """Información técnica disponible, pero fuera del primer impacto visual."""
    with st.expander("Ver características técnicas y fuentes", expanded=False):
        st.markdown("#### Características técnicas")
        filas = [
            ("Peso del panel sin aplanar", FICHA_COVINTEC["peso_panel_sin_aplanar_kg_m2"]),
            ("Peso de losa terminada", FICHA_COVINTEC["peso_losa_azotea_kg_m2"]),
            ("Resistencia térmica de la losa", FICHA_COVINTEC["resistencia_termica_r"]),
            ("Aislamiento acústico", FICHA_COVINTEC["aislamiento_acustico_db"]),
            ("Reducción de acero estructural", FICHA_COVINTEC["reduccion_acero_pct"]),
        ]
        for etiqueta, fuente in filas:
            st.markdown(f"**{etiqueta}:** {fuente.valor}")
            st.caption(fuente.etiqueta)
            _footnote(fuente)

        st.markdown("#### Fuentes")
        st.markdown("**Costo tradicional en República Dominicana**")
        _footnote(COSTO_TRADICIONAL_RD_M2)
        st.markdown(
            f"**Tipo de cambio:** 1 MXN = {TIPO_CAMBIO_MXN_DOP} DOP · "
            f"{TIPO_CAMBIO_FECHA.strftime('%d/%m/%Y')} · "
            f'<a href="{TIPO_CAMBIO_URL}" target="_blank">{TIPO_CAMBIO_FUENTE}</a>',
            unsafe_allow_html=True,
        )
        if PRECIOS_POR_VERIFICAR:
            st.caption(
                f"{len(PRECIOS_POR_VERIFICAR)} partidas todavía usan precios de referencia: "
                + ", ".join(sorted(k.replace("_", " ") for k in PRECIOS_POR_VERIFICAR))
            )

    with st.expander("Datos retirados por falta de fuente", expanded=False):
        for clave, fuente in SIN_FUENTE_CONOCIDA.items():
            st.markdown(f"- **{clave.replace('_', ' ')}**: {fuente.cita}")


def pagina_inicio():
    """Cotizador guiado: simple para visitantes, útil para consultores."""
    inyectar_css()

    estado = ProyectoState.cargar()
    precios = Pricebook(os.path.join("data", "pricebook.json")).load()
    resultado_activo = bool(st.session_state.get("inicio_resultado_activo") or estado.origen_metricas)

    st.markdown(
        """
        <section class="iso-hero">
            <p class="iso-kicker">EPS / ICF en República Dominicana</p>
            <h1>Cotiza una vivienda sin empezar por una hoja de cálculo.</h1>
            <p>
                Elige una entrada: metros cuadrados, plano CAD o pedido libre.
                La app calcula solo cuando hay datos del proyecto.
            </p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    entrada_m2, entrada_plano, entrada_pedido = st.tabs(
        ["Metros cuadrados", "Subir plano", "Pedido voz/texto"]
    )
    with entrada_m2:
        _render_entrada_por_area()
    with entrada_plano:
        _render_entrada_por_plano()
    with entrada_pedido:
        _render_entrada_por_pedido()

    st.divider()
    if resultado_activo:
        _render_resultado(ProyectoState.cargar(), precios)
    else:
        caja_info(
            "Aún no hay presupuesto en pantalla. Introduce un área, sube un DXF "
            "o crea una solicitud CAD para activar los cálculos.",
            "Sin cálculo activo",
        )

    _render_fuentes_y_tecnica()
