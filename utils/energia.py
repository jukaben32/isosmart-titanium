# -*- coding: utf-8 -*-
"""
Módulo de Análisis de Ahorro Energético para IsoSmart Titanium
Cálculos de carga térmica, consumo de aire acondicionado y beneficios de aislamiento
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

from utils.financiera import AnalisisFinancieroRD



@dataclass
class ResultadoAnalisisEnergetico:
    """Resultado del análisis energético"""
    carga_termica_btu_h: float
    consumo_mensual_kwh: float
    consumo_mensual_rd: float
    ahorro_mensual_kwh: float
    ahorro_mensual_rd: float
    ahorro_anual_rd: float
    retorno_inversion_btu_h: float
    roi_energetico_anios: float
    reduccion_pico_demanda_kw: float
    co2_evitado_kg_anio: float


class AnalisisEnergetico:
    """
    Análisis energético completo para construcción con sistemas ISOTEX/ICF
    Comparación con construcción tradicional y cálculo de ahorros
    """

    # Parámetros climáticos República Dominicana
    TEMP_EXTERIOR_DS = 34.0        # °C temperatura máxima diseño (Santo Domingo)
    TEMP_INTERIOR_DS = 24.0        # °C temperatura interior confort
    DIFERENCIAL_TERMICO = TEMP_EXTERIOR_DS - TEMP_INTERIOR_DS  # 10°C

    # Costos de energía (RD$ por kWh - tarifa promedio EdeSur 2024)
    COSTO_KWH = 8.50
    COSTO_KWH_PICO = 12.00        # Tarifa pico
    HORAS_PICO_DIA = 6
    HORAS_FUERA_PICO_DIA = 18

    # Consumo típico de equipos de aire acondicionado (BTU/h → kW)
    BTU_POR_TONELADA = 12000
    KWH_POR_BTU = 0.000293071    # 1 BTU = 0.000293071 kWh

    # Eficiencia típica de equipos AC (SEER rating)
    SEER_ISOTEX = 22.0           # Mejor eficiencia por mejor aislamiento
    SEER_TRADICIONAL = 16.0      # Eficiencia estándar

    # Factores de reducción de carga térmica (ISOTEX vs tradicional)
    FACTOR_REDUCCION_ISOTEX = 0.45   # 55% menos carga térmica
    FACTOR_REDUCCION_ICF = 0.40      # 60% menos carga térmica

    # Emisiones de CO2 por kWh (grid República Dominicana)
    KG_CO2_POR_KWH = 0.4

    # Tarifa de venta de excedentes (net metering)
    TARIFA_NET_METERING = 6.00   # RD$/kWh

    @classmethod
    def calcular_carga_termica(cls, area_m2: float, altura: float = 2.7,
                               sistema: str = "isotex",
                               orientacion: str = "normal") -> Dict[str, float]:
        """
        Calcula la carga térmica de refrigeración del edificio

        Args:
            area_m2: Área de construcción en m²
            altura: Altura del techo en metros
            sistema: 'isotex', 'icf' o 'tradicional'
            orientacion: 'favorable' o 'normal' o 'desfavorable'

        Returns:
            Diccionario con carga térmica en BTU/h y kW
        """
        volumen = area_m2 * altura

        # Factor de orientación
        factores_orientacion = {
            'favorable': 0.85,
            'normal': 1.0,
            'desfavorable': 1.15
        }
        factor_orientacion = factores_orientacion.get(orientacion, 1.0)

        # Carga base por volumen (BTU/h por m³) - varía según sistema
        if sistema.lower() == 'isotex':
            carga_base = 25 * factor_orientacion  # BTU/h por m³
        elif sistema.lower() == 'icf':
            carga_base = 22 * factor_orientacion
        elif sistema.lower() == 'tradicional':
            carga_base = 45 * factor_orientacion
        else:
            carga_base = 40 * factor_orientacion

        carga_termica_btu_h = volumen * carga_base

        # Equivalente en kW de refrigeración
        carga_kw = (carga_termica_btu_h / 3412.14)  # 1 kW = 3412.14 BTU/h

        # Carga en toneladas de refrigeración
        carga_toneladas = carga_termica_btu_h / cls.BTU_POR_TONELADA

        return {
            'carga_termica_btu_h': round(carga_termica_btu_h, 0),
            'carga_termica_kw': round(carga_kw, 2),
            'carga_toneladas_refrigeracion': round(carga_toneladas, 2),
            'volumen_m3': round(volumen, 2)
        }

    @classmethod
    def calcular_consumo_mensual(cls, carga_termica_btu_h: float,
                                  seer: float = 18.0,
                                  horas_operacion: float = 10.0) -> Dict[str, float]:
        """
        Calcula el consumo mensual de energía para aire acondicionado

        Args:
            carga_termica_btu_h: Carga térmica en BTU/h
            seer: Seasonal Energy Efficiency Ratio (BTU/Wh)
            horas_operacion: Horas de operación diaria del AC

        Returns:
            Diccionario con consumo en kWh y costos
        """
        # Consumo hourly = BTU/h / (SEER * 1000) = kWh
        consumo_hora_kwh = carga_termica_btu_h / (seer * 1000)

        # Consumo diario
        consumo_diario_kwh = consumo_hora_kwh * horas_operacion

        # Consumo mensual (30 días)
        dias_mes = 30
        consumo_mes_kwh = consumo_diario_kwh * dias_mes

        # Distribución pico/fuera de pico
        horas_pico = cls.HORAS_PICO_DIA
        horas_fuera_pico = cls.HORAS_FUERA_PICO_DIA

        # Simplificado: asume estructura tarifaria dominicana escalonada BTS2
        consumo_mes_rd = AnalisisFinancieroRD.calcular_costo_energia_rd(consumo_mes_kwh)

        return {
            'consumo_hora_kwh': round(consumo_hora_kwh, 3),
            'consumo_diario_kwh': round(consumo_diario_kwh, 2),
            'consumo_mensual_kwh': round(consumo_mes_kwh, 2),
            'consumo_mensual_rd': round(consumo_mes_rd, 2),
            'costo_por_dia_rd': round(consumo_mes_rd / dias_mes, 2)
        }

    @classmethod
    def calcular_ahorro_energetico(cls, area_m2: float,
                                    sistema: str = "isotex",
                                    calidad_equipo: str = "inverter") -> ResultadoAnalisisEnergetico:
        """
        Calcula el ahorro energético completo comparando ISOTEX vs construcción tradicional

        Args:
            area_m2: Área de construcción en m²
            sistema: Sistema constructivo a analizar
            calidad_equipo: 'economico', 'standard', 'inverter', 'premium'

        Returns:
            ResultadoAnalisisEnergetico con todos los cálculos
        """
        # SEER según calidad del equipo
        seer_por_calidad = {
            'economico': 14.0,
            'standard': 16.0,
            'inverter': 20.0,
            'premium': 24.0
        }
        seer_isotex = seer_por_calidad.get(calidad_equipo, 18.0)
        seer_tradicional = seer_por_calidad.get(calidad_equipo, 16.0)

        # Calcular cargas térmicas
        carga_isotex = cls.calcular_carga_termica(area_m2, sistema='isotex')
        carga_tradicional = cls.calcular_carga_termica(area_m2, sistema='tradicional')

        # Consumos mensuales
        consumo_isotex = cls.calcular_consumo_mensual(
            carga_isotex['carga_termica_btu_h'],
            seer_isotex
        )
        consumo_tradicional = cls.calcular_consumo_mensual(
            carga_tradicional['carga_termica_btu_h'],
            seer_tradicional
        )

        # Ahorros
        ahorro_mensual_kwh = consumo_tradicional['consumo_mensual_kwh'] - \
                            consumo_isotex['consumo_mensual_kwh']
        ahorro_mensual_rd = consumo_tradicional['consumo_mensual_rd'] - \
                           consumo_isotex['consumo_mensual_rd']
        ahorro_anual_rd = ahorro_mensual_rd * 12

        # Reducción de pico de demanda
        # Potencia = BTU/h / (SEER * 1000) = kW
        potencia_isotex = carga_isotex['carga_termica_btu_h'] / (seer_isotex * 1000)
        potencia_tradicional = carga_tradicional['carga_termica_btu_h'] / (seer_tradicional * 1000)
        reduccion_pico_kw = potencia_tradicional - potencia_isotex

        # ROI del aislamiento (tiempo en que el ahorro paga el sobrecosto)
        sobrecosto_isotex = area_m2 * 500  # Estimación RD$/m² sobrecosto por aislamiento
        roi_anios = sobrecosto_isotex / ahorro_anual_rd if ahorro_anual_rd > 0 else float('inf')

        # CO2 evitado
        co2_evitado_anual = ahorro_mensual_kwh * 12 * cls.KG_CO2_POR_KWH

        # Retorno de inversión en términos de capacidad de AC
        reduccion_capacidad = carga_tradicional['carga_toneladas_refrigeracion'] - \
                             carga_isotex['carga_toneladas_refrigeracion']

        return ResultadoAnalisisEnergetico(
            carga_termica_btu_h=carga_isotex['carga_termica_btu_h'],
            consumo_mensual_kwh=consumo_isotex['consumo_mensual_kwh'],
            consumo_mensual_rd=consumo_isotex['consumo_mensual_rd'],
            ahorro_mensual_kwh=ahorro_mensual_kwh,
            ahorro_mensual_rd=ahorro_mensual_rd,
            ahorro_anual_rd=ahorro_anual_rd,
            retorno_inversion_btu_h=reduccion_capacidad,
            roi_energetico_anios=roi_anios,
            reduccion_pico_demanda_kw=reduccion_pico_kw,
            co2_evitado_kg_anio=co2_evitado_anual
        )

    @classmethod
    def generar_proyeccion_ahorro(cls, area_m2: float,
                                   horizonte_anios: int = 20,
                                   tasa_crecimiento_kwh: float = 0.05) -> pd.DataFrame:
        """
        Genera proyección de ahorro energético a lo largo del tiempo

        Args:
            area_m2: Área de construcción
            horizonte_anios: Período de proyección
            tasa_crecimiento_kwh: Crecimiento anual del costo de energía

        Returns:
            DataFrame con proyección anual
        """
        analisis = cls.calcular_ahorro_energetico(area_m2)
        datos = []

        for anio in range(1, horizonte_anios + 1):
            factor_crecimiento = (1 + tasa_crecimiento_kwh) ** anio
            ahorro_anual_ajustado = analisis.ahorro_anual_rd * factor_crecimiento
            ahorro_acumulado = sum(
                analisis.ahorro_anual_rd * (1 + tasa_crecimiento_kwh) ** a
                for a in range(1, anio + 1)
            )

            datos.append({
                'Anio': anio,
                'Factor_Crecimiento': round(factor_crecimiento, 3),
                'Ahorro_Anual_RD': round(ahorro_anual_ajustado, 2),
                'Ahorro_Acumulado_RD': round(ahorro_acumulado, 2),
                'CO2_Evitado_kg': round(analisis.co2_evitado_kg_anio * anio, 2)
            })

        return pd.DataFrame(datos)

    @classmethod
    def calcular_sistema_solar_recomendado(cls, area_m2: float) -> Dict:
        """
        Calcula recomendación de sistema solar para complementar el ahorro

        Args:
            area_m2: Área de construcción

        Returns:
            Diccionario con specs del sistema solar recomendado
        """
        analisis = cls.calcular_ahorro_energetico(area_m2)

        # Consumo mensual del sistema ISOTEX
        consumo_mensual = analisis.consumo_mensual_kwh

        # Paneles típicos (400W por panel)
        potencia_panel_w = 400
        horas_pico_sol = 5.5  # Horas de sol pico en República Dominicana

        # Energía generada por panel por día
        energia_panel_dia_wh = potencia_panel_w * horas_pico_sol
        energia_panel_mes_kwh = (energia_panel_dia_wh / 1000) * 30

        # Número de paneles necesarios
        num_paneles = int(np.ceil(consumo_mensual / energia_panel_mes_kwh)) + 2

        # Capacidad total del sistema
        capacidad_kw = (num_paneles * potencia_panel_w) / 1000

        # Costo estimado (RD$ por W instalado - sistema completo)
        costo_por_watt = 45.0  # RD$/W instalado (2024)
        costo_total = capacidad_kw * 1000 * costo_por_watt

        return {
            'paneles_necesarios': num_paneles,
            'capacidad_sistema_kw': round(capacidad_kw, 2),
            'energia_mensual_kwh': round(num_paneles * energia_panel_mes_kwh, 2),
            'autoconsumo_pct': min(100, (num_paneles * energia_panel_mes_kwh / consumo_mensual) * 100),
            'costo_estimado_rd': round(costo_total, 2),
            'costo_por_panel_rd': round(costo_total / num_paneles, 2),
            'ahorro_solar_mensual_rd': round(AnalisisFinancieroRD.calcular_costo_energia_rd(min(consumo_mensual, num_paneles * energia_panel_mes_kwh)), 2)
        }

    @classmethod
    def calcular_tamano_ac_recomendado(cls, area_m2: float, sistema: str = "isotex") -> Dict:
        """
        Calcula el tamaño recomendado de equipo de AC

        Args:
            area_m2: Área de construcción
            sistema: Sistema constructivo

        Returns:
            Diccionario con recomendaciones de equipos
        """
        carga = cls.calcular_carga_termica(area_m2, sistema=sistema)
        toneladas = carga['carga_toneladas_refrigeracion']

        # Equipos típicos
        equipos = [
            {'nombre': 'Mini Split 12,000 BTU', 'btu': 12000, 'kw': 3.5},
            {'nombre': 'Mini Split 18,000 BTU', 'btu': 18000, 'kw': 5.3},
            {'nombre': 'Mini Split 24,000 BTU', 'btu': 24000, 'kw': 7.0},
            {'nombre': 'Central 3 Toneladas', 'btu': 36000, 'kw': 10.5},
            {'nombre': 'Central 4 Toneladas', 'btu': 48000, 'kw': 14.0},
            {'nombre': 'Central 5 Toneladas', 'btu': 60000, 'kw': 17.6},
        ]

        # Encontrar mejor combinación
        num_unidades = int(np.ceil(toneladas / 2))  # Máximo 2 toneladas por unidad para eficiencia
        btu_por_unidad = carga['carga_termica_btu_h'] / num_unidades

        sugeridos = [e for e in equipos if e['btu'] <= btu_por_unidad * 1.2][:3]
        # Si la carga es tan baja que ningún equipo del catálogo entra en el
        # filtro (ej. áreas pequeñas bien aisladas), sugerir el equipo mínimo.
        if not sugeridos:
            sugeridos = [equipos[0]]

        return {
            'toneladas_recomendadas': round(toneladas, 2),
            'carga_termica_btu_h': carga['carga_termica_btu_h'],
            'num_unidades_recomendado': num_unidades,
            'btu_por_unidad': round(btu_por_unidad, 0),
            'equipos_sugeridos': sugeridos
        }

    @classmethod
    def generar_tabla_comparativa_consumos(cls, area_m2: float) -> pd.DataFrame:
        """
        Genera tabla comparativa de consumos por configuración

        Args:
            area_m2: Área de construcción

        Returns:
            DataFrame con comparativa de consumos
        """
        datos = []
        sistemas = ['tradicional', 'isotex', 'icf']
        calidades = ['economico', 'standard', 'inverter', 'premium']

        for sistema in sistemas:
            carga = cls.calcular_carga_termica(area_m2, sistema=sistema)
            for calidad in calidades:
                seer = {'economico': 14, 'standard': 16, 'inverter': 20, 'premium': 24}.get(calidad, 16)
                consumo = cls.calcular_consumo_mensual(carga['carga_termica_btu_h'], seer)

                datos.append({
                    'Sistema': sistema.capitalize(),
                    'Calidad_Equipo': calidad.capitalize(),
                    'Carga_Termica_BTU_h': carga['carga_termica_btu_h'],
                    'SEER': seer,
                    'Consumo_mensual_kWh': consumo['consumo_mensual_kwh'],
                    'Costo_Mensual_RD': consumo['consumo_mensual_rd'],
                    'Costo_Anual_RD': consumo['consumo_mensual_rd'] * 12
                })

        return pd.DataFrame(datos)
