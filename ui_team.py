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

    # Galería de proyectos
    st.markdown("### 🏠 Proyectos Realizados")

    col_gal1, col_gal2, col_gal3 = st.columns(3)

    with col_gal1:
        st.image("https://images.unsplash.com/photo-1590059390239-03c9e7064e92?w=400",
                 caption="Vivienda Unifamiliar - 150m²", use_container_width=True)

    with col_gal2:
        st.image("https://images.unsplash.com/photo-1582268611958-ebfd161ef9cf?w=400",
                 caption="Edificio de Apartamentos", use_container_width=True)

    with col_gal3:
        st.image("https://images.unsplash.com/photo-1503387762-592deb58ef4e?w=400",
                 caption="Local Comercial", use_container_width=True)

    st.divider()

    # Testimonios (placeholder)
    st.markdown("### 💬 Lo Que Dicen Nuestros Clientes")

    st.markdown("""
    <div class="info-card">
        <em>"Construí mi vivienda con el sistema Isotex y estoy muy satisfecho. La casa quedó
        más fresca y el ahorro en el aire acondicionado es notable. El team fue muy profesional."</em>
        <br><strong>- Juan P., Santo Domingo</strong>
    </div>

    <div class="info-card">
        <em>"Como ingeniero, estaba escéptico al principio. Pero después de ver los resultados
        y los cálculos estructurales, quedé convencido. Es un sistema válido y eficiente."</em>
        <br><strong>- Arq. María G., Santiago</strong>
    </div>
    """, unsafe_allow_html=True)
# ============================================================================
# PASO 1: INTEGRACIÓN DE CANVAS GEOMÉTRICO Y VISIÓN IA
# ============================================================================

