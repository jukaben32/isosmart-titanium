"""Router principal de IsoSmart Titanium (rediseño 2026-09).

Menú único y minimalista de 6 secciones: Inicio -> Plano -> Presupuesto ->
Solar -> Finanzas -> Nosotros. El flujo se guía por el estado del proyecto
(ProyectoState), no por paneles independientes.
"""
import streamlit as st

# Configuracion de la pagina (debe ser la PRIMERA llamada a Streamlit)
st.set_page_config(
    page_title="IsoSmart Titanium",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

from ui_inicio import pagina_inicio  # noqa: E402
from utils.estado import ProyectoState  # noqa: E402
from utils.estilos import caja_info, inyectar_css  # noqa: E402

PAGINAS = {}


def _importar_pagina(nombre_modulo: str):
    """Importa (una sola vez) un módulo de paginas/ y devuelve la función page."""
    import importlib

    return importlib.import_module(f"paginas.{nombre_modulo}")


def _pagina_movida(nombre_modulo: str, funcion: str):
    """Wrapper de una página movida a paginas/ para el router."""
    def render():
        _importar_pagina(nombre_modulo).__dict__[funcion]()
    return render


def _registrar_paginas():
    """Tabla única de navegación. Añadir una página es añadir una entrada aquí."""
    PAGINAS.clear()
    PAGINAS.update({
        "🏠 Inicio": pagina_inicio,
        "📐 Plano": _pagina_movida("plano", "pagina_plano"),
        "🧮 Presupuesto": _pagina_movida("presupuesto", "pagina_presupuesto"),
        "⚡ Solar": _pagina_movida("solar", "pagina_solar"),
        "💰 Finanzas": _pagina_movida("finanzas", "pagina_finanzas"),
        "👷 Nosotros": _pagina_movida("nosotros", "pagina_nosotros"),
    })


def main():
    """
    Router único.

    Invocación directa desde el index principal. El estado de navegación vive
    en `seccion_nav` y se puede programar desde cualquier página escribiendo
    `st.session_state["_nav_destino"] = "<clave del menú>"` y llamando a
    `st.rerun()`.
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
            "Empieza con m², sube un plano o describe la vivienda en Inicio "
            "para activar Plano, Presupuesto, Solar y Finanzas.",
            "Flujo guiado",
        )

    PAGINAS[seccion]()


# ============================================================================
# PUNTO DE ENTRADA
# ============================================================================

_registrar_paginas()

if __name__ == "__main__":
    main()
