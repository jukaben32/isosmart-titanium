"""Módulo de interfaz de IsoSmart Titanium (refactor de app.py, 2026-07-10)."""
import base64
import html
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import google.generativeai as genai
import streamlit as st

from utils.ai_media import generate_facade_image_fal, generate_video_luma
from utils.ai_text_design import DEFAULT_TEXT_DESIGN_PARAMS, analyze_text_design_with_gemini
from utils.estado import ProyectoState
from utils.repositorio import RepositorioSQLite, obtener_repositorio

# ---------------------------------------------------------------------------
# Componente opcional de lienzo interactivo.
#
# FUENTE ÚNICA: este try/except vivía solo en app.py, pero ui_calculadora.py y
# ui_vision.py usaban `st_canvas` sin importarlo -> NameError en cuanto el
# usuario subía un plano. Ahora se define aquí y todos importan desde ui_core.
# ---------------------------------------------------------------------------
try:
    from streamlit_drawable_canvas import st_canvas
except Exception:  # pragma: no cover - depende del entorno de despliegue
    st_canvas = None


class ProjectManager:
    """
    Gestor de proyectos y leads.

    Ahora delega en `utils.repositorio` (SQLite por defecto, Supabase si hay
    credenciales) en vez de escribir JSON al disco local. Motivo: en Streamlit
    Cloud el sistema de archivos es efímero y cada reinicio borraba los leads
    capturados. Se mantiene la misma API pública para no tocar los llamadores.
    """

    def __init__(self, base_dir: str = "data"):
        self.base_dir = base_dir
        self.repo = obtener_repositorio()
        self._sqlite = self.repo if isinstance(self.repo, RepositorioSQLite) else RepositorioSQLite()

    # -- leads -----------------------------------------------------------
    @property
    def leads(self) -> list[dict]:
        try:
            return self.repo.listar()
        except Exception:
            return []

    def save_lead(self, lead_data: dict):
        """Guarda un lead interesado."""
        lead_data = dict(lead_data)
        lead_data.setdefault("fecha", datetime.now().isoformat())
        return self.repo.guardar(lead_data)

    # -- proyectos -------------------------------------------------------
    @property
    def projects(self) -> dict:
        return {p["id"]: p for p in self._sqlite.listar_proyectos()}

    def save_project(self, project_id: str, data: dict):
        self._sqlite.guardar_proyecto(project_id, data)

    def get_project(self, project_id: str) -> dict | None:
        return self._sqlite.obtener_proyecto(project_id)

    def list_projects(self) -> list[dict]:
        return self._sqlite.listar_proyectos()

    def delete_project(self, project_id: str):
        self._sqlite.eliminar_proyecto(project_id)


# ============================================================================
# PASO 3: MOTOR DE CÁLCULO DILUIDO CON PRICEBOOK DINÁMICO
# ============================================================================


# PDFGenerator y _pdf_safe viven ahora en utils/pdf_propuesta.py (sin Streamlit).
# Se reexportan aquí para no romper los imports existentes.
from utils.pdf_propuesta import PDFGenerator, _pdf_safe  # noqa: F401,E402


def create_download_link(pdf_content: bytes, filename: str,
                         button_text: str = "📥 Descargar PDF") -> str:
    """
    Enlace de descarga embebido.

    El estilo pasó a `.streamlit/estilos.css` (clase `iso-btn`) y el nombre de
    archivo se escapa: antes se interpolaba directo en el atributo `download`,
    y en la exportación a Excel se metía el nombre del cliente sin sanear.
    """
    b64 = base64.b64encode(pdf_content).decode()
    nombre = html.escape(filename, quote=True)
    return (
        f'<a href="data:application/pdf;base64,{b64}" download="{nombre}">'
        f'<button class="iso-btn iso-btn--verde">{html.escape(button_text)}</button></a>'
    )


# Era `Optional[any]` con la función incorporada `any` en minúscula, no el
# tipo `Any`. Como anotación no fallaba, pero al modernizar la sintaxis a
# `any | None` se convirtió en TypeError al importar el módulo.
def initialize_gemini(api_key: str) -> Any | None:
    if not api_key:
        return None
    try:
        genai.configure(api_key=api_key)
        return genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        st.error(f"Error configurando Gemini: {e}")
        return None


def get_gemini_api_key_from_config() -> str:
    # Prioridad: secrets.toml -> env var -> vacío
    try:
        k = st.secrets.get("gemini", {}).get("api_key", "")
        if k:
            return str(k)
    except Exception:
        pass
    return os.getenv("GEMINI_API_KEY", "") or ""


def get_fal_key_from_config() -> str:
    try:
        k = st.secrets.get("fal", {}).get("api_key", "")
        if k:
            return str(k)
    except Exception:
        pass
    return os.getenv("FAL_KEY", "") or ""


def get_luma_key_from_config() -> str:
    try:
        k = st.secrets.get("luma", {}).get("api_key", "")
        if k:
            return str(k)
    except Exception:
        pass
    return os.getenv("LUMA_API_KEY", "") or ""


def init_text_design_state():
    """Inicializa valores seguros para el asistente Text-to-Design."""
    if "text_design_params" not in st.session_state:
        st.session_state["text_design_params"] = dict(DEFAULT_TEXT_DESIGN_PARAMS)
    if "text_design_raw" not in st.session_state:
        st.session_state["text_design_raw"] = ""
    if "url_imagen" not in st.session_state:
        st.session_state["url_imagen"] = None
    if "url_video" not in st.session_state:
        st.session_state["url_video"] = None


def render_text_design_assistant(context_key: str):
    """
    Renderiza el asistente de texto libre.

    El asistente solo prellena parámetros; no modifica las fórmulas de cálculo.
    """
    init_text_design_state()
    api_key_default = get_gemini_api_key_from_config()
    fal_key_default = get_fal_key_from_config()
    luma_key_default = get_luma_key_from_config()

    with st.expander("✨ ¿No tienes planos? Diseña el concepto con IA", expanded=False):
        st.caption("Describe la vivienda y la IA estimará parámetros editables para el presupuesto, además de generar un render 3D y video si provees las claves de Fal y Luma.")
        descripcion = st.text_area(
            "Describe tu idea de vivienda",
            placeholder="Ej: Casa moderna de 2 niveles en Samaná, 3 habitaciones, terraza, ventanales amplios...",
            key=f"text_design_desc_{context_key}",
        )
        
        col_keys1, col_keys2, col_keys3 = st.columns(3)
        with col_keys1:
            api_key = st.text_input("Gemini API Key (Requerido)", value=api_key_default, type="password", key=f"text_design_api_key_{context_key}")
        with col_keys2:
            fal_key = st.text_input("Fal.ai Key (Para Imagen)", value=fal_key_default, type="password", key=f"text_design_fal_key_{context_key}")
        with col_keys3:
            luma_key = st.text_input("Luma AI Key (Para Video)", value=luma_key_default, type="password", key=f"text_design_luma_key_{context_key}")

        if st.button("Generar Concepto y Medios Visuales", key=f"text_design_btn_{context_key}", use_container_width=True):
            if not descripcion.strip():
                st.warning("Escribe una descripción corta de la vivienda.")
                return
            if not api_key:
                st.warning("Configura tu Gemini API Key en Streamlit Secrets o pégala aquí.")
                return

            # 1. Extraer dimensiones con Gemini
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel("gemini-1.5-flash")
                with st.spinner("🧠 Interpretando tu idea y calculando dimensiones..."):
                    params, raw = analyze_text_design_with_gemini(model, descripcion)
                st.session_state["text_design_raw"] = raw
            except Exception as e:
                st.error(f"No pude consultar Gemini: {e}")
                return

            if not params:
                st.warning("La IA no devolvió un JSON confiable. Ajusta la descripción e intenta otra vez.")
                return

            # Actualizar estado para la app
            st.session_state["text_design_params"] = params
            st.session_state["calc_area_m2"] = float(params["area_m2"])
            st.session_state["plan_area_m2"] = float(params["area_m2"])
            st.session_state["plan_niveles"] = int(params["niveles"])
            st.session_state["plan_perimetro_m"] = float(params["perimetro_m"])
            st.session_state["plan_altura_muro_m"] = float(params["altura_muro_m"])
            st.session_state["plan_espesor_muro_m"] = float(params["espesor_muro_m"])
            st.session_state["calidad_terminados"] = params.get("calidad_terminados", "media")
            st.session_state["plan_params"] = {
                "area_m2": params["area_m2"],
                "niveles": params["niveles"],
                "perimetro_m": params["perimetro_m"],
                "altura_muro_m": params["altura_muro_m"],
                "espesor_muro_m": params["espesor_muro_m"],
                "calidad_terminados": params.get("calidad_terminados", "media"),
                "observaciones": params.get("observaciones", ""),
            }
            
            # 2. Generar Imagen con Fal.ai
            if fal_key:
                with st.spinner("🖼️ Generando render de fachada fotorrealista..."):
                    image_url = generate_facade_image_fal(descripcion, fal_key)
                    if image_url:
                        st.session_state["url_imagen"] = image_url
                        
                        # 3. Generar Video con Luma si hay imagen y llave de Luma
                        if luma_key:
                            with st.spinner("🎥 Generando recorrido virtual en video (puede tomar un par de minutos)..."):
                                video_url = generate_video_luma(image_url, descripcion, luma_key)
                                if video_url:
                                    st.session_state["url_video"] = video_url
                                else:
                                    st.warning("No se pudo generar el video cinematográfico.")
                    else:
                        st.warning("No se pudo generar el render de fachada.")

            st.success("¡Concepto generado con éxito! Revisa los resultados a continuación.")

    # Mostrar medios generados fuera del expander
    if st.session_state.get("url_imagen") or st.session_state.get("url_video"):
        st.subheader("✨ Visualización del Concepto IA")
        col_media1, col_media2 = st.columns(2)
        with col_media1:
            if st.session_state.get("url_imagen"):
                st.image(st.session_state["url_imagen"], caption="Render de Fachada (Fal.ai)", use_column_width=True)
        with col_media2:
            if st.session_state.get("url_video"):
                st.video(st.session_state["url_video"])


def estimate_build_time_days(area_m2: float, productividad_m2_dia: float, min_days: float = 1.0) -> float:
    if productividad_m2_dia <= 0:
        return float("nan")
    return max(min_days, area_m2 / productividad_m2_dia)


def estimate_foundation_volume_m3(area_m2: float, metodo: str) -> float:
    """
    Estimación rápida para comparar métodos.
    - Tradicional suele requerir mayor cimentación por peso.
    """
    base = area_m2 * 0.15
    metodo = (metodo or "").lower()
    if "tradicional" in metodo:
        return base * 1.15
    if "vigas h" in metodo or "isotex" in metodo or "icf" in metodo:
        return base * 1.00
    return base


def calc_h_beams_kg(area_m2: float, perimetro_m: float, beam_spacing_m: float, kg_per_m: float) -> float:
    """
    Modelo paramétrico simple: longitud total de vigas ≈ (perímetro) + (2 * área/espaciamiento).
    Es una aproximación razonable para una retícula básica.
    """
    if beam_spacing_m <= 0 or kg_per_m <= 0:
        return 0.0
    total_len_m = max(0.0, float(perimetro_m)) + 2.0 * (float(area_m2) / float(beam_spacing_m))
    return max(0.0, total_len_m * float(kg_per_m))


# ============================================================================
# RENDERIZADO DEL ENTORNO WEB INTERACTIVO
# ============================================================================


def sincronizar_parametros_globales(datos: dict, origen: str):
    """
    Inyecta las dimensiones detectadas (canvas, Gemini o Text-to-Design) en el
    estado del proyecto.

    Antes escribía cinco claves sueltas de `st.session_state` que NADIE leía
    (`calc_perimetro_m`, `calc_niveles`, `calc_altura_muro_m`,
    `calc_espesor_muro_m`): cinco escrituras, cero lecturas. Ahora delega en
    `ProyectoState`, que valida, sanea y alimenta al motor de cantidades.
    """
    if not datos:
        return

    estado = ProyectoState.cargar().aplicar_metricas(datos, origen=origen)
    estado.guardar()

    st.success(f"🔄 Parámetros actualizados desde: **{origen}**")

    resumen = []
    if datos.get("area_m2"):
        resumen.append(f"área {estado.area_m2:,.1f} m²")
    if datos.get("perimetro_m"):
        resumen.append(f"perímetro {estado.perimetro_m:,.1f} m")
    if datos.get("niveles"):
        resumen.append(f"{estado.niveles} nivel(es)")
    if resumen:
        st.caption("Se usará en el presupuesto: " + ", ".join(resumen))

    for aviso in estado.avisos:
        st.warning(f"⚠️ {aviso}")
