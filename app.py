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
    PAGINAS.update({
        "🏠 Inicio": pagina_inicio,
        "👷 Nuestro Team": pagina_team,
        "🧮 Calculadora": pagina_calculadora,
        "🧾 Presupuesto Detallado": pagina_presupuesto_detallado,
        "📐 Plano → Estructura": pagina_plano_estructura,
        "🧱 Visor BIM 3D": pagina_visor_bim,
        "📊 Dashboard Financiero": _pagina_dashboard_financiero,
        "⚡ Análisis Energético": _pagina_analisis_energetico,
        "🎛️ Panel Operativo": pagina_panel_operativo,
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

        seccion = st.radio(
            "Navegación",
            list(PAGINAS.keys()),
            label_visibility="collapsed",
        )

        st.divider()

        estado = ProyectoState.cargar()
        st.caption("Proyecto actual")
        st.metric("Área", f"{estado.area_m2:,.0f} m²")
        if estado.origen_metricas:
            st.caption(f"Dimensiones desde: {estado.origen_metricas}")

        st.divider()
        caja_info(
            "El poliestireno expandido puede reducir 20-40% el costo de OBRA GRIS "
            "frente al método tradicional. Los acabados son equivalentes.",
            "💡 ¿Sabías qué?",
        )

    PAGINAS[seccion]()


# ============================================================================
# PUNTO DE ENTRADA
# ============================================================================

_registrar_paginas()

if __name__ == "__main__":
    main()
