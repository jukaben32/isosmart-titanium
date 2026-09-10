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
        self.pdf.cell(190, 10, 'Propuesta Técnica Comercial EPS / ICF', new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')

        self.pdf.ln(20)

        # Información del cliente
        self.pdf.set_font('Helvetica', 'B', 12)
        self.pdf.set_text_color(0, 0, 0)
        self.pdf.cell(95, 10, 'INFORMACIÓN DEL CLIENTE', new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.pdf.cell(95, 10, 'DETALLES DEL PROYECTO', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.pdf.set_font('Helvetica', '', 10)
        self.pdf.cell(95, 8, _pdf_safe(f'Cliente: {cliente}'), new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.pdf.cell(95, 8, f'Fecha: {date.today().strftime("%d/%m/%Y")}', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.pdf.cell(95, 8, f'Area: {datos_proyecto.get("area", 0):.2f} m2', new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.pdf.cell(95, 8, _pdf_safe(f'Sistema: {datos_proyecto.get("sistema", "N/A")}'), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        if datos_proyecto.get("calidad"):
            self.pdf.cell(95, 8, _pdf_safe(f'Calidad: {datos_proyecto["calidad"]}'), new_x=XPos.RIGHT, new_y=YPos.TOP)
            self.pdf.cell(95, 8, _pdf_safe(f'Zona: {datos_proyecto.get("zona_riesgo", "N/A")}'), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.pdf.ln(10)

        # Resumen ejecutivo
        self.pdf.set_font('Helvetica', 'B', 12)
        self.pdf.cell(190, 8, 'RESUMEN EJECUTIVO', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.pdf.set_font('Helvetica', '', 10)
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

        if "Categoria" in presupuesto_df.columns:
            resumen = presupuesto_df.groupby("Categoria", as_index=False)["Subtotal"].sum()
            self.pdf.set_font('Helvetica', 'B', 10)
            self.pdf.cell(95, 8, 'Categoria', border=1, fill=True, align='C')
            self.pdf.cell(95, 8, 'Subtotal', border=1, fill=True, align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.pdf.set_font('Helvetica', '', 9)
            for _, row in resumen.iterrows():
                self.pdf.cell(95, 7, _pdf_safe(row["Categoria"])[:45], border=1)
                self.pdf.cell(95, 7, f"RD$ {float(row['Subtotal']):,.2f}", border=1, align='R',
                              new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.pdf.ln(6)

        # Tabla de presupuesto
        self.pdf.set_font('Helvetica', 'B', 10)
        self.pdf.set_fill_color(240, 240, 240)

        col_widths = [38, 67, 30, 45]
        headers = ['Partida', 'Descripcion', 'Cant.', 'Subtotal']

        for i, header in enumerate(headers):
            self.pdf.cell(col_widths[i], 10, header, border=1, fill=True, align='C')
        self.pdf.ln()

        self.pdf.set_font('Helvetica', '', 9)

        for _, row in presupuesto_df.head(32).iterrows():
            self.pdf.cell(col_widths[0], 8, _pdf_safe(row['Material'])[:30], border=1)
            self.pdf.cell(col_widths[1], 8, _pdf_safe(row['Detalle'])[:45], border=1)
            self.pdf.cell(col_widths[2], 8, f"{row['Cantidad']} {row['Unidad']}", border=1, align='C')
            self.pdf.cell(col_widths[3], 8, f"RD$ {row['Subtotal']:,.2f}", border=1, align='R')
            self.pdf.ln()

        if len(presupuesto_df) > 32:
            self.pdf.set_font('Helvetica', 'I', 8)
            self.pdf.cell(190, 6, _pdf_safe(f"Se muestran 32 de {len(presupuesto_df)} partidas. Ver Excel/CSV para detalle completo."),
                          new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Total
        self.pdf.ln(5)
        self.pdf.set_font('Helvetica', 'B', 12)
        self.pdf.set_fill_color(200, 220, 255)
        self.pdf.cell(100, 10, '', border=0)
        self.pdf.cell(45, 10, 'TOTAL:', border=1, fill=True, align='R')
        self.pdf.cell(45, 10, f"RD$ {total:,.2f}", border=1, fill=True, align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Notas
        self.pdf.ln(10)
        self.pdf.set_font('Helvetica', 'B', 10)
        self.pdf.set_text_color(0, 0, 0)
        self.pdf.cell(190, 7, 'SUPUESTOS Y EXCLUSIONES', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.pdf.set_font('Helvetica', 'I', 8)
        self.pdf.set_text_color(100, 100, 100)
        self.pdf.multi_cell(190, 5,
            _pdf_safe(
                'Nota: Esta propuesta es conceptual y depende de la geometría, precios y supuestos cargados en la app. '
                'Incluye mano de obra estimada cuando aparece en las partidas del motor QTO. '
                'No sustituye planos constructivos, cálculo estructural, permisos, cubicación profesional ni cotización real de proveedor. '
                'Las partidas marcadas como referencia deben validarse antes de emitir una oferta final.'
            ))

        # fpdf2 >= 2.7 devuelve bytearray desde output(); el .encode('latin-1')
        # anterior lanzaba AttributeError y rompía TODA la generación de PDF.
        return bytes(self.pdf.output())


