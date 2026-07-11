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

from utils.calculador import BudgetCalculator
from utils.pricebook import DEFAULT_PRICEBOOK


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
        Calcula el ahorro energético mensual comparado con construcción tradicional.
        Usa la tarifa BTS2 real de las EDES dominicanas (delegado a AnalisisFinancieroRD).

        Args:
            area_m2: Área de construcción en m²
            sistema: 'isotex', 'icf' o 'tradicional'

        Returns:
            Diccionario con consumo y ahorro mensual
        """
        # Consumo tradicional: 45 kWh/m²/mes
        consumo_trad_mes = area_m2 * cls.CONSUMO_AC_TRADICIONAL_KWH_M2

        if sistema.lower() == "tradicional":
            costo = AnalisisFinancieroRD.calcular_costo_energia_rd(consumo_trad_mes)
            return {
                "consumo_kwh_mes": consumo_trad_mes,
                "costo_mes_rd": costo,
                "ahorro_kwh_mes": 0.0,
                "ahorro_rd_mes": 0.0,
            }

        # Isotex/ICF reduce consumo ~45%
        factor_reduccion = 0.55
        consumo_eps_mes = consumo_trad_mes * factor_reduccion

        costo_trad = AnalisisFinancieroRD.calcular_costo_energia_rd(consumo_trad_mes)
        costo_eps  = AnalisisFinancieroRD.calcular_costo_energia_rd(consumo_eps_mes)

        return {
            "consumo_kwh_mes": round(consumo_eps_mes, 2),
            "costo_mes_rd":    round(costo_eps, 2),
            "ahorro_kwh_mes":  round(consumo_trad_mes - consumo_eps_mes, 2),
            "ahorro_rd_mes":   round(costo_trad - costo_eps, 2),
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
        from utils.calculador import BudgetCalculator

        resultados = []
        areas = np.arange(area_min, area_max + paso, paso)
        precios = DEFAULT_PRICEBOOK

        for area in areas:
            obra_gris, obra_terminada = BudgetCalculator.calcular_presupuesto_completo(
                m2=area,
                sistema=f"Paneles {sistema}" if sistema != "icf" else "ICF Proform",
                precios=precios,
                incluir_vigas=True,
                calidad_terminados=calidad
            )

            total_isotex = obra_gris['Subtotal'].sum() + obra_terminada['Subtotal'].sum()
            comparacion = BudgetCalculator.comparar_sistemas(area, precios)
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

        from utils.calculador import BudgetCalculator

        resultados = []
        precios = DEFAULT_PRICEBOOK

        # Calcular baseline
        obra_gris_base, obra_terminada_base = BudgetCalculator.calcular_presupuesto_completo(
            m2=area_m2,
            sistema=f"Paneles {sistema}" if sistema != "icf" else "ICF Proform",
            precios=precios,
            incluir_vigas=True,
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
    def comparar_financiero_densidades(cls, area_m2: float = 120,
                                       sistema: str = "Paneles Isotex",
                                       usar_vigas_h: bool = False) -> pd.DataFrame:
        """
        Compara financieramente las diferentes densidades de panel ISOTEX

        Args:
            area_m2: Área de construcción
            sistema: Sistema constructivo ('Paneles Isotex' | 'ICF Proform')
            usar_vigas_h: Si se incluyen vigas H estructurales

        Returns:
            DataFrame comparativo
        """
        from utils.calculador import BudgetCalculator

        precios = DEFAULT_PRICEBOOK
        densidades = ["15kg", "20kg", "25kg"]
        resultados = []

        for densidad in densidades:
            obra_gris = BudgetCalculator.calcular_obra_grisa(
                m2=area_m2,
                sistema=sistema,
                precios=precios,
                incluir_vigas=usar_vigas_h
            )
            obra_terminada = BudgetCalculator.calcular_obra_terminada(
                area_m2, area_m2 * 2.2, precios, "media"
            )

            total = obra_gris['Subtotal'].sum() + obra_terminada['Subtotal'].sum()
            comparacion = BudgetCalculator.comparar_sistemas(area_m2, precios)

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
    from utils.calculador import BudgetCalculator

    precios = DEFAULT_PRICEBOOK
    resultados = {}

    sistemas = ["Paneles Isotex", "ICF Proform"]

    for sistema in sistemas:
        obra_gris, obra_terminada = BudgetCalculator.calcular_presupuesto_completo(
            m2=area_m2,
            sistema=sistema,
            precios=precios,
            incluir_vigas=True,
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


# ============================================================================
# ECONOMÍA CIRCULAR Y EFICIENCIA ENERGÉTICA (REPUBLICA DOMINICANA)
# ============================================================================

class AnalisisFinancieroRD:
    """
    Simulador de ROI de obra gris + ahorro en climatización residencial (RD$).
    Implementa la curva de amortización termo-estructural utilizando el
    escalonamiento regulado de la tarifa BTS2 (EDES dominicanas).
    """

    # Estructura marginal indexada al mercado dominicano actual (2026)
    TARIFA_BTS2 = {
        "fijo":    145.00,   # Cargo fijo mensual (RD$)
        "bloque_1":  7.20,   # 0–100 kWh
        "bloque_2":  9.80,   # 101–200 kWh
        "bloque_3": 13.50,   # 201–300 kWh
        "bloque_4": 15.20    # >300 kWh
    }


    @classmethod
    def calcular_costo_energia_rd(cls, kwh_mensuales: float) -> float:
        """Aplica la estructura marginal indexada al mercado dominicano actual."""
        costo = cls.TARIFA_BTS2["fijo"]
        if kwh_mensuales <= 100:
            costo += kwh_mensuales * cls.TARIFA_BTS2["bloque_1"]
        elif kwh_mensuales <= 200:
            costo += (
                (100 * cls.TARIFA_BTS2["bloque_1"])
                + ((kwh_mensuales - 100) * cls.TARIFA_BTS2["bloque_2"])
            )
        elif kwh_mensuales <= 300:
            costo += (
                (100 * cls.TARIFA_BTS2["bloque_1"])
                + (100 * cls.TARIFA_BTS2["bloque_2"])
                + ((kwh_mensuales - 200) * cls.TARIFA_BTS2["bloque_3"])
            )
        else:
            costo += (
                (100 * cls.TARIFA_BTS2["bloque_1"])
                + (100 * cls.TARIFA_BTS2["bloque_2"])
                + (100 * cls.TARIFA_BTS2["bloque_3"])
                + ((kwh_mensuales - 300) * cls.TARIFA_BTS2["bloque_4"])
            )
        return costo

    @classmethod
    def simular_ahorro_termico(cls, area_m2: float, horas_ac_dia: float = 8.0) -> dict:
        """
        Calcula la reducción en demanda eléctrica gracias al bajo coeficiente de
        transmitancia térmica del EPS frente a bloques tradicionales.

        Args:
            area_m2: Área del inmueble en m².
            horas_ac_dia: Horas promedio de uso de aire acondicionado al día.

        Returns:
            Diccionario con kWh ahorrados, costos y ahorro mensual/anual en RD$.
        """
        # Diferencial térmico estimado en clima del Caribe (kWh/h por m²)
        kwh_ahorrado_hora = area_m2 * 0.045
        kwh_ahorrado_mes = kwh_ahorrado_hora * horas_ac_dia * 30

        consumo_base_tradicional = 450.0 + (area_m2 * 0.5)
        consumo_con_eps = max(100.0, consumo_base_tradicional - kwh_ahorrado_mes)

        costo_tradicional = cls.calcular_costo_energia_rd(consumo_base_tradicional)
        costo_eps = cls.calcular_costo_energia_rd(consumo_con_eps)

        ahorro_mensual_rds = costo_tradicional - costo_eps

        return {
            "kwh_ahorrado_mes":      round(kwh_ahorrado_mes, 2),
            "costo_tradicional_rds": round(costo_tradicional, 2),
            "costo_eps_rds":         round(costo_eps, 2),
            "ahorro_mensual_rds":    round(ahorro_mensual_rds, 2),
            "ahorro_anual_rds":      round(ahorro_mensual_rds * 12, 2),
        }
