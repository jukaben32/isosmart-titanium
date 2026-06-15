# -*- coding: utf-8 -*-
"""
utils/calculador.py
-------------------
Motor de Presupuesto Adaptativo para IsoSmart Titanium.

Módulo core corregido con los coeficientes reales de merma y desacoplado
de variables estáticas. Recibe el mapeo de precios inyectado en vivo
desde la base de datos atómica (pricebook.json), sin dependencias de
st.session_state para facilitar pruebas unitarias y reutilización.

Uso:
    from utils.calculador import BudgetCalculator
    gris, term = BudgetCalculator.calcular_presupuesto_completo(
        m2=120, sistema="Paneles Isotex", precios=precios_dict
    )
"""

import pandas as pd


# ============================================================================
# MOTOR DE PRESUPUESTO ATÓMICO (CON BUGFIX DE MERMAS)
# ============================================================================

class BudgetCalculator:
    """
    Calculador de presupuesto desacoplado de Streamlit.
    Recibe el diccionario de precios como parámetro en cada llamada,
    lo que permite usarlo en tests, scripts o flujos sin sesión activa.
    """

    FACTORES_RENDIMIENTO = {
        "desperdicio_panel":   0.05,   # 5% de merma en paneles
        "desperdicio_hormigon": 0.08,  # BUGFIX CORREGIDO: Antes diluido o ignorado
    }

    @classmethod
    def calcular_presupuesto_completo(
        cls,
        m2: float,
        sistema: str,
        precios: dict,
        incluir_vigas: bool = True,
        calidad_terminados: str = "media",
        espesor_muro_m: float = 0.12,
    ) -> tuple:
        """
        Genera las dos tablas de presupuesto: obra gris y obra terminada.

        Args:
            m2: Área construida en m².
            sistema: 'Paneles Isotex' | 'ICF Proform'.
            precios: Diccionario de precios unitarios (inyectado desde pricebook).
            incluir_vigas: Si se incluyen vigas H estructurales.
            calidad_terminados: 'economica' | 'media' | 'alta' | 'lujo'.
            espesor_muro_m: Espesor de muro en metros (default 0.12).

        Returns:
            Tuple (DataFrame obra_gris, DataFrame obra_terminada).
        """
        area_muros = m2 * 2.2
        area_techo = m2 * 1.10
        d_panel = cls.FACTORES_RENDIMIENTO["desperdicio_panel"]
        d_hormigon = cls.FACTORES_RENDIMIENTO["desperdicio_hormigon"]

        data_gris = []

        # ── Estructura ──────────────────────────────────────────────────────
        if sistema == "Paneles Isotex":
            # Muros
            muros_cant = area_muros * (1 + d_panel)
            data_gris.append({
                "Categoria": "Estructura",
                "Material":  "Paneles Isotex (Muros)",
                "Unidad":    "m²",
                "Cantidad":  round(muros_cant, 2),
                "P_Unitario": precios.get("Panel_Muro", 925.0),
                "Subtotal":  muros_cant * precios.get("Panel_Muro", 925.0),
            })

            # Techo
            techo_cant = area_techo * (1 + d_panel)
            data_gris.append({
                "Categoria": "Estructura",
                "Material":  "Paneles Isotex (Techo)",
                "Unidad":    "m²",
                "Cantidad":  round(techo_cant, 2),
                "P_Unitario": precios.get("Panel_Techo", 1125.0),
                "Subtotal":  techo_cant * precios.get("Panel_Techo", 1125.0),
            })

            # Hormigón estructural — inyección limpia del desperdicio (0.08)
            vol_hormigon = (area_muros + area_techo) * espesor_muro_m
            vol_hormigon *= (1 + d_hormigon)
            data_gris.append({
                "Categoria": "Hormigón",
                "Material":  "Hormigón Cemex 3000 PSI",
                "Unidad":    "m³",
                "Cantidad":  round(vol_hormigon, 2),
                "P_Unitario": precios.get("H_3000_PSI", 7350.0),
                "Subtotal":  vol_hormigon * precios.get("H_3000_PSI", 7350.0),
            })

        else:
            # ── Lógica alternativa para encofrados modulares ICF ───────────
            icf_cant = area_muros * 0.85
            data_gris.append({
                "Categoria": "Estructura",
                "Material":  "Bloques ICF Proform",
                "Unidad":    "m²",
                "Cantidad":  round(icf_cant, 2),
                "P_Unitario": precios.get("Panel_Muro", 925.0) * 1.15,
                "Subtotal":  icf_cant * (precios.get("Panel_Muro", 925.0) * 1.15),
            })

            vol_icf = area_muros * 0.15
            data_gris.append({
                "Categoria": "Hormigón",
                "Material":  "Hormigón Cemex 3500 PSI",
                "Unidad":    "m³",
                "Cantidad":  round(vol_icf, 2),
                "P_Unitario": precios.get("H_3500_PSI", 7950.0),
                "Subtotal":  vol_icf * precios.get("H_3500_PSI", 7950.0),
            })

        # ── Cimentaciones ───────────────────────────────────────────────────
        vol_cim = m2 * 0.15
        data_gris.append({
            "Categoria": "Cimentación",
            "Material":  "Cimentación Armada",
            "Unidad":    "m³",
            "Cantidad":  round(vol_cim, 2),
            "P_Unitario": precios.get("H_3000_PSI", 7350.0) * 1.2,
            "Subtotal":  vol_cim * (precios.get("H_3000_PSI", 7350.0) * 1.2),
        })

        # ── Acero de refuerzo ───────────────────────────────────────────────
        kg_acero = m2 * 8.5
        data_gris.append({
            "Categoria": "Acero",
            "Material":  "Acero de Refuerzo (Varillas)",
            "Unidad":    "kg",
            "Cantidad":  round(kg_acero, 2),
            "P_Unitario": precios.get("Acero_Varilla", 85.0),
            "Subtotal":  kg_acero * precios.get("Acero_Varilla", 85.0),
        })

        # ── Módulo de acabados ──────────────────────────────────────────────
        factores_calidad = {"economica": 0.8, "media": 1.0, "alta": 1.5, "lujo": 2.5}
        f_c = factores_calidad.get(calidad_terminados, 1.0)

        data_term = [
            {
                "Categoria":  "Pisos",
                "Material":   "Cerámica/Porcelanato Base",
                "Unidad":     "m²",
                "Cantidad":   round(m2 * 0.9, 2),
                "P_Unitario": precios.get("Ceramica_m2", 450.0) * f_c,
                "Subtotal":   (m2 * 0.9) * precios.get("Ceramica_m2", 450.0) * f_c,
            },
            {
                "Categoria":  "Pintura",
                "Material":   "Pintura Vinílica Premium",
                "Unidad":     "gal",
                "Cantidad":   round(area_muros / 12, 1),
                "P_Unitario": precios.get("Pintura_galon", 1200.0) * f_c,
                "Subtotal":   (area_muros / 12) * precios.get("Pintura_galon", 1200.0) * f_c,
            },
        ]

        return pd.DataFrame(data_gris), pd.DataFrame(data_term)
