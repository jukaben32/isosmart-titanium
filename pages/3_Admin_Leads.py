# -*- coding: utf-8 -*-
import hmac
import os
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.repositorio import obtener_repositorio  # noqa: E402

st.set_page_config(page_title="CRM - Leads", page_icon="🗃️", layout="wide")

st.title("🗃️ Panel de Administración - Leads")

# ---------------------------------------------------------------------------
# Clave maestra.
#
# SIN FALLBACK. La versión anterior caía a "admin123", de modo que un despliegue
# sin variable de entorno exponía el CRM completo (nombres, correos, teléfonos)
# a cualquiera con la URL. Si no hay clave configurada, la página no carga.
# ---------------------------------------------------------------------------
def _get_admin_password() -> str:
    try:
        valor = st.secrets.get("ADMIN_PASSWORD", "")
        if valor:
            return str(valor)
    except Exception:
        pass
    return os.environ.get("ADMIN_PASSWORD", "")


ADMIN_PASSWORD = _get_admin_password()

if not ADMIN_PASSWORD:
    st.error(
        "🔒 Panel deshabilitado: no hay `ADMIN_PASSWORD` configurada.\n\n"
        "Defínela en *Streamlit Secrets* o como variable de entorno para habilitar el CRM."
    )
    st.stop()

MAX_INTENTOS = 5

st.session_state.setdefault("admin_logged_in", False)
st.session_state.setdefault("admin_intentos", 0)

if not st.session_state.admin_logged_in:
    st.markdown("### 🔒 Acceso Restringido")

    if st.session_state.admin_intentos >= MAX_INTENTOS:
        st.error("❌ Demasiados intentos fallidos. Recarga la página para volver a intentarlo.")
        st.stop()

    password = st.text_input("Ingrese la clave maestra", type="password")
    if st.button("Ingresar"):
        # compare_digest evita filtrar información por tiempo de respuesta
        if hmac.compare_digest(password, ADMIN_PASSWORD):
            st.session_state.admin_logged_in = True
            st.session_state.admin_intentos = 0
            st.rerun()
        else:
            st.session_state.admin_intentos += 1
            restantes = MAX_INTENTOS - st.session_state.admin_intentos
            st.error(f"❌ Clave incorrecta. Intentos restantes: {max(0, restantes)}")
    st.stop()

# Si está logueado
if st.button("Cerrar Sesión"):
    st.session_state.admin_logged_in = False
    st.rerun()

st.markdown("### 📋 Listado de Contactos (Leads)")

def load_leads():
    """
    Lee los leads del repositorio activo (Supabase si hay credenciales,
    SQLite en caso contrario). Antes leía `data/leads_db.json`, que en
    Streamlit Cloud se borraba en cada reinicio del contenedor.
    """
    try:
        return obtener_repositorio().listar()
    except Exception as e:
        st.error(f"No se pudo leer el repositorio de leads: {e}")
        return []


leads = load_leads()

if not leads:
    st.info("No hay leads registrados todavía.")
else:
    df = pd.DataFrame(leads)
    
    # Reordenar columnas si existen
    column_order = ['fecha', 'nombre', 'email', 'telefono', 'ubicacion', 'tipo_proyecto', 'area_estimada', 'mensaje']
    existing_cols = [col for col in column_order if col in df.columns]
    existing_cols += [col for col in df.columns if col not in column_order]
    
    df = df[existing_cols]
    
    # Buscador / Filtro
    search = st.text_input("🔍 Buscar por nombre o email...")
    if search:
        df = df[df['nombre'].str.contains(search, case=False, na=False) | 
                df['email'].str.contains(search, case=False, na=False)]
                
    st.dataframe(df, use_container_width=True)
    
    # Descargar CSV
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Descargar Leads (CSV)",
        data=csv,
        file_name="leads_export.csv",
        mime="text/csv",
    )
