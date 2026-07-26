from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def points_from_object(obj: dict[str, Any]) -> list[tuple[float, float]] | None:
    """
    Extrae puntos absolutos (px) de objetos fabric.js comunes:
    - polygon: puntos relativos + (left,top)
    - polyline: puntos relativos + (left,top)
    - path: lista de comandos, tomamos coordenadas de tipo 'L'/'M' cuando existan
    """
    if not isinstance(obj, dict):
        return None
    t = obj.get("type")
    left = float(obj.get("left", 0.0))
    top = float(obj.get("top", 0.0))

    if t in ("polygon", "polyline"):
        pts = obj.get("points")
        if not isinstance(pts, list) or len(pts) < 2:
            return None
        out: list[tuple[float, float]] = []
        for p in pts:
            if not isinstance(p, dict):
                continue
            x = p.get("x")
            y = p.get("y")
            if x is None or y is None:
                continue
            out.append((left + float(x), top + float(y)))
        return out if len(out) >= 2 else None

    if t == "path":
        path = obj.get("path")
        if not isinstance(path, list):
            return None
        out2: list[tuple[float, float]] = []
        for cmd in path:
            if not isinstance(cmd, list) or len(cmd) < 3:
                continue
            if cmd[0] in ("M", "L"):
                try:
                    out2.append((left + float(cmd[1]), top + float(cmd[2])))
                except Exception:
                    continue
        return out2 if len(out2) >= 2 else None

    return None


def extract_line_segments(objects: list[dict[str, Any]]) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """
    Devuelve segmentos (a,b) en px para:
    - type='line' (x1,y1,x2,y2)
    - polyline/path (segmentos consecutivos)
    """
    segs: list[tuple[tuple[float, float], tuple[float, float]]] = []
    if not objects:
        return segs

    for obj in objects:
        if not isinstance(obj, dict):
            continue
        if obj.get("type") == "line":
            x1, y1, x2, y2 = obj.get("x1"), obj.get("y1"), obj.get("x2"), obj.get("y2")
            if None in (x1, y1, x2, y2):
                continue
            a = (float(x1), float(y1))
            b = (float(x2), float(y2))
            segs.append((a, b))
            continue

        pts = points_from_object(obj)
        if pts and len(pts) >= 2:
            for i in range(len(pts) - 1):
                segs.append((pts[i], pts[i + 1]))

    return segs


def extract_points(objects: list[dict[str, Any]]) -> list[tuple[float, float]]:
    """
    Extrae puntos (centros) desde objetos 'circle' fabric.js para marcar fixtures (tomas, sanitarios, etc.).
    """
    out: list[tuple[float, float]] = []
    if not objects:
        return out
    for obj in objects:
        if not isinstance(obj, dict):
            continue
        if obj.get("type") != "circle":
            continue
        left = float(obj.get("left", 0.0))
        top = float(obj.get("top", 0.0))
        r = float(obj.get("radius", 0.0))
        out.append((left + r, top + r))
    return out


def scale_from_canvas_line(objects: list[dict[str, Any]], real_length_m: float) -> float | None:
    """
    Devuelve metros por pixel (m/px) usando la PRIMERA línea dibujada.
    Compatible con objetos tipo "line" del drawable canvas.
    """
    if not objects or real_length_m <= 0:
        return None
    for obj in objects:
        if obj.get("type") != "line":
            continue
        x1, y1, x2, y2 = obj.get("x1"), obj.get("y1"), obj.get("x2"), obj.get("y2")
        if None in (x1, y1, x2, y2):
            continue
        px_len = _dist((float(x1), float(y1)), (float(x2), float(y2)))
        if px_len <= 0:
            continue
        return float(real_length_m) / px_len
    return None


def polygon_from_canvas(objects: list[dict[str, Any]]) -> list[tuple[float, float]] | None:
    """
    Extrae el PRIMER polígono (type='polygon') y devuelve puntos absolutos en pixeles.
    drawable-canvas guarda puntos relativos a (left, top).
    """
    if not objects:
        return None
    for obj in objects:
        if obj.get("type") != "polygon":
            continue
        pts = obj.get("points")
        if not isinstance(pts, list) or len(pts) < 3:
            continue
        left = float(obj.get("left", 0.0))
        top = float(obj.get("top", 0.0))
        out: list[tuple[float, float]] = []
        for p in pts:
            if not isinstance(p, dict):
                continue
            x = p.get("x")
            y = p.get("y")
            if x is None or y is None:
                continue
            out.append((left + float(x), top + float(y)))
        if len(out) >= 3:
            return out
    return None


def polygon_area_perimeter(points: list[tuple[float, float]]) -> tuple[float, float]:
    """
    Shoelace para área (px^2) y perímetro (px).
    """
    if len(points) < 3:
        return 0.0, 0.0
    area2 = 0.0
    per = 0.0
    for i in range(len(points)):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % len(points)]
        area2 += x1 * y2 - x2 * y1
        per += _dist((x1, y1), (x2, y2))
    return abs(area2) / 2.0, per

