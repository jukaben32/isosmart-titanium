# -*- coding: utf-8 -*-
"""
utils/calculador.py
-------------------
Motor de Presupuesto ÚNICO y desacoplado para IsoSmart Titanium.

Esta es la FUENTE DE VERDAD del cálculo de presupuestos (unificado el 2026-07-10).
Sustituye a la clase BudgetCalculator que vivía dentro de app.py.

Diseño:
- No depende de st.session_state (testeable y reutilizable).
- Recibe el diccionario de precios inyectado en vivo desde pricebook.json.
- Incluye el factor de zona de riesgo (sismo / huracán RD) agregado en la
  versión moderna, y los rubros completos que mostraba la UI (Vigas H,
  Puertas, columna "Detalle").

Uso:
    from utils.calculador import BudgetCalculator
    gris, term = BudgetCalculator.calcular_presupuesto_completo(
        m2=120, sistema="Paneles Isotex", precios=precios_dict
    )
"""

import pandas as pd


# ============================================================================
# MOTOR DE PRESUPUESTO ATÓMICO (ÚNICA FUENTE DE VERDAD)
# ============================================================================

class BudgetCalculator:
    """
    Calculador de presupuesto desacoplado de Streamlit.
    Recibe el diccionario de precios como parámetro en cada llamada.
    """

    FACTORES_RENDIMIENTO = {
        "desperdicio_panel": 0.05,      # 5% de merma en paneles
        "desperdicio_hormigon": 0.08,   # 8% de merma en hormigón (bugfix corregido)
    }

    @classmethod
    def _factor_riesgo(cls, zona_riesgo: str):
        """Devuelve (factor_acero, factor_hormigon) según la zona de RD."""
        factor_acero = 1.0
        factor_hormigon = 1.0
        if "Muy Alto" in zona_riesgo:
            factor_acero = 1.35    # +35% acero (ruta de huracanes / punta cana)
        elif "Alto" in zona_riesgo:
            factor_acero = 1.20    # +20% acero (falla septentrional/suroeste)
            factor_hormigon = 1.10  # +10% cimientos
        return factor_acero, factor_hormigon

    @classmethod
    def calcular_obra_grisa(cls, m2, sistema, precios, incluir_vigas=True,
                            zona_riesgo="Moderado (Base)"):
        """Calcula la obra gris (estructura + cimentación + acero)."""
        area_muros = m2 * 2.2
        area_techo = m2 * 1.10
        d_panel = cls.FACTORES_RENDIMIENTO["desperdicio_panel"]
        d_hormigon = cls.FACTORES_RENDIMIENTO["desperdicio_hormigon"]
        factor_acero, factor_hormigon = cls._factor_riesgo(zona_riesgo)

        data = []

        if sistema == "Paneles Isotex":
            # Muros
            total_muros = area_muros * (1 + d_panel)
            data.append({
                "Categoria": "Estructura",
                "Material": "Paneles Isotex (Muros)",
                "Detalle": "Panel estructural EPS con malla electrosoldada",
                "Cantidad": round(total_muros, 2),
                "Unidad": "m²",
                "P_Unitario": precios.get("Panel_Muro", 925.0),
                "Subtotal": total_muros * precios.get("Panel_Muro", 925.0),
            })
            # Techo
            total_techo = area_techo * (1 + d_panel)
            data.append({
                "Categoria": "Estructura",
                "Material": "Paneles Isotex (Techo)",
                "Detalle": "Panel aligerado para losa",
                "Cantidad": round(total_techo, 2),
                "Unidad": "m²",
                "P_Unitario": precios.get("Panel_Techo", 1125.0),
                "Subtotal": total_techo * precios.get("Panel_Techo", 1125.0),
            })
            # Hormigón (con desperdicio de 0.08 aplicado)
            vol_hormigon = (area_muros + area_techo) * 0.12 * (1 + d_hormigon)
            data.append({
                "Categoria": "Hormigón",
                "Material": "Hormigón Cemex 3000 PSI",
                "Detalle": "Concreto premezclado para llenado",
                "Cantidad": round(vol_hormigon, 2),
                "Unidad": "m³",
                "P_Unitario": precios.get("H_3000_PSI", 7350.0),
                "Subtotal": vol_hormigon * precios.get("H_3000_PSI", 7350.0),
            })
        else:  # ICF Proform
            data.append({
                "Categoria": "Estructura",
                "Material": "Bloques ICF Proform",
                "Detalle": "Bloques de poliestireno para encofrado",
                "Cantidad": round(area_muros * 0.85, 2),
                "Unidad": "m²",
                "P_Unitario": precios.get("Panel_Muro", 925.0) * 1.15,
                "Subtotal": area_muros * 0.85 * (precios.get("Panel_Muro", 925.0) * 1.15),
            })
            vol_hormigon = area_muros * 0.15
            data.append({
                "Categoria": "Hormigón",
                "Material": "Hormigón Cemex 3500 PSI",
                "Detalle": "Concreto de alta resistencia para ICF",
                "Cantidad": round(vol_hormigon, 2),
                "Unidad": "m³",
                "P_Unitario": precios.get("H_3500_PSI", 7950.0),
                "Subtotal": vol_hormigon * precios.get("H_3500_PSI", 7950.0),
            })

        # Cimentación (con factor de zona de riesgo)
        vol_cimentacion = m2 * 0.15 * factor_hormigon
        data.append({
            "Categoria": "Cimentación",
            "Material": "Cimentación Armada",
            "Detalle": "Zapatas y vigas de fundación",
            "Cantidad": round(vol_cimentacion, 2),
            "Unidad": "m³",
            "P_Unitario": precios.get("H_3000_PSI", 7350.0) * 1.2,
            "Subtotal": vol_cimentacion * (precios.get("H_3000_PSI", 7350.0) * 1.2),
        })

        # Vigas H estructurales (opcional)
        if incluir_vigas:
            kg_vigas = m2 * 25
            data.append({
                "Categoria": "Acero",
                "Material": "Vigas H Estructurales",
                "Detalle": "Perfil de acero A36 para estructura",
                "Cantidad": round(kg_vigas, 2),
                "Unidad": "kg",
                "P_Unitario": precios.get("Viga_H_kg", 105.0),
                "Subtotal": kg_vigas * precios.get("Viga_H_kg", 105.0),
            })

        # Acero de refuerzo (con factor de zona de riesgo)
        kg_acero = m2 * 8.5 * factor_acero
        barras = kg_acero / 12
        data.append({
            "Categoria": "Acero",
            "Material": "Acero de Refuerzo",
            "Detalle": f"Varillas corrugadas (~{int(barras)} barras)",
            "Cantidad": round(kg_acero, 2),
            "Unidad": "kg",
            "P_Unitario": precios.get("Acero_Varilla", 85.0),
            "Subtotal": kg_acero * precios.get("Acero_Varilla", 85.0),
        })

        return pd.DataFrame(data)

    @classmethod
    def calcular_obra_terminada(cls, m2, area_muros, precios, calidad="media"):
        """Calcula la obra terminada (pisos, pintura, puertas)."""
        factores = {"economica": 0.8, "media": 1.0, "alta": 1.5, "lujo": 2.5}
        factor = factores.get(calidad, 1.0)

        data = []
        area_piso = m2 * 0.9
        data.append({
            "Categoria": "Pisos",
            "Material": "Cerámica/Porcelanato",
            "Detalle": f"Piso calidad {calidad}",
            "Cantidad": round(area_piso, 2),
            "Unidad": "m²",
            "P_Unitario": precios.get("Ceramica_m2", 450.0) * factor,
            "Subtotal": area_piso * precios.get("Ceramica_m2", 450.0) * factor,
        })

        galones_pintura = area_muros / 12
        data.append({
            "Categoria": "Pintura",
            "Material": "Pintura Interior/Exterior",
            "Detalle": "Pintura vinílica premium (3 manos)",
            "Cantidad": round(galones_pintura, 1),
            "Unidad": "gal",
            "P_Unitario": precios.get("Pintura_galon", 1200.0) * factor,
            "Subtotal": galones_pintura * precios.get("Pintura_galon", 1200.0) * factor,
        })

        num_puertas = max(4, int(m2 / 15))
        data.append({
            "Categoria": "Carpintería",
            "Material": "Puertas Interiores",
            "Detalle": f"{num_puertas} puertas de madera con marcos",
            "Cantidad": num_puertas,
            "Unidad": "ud",
            "P_Unitario": precios.get("Puerta_interior", 8500.0),
            "Subtotal": num_puertas * precios.get("Puerta_interior", 8500.0),
        })

        return pd.DataFrame(data)

    @classmethod
    def calcular_presupuesto_completo(cls, m2, sistema, precios,
                                      incluir_vigas=True, calidad_terminados="media",
                                      espesor_muro_m=0.12,
                                      zona_riesgo="Moderado (Base)"):
        """Genera las dos tablas de presupuesto: obra gris y obra terminada."""
        obra_gris = cls.calcular_obra_grisa(m2, sistema, precios, incluir_vigas, zona_riesgo)
        area_muros = m2 * 2.2
        obra_terminada = cls.calcular_obra_terminada(m2, area_muros, precios, calidad_terminados)
        return obra_gris, obra_terminada

    @classmethod
    def comparar_sistemas(cls, m2, precios, sistema="Paneles Isotex",
                          usar_vigas=False, calidad="media"):
        """Compara Isotex vs Construcción Tradicional con precios dinámicos."""
        isotex_gris, isotex_term = cls.calcular_presupuesto_completo(m2, sistema, precios, usar_vigas, calidad)
        total_isotex = isotex_gris['Subtotal'].sum() + isotex_term['Subtotal'].sum()

        matriz_tradicional = {
            "economica": {"gris": 22000.00, "terminado": 16000.00},
            "media":     {"gris": 35000.00, "terminado": 25000.00},
            "alta":      {"gris": 52000.00, "terminado": 38000.00},
            "lujo":      {"gris": 75000.00, "terminado": 60000.00},
        }
        costos_trad = matriz_tradicional.get(calidad, matriz_tradicional["media"])
        tradicional_gris = m2 * costos_trad["gris"]
        tradicional_term = m2 * costos_trad["terminado"]
        total_tradicional = tradicional_gris + tradicional_term

        tiempo_isotex = m2 * (1.1 if usar_vigas else 1.5)
        tiempo_tradicional = m2 * 2.5
        peso_tradicional = m2 * 850
        peso_isotex = m2 * (220 if sistema == "Paneles Isotex" else 380)

        return {
            'isotex': {
                'costo_total': total_isotex,
                'costo_m2': total_isotex / m2,
                'tiempo_dias': tiempo_isotex,
                'peso_kg': peso_isotex,
            },
            'tradicional': {
                'costo_total': total_tradicional,
                'costo_m2': total_tradicional / m2,
                'tiempo_dias': tiempo_tradicional,
                'peso_kg': peso_tradicional,
            },
            'ahorro': {
                'dinero': total_tradicional - total_isotex,
                'porcentaje': ((total_tradicional - total_isotex) / total_tradicional) * 100,
                'tiempo_dias': tiempo_tradicional - tiempo_isotex,
                'peso_kg': peso_tradicional - peso_isotex,
            },
        }
