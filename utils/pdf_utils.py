from __future__ import annotations

from io import BytesIO
from typing import Optional

from PIL import Image


def pdf_first_page_to_image(pdf_bytes: bytes, dpi: int = 150) -> Optional[Image.Image]:
    """
    Convierte la primera página de un PDF a imagen (PIL).
    Requiere PyMuPDF.
    """
    try:
        import fitz  # PyMuPDF
    except Exception:
        return None

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if doc.page_count < 1:
            return None
        page = doc.load_page(0)
        pix = page.get_pixmap(dpi=dpi, alpha=False)
        img_bytes = pix.tobytes("png")
        return Image.open(BytesIO(img_bytes)).convert("RGB")
    except Exception:
        return None

