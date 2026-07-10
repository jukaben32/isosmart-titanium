# -*- coding: utf-8 -*-
"""
Test de regresión: la calculadora única (utils/calculador.py) debe dar los
MISMOS totales que la UI mostraba antes (cuando usaba la clase de app.py).

Esto garantiza que al unificar no cambiamos los precios del cliente.
Valores de referencia tomados del test de comparación del 2026-07-10
(con la clase completa de app.py, que incluía Vigas H y Puertas).

Ejecutar:
    uv run --with pandas python tests/comparar_calculadoras.py
"""

import sys
sys.path.insert(0, ".")

from utils.calculador import BudgetCalculator

PRECIOS = {
    "Panel_Muro": 925.00, "Panel_Techo": 1125.00,
    "H_3000_PSI": 7350.00, "H_3500_PSI": 7950.00,
    "Viga_H_kg": 105.00, "Acero_Varilla": 85.00,
    "Ceramica_m2": 450.00, "Pintura_galon": 1200.00,
    "Puerta_interior": 8500.00,
}

# (m2, sistema, calidad, vigas, total_esperado_RD)
CASOS = [
    (120, "Paneles Isotex", "media",    True,  1493008.76),
    (120, "Paneles Isotex", "lujo",     False, 1290508.76),
    (250, "ICF Proform",    "alta",     True,  2691178.12),
    (80,  "Paneles Isotex", "economica", True,  982505.84),
]


def main():
    fallos = 0
    print("=" * 60)
    print("REGRESIÓN: calculadora única vs precios de la UI anterior")
    print("=" * 60)
    for m2, sistema, calidad, vigas, esperado in CASOS:
        g, t = BudgetCalculator.calcular_presupuesto_completo(m2, sistema, PRECIOS, vigas, calidad)
        total = float(g["Subtotal"].sum() + t["Subtotal"].sum())
        ok = abs(total - esperado) < 1.0
        estado = "OK" if ok else "FAIL"
        if not ok:
            fallos += 1
        print(f"[{estado}] m2={m2} {sistema} {calidad} vigas={vigas} -> "
              f"RD$ {total:,.2f} (esperado {esperado:,.2f})")
    print("=" * 60)
    if fallos == 0:
        print("REGRESIÓN OK: los precios del cliente no cambiaron ✅")
    else:
        print(f"REGRESIÓN FALLÓ: {fallos} caso(s) distinto(s) ❌")
    return fallos


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
