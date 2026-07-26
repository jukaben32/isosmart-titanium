# -*- coding: utf-8 -*-
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
from ui_presupuesto import pagina_panel_operativo
from ui_team import pagina_team
from ui_visor_bim import pagina_visor_bim

try:
    from streamlit_drawable_canvas import st_canvas
except Exception:
    st_canvas = None

def main():
    # Menú de navegación
    with st.sidebar:
        st.image("https://img.icons8.com/color/96/construction.png", width=80)
        st.markdown("### 🏗️ IsoSmart Titanium")

        menu = st.radio(
            "Navegación",
            ["🏠 Inicio", "👷 Nuestro Team", "🧮 Calculadora", "📐 Plano → Estructura", "🧱 Visor BIM 3D", "🎛️ Panel Operativo", "📞 Contacto"],
            label_visibility="collapsed"
        )

        st.divider()

        # Información rápida
        st.markdown("""
        <div style="background:#f0f2f6; padding:15px; border-radius:10px;">
            <strong>💡 ¿Sabías qué?</strong><br>
            El poliestireno expandido puede reducir hasta 30% los costos de construcción
            comparado con el método tradicional.
        </div>
        """, unsafe_allow_html=True)

    # Router de páginas
    if menu == "🏠 Inicio":
        pagina_inicio()
    elif menu == "👷 Nuestro Team":
        pagina_team()
    elif menu == "🧮 Calculadora":
        pagina_calculadora()
    elif menu == "📐 Plano → Estructura":
        pagina_plano_estructura()
    elif menu == "🧱 Visor BIM 3D":
        pagina_visor_bim()
    elif menu == "🎛️ Panel Operativo":
        pagina_panel_operativo()
    elif menu == "📞 Contacto":
        pagina_contacto()


# ============================================================================
# PUNTO DE ENTRADA
# ============================================================================

if __name__ == "__main__":
    main()
