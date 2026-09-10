import sys

import pandas as pd

sys.path.insert(0, ".")

from utils.pdf_propuesta import PDFGenerator  # noqa: E402


def test_pdf_comercial_genera_bytes_validos():
    df = pd.DataFrame([
        {
            "Categoria": "Muros",
            "Material": "Panel estructural",
            "Detalle": "Panel EPS con malla",
            "Cantidad": 10,
            "Unidad": "m2",
            "P_Unitario": 1000,
            "Subtotal": 10000,
        }
    ])

    pdf = PDFGenerator().generar_propuesta(
        "Cliente Prueba",
        {"area": 10, "sistema": "Paneles Isotex", "calidad": "media", "zona_riesgo": "moderado"},
        df,
        10000,
    )

    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000

