"""
utils/estilos.py
----------------
Carga de la hoja de estilos compartida y componentes de presentación.

Sustituye a los 43 bloques `unsafe_allow_html=True` dispersos por siete
archivos, incluidos dos `<style>` completos duplicados entre el Dashboard
Financiero y el Análisis Energético.

Además reduce la superficie de inyección de HTML: los helpers de aquí escapan
el contenido que reciben, cosa que las f-strings sueltas no hacían.
"""

from __future__ import annotations

import html
import os
from functools import lru_cache

RUTA_CSS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".streamlit",
    "estilos.css",
)

_CLAVE_INYECTADO = "_css_inyectado"


@lru_cache(maxsize=2)
def _leer_css(ruta: str = RUTA_CSS) -> str:
    if not os.path.exists(ruta):
        return ""
    with open(ruta, encoding="utf-8") as f:
        return f.read()


def inyectar_css() -> None:
    """
    Inserta la hoja de estilos una sola vez por sesión.

    Streamlit re-ejecuta el script entero en cada interacción; sin este guardia
    el mismo `<style>` se insertaba decenas de veces por sesión.
    """
    import streamlit as st

    if st.session_state.get(_CLAVE_INYECTADO):
        return
    css = _leer_css()
    if css:
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
        st.session_state[_CLAVE_INYECTADO] = True


def encabezado(titulo: str, subtitulo: str = "") -> None:
    """Cabecera de página con el degradado corporativo."""
    import streamlit as st

    inyectar_css()
    sub = f"<p>{html.escape(subtitulo)}</p>" if subtitulo else ""
    st.markdown(
        f'<div class="page-header"><h1>{html.escape(titulo)}</h1>{sub}</div>',
        unsafe_allow_html=True,
    )


def tarjeta_metrica(etiqueta: str, valor: str, subtexto: str = "",
                    variante: str = "", clase_base: str = "metric-card") -> None:
    """
    Tarjeta de métrica.

    Unifica `render_metric_card` (Dashboard Financiero) y `render_energy_card`
    (Análisis Energético), que eran la misma función copiada con otro nombre y
    otra clase CSS.

    `variante`: "" | "green" | "orange" | "blue"
    """
    import streamlit as st

    inyectar_css()
    prefijo = "metric" if clase_base == "metric-card" else "energy"
    variante = variante if variante in ("green", "orange", "blue") else ""
    sub = (f'<p class="{prefijo}-sub">{html.escape(subtexto)}</p>' if subtexto else "")

    st.markdown(
        f'<div class="{clase_base} {variante}">'
        f'<p class="{prefijo}-value">{html.escape(str(valor))}</p>'
        f'<p class="{prefijo}-label">{html.escape(etiqueta)}</p>'
        f"{sub}</div>",
        unsafe_allow_html=True,
    )


def caja_info(texto: str, titulo: str = "") -> None:
    import streamlit as st

    inyectar_css()
    encabezado_html = f"<strong>{html.escape(titulo)}</strong><br>" if titulo else ""
    st.markdown(
        f'<div class="info-box">{encabezado_html}{html.escape(texto)}</div>',
        unsafe_allow_html=True,
    )


def boton_enlace(url: str, texto: str, variante: str = "verde") -> None:
    """
    Botón que envuelve un enlace (descarga de PDF/Excel, WhatsApp).

    Los originales interpolaban el nombre del cliente sin escapar dentro del
    `href` y del texto del botón.
    """
    import streamlit as st

    inyectar_css()
    clase = f"iso-btn iso-btn--{variante}"
    st.markdown(
        f'<a href="{html.escape(url, quote=True)}" target="_blank">'
        f'<button class="{clase}">{html.escape(texto)}</button></a>',
        unsafe_allow_html=True,
    )
