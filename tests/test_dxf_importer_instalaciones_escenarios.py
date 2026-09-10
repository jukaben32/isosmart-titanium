import sys
from pathlib import Path

sys.path.insert(0, ".")

from utils.dxf_importer import analizar_dxf, analizar_dxf_bytes  # noqa: E402
from utils.escenarios import calcular_escenarios  # noqa: E402
from utils.geometria import Geometria  # noqa: E402
from utils.instalaciones import InstalacionesDetalle  # noqa: E402
from utils.pricebook import DEFAULT_PRICEBOOK  # noqa: E402
from utils.qto import MotorQTO  # noqa: E402


def test_importador_dxf_extrae_geometria_del_plano_generado():
    plano = Path("..") / "plano_casa_moderna_lujo_instalaciones.dxf"
    mediciones = analizar_dxf(plano)

    assert mediciones.area_m2 > 300
    assert mediciones.perimetro_m > 90
    assert mediciones.ventanas >= 8
    assert mediciones.banos == 2
    assert mediciones.instalaciones.luminarias >= 10
    assert mediciones.instalaciones.tomacorrientes >= 8


def test_importador_dxf_falla_si_no_hay_muros():
    dxf_minimo = b"0\nSECTION\n2\nENTITIES\n0\nENDSEC\n0\nEOF\n"

    try:
        analizar_dxf_bytes(dxf_minimo)
    except ValueError as exc:
        assert "A-MUROS" in str(exc)
    else:
        raise AssertionError("Un DXF sin capa A-MUROS no debe producir mediciones falsas")


def test_motor_qto_usa_instalaciones_detalladas_si_existen():
    geo = Geometria(area_m2=120, perimetro_m=44, altura_muro_m=2.8)
    detalle = InstalacionesDetalle(
        tomacorrientes=12,
        interruptores=8,
        luminarias=10,
        puntos_agua=8,
        puntos_sanitarios=6,
        ml_canalizacion_electrica=70,
        ml_tuberia_agua=38,
        ml_tuberia_sanitaria=32,
    )

    df = MotorQTO(geo, DEFAULT_PRICEBOOK, instalaciones=detalle).presupuesto()
    partidas = set(df["partida"])

    assert "Tomacorrientes" in partidas
    assert "Puntos sanitarios" in partidas
    assert "Instalación eléctrica" not in partidas
    assert "Instalación sanitaria y agua potable" not in partidas


def test_escenarios_comparan_lujo_y_mecanizado():
    geo = Geometria(area_m2=120, perimetro_m=44, altura_muro_m=2.8)
    tabla = calcular_escenarios(geo, DEFAULT_PRICEBOOK)

    assert {"economico", "lujo", "lujo_mecanizado"} <= set(tabla["clave"])
    lujo = tabla.loc[tabla["clave"] == "lujo", "total"].iloc[0]
    economico = tabla.loc[tabla["clave"] == "economico", "total"].iloc[0]
    mecanizado = tabla.loc[tabla["clave"] == "lujo_mecanizado", "total"].iloc[0]

    assert lujo > economico
    assert mecanizado < lujo

