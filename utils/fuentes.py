# -*- coding: utf-8 -*-
"""
utils/fuentes.py
-----------------
Sistema de trazabilidad de datos técnicos y comerciales.

POR QUÉ EXISTE
==============
La pantalla de inicio (`ui_inicio.py`) mostraba una tabla comparativa con nueve
cifras y tres afirmaciones de texto ("Excelente", "Hasta 45dB", "Alta
(flexible)") sin ninguna fuente. Al trazarlas se encontró que:

  - Los 9 números salían del motor CLÁSICO (`utils/calculador.py`), que la
    Fase 1 de esta auditoría ya reemplazó por `utils/qto.py` en el resto de la
    app — pero la pantalla de inicio nunca se migró.
  - Peso, tiempo de construcción y comparación tradicional eran CONSTANTES
    (`m2 * 220`, `m2 * 1.5`...) sin ninguna fuente citada.
  - "Excelente/Regular", "45dB/20dB" y "Alta/Media" eran texto fijo en el HTML,
    sin cálculo ni cita detrás.

Este módulo obliga a que cualquier dato mostrado en pantalla declare su
`Fuente`. Un dato sin fuente no se puede marcar como VERIFICADO: por diseño,
si no se declara, se muestra como REFERENCIA con la advertencia visible.

USO
===
    from utils.fuentes import Fuente, TIPO_CAMBIO_MXN_DOP

    dato = Fuente(
        valor="44 dB",
        tipo="verificado",
        cita="Ficha técnica Covintec (México), aislamiento acústico panel EPS+malla",
        url="https://covintec.com/wp-content/uploads/2022/04/covintec-ficha-tecnica-panel-covintec-3-pulgadas.pdf",
    )
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

# ---------------------------------------------------------------------------
# Tipo de cambio usado para convertir precios de referencia de Covintec México
# (cotizados en MXN) a RD$. Con fuente y fecha de captura explícitas: un tipo
# de cambio sin fecha es tan poco trazable como un precio sin fuente.
# ---------------------------------------------------------------------------
TIPO_CAMBIO_MXN_DOP = 3.36          # 1 MXN = 3.36 DOP
TIPO_CAMBIO_FECHA = date(2026, 7, 26)
TIPO_CAMBIO_FUENTE = "Xe.com, tasa media de mercado interbancario"
TIPO_CAMBIO_URL = "https://www.xe.com/es/currencyconverter/convert/?Amount=1&From=MXN&To=DOP"


TIPOS_VALIDOS = ("verificado", "referencia", "estimado", "no_disponible")


@dataclass(frozen=True)
class Fuente:
    """
    Un dato con su procedencia declarada.

    tipo:
      - "verificado"    -> ficha técnica de fabricante, norma o índice oficial
      - "referencia"    -> precio o dato de mercado (Covintec México, ICDV...)
                           usado como sustituto documentado mientras no hay
                           datos locales
      - "estimado"      -> ingeniería de la auditoría, marcado [supuesto]
      - "no_disponible" -> no hay dato defendible; NO debe mostrarse como cifra
    """

    valor: str
    tipo: str
    cita: str
    url: Optional[str] = None
    fecha: Optional[date] = None

    def __post_init__(self):
        if self.tipo not in TIPOS_VALIDOS:
            raise ValueError(f"tipo de fuente inválido: {self.tipo!r}. Usa uno de {TIPOS_VALIDOS}")
        if self.tipo != "no_disponible" and not self.cita:
            raise ValueError("toda Fuente con dato debe declarar una cita")

    @property
    def etiqueta(self) -> str:
        return {
            "verificado": "✅ Verificado",
            "referencia": "📎 Referencia",
            "estimado": "🔧 Estimado (ingeniería)",
            "no_disponible": "❓ No disponible",
        }[self.tipo]

    def html_footnote(self) -> str:
        """Pie de página HTML-safe para mostrar junto al dato."""
        import html as _html

        texto = _html.escape(self.cita)
        if self.url:
            enlace = _html.escape(self.url, quote=True)
            return f'<small>{self.etiqueta}: <a href="{enlace}" target="_blank">{texto}</a></small>'
        return f"<small>{self.etiqueta}: {texto}</small>"


def convertir_mxn_a_dop(monto_mxn: float) -> float:
    """Conversión con tipo de cambio y fecha trazables (ver TIPO_CAMBIO_*)."""
    return monto_mxn * TIPO_CAMBIO_MXN_DOP


# ---------------------------------------------------------------------------
# Fichas técnicas verificadas — Isotex Dominicana (proveedor local, RD)
# ---------------------------------------------------------------------------
# Fuente: isotexdominicana.com, fabricante que opera en Santo Domingo desde
# 2005 (Parque Industrial Duarte, Autopista Duarte Km 22 1/2). El teléfono y
# correo que aparecen en ui_team.py (+809 561 5599, info@grupoisotex.net)
# coinciden exactamente con los publicados en su sitio -- es contacto real,
# no inventado.
#
# Esta es una fuente MEJOR que Covintec México (FICHA_COVINTEC más abajo)
# para las partidas donde ya está disponible: es el mercado local real, no
# una referencia de otro país. Ficha técnica en PDF enlazada desde la propia
# página del producto.
#
# El "ahorro hasta 65%" es una afirmación del FABRICANTE (marketing propio),
# no una medición independiente -- se marca "referencia", nunca "verificado".
# ---------------------------------------------------------------------------

FICHA_ISOTEX_DOMINICANA = {
    "mpanel_ancho_util_m": Fuente(
        valor="1.2 m",
        tipo="referencia",
        cita="Ficha técnica MPanel®, Isotex Dominicana (Santo Domingo, RD)",
        url="https://isotexdominicana.com/paredes/mpanel/",
    ),
    "mpanel_densidad_eps_kg_m3": Fuente(
        valor="13-15 kg/m³",
        tipo="referencia",
        cita="Ficha técnica MPanel®, Isotex Dominicana",
        url="https://isotexdominicana.com/paredes/mpanel/",
    ),
    "mpanel_espesor_pared_terminada_mm": Fuente(
        valor="90-270 mm",
        tipo="referencia",
        cita="Ficha técnica MPanel®, Isotex Dominicana",
        url="https://isotexdominicana.com/paredes/mpanel/",
    ),
    "termopanel_peso_kg_m2": Fuente(
        valor="8-15 kg/m²",
        tipo="referencia",
        cita="Ficha técnica Termopanel® (techos), Isotex Dominicana",
        url="https://isotexdominicana.com/techos/termopanel/",
    ),
    "termopanel_resistencia_termica_k": Fuente(
        valor="K = 0.343",
        tipo="referencia",
        cita="Ficha técnica Termopanel® (techos), Isotex Dominicana",
        url="https://isotexdominicana.com/techos/termopanel/",
    ),
    "mpanel_ahorro_energetico_pct": Fuente(
        valor="hasta 65%",
        tipo="referencia",
        cita="Afirmación del FABRICANTE (Isotex Dominicana), no una medición "
             "independiente: 'Ahorro hasta un 65% de la energía necesaria "
             "para acondicionar los ambientes construidos'",
        url="https://isotexdominicana.com/paredes/mpanel/",
    ),
}


# ---------------------------------------------------------------------------
# NotebookLM del usuario — 50 videos de YouTube sobre EPS/ICF
# ---------------------------------------------------------------------------
# El usuario mantiene un cuaderno de NotebookLM curado con 50 videos sobre
# mejores prácticas de sistemas constructivos EPS/ICF (Covintec, ICF, Isotex).
# No es accesible directamente (notebooklm.google.com bloquea el rastreo
# automatizado y requiere sesión de Google), así que el usuario comparte
# resúmenes puntuales cuando se necesita verificar un parámetro específico.
#
# Videos consultados hasta ahora:
#   #37 "NUEVO CURSO CUANTIFICACION DE MATERIALES" -- fórmulas de malla
#       zigzag/esquinera/unión, espesores de capa de compresión
#   #42 "Sabe Usted Como Hacer las Proporciones del Concreto" -- confirmó
#       exactamente los valores ya usados (3.5/5.5 botes, 138-148 L/bulto)
#   #20/#34 "Costos Covintec" / "Costos del sistema Constructivo Covintec"
#       -- rendimientos reales de cuadrilla (armado de muros, losas),
#       herramienta menor, comparación de ahorro 20-40%
#   #37 (seguimiento) -- malla esquinera: DOS productos distintos (interna
#       10x10/14x14cm, externa 20x20cm), redondeo por esquina y por tipo
#       (no en agregado), verificado con ejemplo numérico resuelto
FUENTE_NOTEBOOKLM_USUARIO = Fuente(
    valor="NotebookLM del usuario (50 videos de YouTube sobre EPS/ICF)",
    tipo="referencia",
    cita="Cuaderno curado por el usuario con videos de canales como "
         "Covintec México, Construcciones Ideales y otros, sobre mejores "
         "prácticas de construcción con EPS/ICF. Consultado por resúmenes "
         "puntuales que el usuario comparte, citando el video de origen.",
    url=None,
)


# ---------------------------------------------------------------------------
# Manual Técnico Panel Covintec 2011 — fuente primaria del fabricante
# ---------------------------------------------------------------------------
# Encontrado al verificar el conflicto de anclaje de la ronda anterior.
# Corroborado en 5 copias independientes con texto idéntico (Scribd,
# SlideShare, StudyLib, VSIP) -- alta confianza en que es una transcripción
# fiel del manual técnico real del fabricante mexicano de paneles Covintec
# (el mismo sistema constructivo EPS + malla que Isotex/Covintex en RD).
#
# Resolvió con precisión el conflicto de anclaje (10 cm empotrado + 40 cm
# libre, no los 5 cm de BASE_TECNICA_EPS_ICF.md ni los 40-50 cm de otra
# fuente ambigua) y corrigió la resistencia de concreto de la platea de
# cimentación (200 kg/cm², no 250 kg/cm²).
FUENTE_MANUAL_TECNICO_COVINTEC_2011 = Fuente(
    valor="Manual Técnico Panel Covintec 2011",
    tipo="referencia",
    cita="Manual técnico oficial del fabricante (México), corroborado en 5 "
         "copias independientes. Resolvió el conflicto de anclaje "
         "(10 cm empotrado + 40 cm libre) y la resistencia de la platea "
         "de cimentación (200 kg/cm²).",
    url="https://es.scribd.com/document/237263489/Manual-Tecnico-Covintec-2011",
)


# ---------------------------------------------------------------------------
# Fichas técnicas verificadas — panel Covintec (México)
# ---------------------------------------------------------------------------
# Fuente: covintec.com/fichas-tecnicas/ (fichas técnicas oficiales del
# fabricante). Los datos de AISLAMIENTO son del panel; NO son específicos de
# Isotex/República Dominicana, así que se marcan "referencia" y no
# "verificado": son la mejor fuente disponible del mismo sistema constructivo
# (EPS + malla electrosoldada), no una medición local.
# ---------------------------------------------------------------------------

FICHA_COVINTEC = {
    "aislamiento_acustico_db": Fuente(
        valor="44 dB",
        tipo="referencia",
        cita="Ficha técnica Covintec (panel EPS + malla electrosoldada, México). "
             "Dato del fabricante del sistema constructivo, no de una medición en RD.",
        url="https://covintec.com/wp-content/uploads/2022/04/covintec-ficha-tecnica-panel-covintec-3-pulgadas.pdf",
    ),
    "resistencia_termica_r": Fuente(
        valor="R = 1.61 m²K/W",
        tipo="referencia",
        cita="Ficha técnica Qualylosa Covintec 4\" (México)",
        url="https://covintec.com/wp-content/uploads/2024/08/QLOSA-4PULG-325-1.pdf",
    ),
    "peso_losa_azotea_kg_m2": Fuente(
        valor="114.76 kg/m²",
        tipo="referencia",
        cita="Ficha técnica Qualylosa Covintec 4\", peso de losa terminada (azotea)",
        url="https://covintec.com/wp-content/uploads/2024/08/QLOSA-4PULG-325-1.pdf",
    ),
    "peso_losa_entrepiso_kg_m2": Fuente(
        valor="124.16 kg/m²",
        tipo="referencia",
        cita="Ficha técnica Qualylosa Covintec 4\", peso de losa terminada (entrepiso)",
        url="https://covintec.com/wp-content/uploads/2024/08/QLOSA-4PULG-325-1.pdf",
    ),
    "peso_panel_sin_aplanar_kg_m2": Fuente(
        valor="2.8 kg/m²",
        tipo="referencia",
        cita="Ficha técnica Qualy Panel Covintec 4\" (México), peso sin aplanar",
        url="https://covintec.com/productos/qualy-panel-de-3x1-22x2-44m/",
    ),
    "reduccion_acero_pct": Fuente(
        valor="hasta 25%",
        tipo="referencia",
        cita="Covintec México: 'Reduce hasta un 25% de acero sin comprometer "
             "la seguridad ni la resistencia del proyecto'",
        url="https://covintec.com/",
    ),
}

# ---------------------------------------------------------------------------
# Construcción tradicional en RD — índice oficial
# ---------------------------------------------------------------------------
COSTO_TRADICIONAL_RD_M2 = Fuente(
    valor="RD$ 30,000 – 45,000 /m²",
    tipo="referencia",
    cita="Índice de Costos Directos de la Construcción de Viviendas (ICDV), "
         "ACOPROVI y la Oficina Nacional de Estadística (ONE): costo promedio "
         "superó RD$35,000/m² en 2024-2025",
    url="https://1122.com.do/es/blog/construir-en-rd-2026-costos-permisos-e-incentivos-fiscales-para-desarrolladores",
)

# ---------------------------------------------------------------------------
# Datos SIN fuente defendible — se documentan explícitamente para que no se
# vuelvan a inventar por accidente en un futuro refactor.
# ---------------------------------------------------------------------------
SIN_FUENTE_CONOCIDA = {
    "resistencia_sismica_comparativa": Fuente(
        valor="", tipo="no_disponible",
        cita="No se encontró ensayo o norma sismorresistente específica que "
             "compare EPS/ICF vs. mampostería tradicional en RD. Requiere un "
             "informe de ingeniería estructural local antes de mostrarse.",
    ),
    "tiempo_construccion_comparativo": Fuente(
        valor="", tipo="no_disponible",
        cita="El '180 vs 300 días' salía de multiplicar el área por una "
             "constante de días/m² sin fuente ni cronograma real. Se retira "
             "hasta tener datos de obra ejecutada (ver docs/BASE_TECNICA).",
    ),
}
