# -*- coding: utf-8 -*-
"""Página 👷 Nosotros: el equipo y una forma de contacto sencilla.

Reutiliza `pagina_team()` (presentación sin testimonios falsos) y añade un
formulario minimalista. El lead se guarda en el repositorio (SQLite/Supabase)
aunque el CRM ya no esté en el menú.
"""
import streamlit as st

from ui_core import ProjectManager
from ui_team import pagina_team
from utils.estilos import inyectar_css


def pagina_nosotros():
    """Punto de entrada de la página Nosotros."""
    inyectar_css()
    # pagina_team() ya pinta su propia cabecera y las tarjetas del equipo.
    pagina_team()
    _render_contacto()


def _render_contacto():
    """Formulario mínimo de contacto; guarda el lead en el repositorio."""
    st.markdown("### 📩 ¿Hablamos de tu proyecto?")
    with st.form("contacto_nosotros"):
        c1, c2 = st.columns(2)
        nombre = c1.text_input("Nombre")
        email = c2.text_input("Correo")
        telefono = c1.text_input("Teléfono / WhatsApp")
        ubicacion = c2.text_input("Ciudad / Provincia")
        tipo = st.selectbox("Tipo de proyecto", ["Vivienda", "Multifamiliar", "Comercial", "Otra"])
        mensaje = st.text_area("Cuéntanos tu idea", height=110)
        enviado = st.form_submit_button("🚀 Enviar", type="primary", use_container_width=True)

    if enviado:
        if not nombre.strip() or not email.strip():
            st.warning("El nombre y el correo son obligatorios.")
            return
        ProjectManager().save_lead(
            {
                "nombre": nombre.strip(),
                "email": email.strip(),
                "telefono": telefono.strip(),
                "ubicacion": ubicacion.strip(),
                "tipo_proyecto": tipo,
                "mensaje": mensaje.strip(),
                "fuente": "contacto_nosotros",
            }
        )
        st.success("¡Gracias! Te contactamos en breve.")


if __name__ == "__main__":
    pagina_nosotros()