# -*- coding: utf-8 -*-
"""
Módulo de Análisis Financiero para IsoSmart Titanium
Cálculos de ROI, VAN, TIR, análisis de sensibilidad y proyecciones
"""

import pandas as pd
import numpy as np
try:
    import numpy_financial as npf
except ImportError:
    npf = None  # Fallback si no está instalado
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import streamlit as st


@dataclass
class ResultadoFinanciero:
    """Resultado de análisis financiero"""
    roi_nominal: float          # % ROI total
    roi_anualizado: float      # % ROI anual compuesto
    payback_anios: float       # Período de recuperación
    van: float                  # Valor Actual Neto
    tir: float                  # Tasa Interna de Retorno
    tco: float                  # Costo Total de Propiedad
    ahorro_acumulado: float     # Ahorro vs construcción tradicional
    flujo_caja: List[float]    # Flujos de caja por año


class AnalisisFinanciero:
    """
    Análisis financiero completo para proyectos de construcción ISOTEX/ICF
    """

    # Parámetros por defecto ( República Dominicana)
    COSTO_KWH_RD = 8.50           # RD$ por kWh (Edenorte/EdeEste)
    HORAS_AIRE_DIA = 10           # Horas promedio de AC
    DIAS_ANO = 365
    MANTENIMIENTO_PORCENTAJE = 0.015  # 1.5% del valor por año
    SEGURO_PORCENTAJE = 0.005     # 0.5% del valor por año
    TASA_DESCUENTO_DEFAULT = 0.12  # 12% anual

    # Costos de energía tradicionales (referencia)
    CONSUMO_AC_TRADICIONAL_KWH_M2 = 45  # kWh/m²/mes (aire acondicionado)
    CONSUMO_AC_ISOTEX_KWH_M2 = 25       # kWh/m²/mes (hasta 50% menos)

    @classmethod
    def calcular_ahorro_energia_mensual(cls, area_m2: float, sistema: str = "isotex") -> Dict[str, float]:
        """
        Calcula el ahorro energético mensual comparado con construcción tradicional

        Args:
            area_m2: Área de construcción en m²
            sistema: 'isotex', 'icf' o 'tradicional'

        Returns:
            Diccionario con consumo y ahorro mensual
        """
        if sistema.lower() == "tradicional":
            consumo_mes = area_m2 * cls.CONSUMO_AC_TRADICIONAL_KWH_M2
            return {
                "consumo_kwh_mes": consumo_mes,
                "costo_mes_rd": consumo_mes * cls.COSTO_KWH_RD,
                "ahorro_kwh_mes": 0,
                "ahorro_rd_mes": 0
            }

        # Para Isotex/ICF, el consumo es ~45% menor
        factor_reduccion = 0.55  # 45% de reducción
        consumo_mes_isotex = area_m2 * cls.CONSUMO_AC_TRADICIONAL_KWH_M2 * factor_reduccion
        consumo_mes_tradicional = area_m2 * cls.CONSUMO_AC_TRADICIONAL_KWH_M2

        return {
            "consumo_kwh_mes": consumo_mes_isotex,
            "costo_mes_rd": consumo_mes_isotex * cls.COSTO_KWH_RD,
            "ahorro_kwh_mes": consumo_mes_tradicional - consumo_mes_isotex,
            "ahorro_rd_mes": (consumo_mes_tradicional - consumo_mes_isotex) * cls.COSTO_KWH_RD
        }

    @classmethod
    def calcular_roi(cls, area_m2: float, costo_total_isotex: float,
                    costo_tradicional: float, horizonte_anios: int = 10,
                    tasa_descuento: float = None) -> ResultadoFinanciero:
        """
        Calcula ROI, VAN, TIR y payback para un proyecto ISOTEX vs Tradicional

        Args:
            area_m2: Área de construcción en m²
            costo_total_isotex: Costo total de construcción ISOTEX (RD$)
            costo_tradicional: Costo total construcción tradicional (RD$)
            horizonte_anios: Período de análisis en años
            tasa_descuento: Tasa de descuento para VAN (default 12%)

        Returns:
            ResultadoFinanciero con todas las métricas
        """
        if tasa_descuento is None:
            tasa_descuento = cls.TASA_DESCUENTO_DEFAULT

        # Inversión inicial (diferencia)
        inversion_inicial = costo_tradicional - costo_total_isotex
        if inversion_inicial < 0:
            # ISOTEX es más caro - ajustar análisis
            inversion_inicial = costo_total_isotex - costo_tradicional
            es_mas_caro = True
        else:
            es_mas_caro = False

        # Flujos anuales (ahorro + mantenimiento)
        flujos = []
        mantenimiento_isotex = costo_total_isotex * cls.MANTENIMIENTO_PORCENTAJE
        mantenimiento_tradicional = costo_tradicional * cls.MANTENIMIENTO_PORCENTAJE
        ahorro_energia_anual = (
            cls.calcular_ahorro_energia_mensual(area_m2, "isotex")["ahorro_rd_mes"] * 12
        )
        ahorro_mantenimiento = (mantenimiento_tradicional - mantenimiento_isotex)

        # Año 0: inversión inicial (negativo)
        flujos.append(-inversion_inicial)

        # Años 1 a horizonte
        for anio in range(1, horizonte_anios + 1):
            flujo_anual = ahorro_energia_anual + ahorro_mantenimiento
            # Acumular ahorros
            flujos.append(flujo_anual * anio if anio == 1 else flujo_anual)

        # Crear array de numpy para cálculos
        flujos_np = np.array(flujos)

        # Calcular VAN (usando numpy-financial si está disponible)
        if npf is not None:
            van = npf.npv(tasa_descuento, flujos_np)
        else:
            # Cálculo manual del VAN como fallback
            van = sum(f / (1 + tasa_descuento)**i for i, f in enumerate(flujos_np))

        # Calcular TIR (usando numpy-financial si está disponible)
        try:
            if npf is not None:
                tir = npf.irr(flujos_np) * 100  # En porcentaje
            else:
                tir = 0.0
        except Exception:
            tir = 0.0

        # Payback simple (sin descontar)
        flujo_acumulado = 0
        payback = horizonte_anios
        for i, flujo in enumerate(flujos[1:], 1):
            flujo_acumulado += flujo
            if flujo_acumulado >= inversion_inicial:
                payback = i
                break

        # ROI nominal
        total_ahorros = sum(flujos[1:])
        roi_nominal = ((total_ahorros - abs(flujos[0])) / abs(flujos[0])) * 100 if flujos[0] != 0 else 0

        # ROI anualizado (CAGR)
        if flujos[0] < 0 and payback < horizonte_anios:
            valor_final = abs(flujos[0]) * (1 + roi_nominal/100)
            if valor_final > 0 and abs(flujos[0]) > 0:
                roi_anualizado = ((valor_final / abs(flujos[0])) ** (1/horizonte_anios) - 1) * 100
            else:
                roi_anualizado = 0
        else:
            roi_anualizado = 0

        # Costo Total de Propiedad
        tco_isotex = costo_total_isotex + (mantenimiento_isotex * horizonte_anios)
        tco_tradicional = costo_tradicional + (mantenimiento_tradicional * horizonte_anios)
        tco = tco_isotex

        # Ahorro acumulado
        ahorro_acumulado = tco_tradicional - tco_isotex

        return ResultadoFinanciero(
            roi_nominal=roi_nominal,
            roi_anualizado=roi_anualizado,
            payback_anios=payback,
            van=van,
            tir=tir,
            tco=tco,
            ahorro_acumulado=ahorro_acumulado,
            flujo_caja=flujos
        )

    @classmethod
    def analizar_sensibilidad_area(cls, area_min: float = 50, area_max: float = 1000,
                                   paso: float = 50,
                                   sistema: str = "isotex",
                                   calidad: str = "media") -> pd.DataFrame:
        """
        Analiza sensibilidad de costos según el área de construcción

        Args:
            area_min: Área mínima en m²
            area_max: Área máxima en m²
            paso: Incremento de área
            sistema: Sistema constructivo
            calidad: Calidad de terminados

        Returns:
            DataFrame con análisis de sensibilidad
        """
        from app import BudgetCalculator

        resultados = []
        areas = np.arange(area_min, area_max + paso, paso)

        for area in areas:
            budget = BudgetCalculator()
            obra_gris, obra_terminada = budget.calcular_presupuesto_completo(
                m2=area,
                sistema=f"Paneles {sistema}" if sistema != "icf" else "ICF Proform",
                usar_vigas_h=True,
                calidad_terminados=calidad
            )

            total_isotex = obra_gris['Subtotal'].sum() + obra_terminada['Subtotal'].sum()
            comparacion = budget.comparar_sistemas(area)
            total_tradicional = comparacion['tradicional']['costo_total']

            costo_m2_isotex = total_isotex / area
            costo_m2_trad = total_tradicional / area
            ahorro_pct = ((total_tradicional - total_isotex) / total_tradicional) * 100

            resultados.append({
                'Area_m2': area,
                'Costo_Isotex_RD': total_isotex,
                'Costo_Tradicional_RD': total_tradicional,
                'Costo_m2_Isotex': costo_m2_isotex,
                'Costo_m2_Tradicional': costo_m2_trad,
                'Ahorro_RD': total_tradicional - total_isotex,
                'Ahorro_Pct': ahorro_pct,
                'Tiempo_Construccion_Dias': comparacion['isotex']['tiempo_dias']
            })

        return pd.DataFrame(resultados)

    @classmethod
    def analizar_sensibilidad_precio_materiales(cls, area_m2: float = 120,
                                                 variacion_pct: List[float] = None,
                                                 sistema: str = "isotex") -> pd.DataFrame:
        """
        Analiza sensibilidad a variaciones en precios de materiales

        Args:
            area_m2: Área de construcción
            variacion_pct: Lista de variaciones porcentuales [(-20,), (-10,), 0, 10, 20]
            sistema: Sistema constructivo

        Returns:
            DataFrame con análisis de sensibilidad
        """
        if variacion_pct is None:
            variacion_pct = [-20, -10, 0, 10, 20]

        from app import BudgetCalculator

        resultados = []
        budget = BudgetCalculator()

        # Calcular baseline
        obra_gris_base, obra_terminada_base = budget.calcular_presupuesto_completo(
            m2=area_m2,
            sistema=f"Paneles {sistema}" if sistema != "icf" else "ICF Proform",
            usar_vigas_h=True,
            calidad_terminados="media"
        )
        costo_base = obra_gris_base['Subtotal'].sum() + obra_terminada_base['Subtotal'].sum()

        for variacion in variacion_pct:
            factor = 1 + (variacion / 100)
            costo_ajustado = costo_base * factor
            diferencia = costo_ajustado - costo_base

            resultados.append({
                'Variacion_Pct': variacion,
                'Costo_Ajustado_RD': costo_ajustado,
                'Diferencia_RD': diferencia,
                'Costo_m2_Ajustado': costo_ajustado / area_m2,
                'Factor': factor
            })

        return pd.DataFrame(resultados)

    @classmethod
    def generar_proyeccion_flujo_caja(cls, area_m2: float, costo_total: float,
                                      horizonte_anios: int = 20,
                                      tasa_crecimiento_energia: float = 0.05,
                                      tasa_descuento: float = None) -> pd.DataFrame:
        """
        Genera proyección de flujo de caja año por año

        Args:
            area_m2: Área de construcción
            costo_total: Costo total del proyecto
            horizonte_anios: Período de proyección
            tasa_crecimiento_energia: Crecimiento anual del costo de energía
            tasa_descuento: Tasa de descuento

        Returns:
            DataFrame con proyección anual
        """
        if tasa_descuento is None:
            tasa_descuento = cls.TASA_DESCUENTO_DEFAULT

        datos = []
        energia_mensual = cls.calcular_ahorro_energia_mensual(area_m2, "isotex")
        ahorro_energia_anual = energia_mensual["ahorro_rd_mes"] * 12

        for anio in range(1, horizonte_anios + 1):
            # Actualizar costo de energía con crecimiento
            factor_crecimiento = (1 + tasa_crecimiento_energia) ** anio
            ahorro_energia_ajustado = ahorro_energia_anual * factor_crecimiento

            # Mantenimiento (crece con inflación)
            mantenimiento_anual = costo_total * cls.MANTENIMIENTO_PORCENTAJE * (1.03 ** anio)

            # Flujo neto
            flujo_neto = ahorro_energia_ajustado - mantenimiento_anual

            # Valor presente
            factor_descuento = (1 + tasa_descuento) ** anio
            valor_presente = flujo_neto / factor_descuento

            # Acumulado
            if anio == 1:
                acumulado = flujo_neto - costo_total
            else:
                acumulado = datos[-1]['Acumulado_Nominal'] + flujo_neto

            datos.append({
                'Anio': anio,
                'Ahorro_Energia_RD': ahorro_energia_ajustado,
                'Mantenimiento_RD': mantenimiento_anual,
                'Flujo_Neto_RD': flujo_neto,
                'Valor_Presente_RD': valor_presente,
                'Acumulado_Nominal': acumulado
            })

        return pd.DataFrame(datos)

    @classmethod
    def comparar_financiero_densidades(cls, area_m2: float = 120) -> pd.DataFrame:
        """
        Compara financieramente las diferentes densidades de panel ISOTEX

        Args:
            area_m2: Área de construcción

        Returns:
            DataFrame comparativo
        """
        from app import BudgetCalculator

        densidades = ["15kg", "20kg", "25kg"]
        resultados = []

        for densidad in densidades:
            budget = BudgetCalculator()
            
            usar_vigas = st.session_state.get("usar_vigas_h", False)
            sistema_act = st.session_state.get("sistema_seleccionado", "Paneles Isotex")
            
            obra_gris = budget.calcular_obra_grisa(
                m2=area_m2,
                sistema=sistema_act,
                usar_vigas_h=usar_vigas
            )
            obra_terminada = budget.calcular_obra_terminada(area_m2, area_m2 * 2.2, "media")

            total = obra_gris['Subtotal'].sum() + obra_terminada['Subtotal'].sum()
            comparacion = budget.comparar_sistemas(area_m2)

            resultados.append({
                'Densidad_Panel': densidad,
                'Costo_Total_RD': total,
                'Costo_m2_RD': total / area_m2,
                'Ahorro_vs_Tradicional_RD': comparacion['tradicional']['costo_total'] - total,
                'Ahorro_Pct': ((comparacion['tradicional']['costo_total'] - total) /
                              comparacion['tradicional']['costo_total']) * 100,
                'Peso_kg_m2': 15 if densidad == "15kg" else (20 if densidad == "20kg" else 25)
            })

        return pd.DataFrame(resultados)

    @classmethod
    def calcular_costo_financiamiento(cls, monto: float, tasa_anual: float = 0.15,
                                     plazo_meses: int = 60) -> Dict:
        """
        Calcula costos de financiamiento bancario

        Args:
            monto: Monto del préstamo
            tasa_anual: Tasa de interés anual (default 15%)
            plazo_meses: Plazo en meses

        Returns:
            Diccionario con detalles del financiamiento
        """
        tasa_mensual = tasa_anual / 12

        # Cuota mensual (fórmula de amortización francesa)
        if tasa_mensual > 0:
            cuota = monto * (tasa_mensual * (1 + tasa_mensual) ** plazo_meses) / \
                    ((1 + tasa_mensual) ** plazo_meses - 1)
        else:
            cuota = monto / plazo_meses

        total_pagado = cuota * plazo_meses
        total_intereses = total_pagado - monto

        return {
            'monto_prestamo': monto,
            'cuota_mensual': cuota,
            'total_pagado': total_pagado,
            'total_intereses': total_intereses,
            'tasa_anual': tasa_anual * 100,
            'plazo_meses': plazo_meses
        }


def calcular_costo_unitario_por_sistema(area_m2: float) -> Dict[str, Dict]:
    """
    Compara costos unitarios por m² entre sistemas constructivos

    Args:
        area_m2: Área de construcción

    Returns:
        Diccionario con costos por sistema
    """
    from app import BudgetCalculator

    budget = BudgetCalculator()
    resultados = {}

    sistemas = ["Paneles Isotex", "ICF Proform"]

    for sistema in sistemas:
        obra_gris, obra_terminada = budget.calcular_presupuesto_completo(
            m2=area_m2,
            sistema=sistema,
            usar_vigas_h=True,
            calidad_terminados="media"
        )

        total = obra_gris['Subtotal'].sum() + obra_terminada['Subtotal'].sum()

        # Desglose por categoría
        obra_gris_categorias = obra_gris.groupby('Categoria')['Subtotal'].sum().to_dict()
        obra_term_categorias = obra_terminada.groupby('Categoria')['Subtotal'].sum().to_dict()

        resultados[sistema] = {
            'costo_total': total,
            'costo_m2': total / area_m2,
            'obra_gris_total': obra_gris['Subtotal'].sum(),
            'obra_terminada_total': obra_terminada['Subtotal'].sum(),
            'categorias_obra_gris': obra_gris_categorias,
            'categorias_obra_terminada': obra_term_categorias
        }

    return resultados
