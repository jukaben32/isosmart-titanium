"""
utils/pdf_propuesta.py
----------------------
Generación del PDF de propuesta comercial. **Sin dependencia de Streamlit.**

Vivía dentro de ui_core.py, un módulo que importa streamlit, plotly, PIL y el
SDK de Gemini. Eso hacía imposible testear el entregable comercial más
importante de la app sin levantar medio entorno gráfico — y es parte de por qué
nadie notó que `output(dest='S').encode('latin-1')` llevaba tiempo roto.

ui_core.py lo reexporta para no romper los imports existentes.
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

    def __init__(self):
        self.pdf = FPDF()
        self.pdf.set_auto_page_break(auto=True, margin=15)

    def generar_propuesta(self, cliente: str, datos_proyecto: dict,
                         presupuesto_df: pd.DataFrame, total: float) -> bytes:
        self.pdf.add_page()

        # Encabezado
        self.pdf.set_fill_color(30, 60, 114)
        self.pdf.rect(0, 0, 210, 40, 'F')

        self.pdf.set_font('Helvetica', 'B', 20)
        self.pdf.set_text_color(255, 255, 255)
        self.pdf.cell(190, 15, 'IsoSmart Titanium', new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')

        self.pdf.set_font('Helvetica', '', 12)
        self.pdf.cell(190, 10, 'Propuesta Técnica Comercial', new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')

        self.pdf.ln(20)

        # Información del cliente
        self.pdf.set_font('Helvetica', 'B', 12)
        self.pdf.set_text_color(0, 0, 0)
        self.pdf.cell(95, 10, 'INFORMACIÓN DEL CLIENTE', new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.pdf.cell(95, 10, 'DETALLES DEL PROYECTO', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.pdf.set_font('Helvetica', '', 10)
        self.pdf.cell(95, 8, _pdf_safe(f'Cliente: {cliente}'), new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.pdf.cell(95, 8, f'Fecha: {date.today().strftime("%d/%m/%Y")}', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.pdf.cell(95, 8, f'Área: {datos_proyecto.get("area", 0):.2f} m²', new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.pdf.cell(95, 8, _pdf_safe(f'Sistema: {datos_proyecto.get("sistema", "N/A")}'), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.pdf.ln(10)

        # Tabla de presupuesto
        self.pdf.set_font('Helvetica', 'B', 10)
        self.pdf.set_fill_color(240, 240, 240)

        col_widths = [50, 70, 25, 45]
        headers = ['Material', 'Descripción', 'Cant.', 'Subtotal']

        for i, header in enumerate(headers):
            self.pdf.cell(col_widths[i], 10, header, border=1, fill=True, align='C')
        self.pdf.ln()

        self.pdf.set_font('Helvetica', '', 9)

        for _, row in presupuesto_df.iterrows():
            self.pdf.cell(col_widths[0], 8, _pdf_safe(row['Material'])[:30], border=1)
            self.pdf.cell(col_widths[1], 8, _pdf_safe(row['Detalle'])[:45], border=1)
            self.pdf.cell(col_widths[2], 8, f"{row['Cantidad']} {row['Unidad']}", border=1, align='C')
            self.pdf.cell(col_widths[3], 8, f"RD$ {row['Subtotal']:,.2f}", border=1, align='R')
            self.pdf.ln()

        # Total
        self.pdf.ln(5)
        self.pdf.set_font('Helvetica', 'B', 12)
        self.pdf.set_fill_color(200, 220, 255)
        self.pdf.cell(145, 10, '', border=0)
        self.pdf.cell(45, 10, 'TOTAL:', border=1, fill=True, align='R')
        self.pdf.cell(20, 10, f"RD$ {total:,.2f}", border=1, fill=True, align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Notas
        self.pdf.ln(10)
        self.pdf.set_font('Helvetica', 'I', 8)
        self.pdf.set_text_color(100, 100, 100)
        self.pdf.multi_cell(190, 5,
            'Nota: Esta cotización es estimada y puede variar según especificaciones finales. '
            'Precios válidos por 15 días. No incluye mano de obra ni transporte.')

        # fpdf2 >= 2.7 devuelve bytearray desde output(); el .encode('latin-1')
        # anterior lanzaba AttributeError y rompía TODA la generación de PDF.
        return bytes(self.pdf.output())


