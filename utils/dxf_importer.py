"""Importador DXF ligero para alimentar la geometría del presupuesto."""

from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .instalaciones import InstalacionesDetalle


@dataclass(frozen=True)
class LineaDXF:
    layer: str
    start: tuple[float, float]
    end: tuple[float, float]

    @property
    def length(self) -> float:
        return math.dist(self.start, self.end)

    @property
    def midpoint(self) -> tuple[float, float]:
        return ((self.start[0] + self.end[0]) / 2, (self.start[1] + self.end[1]) / 2)


@dataclass(frozen=True)
class PolilineaDXF:
    layer: str
    points: tuple[tuple[float, float], ...]
    closed: bool

    @property
    def length(self) -> float:
        pts = list(self.points)
        if self.closed and pts:
            pts.append(pts[0])
        return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        return min(xs), min(ys), max(xs), max(ys)

    @property
    def area(self) -> float:
        if not self.closed or len(self.points) < 3:
            return 0.0
        pts = list(self.points)
        return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]))) / 2

    @property
    def es_rectangulo(self) -> bool:
        if not self.closed or len(self.points) != 4:
            return False
        xs = {round(p[0], 6) for p in self.points}
        ys = {round(p[1], 6) for p in self.points}
        return len(xs) == 2 and len(ys) == 2 and self.area > 0


@dataclass(frozen=True)
class CirculoDXF:
    layer: str
    center: tuple[float, float]
    radius: float


@dataclass(frozen=True)
class ArcoDXF:
    layer: str
    center: tuple[float, float]
    radius: float


@dataclass(frozen=True)
class TextoDXF:
    layer: str
    value: str
    point: tuple[float, float]


@dataclass(frozen=True)
class EntidadesDXF:
    lineas: tuple[LineaDXF, ...] = ()
    polilineas: tuple[PolilineaDXF, ...] = ()
    circulos: tuple[CirculoDXF, ...] = ()
    arcos: tuple[ArcoDXF, ...] = ()
    textos: tuple[TextoDXF, ...] = ()


@dataclass(frozen=True)
class MedicionesDXF:
    area_m2: float
    perimetro_m: float
    ventanas: int = 0
    puertas_interiores: int = 0
    puertas_exteriores: int = 2
    banos: int = 0
    ml_cocina: float | None = None
    esquinas: int = 4
    instalaciones: InstalacionesDetalle = field(default_factory=InstalacionesDetalle)
    advertencias: tuple[str, ...] = ()

    def a_metricas(self) -> dict[str, Any]:
        return {
            "area_m2": self.area_m2,
            "perimetro_m": self.perimetro_m,
            "ventanas": self.ventanas,
            "puertas_interiores": self.puertas_interiores,
            "puertas_exteriores": self.puertas_exteriores,
            "banos": self.banos,
            "ml_cocina": self.ml_cocina,
            "esquinas": self.esquinas,
            "instalaciones_detalle": self.instalaciones.a_dict(),
        }


def analizar_dxf_bytes(data: bytes) -> MedicionesDXF:
    """Lee un DXF ASCII y devuelve métricas útiles para `ProyectoState`."""
    texto = data.decode("utf-8", errors="ignore")
    entidades = parsear_dxf(texto)
    return medir_entidades(entidades)


def analizar_dxf(path: str | Path) -> MedicionesDXF:
    return analizar_dxf_bytes(Path(path).read_bytes())


def parsear_dxf(texto: str) -> EntidadesDXF:
    lines = [l.rstrip("\r") for l in texto.splitlines()]
    pairs = [(lines[i].strip(), lines[i + 1].strip()) for i in range(0, len(lines) - 1, 2)]

    lineas: list[LineaDXF] = []
    polilineas: list[PolilineaDXF] = []
    circulos: list[CirculoDXF] = []
    arcos: list[ArcoDXF] = []
    textos: list[TextoDXF] = []

    i = 0
    while i < len(pairs):
        code, value = pairs[i]
        if code != "0":
            i += 1
            continue

        if value == "LINE":
            data, i = _leer_entidad(pairs, i + 1)
            lineas.append(
                LineaDXF(
                    layer=_str(data, "8"),
                    start=(_float(data, "10"), _float(data, "20")),
                    end=(_float(data, "11"), _float(data, "21")),
                )
            )
            continue

        if value == "CIRCLE":
            data, i = _leer_entidad(pairs, i + 1)
            circulos.append(
                CirculoDXF(_str(data, "8"), (_float(data, "10"), _float(data, "20")), _float(data, "40"))
            )
            continue

        if value == "ARC":
            data, i = _leer_entidad(pairs, i + 1)
            arcos.append(ArcoDXF(_str(data, "8"), (_float(data, "10"), _float(data, "20")), _float(data, "40")))
            continue

        if value == "TEXT":
            data, i = _leer_entidad(pairs, i + 1)
            textos.append(TextoDXF(_str(data, "8"), _str(data, "1"), (_float(data, "10"), _float(data, "20"))))
            continue

        if value == "POLYLINE":
            poly_header, j = _leer_entidad(pairs, i + 1, parar_en_vertex=True)
            pts: list[tuple[float, float]] = []
            layer = _str(poly_header, "8")
            closed = int(_float(poly_header, "70", 0)) & 1 == 1
            while j < len(pairs):
                c, v = pairs[j]
                if c == "0" and v == "VERTEX":
                    data, j = _leer_entidad(pairs, j + 1)
                    pts.append((_float(data, "10"), _float(data, "20")))
                    continue
                if c == "0" and v == "SEQEND":
                    j += 1
                    break
                j += 1
            if pts:
                polilineas.append(PolilineaDXF(layer, tuple(pts), closed))
            i = j
            continue

        if value == "LWPOLYLINE":
            data, i = _leer_entidad(pairs, i + 1)
            xs = data.get("10", [])
            ys = data.get("20", [])
            pts = tuple((float(x), float(y)) for x, y in zip(xs, ys))
            closed = int(_float(data, "70", 0)) & 1 == 1
            if pts:
                polilineas.append(PolilineaDXF(_str(data, "8"), pts, closed))
            continue

        i += 1

    return EntidadesDXF(tuple(lineas), tuple(polilineas), tuple(circulos), tuple(arcos), tuple(textos))


def medir_entidades(entidades: EntidadesDXF) -> MedicionesDXF:
    rectangulos = [p.bounds for p in entidades.polilineas if _layer(p.layer, "A-MUROS") and p.es_rectangulo and p.area >= 1]
    advertencias: list[str] = []
    if not rectangulos:
        raise ValueError("No encontré polilíneas rectangulares en la capa A-MUROS.")

    area, perimetro = _union_rectangulos(rectangulos)
    bounds = _bounds_union(rectangulos)
    esquinas = _contar_esquinas_union(rectangulos)

    lineas_ventana = [l for l in entidades.lineas if _layer(l.layer, "A-VENTANAS") and _en_bounds(l.midpoint, bounds, margen=0.75)]
    ventanas = max(0, round(len(lineas_ventana) / 2))

    arcos_puerta = [a for a in entidades.arcos if _layer(a.layer, "A-PUERTAS") and _en_bounds(a.center, bounds, margen=0.75)]
    puertas_total = len(arcos_puerta)
    puertas_exteriores = max(2, sum(1 for a in arcos_puerta if _cerca_del_borde(a.center, bounds, tol=0.3))) if puertas_total else 2
    puertas_interiores = max(0, puertas_total - puertas_exteriores)

    textos = [_normalizar(t.value) for t in entidades.textos if _en_bounds(t.point, bounds, margen=0.75)]
    banos = len([t for t in textos if "BANO" in t or "BATH" in t])
    if banos == 0:
        advertencias.append("No detecté baños por texto; se usará la estimación por área si no se corrige manualmente.")

    ml_cocina = _estimar_ml_cocina(entidades, bounds)
    instalaciones = _medir_instalaciones(entidades, bounds)

    return MedicionesDXF(
        area_m2=round(area, 2),
        perimetro_m=round(perimetro, 2),
        ventanas=ventanas,
        puertas_interiores=puertas_interiores,
        puertas_exteriores=puertas_exteriores,
        banos=banos,
        ml_cocina=ml_cocina,
        esquinas=max(4, esquinas),
        instalaciones=instalaciones,
        advertencias=tuple(advertencias),
    )


def _leer_entidad(
    pairs: list[tuple[str, str]], start: int, parar_en_vertex: bool = False
) -> tuple[dict[str, list[str]], int]:
    data: dict[str, list[str]] = {}
    i = start
    while i < len(pairs):
        code, value = pairs[i]
        if code == "0" and (not parar_en_vertex or value in {"VERTEX", "SEQEND"}):
            break
        data.setdefault(code, []).append(value)
        i += 1
    return data, i


def _float(data: dict[str, list[str]], code: str, default: float = 0.0) -> float:
    try:
        return float(data.get(code, [default])[0])
    except (TypeError, ValueError):
        return default


def _str(data: dict[str, list[str]], code: str, default: str = "0") -> str:
    return str(data.get(code, [default])[0])


def _layer(actual: str, esperado: str) -> bool:
    return actual.upper() == esperado.upper()


def _normalizar(texto: str) -> str:
    s = unicodedata.normalize("NFKD", texto.upper())
    return "".join(c for c in s if not unicodedata.combining(c))


def _bounds_union(rects: list[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    return min(r[0] for r in rects), min(r[1] for r in rects), max(r[2] for r in rects), max(r[3] for r in rects)


def _en_bounds(point: tuple[float, float], bounds: tuple[float, float, float, float], margen: float = 0) -> bool:
    x, y = point
    minx, miny, maxx, maxy = bounds
    return minx - margen <= x <= maxx + margen and miny - margen <= y <= maxy + margen


def _cerca_del_borde(point: tuple[float, float], bounds: tuple[float, float, float, float], tol: float) -> bool:
    x, y = point
    minx, miny, maxx, maxy = bounds
    return min(abs(x - minx), abs(x - maxx), abs(y - miny), abs(y - maxy)) <= tol


def _union_rectangulos(rects: list[tuple[float, float, float, float]]) -> tuple[float, float]:
    xs = sorted({x for r in rects for x in (r[0], r[2])})
    ys = sorted({y for r in rects for y in (r[1], r[3])})
    cells: set[tuple[int, int]] = set()
    area = 0.0
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            xmid = (xs[i] + xs[i + 1]) / 2
            ymid = (ys[j] + ys[j + 1]) / 2
            if any(x1 <= xmid <= x2 and y1 <= ymid <= y2 for x1, y1, x2, y2 in rects):
                cells.add((i, j))
                area += (xs[i + 1] - xs[i]) * (ys[j + 1] - ys[j])

    perim = 0.0
    for i, j in cells:
        dx = xs[i + 1] - xs[i]
        dy = ys[j + 1] - ys[j]
        if (i - 1, j) not in cells:
            perim += dy
        if (i + 1, j) not in cells:
            perim += dy
        if (i, j - 1) not in cells:
            perim += dx
        if (i, j + 1) not in cells:
            perim += dx
    return area, perim


def _contar_esquinas_union(rects: list[tuple[float, float, float, float]]) -> int:
    xs = sorted({x for r in rects for x in (r[0], r[2])})
    ys = sorted({y for r in rects for y in (r[1], r[3])})
    cells: set[tuple[int, int]] = set()
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            xmid = (xs[i] + xs[i + 1]) / 2
            ymid = (ys[j] + ys[j + 1]) / 2
            if any(x1 <= xmid <= x2 and y1 <= ymid <= y2 for x1, y1, x2, y2 in rects):
                cells.add((i, j))

    esquinas = 0
    for i in range(len(xs)):
        for j in range(len(ys)):
            alrededor = [
                (i - 1, j - 1) in cells,
                (i, j - 1) in cells,
                (i - 1, j) in cells,
                (i, j) in cells,
            ]
            # Una esquina aparece cuando alrededor del vértice hay 1 celda
            # ocupada (esquina convexa) o 3 ocupadas (esquina cóncava).
            if sum(alrededor) in {1, 3}:
                esquinas += 1
    return esquinas


def _longitud_por_layer(entidades: EntidadesDXF, layer: str, bounds: tuple[float, float, float, float]) -> float:
    total = sum(l.length for l in entidades.lineas if _layer(l.layer, layer) and _en_bounds(l.midpoint, bounds, 1.0))
    total += sum(p.length for p in entidades.polilineas if _layer(p.layer, layer) and _en_bounds(_centro_bounds(p.bounds), bounds, 1.0))
    return round(total, 2)


def _centro_bounds(bounds: tuple[float, float, float, float]) -> tuple[float, float]:
    return ((bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2)


def _contar_circulos(entidades: EntidadesDXF, layer: str, bounds: tuple[float, float, float, float]) -> int:
    return sum(1 for c in entidades.circulos if _layer(c.layer, layer) and _en_bounds(c.center, bounds, 1.0))


def _contar_textos(entidades: EntidadesDXF, layer: str, patron: str, bounds: tuple[float, float, float, float]) -> int:
    return sum(1 for t in entidades.textos if _layer(t.layer, layer) and patron in _normalizar(t.value) and _en_bounds(t.point, bounds, 1.0))


def _estimar_ml_cocina(entidades: EntidadesDXF, bounds: tuple[float, float, float, float]) -> float | None:
    cocina = [t.point for t in entidades.textos if "COCINA" in _normalizar(t.value) or "KITCHEN" in _normalizar(t.value)]
    if not cocina:
        return None
    return 8.0


def _medir_instalaciones(entidades: EntidadesDXF, bounds: tuple[float, float, float, float]) -> InstalacionesDetalle:
    sanitarios = _longitud_por_layer(entidades, "I-SANITARIA", bounds)
    agua = _longitud_por_layer(entidades, "I-HIDRO-FRIA", bounds) + _longitud_por_layer(entidades, "I-HIDRO-CALIENTE", bounds)

    return InstalacionesDetalle(
        tableros=max(1, _contar_textos(entidades, "I-ELECTRICA", "TABLERO", bounds)),
        tomacorrientes=_contar_circulos(entidades, "I-ELECTRICA", bounds),
        interruptores=_contar_textos(entidades, "I-ELECTRICA", "S", bounds),
        luminarias=_contar_circulos(entidades, "I-ILUMINACION", bounds),
        puntos_datos=_contar_circulos(entidades, "I-DATOS", bounds),
        camaras=_contar_textos(entidades, "I-SEGURIDAD", "CAM", bounds),
        ml_canalizacion_electrica=_longitud_por_layer(entidades, "I-ELECTRICA", bounds),
        puntos_agua=max(0, round(agua / 5)),
        puntos_sanitarios=max(0, round(sanitarios / 4)),
        registros_sanitarios=_contar_circulos(entidades, "I-SANITARIA", bounds),
        ml_tuberia_agua=round(agua, 2),
        ml_tuberia_sanitaria=sanitarios,
        puntos_gas=max(0, _contar_textos(entidades, "I-GAS", "GLP", bounds)),
        puntos_clima=_contar_textos(entidades, "I-CLIMA", "AC", bounds),
    )
