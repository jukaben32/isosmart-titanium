# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import json
import os
from io import BytesIO
import base64

st.set_page_config(page_title="CRM - Leads", page_icon="🗃️", layout="wide")

st.title("🗃️ Panel de Administración - Leads")

# Obtener clave maestra de las variables de entorno o st.secrets
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")  # Fallback a admin123

if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False

if not st.session_state.admin_logged_in:
    st.markdown("### 🔒 Acceso Restringido")
    password = st.text_input("Ingrese la clave maestra", type="password")
    if st.button("Ingresar"):
        if password == ADMIN_PASSWORD:
            st.session_state.admin_logged_in = True
            st.rerun()
        else:
            st.error("❌ Clave incorrecta")
    st.stop()

# Si está logueado
if st.button("Cerrar Sesión"):
    st.session_state.admin_logged_in = False
    st.rerun()

st.markdown("### 📋 Listado de Contactos (Leads)")

def load_leads():
    leads_path = os.path.join("data", "leads_db.json")
    if os.path.exists(leads_path):
        try:
            with open(leads_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            st.error(f"Error al leer la base de datos: {e}")
            return []
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
