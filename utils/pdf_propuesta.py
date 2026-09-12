"""
utils/pdf_propuesta.py
---------------------
Generación del PDF de propuesta comercial. **Sin dependencia de Streamlit.**

Vivía dentro de ui_core.py, un módulo que importa streamlit, plotly, PIL y el
SDK de Gemini. Eso hacía imposible testear el entregable comercial más
importante de la app sin levantar medio entorno gráfico — y es parte de por qué
nadie notó que `output(dest='S').encode('latin-1')` llevaba tiempo roto.

ui_core.py lo reexporta para no romper los imports existentes.

La tabla de partidas imprime el presupuesto COMPLETO con paginación automática
(FPDF añade páginas y repite la cabecera de tabla hasta terminar todas las
filas). Acepta dos esquemas de columnas:

  - QTO nuevo (utils/qto.py::presupuesto): ``partida``, ``detalle``,
    ``unidad``, ``cantidad``, ``precio_unitario``, ``subtotal``,
    ``clave_precio``, ``precio_por_verificar``, ``categoria``.
  - Legado (utils/calculador.py): ``Material``, ``Detalle``, ``Cantidad``,
    ``Unidad``, ``P_Unitario``, ``Subtotal``, ``Categoria``.

Se detecta por la presencia de la columna ``Material``.
"""

from __future__ import annotations

from datetime import date
from typing import Dict

import pandas as pd
from fpdf import FPDF
from fpdf.enums import XPos, YPos


def _pdf_safe(texto: object) -> str:
    """
    Las fuentes core de FPDF (Helvetica) solo soportan latin-1.

    Un nombre de cliente pegado desde WhatsApp (comillas tipográficas, emojis,
    guiones largos) reventaba la generación del PDF. Aquí se degrada de forma
    controlada en vez de lanzar excepción.
    """
    return str(texto).encode("latin-1", errors="replace").decode("latin-1")


class PDFGenerator:
    """Generador de documentos PDF profesionales"""

    ANCHO_PAGINA = 210
    MARGEN = 10
    ANCHO_TABLA = 190
    ALTO_FILA = 8
    PIE_PAGINA = 20

    def __init__(self):
        self.pdf = FPDF()
        self.pdf.set_margins(self.MARGEN, 15, self.MARGEN)
        self.pdf.set_auto_page_break(auto=True, margin=15)

    # ------------------------------------------------------------------
    # Tabla de partidas con paginación
    # ------------------------------------------------------------------
    def _tabla_partidas_qto(self, df: pd.DataFrame) -> None:
        """Formato nuevo del motor QTO: partida, clave, precio y marca por verificar."""
        col_widths = [34, 52, 16, 10, 22, 26, 30]
        headers = ["Partida", "Detalle", "Cant.", "Unid.", "P. Unitario", "Subtotal", "Clave precio"]

        def encabezado_tabla():
            self.pdf.set_font("Helvetica", "B", 9)
            self.pdf.set_fill_color(240, 240, 240)
            for i, h in enumerate(headers):
                self.pdf.cell(col_widths[i], 10, h, border=1, fill=True, align="C")
            self.pdf.ln()
            self.pdf.set_font("Helvetica", "", 8.5)

        encabezado_tabla()
        for _, row in df.iterrows():
            if self.pdf.get_y() > self.pdf.page_break_trigger - self.PIE_PAGINA:
                self.pdf.add_page()
                encabezado_tabla()
            clave = _pdf_safe(row.get("clave_precio", "") or "")
            if row.get("precio_por_verificar", False):
                clave = clave + " *"
            self.pdf.cell(col_widths[0], self.ALTO_FILA,
                          _pdf_safe(row["partida"])[:32], border=1)
            self.pdf.cell(col_widths[1], self.ALTO_FILA,
                          _pdf_safe(row["detalle"])[:50], border=1)
            self.pdf.cell(col_widths[2], self.ALTO_FILA,
                          f"{row['cantidad']:g}", border=1, align="C")
            self.pdf.cell(col_widths[3], self.ALTO_FILA,
                          _pdf_safe(row["unidad"]), border=1, align="C")
            self.pdf.cell(col_widths[4], self.ALTO_FILA,
                          f"{row['precio_unitario']:,.0f}",
                          border=1, align="R")
            self.pdf.cell(col_widths[5], self.ALTO_FILA,
                          f"{row['subtotal']:,.0f}", border=1, align="R")
            self.pdf.cell(col_widths[6], self.ALTO_FILA, clave,
                          border=1, align="L")
            self.pdf.ln()

    def _tabla_partidas_legado(self, df: pd.DataFrame) -> None:
        """Esquema de utils/calculador.py (Material/Cantidad/P_Unitario)."""
        tiene_precio = "P_Unitario" in df.columns
        col_widths = [48, 70, 16, 12, 20, 24] if tiene_precio else [52, 80, 20, 14, 24]
        headers = (["Partida", "Detalle", "Cant.", "Unid.", "P. Unitario", "Subtotal"]
                   if tiene_precio else ["Partida", "Detalle", "Cant.", "Unid.", "Subtotal"])

        def encabezado_tabla():
            self.pdf.set_font("Helvetica", "B", 9)
            self.pdf.set_fill_color(240, 240, 240)
            for i, h in enumerate(headers):
                self.pdf.cell(col_widths[i], 10, h, border=1, fill=True, align="C")
            self.pdf.ln()
            self.pdf.set_font("Helvetica", "", 8.5)

        encabezado_tabla()
        for _, row in df.iterrows():
            if self.pdf.get_y() > self.pdf.page_break_trigger - self.PIE_PAGINA:
                self.pdf.add_page()
                encabezado_tabla()
            fila = 0
            self.pdf.cell(col_widths[fila], self.ALTO_FILA,
                          _pdf_safe(row["Material"])[:46], border=1)
            fila += 1
            self.pdf.cell(col_widths[fila], self.ALTO_FILA,
                          _pdf_safe(row["Detalle"])[:66], border=1)
            fila += 1
            self.pdf.cell(col_widths[fila], self.ALTO_FILA,
                          f"{float(row['Cantidad']):g}", border=1, align="C")
            fila += 1
            self.pdf.cell(col_widths[fila], self.ALTO_FILA,
                          _pdf_safe(row["Unidad"]), border=1, align="C")
            fila += 1
            if tiene_precio:
                self.pdf.cell(col_widths[fila], self.ALTO_FILA,
                              f"{float(row['P_Unitario']):,.0f}", border=1, align="R")
                fila += 1
            self.pdf.cell(col_widths[fila], self.ALTO_FILA,
                          f"{float(row['Subtotal']):,.0f}", border=1, align="R")
            self.pdf.ln()

    def _resumen_por_categoria(self, df: pd.DataFrame) -> None:
        """Subtotales por categoría, compatible con ambos esquemas."""
        if "Categoria" in df.columns:
            grupo, sub = "Categoria", "Subtotal"
            fila_cat = "Categoria"
        elif "categoria" in df.columns:
            grupo, sub = "categoria", "subtotal"
            fila_cat = "categoria"
        elif "Subtotal" in df.columns:
            self.pdf.set_font("Helvetica", "B", 10)
            self.pdf.set_font("Helvetica", "", 9)
            self.pdf.cell(95, 7, "Total del presupuesto", border=1)
            self.pdf.cell(95, 7, f"RD$ {float(df['Subtotal'].sum()):,.2f}",
                          border=1, align="R",
                          new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.pdf.ln(6)
            return
        else:
            return
        resumen = df.groupby(grupo, as_index=False)[sub].sum()

        self.pdf.set_font("Helvetica", "B", 10)
        self.pdf.cell(95, 8, "Categoria", border=1, fill=True, align="C")
        self.pdf.cell(95, 8, "Subtotal", border=1, fill=True, align="C",
                      new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.pdf.set_font("Helvetica", "", 9)
        for _, row in resumen.iterrows():
            if self.pdf.get_y() > self.pdf.page_break_trigger - self.PIE_PAGINA:
                self.pdf.add_page()
            self.pdf.cell(95, 7, _pdf_safe(row[fila_cat])[:45], border=1)
            self.pdf.cell(95, 7, f"RD$ {float(row[sub]):,.2f}", border=1,
                          align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.pdf.ln(6)

    # ------------------------------------------------------------------
    # Propuesta completa
    # ------------------------------------------------------------------
    def generar_propuesta(self, cliente: str, datos_proyecto: dict,
                         presupuesto_df: pd.DataFrame, total: float) -> bytes:
        es_qto = "Material" not in presupuesto_df.columns
        self.pdf.add_page()

        # Encabezado
        self.pdf.set_fill_color(30, 60, 114)
        self.pdf.rect(0, 0, 210, 40, "F")

        self.pdf.set_font("Helvetica", "B", 20)
        self.pdf.set_text_color(255, 255, 255)
        self.pdf.cell(190, 15, "IsoSmart Titanium", new_x=XPos.LMARGIN,
                      new_y=YPos.NEXT, align="C")

        self.pdf.set_font("Helvetica", "", 12)
        self.pdf.cell(190, 10, "Propuesta Técnica Comercial EPS / ICF",
                      new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")

        self.pdf.ln(20)

        # Información del cliente
        self.pdf.set_font("Helvetica", "B", 12)
        self.pdf.set_text_color(0, 0, 0)
        self.pdf.cell(95, 10, "INFORMACION DEL CLIENTE",
                      new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.pdf.cell(95, 10, "DETALLES DEL PROYECTO",
                      new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.pdf.set_font("Helvetica", "", 10)
        self.pdf.cell(95, 8, _pdf_safe(f"Cliente: {cliente}"),
                      new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.pdf.cell(95, 8, f"Fecha: {date.today().strftime('%d/%m/%Y')}",
                      new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.pdf.cell(95, 8, f"Area: {datos_proyecto.get('area', 0):.2f} m2",
                      new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.pdf.cell(95, 8, _pdf_safe(f"Sistema: {datos_proyecto.get('sistema', 'N/A')}"),
                      new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        if datos_proyecto.get("calidad"):
            self.pdf.cell(95, 8, _pdf_safe(f"Calidad: {datos_proyecto['calidad']}"),
                          new_x=XPos.RIGHT, new_y=YPos.TOP)
            self.pdf.cell(95, 8,
                          _pdf_safe(f"Zona: {datos_proyecto.get('zona_riesgo', 'N/A')}"),
                          new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.pdf.ln(10)

        # Resumen ejecutivo
        self.pdf.set_font("Helvetica", "B", 12)
        self.pdf.cell(190, 8, "RESUMEN EJECUTIVO",
                      new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.pdf.set_font("Helvetica", "", 10)
        area = float(datos_proyecto.get("area", 0) or 0)
        costo_m2 = total / area if area else 0
        self.pdf.multi_cell(
            190,
            5,
            _pdf_safe(
                f"Presupuesto conceptual para vivienda con sistema {datos_proyecto.get('sistema', 'EPS/ICF')}. "
                f"Total estimado: RD$ {total:,.2f}. Costo unitario: RD$ {costo_m2:,.2f}/m2. "
                "El documento separa obra gris y terminada, e identifica partidas con precios de referencia."
            ),
        )
        self.pdf.ln(4)

        self._resumen_por_categoria(presupuesto_df)

        # Tabla de presupuesto (completa, con paginación)
        self.pdf.set_font("Helvetica", "B", 10)
        self.pdf.set_fill_color(240, 240, 240)
        self.pdf.cell(190, 8, "DETALLE DE PARTIDAS",
                      new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")
        self.pdf.ln(2)

        if es_qto:
            self._tabla_partidas_qto(presupuesto_df)
        else:
            self._tabla_partidas_legado(presupuesto_df)

        # Total
        self.pdf.ln(5)
        self.pdf.set_font("Helvetica", "B", 12)
        self.pdf.set_fill_color(200, 220, 255)
        self.pdf.cell(100, 10, "", border=0)
        self.pdf.cell(45, 10, "TOTAL:", border=1, fill=True, align="R")
        self.pdf.cell(45, 10, f"RD$ {total:,.2f}", border=1, fill=True,
                      align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Notas
        self.pdf.ln(10)
        self.pdf.set_font("Helvetica", "B", 10)
        self.pdf.set_text_color(0, 0, 0)
        self.pdf.cell(190, 7, "SUPUESTOS Y EXCLUSIONES",
                      new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.pdf.set_font("Helvetica", "I", 8)
        self.pdf.set_text_color(100, 100, 100)
        nota_verificar = (
            "  (*) Clave de precio marcada con asterisco: precio de REFERENCIA, no cotizacion firme de proveedor."
            if es_qto and presupuesto_df.get("precio_por_verificar", pd.Series(dtype=bool)).any()
            else ""
        )
        self.pdf.multi_cell(
            190,
            5,
            _pdf_safe(
                "Nota: Esta propuesta es conceptual y depende de la geometria, precios y supuestos "
                "cargados en la app. Incluye mano de obra estimada cuando aparece en las partidas del "
                "motor QTO. No sustituye planos constructivos, calculo estructural, permisos, cubicacion "
                "profesional ni cotizacion real de proveedor. Las partidas marcadas como referencia deben "
                "validarse antes de emitir una oferta final." + nota_verificar
            ),
        )

        # fpdf2 >= 2.7 devuelve bytearray desde output(); el .encode('latin-1')
        # anterior lanzaba AttributeError y rompía TODA la generación de PDF.
        return bytes(self.pdf.output())