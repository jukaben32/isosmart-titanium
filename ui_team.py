"""Módulo de interfaz de IsoSmart Titanium (refactor de app.py, 2026-07-10)."""
import streamlit as st

# Helpers compartidos desde ui_core

def pagina_team():
    """Página de presentación del team constructor"""

    st.markdown("""
    <div class="main-header">
        <h1 style="margin:0;">👷 Nuestro Team de Construcción</h1>
        <p style="margin:10px 0 0 0; font-size:1.2rem;">Expertos en Construcción con Poliestireno Expandido en República Dominicana</p>
    </div>
    """, unsafe_allow_html=True)

    # Información del team
    col_team1, col_team2 = st.columns([2, 1])

    with col_team1:
        st.markdown("""
        <div class="team-card">
        <h3>🏆 Experiencia y Profesionalismo</h3>
        <p>Somos un equipo de constructores dominicanos con experiencia en el sistema de
        poliestireno expandido. Entendemos las necesidades específicas de construcción
        en nuestro país y ofrecemos soluciones adaptadas al clima y condiciones de RD.</p>

        <h4>✅ Nuestros Servicios:</h4>
        <ul>
            <li>Asesoría técnica personalizada</li>
            <li>Cálculo estructural y de materiales</li>
            <li>Supervisión de obra</li>
            <li>Capacitación a albañiles y maestros</li>
            <li>Ejecución completa de proyectos</li>
        </ul>
        </div>
        """, unsafe_allow_html=True)

    with col_team2:
        st.markdown("""
        <div class="team-card" style="text-align:center;">
            <div style="font-size:4rem;">📞</div>
            <h4>Contáctanos</h4>
            <p><strong>Teléfono:</strong><br>+809 561 5599</p>
            <p><strong>Email:</strong><br>info@grupoisotex.net</p>
            <p><strong>Ubicación:</strong><br>Parque Industrial Duarte, Autopista Duarte Km 22 1/2, Santo Domingo, RD</p>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # ------------------------------------------------------------------
    # Galería de proyectos.
    #
    # ANTES: fotos de stock de Unsplash con pies de foto que simulaban ser
    # proyectos reales de la empresa ("Vivienda Unifamiliar - 150m²",
    # "Edificio de Apartamentos"). Presentar fotografía de stock como
    # documentación del propio trabajo terminado es exactamente lo que el
    # principio de trazabilidad de esta app prohíbe: un dato (aquí, una
    # imagen) que parece evidencia real sin serlo.
    # ------------------------------------------------------------------
    st.markdown("### 🏠 Nuestro Sistema Constructivo")
    st.caption(
        "Las imágenes de esta sección son ilustrativas (no son fotos de "
        "proyectos propios). Cuando existan fotos reales de obras ejecutadas, "
        "deben reemplazar a estas."
    )

    col_gal1, col_gal2, col_gal3 = st.columns(3)

    with col_gal1:
        st.image("https://images.unsplash.com/photo-1590059390239-03c9e7064e92?w=400",
                 caption="Ilustrativa: instalación de panel EPS", use_container_width=True)

    with col_gal2:
        st.image("https://images.unsplash.com/photo-1582268611958-ebfd161ef9cf?w=400",
                 caption="Ilustrativa: construcción residencial", use_container_width=True)

    with col_gal3:
        st.image("https://images.unsplash.com/photo-1503387762-592deb58ef4e?w=400",
                 caption="Ilustrativa: local comercial", use_container_width=True)

    st.divider()

    # ------------------------------------------------------------------
    # ANTES: esta sección mostraba dos citas atribuidas a "Juan P., Santo
    # Domingo" y "Arq. María G., Santiago" bajo el título "Lo Que Dicen
    # Nuestros Clientes". El propio comentario del código decía
    # "Testimonios (placeholder)" -- eran fabricados, no clientes reales.
    # Presentar testimonios inventados con nombres de personas como si
    # fueran reseñas reales es publicidad engañosa, no un dato con fuente
    # débil: no hay ninguna fuente porque no hay ningún cliente real detrás.
    #
    # Se retira hasta que existan testimonios reales que recopilar (con
    # consentimiento del cliente para citarlo).
    # ------------------------------------------------------------------
    st.markdown("### 💬 Testimonios de Clientes")
    st.info(
        "Aún no se han recopilado testimonios de clientes reales para "
        "mostrar aquí. En cuanto existan (con su consentimiento para "
        "publicarlos), reemplazan a este aviso."
    )
# ============================================================================
# PASO 1: INTEGRACIÓN DE CANVAS GEOMÉTRICO Y VISIÓN IA
# ============================================================================

