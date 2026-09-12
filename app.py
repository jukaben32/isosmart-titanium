"""Módulo de interfaz de IsoSmart Titanium (refactor de app.py, 2026-07-10)."""
import streamlit as st

# Configuracion de la pagina (debe ser la PRIMERA llamada a Streamlit)
st.set_page_config(
    page_title="IsoSmart Titanium",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# Módulos de interfaz (refactor de app.py, 2026-07-10)
from ui_calculadora import (
    pagina_calculadora,
    pagina_contacto,
    pagina_plano_estructura,
)
from ui_inicio import pagina_inicio
from ui_presupuesto import (
    pagina_panel_operativo,
    pagina_presupuesto_detallado,
)
from ui_team import pagina_team
from ui_visor_bim import pagina_visor_bim
from utils.estado import ProyectoState
from utils.estilos import caja_info, inyectar_css

try:
    from streamlit_drawable_canvas import st_canvas
except Exception:
    st_canvas = None

PAGINAS = {}


def _registrar_paginas():
    """Tabla única de navegación. Añadir una página es añadir una entrada aquí."""
    PAGINAS.clear()
    PAGINAS.update({
        "🏠 Cotizador": pagina_inicio,
        "👷 Equipo": pagina_team,
        "🧮 Calculadora Avanzada": pagina_calculadora,
        "🧾 Presupuesto Detallado": pagina_presupuesto_detallado,
        "📐 Planos y CAD": pagina_plano_estructura,
        "🧱 Visor BIM 3D": pagina_visor_bim,
        "📊 Finanzas": _pagina_dashboard_financiero,
        "⚡ Energía Solar": _pagina_analisis_energetico,
        "🎛️ Operación": pagina_panel_operativo,
        "📞 Contacto": pagina_contacto,
    })


def _pagina_dashboard_financiero():
    """Envuelve pages/1_Dashboard_Financiero.py para el router unificado."""
    import importlib

    modulo = importlib.import_module("paginas.dashboard_financiero")
    modulo.main()


def _pagina_analisis_energetico():
    import importlib

    modulo = importlib.import_module("paginas.analisis_energetico")
    modulo.main()


def main():
    """
    Router único.

    ANTES coexistían DOS sistemas de navegación: este menú `st.radio` y la
    carpeta `pages/`, que Streamlit convierte automáticamente en navegación
    multipágina. El usuario veía dos barras laterales con contenidos distintos,
    y las páginas de `pages/` no compartían el estado del menú principal (el
    Dashboard pedía el área otra vez con su propio slider).

    Ahora hay un solo menú. Las páginas antiguas siguen accesibles desde aquí.
    """
    inyectar_css()

    with st.sidebar:
        st.image("https://img.icons8.com/color/96/construction.png", width=80)
        st.markdown("### 🏗️ IsoSmart Titanium")

        destino = st.session_state.pop("_nav_destino", None)
        if destino in PAGINAS:
            st.session_state["seccion_nav"] = destino
        elif st.session_state.get("seccion_nav") not in PAGINAS:
            st.session_state["seccion_nav"] = next(iter(PAGINAS))

        seccion = st.radio(
            "Navegación",
            list(PAGINAS.keys()),
            label_visibility="collapsed",
            key="seccion_nav",
        )

        st.divider()

        estado = ProyectoState.cargar()
        st.caption("Proyecto actual")
        if estado.origen_metricas or st.session_state.get("inicio_resultado_activo"):
            st.metric("Área", f"{estado.area_m2:,.0f} m²")
            if estado.origen_metricas:
                st.caption(f"Dimensiones desde: {estado.origen_metricas}")
        else:
            st.caption("Sin cálculo activo")

        st.divider()
        caja_info(
            "Empieza con m², sube un plano o describe la vivienda para activar "
            "el presupuesto y la solicitud CAD.",
            "Flujo guiado",
        )

    PAGINAS[seccion]()


# ============================================================================
# PUNTO DE ENTRADA
# ============================================================================

_registrar_paginas()

if __name__ == "__main__":
    main()
