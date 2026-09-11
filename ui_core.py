"""Módulo de interfaz de IsoSmart Titanium (refactor de app.py, 2026-07-10)."""
import base64
import html
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from utils.gemini_client import crear_modelo_gemini
import streamlit as st

from utils.ai_media import generate_facade_image_fal, generate_video_luma
from utils.ai_text_design import DEFAULT_TEXT_DESIGN_PARAMS, analyze_text_design_with_gemini
from utils.cad_jobs import crear_cad_job, listar_cad_jobs
from utils.energia import AnalisisEnergetico
from utils.estado import ProyectoState
from utils.floor_plan import generar_esquema_svg
from utils.pricebook import DEFAULT_PRICEBOOK
from utils.qto import MotorQTO
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
        return {p["id"]: p for p in self.list_projects()}

    def save_project(self, project_id: str, data: dict):
        if hasattr(self.repo, "guardar_proyecto"):
            self.repo.guardar_proyecto(project_id, data)
            return
        self._sqlite.guardar_proyecto(project_id, data)

    def get_project(self, project_id: str) -> dict | None:
        if hasattr(self.repo, "obtener_proyecto"):
            return self.repo.obtener_proyecto(project_id)
        return self._sqlite.obtener_proyecto(project_id)

    def list_projects(self) -> list[dict]:
        if hasattr(self.repo, "listar_proyectos"):
            return self.repo.listar_proyectos()
        return self._sqlite.listar_proyectos()

    def delete_project(self, project_id: str):
        if hasattr(self.repo, "eliminar_proyecto"):
            self.repo.eliminar_proyecto(project_id)
            return
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
    """
    Migrado al SDK nuevo (google-genai) vía utils/gemini_client.py -- el
    viejo (google-generativeai, usado aquí con `genai.GenerativeModel`)
    llegó a su fin de soporte permanente el 30 de noviembre de 2025, y el
    modelo Gemini 1.5 que se usaba es de una generación anterior a Gemini
    2.0 Flash, que a su vez se apagó el 1 de junio de 2026 -- casi con toda
    seguridad ya no respondía en absoluto.
    """
    try:
        return crear_modelo_gemini(api_key)
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
    Asistente Texto -> Diseño: convierte una descripción libre en un
    presupuesto real y un esquema de planta, y captura el lead.

    REESCRITO (2026-07-26): antes solo extraía dimensiones agregadas (área,
    perímetro) y generaba un render de fachada -- útil como imagen bonita,
    pero no era lo que un lead pide cuando describe "3 dormitorios, 2 con
    baño": quiere ver cómo se distribuye eso y cuánto cuesta, no una foto
    de la fachada.

    Ahora:
      1. Gemini extrae el PROGRAMA DE AMBIENTES (dormitorios, baños, cocina,
         marquesina...), no solo área/perímetro -- ver utils/ai_text_design.py.
      2. Ese programa alimenta ProyectoState -> Geometria con conteos reales
         (banos, puertas, ventanas), reemplazando la estimación genérica por
         área que usa el resto de la app cuando no hay mejor dato.
      3. Se corre el motor QTO real (el mismo que usa el resto de la app,
         no un cálculo aparte) y se muestra un presupuesto de verdad.
      4. Se dibuja un ESQUEMA de planta (utils/floor_plan.py) -- un diagrama
         de bloques proporcional, etiquetado como lo que es, no una imagen
         generada que finge ser un plano arquitectónico.
      5. El render de fachada (Fal.ai) y el video (Luma) siguen disponibles,
         pero como una impresión artística OPCIONAL y claramente marcada
         como tal -- no son la fuente de ningún dato del presupuesto.
      6. Se ofrece capturar el lead (nombre + contacto) justo después de
         ver su presupuesto -- el momento de mayor interés.
    """
    init_text_design_state()
    api_key_default = get_gemini_api_key_from_config()

    with st.expander("✨ ¿No tienes planos? Describe tu idea y te cotizamos", expanded=False):
        st.caption(
            "Describe la vivienda que imaginas -- cuántos dormitorios, baños, si "
            "quieres marquesina, terraza, etc. Generamos un presupuesto real y un "
            "esquema de cómo se distribuiría."
        )
        descripcion = st.text_area(
            "Describe tu idea de vivienda",
            placeholder="Ej: Casa de 2 niveles, 3 dormitorios (2 con baño), cocina, "
                       "sala, comedor, terraza con lavadero, marquesina para 2 carros...",
            key=f"text_design_desc_{context_key}",
        )
        api_key = st.text_input("Gemini API Key", value=api_key_default, type="password",
                                key=f"text_design_api_key_{context_key}")

        if st.button("🏠 Generar Presupuesto y Esquema", key=f"text_design_btn_{context_key}",
                     use_container_width=True, type="primary"):
            if not descripcion.strip():
                st.warning("Escribe una descripción corta de la vivienda.")
                return
            if not api_key:
                st.warning("Configura tu Gemini API Key en Streamlit Secrets o pégala aquí.")
                return

            try:
                model = crear_modelo_gemini(api_key)
                with st.spinner("🧠 Interpretando tu idea..."):
                    params, raw = analyze_text_design_with_gemini(model, descripcion)
                st.session_state["text_design_raw"] = raw
            except Exception as e:
                st.error(f"No pude consultar Gemini: {e}")
                return

            if not params:
                st.warning("La IA no devolvió un JSON confiable. Ajusta la descripción e intenta otra vez.")
                return

            # Antes: escritura directa de claves plan_* sueltas. Ahora pasa
            # por ProyectoState, la única fuente de verdad (Fase 2) -- así
            # el programa de ambientes (baños, puertas, ventanas reales)
            # llega hasta Geometria, no solo el área.
            estado = ProyectoState.cargar()
            estado.aplicar_metricas(params, origen="Texto → Diseño (IA)")
            estado.guardar()

            st.session_state["text_design_params"] = params
            st.session_state["descripcion_lead"] = descripcion
            st.success("¡Listo! Revisa tu presupuesto y el esquema a continuación.")

    # -- resultados: fuera del expander para que no se colapsen -----------
    estado = ProyectoState.cargar()
    params = st.session_state.get("text_design_params")
    if not params:
        return

    st.subheader("📋 Tu proyecto")
    if estado.avisos:
        for aviso in estado.avisos:
            st.caption(f"⚠️ {aviso}")

    try:
        geo = estado.geometria()
        precios = st.session_state.get("precios_sincronizados") or DEFAULT_PRICEBOOK
        motor = MotorQTO(geo, precios, calidad=estado.calidad)
    except (KeyError, ValueError) as e:
        st.error(f"No se pudo calcular el presupuesto: {e}")
        return

    col_r1, col_r2, col_r3 = st.columns(3)
    col_r1.metric("Área estimada", f"{geo.area_m2:,.0f} m²")
    col_r2.metric("Presupuesto estimado", f"RD$ {motor.total():,.0f}")
    col_r3.metric("Costo por m²", f"RD$ {motor.costo_m2():,.0f}")
    st.caption(
        "Calculado con el mismo motor de cantidades que el resto de la app "
        "(utils/qto.py) -- no es una cifra genérica ni un promedio de mercado."
    )

    if params.get("habitaciones"):
        st.markdown("#### 🗺️ Esquema de distribución")
        svg = generar_esquema_svg(params["habitaciones"], area_total_m2=geo.area_m2)
        st.markdown(svg, unsafe_allow_html=True)

    st.markdown("#### Activación CAD / Open CAD Studio")
    incluir_solar_cad = st.checkbox(
        "Incluir sistema solar e instalaciones ecológicas",
        value=True,
        key=f"cad_solar_{context_key}",
    )
    col_cad_1, col_cad_2 = st.columns([1, 1])
    with col_cad_1:
        if st.button("Crear solicitud CAD/OCS", key=f"cad_job_btn_{context_key}",
                     use_container_width=True):
            solar = (
                AnalisisEnergetico.calcular_sistema_solar_recomendado(geo.area_m2)
                if incluir_solar_cad else None
            )
            job = crear_cad_job(
                st.session_state.get("descripcion_lead", "") or "Proyecto residencial sin descripción guardada",
                estado,
                solar=solar,
            )
            st.session_state["ultimo_cad_job_id"] = job["id"]
            st.success(f"Solicitud CAD creada: {job['id']}")
    with col_cad_2:
        ultimo = st.session_state.get("ultimo_cad_job_id")
        if ultimo:
            st.info(f"Último job CAD: `{ultimo}`")

    jobs = listar_cad_jobs(limite=5)
    if jobs:
        st.dataframe(
            [{"ID": j["id"], "Estado": j["status"], "Creado": j["created_at"]}
             for j in jobs],
            use_container_width=True,
            hide_index=True,
        )

    # -- fachada/video: opcional, claramente aparte del presupuesto -------
    with st.expander("🎨 Ver una impresión artística de la fachada (opcional)", expanded=False):
        st.caption(
            "⚠️ Esta imagen es generada por IA como referencia visual -- NO "
            "representa el diseño final ni afecta el presupuesto de arriba, "
            "que se calcula con el motor de cantidades real."
        )
        fal_key_default = get_fal_key_from_config()
        luma_key_default = get_luma_key_from_config()
        col_keys1, col_keys2 = st.columns(2)
        with col_keys1:
            fal_key = st.text_input("Fal.ai Key", value=fal_key_default, type="password",
                                    key=f"text_design_fal_key_{context_key}")
        with col_keys2:
            luma_key = st.text_input("Luma AI Key", value=luma_key_default, type="password",
                                     key=f"text_design_luma_key_{context_key}")
        if st.button("Generar imagen y video", key=f"text_design_media_btn_{context_key}"):
            descripcion_previa = st.session_state.get("descripcion_lead", "")
            if fal_key and descripcion_previa:
                with st.spinner("🖼️ Generando render de fachada..."):
                    image_url = generate_facade_image_fal(descripcion_previa, fal_key)
                    if image_url:
                        st.session_state["url_imagen"] = image_url
                        if luma_key:
                            with st.spinner("🎥 Generando video (puede tomar un par de minutos)..."):
                                video_url = generate_video_luma(image_url, descripcion_previa, luma_key)
                                if video_url:
                                    st.session_state["url_video"] = video_url
                    else:
                        st.warning("No se pudo generar el render de fachada.")
            else:
                st.warning("Falta la Fal.ai Key o la descripción original.")

        if st.session_state.get("url_imagen"):
            st.image(st.session_state["url_imagen"], caption="Impresión artística (no final)",
                     use_container_width=True)
        if st.session_state.get("url_video"):
            st.video(st.session_state["url_video"])

    # -- captura de lead: el momento de mayor interés ----------------------
    st.divider()
    st.markdown("#### 📞 ¿Te interesa este presupuesto? Déjanos tus datos")
    with st.form(f"lead_text_design_{context_key}", clear_on_submit=True):
        col_l1, col_l2 = st.columns(2)
        with col_l1:
            nombre = st.text_input("Nombre completo *")
            telefono = st.text_input("Teléfono")
        with col_l2:
            email = st.text_input("Email *")
            ubicacion = st.selectbox(
                "Ubicación del proyecto",
                ["Santo Domingo", "Santiago", "Punta Cana", "La Romana",
                 "Puerto Plata", "San Pedro", "La Vega", "Otro"],
            )
        if st.form_submit_button("Solicitar cotización formal", use_container_width=True, type="primary"):
            if nombre and email:
                ProjectManager().save_lead({
                    "nombre": nombre,
                    "email": email,
                    "telefono": telefono,
                    "ubicacion": ubicacion,
                    "tipo_proyecto": "Vivienda Unifamiliar",
                    "area_estimada": geo.area_m2,
                    "mensaje": (
                        f"[Generado con asistente IA] {st.session_state.get('descripcion_lead', '')} "
                        f"-- Presupuesto estimado: RD$ {motor.total():,.0f}"
                    ),
                })
                st.success("✅ ¡Gracias! Un asesor se pondrá en contacto pronto con tu cotización formal.")
            else:
                st.error("❌ Completa al menos nombre y email.")


def estimate_build_time_days(area_m2: float, productividad_m2_dia: float, min_days: float = 1.0) -> float:
    if productividad_m2_dia <= 0:
        return float("nan")
    return max(min_days, area_m2 / productividad_m2_dia)


def estimate_foundation_volume_m3(area_m2: float, metodo: str) -> float:
    """
    ⚠️ CÓDIGO MUERTO (verificado 2026-07-26): sin ningún caller fuera de este
    archivo. Vivía en el modelo paramétrico "vigas H + cerramiento" de
    `pagina_plano_estructura()`, retirado por estar desconectado del motor
    QTO real (usaba `Panel_Muro: 925.00`, un precio sin fuente ya corregido
    a 1,072 en todo el resto de la app). Ver utils/qto.py para el cálculo
    real de cimentación (replantillo, plantilla, platea, dentellón).

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
    ⚠️ CÓDIGO MUERTO (verificado 2026-07-26): mismo origen y motivo que
    `estimate_foundation_volume_m3` -- ver esa nota. El propio informe de
    auditoría original ya había señalado el peligro de activar vigas de
    acero por defecto en un sistema cuyo argumento de venta es no
    necesitarlas.

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
