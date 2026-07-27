# -*- coding: utf-8 -*-
"""
utils/floor_plan.py
--------------------
Esquema de planta a partir del programa de ambientes.

POR QUÉ EXISTE
==============
El asistente Texto → Diseño (utils/ai_text_design.py) ya generaba un render
de fachada con Fal.ai y un video con Luma -- pero eso es una fachada, no una
planta. Cuando un lead escribe "3 dormitorios, 2 con baño, marquesina doble,
cocina, terraza/lavadero", lo que quiere ver es cómo se distribuye eso, no
cómo se ve la casa por fuera.

Se descartó a propósito pedirle a un modelo de generación de imágenes que
"dibuje una planta arquitectónica": los modelos de difusión son notoriamente
malos para esto -- proporciones incoherentes, paredes que no cierran, texto
ilegible dentro de la imagen. Parecería un plano sin serlo.

En su lugar, este módulo genera un DIAGRAMA DE BLOQUES: rectángulos
proporcionales al área de cada ambiente, etiquetados, acomodados con un
algoritmo simple (empaquetado en filas, tipo treemap). No es una planta
arquitectónica real -- no resuelve circulación, orientación ni estructura --
y se etiqueta como lo que es: un esquema de distribución, útil para que un
lead visualice el programa antes de hablar con un arquitecto real.

USO
===
    from utils.floor_plan import generar_esquema_svg

    svg = generar_esquema_svg(params["habitaciones"], area_total_m2=165)
    st.markdown(svg, unsafe_allow_html=True)
"""

from __future__ import annotations

import html
import math
from typing import Any

# Color por tipo de ambiente -- solo estético, ayuda a distinguir de un
# vistazo dormitorios de áreas sociales sin necesidad de leer cada etiqueta.
_COLOR_POR_TIPO = {
    "dormitorio": "#a8d5e2",
    "bano": "#c9b8db",
    "cocina": "#f6d186",
    "sala": "#b8e0b8",
    "comedor": "#f4b8b8",
    "terraza_lavadero": "#d9d9d9",
    "marquesina": "#bfbfbf",
    "otro": "#e0e0e0",
}

_ETIQUETA_TIPO = {
    "dormitorio": "🛏️", "bano": "🚿", "cocina": "🍳", "sala": "🛋️",
    "comedor": "🍽️", "terraza_lavadero": "🧺", "marquesina": "🚗", "otro": "◻️",
}


def _empaquetar_filas(habitaciones: list[dict[str, Any]], ancho_total: float,
                      area_visual_minima: float) -> list[list[dict]]:
    """
    Agrupa ambientes en filas para el diagrama, intentando que cada fila no
    exceda demasiado el ancho disponible (empaquetado simple, no óptimo --
    es un esquema, no un algoritmo de space planning real).
    """
    filas: list[list[dict]] = []
    fila_actual: list[dict] = []
    ancho_fila = 0.0
    area_total = sum(max(h["area_aprox_m2"], area_visual_minima) for h in habitaciones)
    ancho_objetivo = math.sqrt(area_total * (ancho_total / 10.0)) or ancho_total

    for h in habitaciones:
        lado = math.sqrt(max(h["area_aprox_m2"], area_visual_minima))
        if fila_actual and ancho_fila + lado > ancho_objetivo:
            filas.append(fila_actual)
            fila_actual = []
            ancho_fila = 0.0
        fila_actual.append(h)
        ancho_fila += lado

    if fila_actual:
        filas.append(fila_actual)
    return filas


def generar_esquema_svg(
    habitaciones: list[dict[str, Any]],
    area_total_m2: float | None = None,
    ancho_px: int = 720,
    escala_px_por_m: float = 18.0,
) -> str:
    """
    Genera un SVG con el diagrama de bloques del programa de ambientes.

    Devuelve una cadena SVG completa (con el aviso de que es un esquema, no
    un plano arquitectónico final) lista para `st.markdown(..., unsafe_allow_html=True)`.
    """
    if not habitaciones:
        return (
            '<div style="padding:2rem;text-align:center;color:#888;'
            'border:1px dashed #ccc;border-radius:8px;">'
            "Sin programa de ambientes para dibujar todavía.</div>"
        )

    margen = 12
    # Piso visual: un baño de 4-5 m² da una caja de ~36-40px a esta escala,
    # demasiado chica para el texto de dos líneas (nombre + área). Se usa un
    # área mínima solo para el TAMAÑO del rectángulo; la etiqueta sigue
    # mostrando el área real declarada, no la inflada.
    area_visual_minima = 9.0
    ancho_disponible_m = (ancho_px - 2 * margen) / escala_px_por_m
    filas = _empaquetar_filas(habitaciones, ancho_disponible_m, area_visual_minima)

    elementos: list[str] = []
    y_actual = margen
    alto_total = margen

    for fila in filas:
        alto_fila_m = max(math.sqrt(max(h["area_aprox_m2"], area_visual_minima)) for h in fila)
        alto_fila_px = alto_fila_m * escala_px_por_m

        x_actual = margen
        for h in fila:
            area_visual = max(h["area_aprox_m2"], area_visual_minima)
            alto_px_h = alto_fila_px
            ancho_px_h = (area_visual / alto_fila_m) * escala_px_por_m if alto_fila_m else 0.0

            color = _COLOR_POR_TIPO.get(h["tipo"], _COLOR_POR_TIPO["otro"])
            icono = _ETIQUETA_TIPO.get(h["tipo"], _ETIQUETA_TIPO["otro"])
            nombre = html.escape(h["nombre"])
            area_txt = f'{h["area_aprox_m2"]:.0f} m²'
            # Fuente más chica si la caja es angosta, para que el texto no
            # se desborde en ambientes pequeños (baños, closets).
            fuente_nombre = 13 if ancho_px_h >= 90 else 10
            fuente_area = 11 if ancho_px_h >= 90 else 9

            elementos.append(
                f'<rect x="{x_actual:.1f}" y="{y_actual:.1f}" '
                f'width="{ancho_px_h:.1f}" height="{alto_px_h:.1f}" '
                f'fill="{color}" stroke="#555" stroke-width="1.5" rx="4"/>'
            )
            cx, cy = x_actual + ancho_px_h / 2, y_actual + alto_px_h / 2
            elementos.append(
                f'<text x="{cx:.1f}" y="{cy - 6:.1f}" text-anchor="middle" '
                f'font-size="{fuente_nombre}" font-family="sans-serif" fill="#222">{icono} {nombre}</text>'
            )
            elementos.append(
                f'<text x="{cx:.1f}" y="{cy + 12:.1f}" text-anchor="middle" '
                f'font-size="{fuente_area}" font-family="sans-serif" fill="#555">{area_txt}</text>'
            )
            x_actual += ancho_px_h + 6

        y_actual += alto_fila_px + 6
        alto_total = y_actual

    alto_svg = alto_total + margen
    area_dibujada = sum(h["area_aprox_m2"] for h in habitaciones)
    nota_area = (
        f"Área de referencia del programa: {area_dibujada:.0f} m² "
        f"(el presupuesto usa {area_total_m2:.0f} m² del motor de cálculo)."
        if area_total_m2 else f"Área de referencia del programa: {area_dibujada:.0f} m²."
    )

    svg = (
        f'<div style="border:1px solid #ddd;border-radius:8px;padding:8px;background:#fafafa;">'
        f'<svg viewBox="0 0 {ancho_px} {alto_svg:.0f}" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:100%;height:auto;">{"".join(elementos)}</svg>'
        f'<p style="font-size:0.8rem;color:#888;margin:6px 2px 0;">'
        f"⚠️ Esquema de distribución generado a partir de tu descripción -- NO es un plano "
        f"arquitectónico final. Las proporciones son aproximadas; un arquitecto define la "
        f"distribución, circulación y orientación reales. {html.escape(nota_area)}</p>"
        f"</div>"
    )
    return svg
