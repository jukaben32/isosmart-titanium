import sys

import pytest

sys.path.insert(0, ".")

from utils.comparativa_inicio import calcular_comparativa_area  # noqa: E402


def test_comparativa_de_inicio_responde_al_area():
    chico = calcular_comparativa_area(100)
    grande = calcular_comparativa_area(200)

    assert chico["area_m2"] == 100
    assert grande["area_m2"] == 200
    assert grande["comparativa"]["eps"]["costo_total"] > chico["comparativa"]["eps"]["costo_total"]
    assert grande["comparativa"]["tradicional"]["costo_total"] > chico["comparativa"]["tradicional"]["costo_total"]
    assert grande["geometria"]["ventanas"] > chico["geometria"]["ventanas"]


def test_comparativa_de_inicio_rechaza_area_invalida():
    with pytest.raises(ValueError, match="area_m2"):
        calcular_comparativa_area(0)
