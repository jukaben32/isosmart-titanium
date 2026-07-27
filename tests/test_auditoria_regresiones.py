"""
Regresiones de la auditoría (2026-07-26).

Cada test de este archivo corresponde a un bug real encontrado y corregido.
Si alguno vuelve a fallar, el bug volvió.

    pytest tests/test_auditoria_regresiones.py
"""

import sys

import pytest

sys.path.insert(0, ".")

from utils.calculador import BudgetCalculator  # noqa: E402
from utils.dominio import (  # noqa: E402
    Calidad,
    Sistema,
    normalizar_calidad,
    normalizar_sistema,
)
from utils.financiera import AnalisisFinanciero  # noqa: E402
from utils.pricebook import DEFAULT_PRICEBOOK, Pricebook  # noqa: E402
from utils.tarifa import calcular_costo_energia_rd  # noqa: E402

# ---------------------------------------------------------------------------
# 1. La tilde de "económica" ya no se traga el descuento
# ---------------------------------------------------------------------------

def test_calidad_con_tilde_equivale_a_sin_tilde():
    """
    Bug: pages/1_Dashboard_Financiero.py ofrecía "económica" y calculador.py
    buscaba "economica". `.get(calidad, 1.0)` devolvía el factor de "media",
    así que elegir económica cotizaba igual que media, sin ningún aviso.
    """
    total = {}
    for etiqueta in ("economica", "económica", "ECONÓMICA", "  Económica  "):
        gris, term = BudgetCalculator.calcular_presupuesto_completo(
            120, "Paneles Isotex", DEFAULT_PRICEBOOK, calidad_terminados=etiqueta
        )
        total[etiqueta] = gris["Subtotal"].sum() + term["Subtotal"].sum()

    assert len(set(round(v, 2) for v in total.values())) == 1

    gris_media, term_media = BudgetCalculator.calcular_presupuesto_completo(
        120, "Paneles Isotex", DEFAULT_PRICEBOOK, calidad_terminados="media"
    )
    total_media = gris_media["Subtotal"].sum() + term_media["Subtotal"].sum()
    assert total["económica"] < total_media, "económica debe costar menos que media"


def test_valores_desconocidos_fallan_ruidosamente():
    """Un valor no reconocido debe reventar, no degradarse en silencio."""
    with pytest.raises(ValueError):
        normalizar_calidad("barata")
    with pytest.raises(ValueError):
        normalizar_sistema("Sistema Marciano")


def test_alias_de_sistema():
    assert normalizar_sistema("Paneles Isotex") is Sistema.ISOTEX
    assert normalizar_sistema("EPS") is Sistema.ISOTEX
    assert normalizar_sistema("ICF Proform") is Sistema.ICF
    assert normalizar_calidad("Lujo") is Calidad.LUJO


# ---------------------------------------------------------------------------
# 2. Zona de riesgo: "Alto" ya no hace match dentro de "Muy Alto"
# ---------------------------------------------------------------------------

def test_factores_de_zona_de_riesgo_no_se_solapan():
    acero_muy_alto, horm_muy_alto = BudgetCalculator._factor_riesgo("Muy Alto")
    acero_alto, horm_alto = BudgetCalculator._factor_riesgo("Alto")
    acero_base, horm_base = BudgetCalculator._factor_riesgo("Moderado (Base)")

    assert acero_muy_alto == 1.35
    assert (acero_alto, horm_alto) == (1.20, 1.10)
    assert (acero_base, horm_base) == (1.00, 1.00)


# ---------------------------------------------------------------------------
# 3. Pricebook: fuente única, sin claves duplicadas
# ---------------------------------------------------------------------------

def test_pricebook_sin_clave_duplicada_de_ladrillo():
    """
    Bug: el código traía "Ladrillounidad" y el JSON "Ladrillo_unidad".
    El merge producía 28 claves con dos variantes del mismo material.
    """
    precios = Pricebook("data/pricebook.json").load()
    assert "Ladrillounidad" not in precios
    assert "Ladrillo_unidad" in precios
    # Sin claves duplicadas: cada material aparece una sola vez.
    assert len(precios) == len(set(precios))
    assert len(precios) == len(DEFAULT_PRICEBOOK)


def test_claves_usadas_existen_en_el_pricebook():
    faltantes = BudgetCalculator.claves_precio_usadas() - set(DEFAULT_PRICEBOOK)
    assert not faltantes, f"El motor pide precios inexistentes: {faltantes}"


# ---------------------------------------------------------------------------
# 4. ROI: el signo del año 0
# ---------------------------------------------------------------------------

def test_roi_eps_mas_barato_no_inventa_una_inversion():
    """
    Bug: ambas ramas del if producían un flujo negativo en el año 0. Cuando EPS
    salía más barato, el modelo trataba el ahorro como si fuera un desembolso.
    """
    res = AnalisisFinanciero.calcular_roi(
        area_m2=120, costo_total_isotex=1_200_000,
        costo_tradicional=1_500_000, horizonte_anios=10,
    )
    assert res.flujo_caja[0] > 0, "EPS más barato => el año 0 es un ahorro, no un gasto"
    assert res.payback_anios == 0.0, "sin sobrecosto no hay nada que recuperar"
    assert res.van > 0
    assert res.ahorro_acumulado > 0


def test_roi_eps_mas_caro_si_es_una_inversion_real():
    res = AnalisisFinanciero.calcular_roi(
        area_m2=120, costo_total_isotex=1_800_000,
        costo_tradicional=1_500_000, horizonte_anios=10,
    )
    assert res.flujo_caja[0] < 0
    assert res.van < 0


def test_payback_es_none_cuando_nunca_se_recupera():
    """Antes devolvía `horizonte_anios`, haciendo pasar un fracaso por un éxito."""
    res = AnalisisFinanciero.calcular_roi(
        area_m2=50, costo_total_isotex=10_000_000,
        costo_tradicional=1_000_000, horizonte_anios=5,
    )
    assert res.payback_anios is None


# ---------------------------------------------------------------------------
# 5. Modelo energético unificado y con órdenes de magnitud reales
# ---------------------------------------------------------------------------

def test_consumo_electrico_en_rango_realista():
    """
    Bug: el modelo que alimentaba el ROI usaba 45 kWh/m²/mes -> 5,400 kWh/mes
    y una factura de RD$ 43,779 para una casa de 120 m². Una vivienda
    dominicana de ese tamaño consume 300–800 kWh/mes en total.
    """
    r = AnalisisFinanciero.calcular_ahorro_energia_mensual(120, "isotex")
    assert 30 <= r["consumo_kwh_mes"] <= 600, r
    assert 0 < r["ahorro_rd_mes"] < 10_000, r


def test_ahorro_energetico_crece_con_el_area():
    a = AnalisisFinanciero.calcular_ahorro_energia_mensual(80, "isotex")
    b = AnalisisFinanciero.calcular_ahorro_energia_mensual(200, "isotex")
    assert b["ahorro_rd_mes"] > a["ahorro_rd_mes"]


def test_tarifa_por_bloques_es_monotona_y_marginal():
    assert calcular_costo_energia_rd(0) == 145.0            # solo cargo fijo
    assert calcular_costo_energia_rd(80) == 145 + 80 * 7.20
    assert calcular_costo_energia_rd(150) == 145 + 100 * 7.20 + 50 * 9.80
    anterior = -1.0
    for kwh in range(0, 900, 50):
        actual = calcular_costo_energia_rd(kwh)
        assert actual > anterior
        anterior = actual


# ---------------------------------------------------------------------------
# 6. PDF: el entregable comercial que nunca se generó
# ---------------------------------------------------------------------------

def test_pdf_se_genera_y_es_un_pdf_valido():
    """
    Bug: `self.pdf.output(dest='S').encode('latin-1')` -> en fpdf2 >= 2.7
    output() devuelve bytearray y .encode() lanza AttributeError. Ningún
    cliente recibió jamás un PDF.
    """
    pytest.importorskip("fpdf")
    import pandas as pd

    from utils.pdf_propuesta import PDFGenerator

    df = pd.DataFrame([{
        "Material": "Paneles Isotex (Muros)",
        "Detalle": "Panel estructural EPS",
        "Cantidad": 277.2, "Unidad": "m²", "Subtotal": 256410.0,
    }])

    pdf_bytes = PDFGenerator().generar_propuesta(
        cliente="Cliente de Prueba",
        datos_proyecto={"area": 120.0, "sistema": "Paneles Isotex"},
        presupuesto_df=df,
        total=1_493_008.76,
    )

    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1000


def test_pdf_sobrevive_a_caracteres_no_latin1():
    """Un nombre pegado desde WhatsApp (comillas curvas, emoji) no debe romperlo."""
    pytest.importorskip("fpdf")
    import pandas as pd

    from utils.pdf_propuesta import PDFGenerator

    df = pd.DataFrame([{
        "Material": "Panel — “premium” 🏗️",
        "Detalle": "Acabado especial",
        "Cantidad": 1, "Unidad": "ud", "Subtotal": 1000.0,
    }])

    pdf_bytes = PDFGenerator().generar_propuesta(
        cliente="José Peña — “Constructora” 🏠",
        datos_proyecto={"area": 100.0, "sistema": "ICF Proform"},
        presupuesto_df=df, total=1000.0,
    )
    assert pdf_bytes.startswith(b"%PDF")


# ---------------------------------------------------------------------------
# 7. Persistencia: los leads dejan de vivir en un disco efímero
# ---------------------------------------------------------------------------

def test_repositorio_sqlite_persiste_leads(tmp_path):
    from utils.repositorio import RepositorioSQLite

    ruta = tmp_path / "isosmart.sqlite3"
    repo = RepositorioSQLite(str(ruta))
    repo.guardar({"nombre": "Ana Pérez", "email": "ana@ejemplo.do", "area_estimada": 120})
    repo.guardar({"nombre": "Luis Gómez", "email": "luis@ejemplo.do"})

    # Una instancia nueva (simula el reinicio del contenedor) sigue viéndolos.
    del repo
    leads = RepositorioSQLite(str(ruta)).listar()
    assert len(leads) == 2
    assert {lead["nombre"] for lead in leads} == {"Ana Pérez", "Luis Gómez"}
    assert all(lead["id"] and lead["fecha"] for lead in leads)


def test_repositorio_sqlite_persiste_proyectos(tmp_path):
    from utils.repositorio import RepositorioSQLite

    repo = RepositorioSQLite(str(tmp_path / "p.sqlite3"))
    repo.guardar_proyecto("casa-samana", {"area": 180.0, "sistema": "Paneles Isotex"})
    recuperado = repo.obtener_proyecto("casa-samana")

    assert recuperado["area"] == 180.0
    assert recuperado["sistema"] == "Paneles Isotex"
    assert repo.obtener_proyecto("no-existe") is None

    repo.eliminar_proyecto("casa-samana")
    assert repo.obtener_proyecto("casa-samana") is None


def test_repositorio_por_defecto_es_sqlite_sin_credenciales(monkeypatch, tmp_path):
    """Sin credenciales de Supabase la app debe seguir funcionando en local."""
    from utils import repositorio

    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    monkeypatch.setattr(repositorio, "RUTA_SQLITE_DEFECTO", str(tmp_path / "x.sqlite3"))
    monkeypatch.setattr(repositorio, "_leer_config_supabase", lambda: None)

    assert isinstance(repositorio.obtener_repositorio(), repositorio.RepositorioSQLite)
