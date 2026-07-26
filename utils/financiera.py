"""
Módulo de Análisis Financiero para IsoSmart Titanium
Cálculos de ROI, VAN, TIR, análisis de sensibilidad y proyecciones
"""

import numpy as np
import pandas as pd

try:
    import numpy_financial as npf
except ImportError:
    npf = None  # Fallback si no está instalado
from dataclasses import dataclass
from typing import Dict, List, Optional

from utils.pricebook import DEFAULT_PRICEBOOK
from utils.tarifa import TARIFA_BLOQUES, calcular_costo_energia_rd


@dataclass
class ResultadoFinanciero:
    """Resultado de análisis financiero"""
    roi_nominal: float          # % ROI total
    roi_anualizado: float      # % ROI anual compuesto
    payback_anios: float | None  # Años hasta recuperar el sobrecosto; None si nunca
    van: float                  # Valor Actual Neto
    tir: float                  # Tasa Interna de Retorno
    tco: float                  # Costo Total de Propiedad
    ahorro_acumulado: float     # Ahorro vs construcción tradicional
    flujo_caja: list[float]    # Flujos de caja por año


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
    def calcular_ahorro_energia_mensual(cls, area_m2: float, sistema: str = "isotex") -> dict[str, float]:
        """
        Ahorro energético mensual frente a construcción tradicional.

        MODELO UNIFICADO (corrección de auditoría)
        ------------------------------------------
        El repositorio tenía TRES modelos energéticos incompatibles que, para la
        misma casa de 120 m², devolvían RD$ 36,936 / RD$ 5,522 / RD$ 1,022 de
        ahorro mensual: un factor de 36x entre el primero y el tercero.

        El que alimentaba el ROI era el peor: 45 kWh/m²/mes de consumo de aire
        acondicionado, es decir 5,400 kWh/mes y una factura de RD$ 43,779 para
        una vivienda de 120 m². El consumo real de una vivienda dominicana de
        ese tamaño ronda los 300–800 kWh/mes.

        Ahora esta función delega en `AnalisisEnergetico`, que es el único de los
        tres con una base física trazable (carga térmica por volumen -> BTU/h ->
        consumo vía SEER -> tarifa por bloques).
        """
        from utils.energia import AnalisisEnergetico  # import diferido: evita ciclo

        carga_trad = AnalisisEnergetico.calcular_carga_termica(area_m2, sistema="tradicional")
        consumo_trad = AnalisisEnergetico.calcular_consumo_mensual(
            carga_trad["carga_termica_btu_h"], seer=16.0
        )

        if str(sistema).strip().lower() == "tradicional":
            return {
                "consumo_kwh_mes": round(consumo_trad["consumo_mensual_kwh"], 2),
                "costo_mes_rd": round(consumo_trad["consumo_mensual_rd"], 2),
                "ahorro_kwh_mes": 0.0,
                "ahorro_rd_mes": 0.0,
            }

        sistema_eps = "icf" if str(sistema).strip().lower() == "icf" else "isotex"
        carga_eps = AnalisisEnergetico.calcular_carga_termica(area_m2, sistema=sistema_eps)
        consumo_eps = AnalisisEnergetico.calcular_consumo_mensual(
            carga_eps["carga_termica_btu_h"], seer=16.0
        )

        return {
            "consumo_kwh_mes": round(consumo_eps["consumo_mensual_kwh"], 2),
            "costo_mes_rd": round(consumo_eps["consumo_mensual_rd"], 2),
            "ahorro_kwh_mes": round(
                consumo_trad["consumo_mensual_kwh"] - consumo_eps["consumo_mensual_kwh"], 2
            ),
            "ahorro_rd_mes": round(
                consumo_trad["consumo_mensual_rd"] - consumo_eps["consumo_mensual_rd"], 2
            ),
        }

    @classmethod
    def calcular_roi(cls, area_m2: float, costo_total_isotex: float,
                    costo_tradicional: float, horizonte_anios: int = 10,
                    tasa_descuento: float = None) -> ResultadoFinanciero:
        """
        ROI, VAN, TIR, payback y TCO de EPS/ICF frente a construcción tradicional.

        CORRECCIÓN DE SIGNO (auditoría)
        -------------------------------
        La versión anterior hacía:

            inversion_inicial = costo_tradicional - costo_total_isotex
            if inversion_inicial < 0:
                inversion_inicial = costo_total_isotex - costo_tradicional
            flujos.append(-inversion_inicial)

        Ambas ramas producían un flujo NEGATIVO en el año 0. Es decir: cuando
        EPS resultaba más barato —el caso que la app siempre presenta— el modelo
        trataba el ahorro inicial como si fuera un desembolso. VAN, TIR y payback
        se calculaban sobre una inversión inexistente.

        Ahora el año 0 lleva su signo real:
          - EPS más caro   -> diferencial negativo (inversión real a recuperar)
          - EPS más barato -> diferencial positivo (ahorro disponible desde el día 0)
        """
        if tasa_descuento is None:
            tasa_descuento = cls.TASA_DESCUENTO_DEFAULT

        # >0 si EPS ahorra desde el inicio; <0 si EPS cuesta más.
        diferencial_inicial = float(costo_tradicional) - float(costo_total_isotex)
        sobrecosto_inicial = max(0.0, -diferencial_inicial)   # lo que hay que recuperar

        mantenimiento_isotex = costo_total_isotex * cls.MANTENIMIENTO_PORCENTAJE
        mantenimiento_tradicional = costo_tradicional * cls.MANTENIMIENTO_PORCENTAJE
        ahorro_mantenimiento = mantenimiento_tradicional - mantenimiento_isotex
        ahorro_energia_anual = (
            cls.calcular_ahorro_energia_mensual(area_m2, "isotex")["ahorro_rd_mes"] * 12
        )
        flujo_anual = ahorro_energia_anual + ahorro_mantenimiento

        # Año 0 con su signo real + flujos anuales constantes.
        # (Antes: `flujo_anual * anio if anio == 1 else flujo_anual`, un `*1`
        #  residual que solo hacía ilegible la intención.)
        flujos = [diferencial_inicial] + [flujo_anual] * int(horizonte_anios)
        flujos_np = np.array(flujos, dtype=float)

        # VAN
        if npf is not None:
            van = float(npf.npv(tasa_descuento, flujos_np))
        else:
            van = float(sum(f / (1 + tasa_descuento) ** i for i, f in enumerate(flujos_np)))

        # TIR: solo tiene sentido si hay cambio de signo en la serie.
        tir = 0.0
        hay_cambio_signo = min(flujos) < 0 < max(flujos)
        if npf is not None and hay_cambio_signo:
            try:
                valor = npf.irr(flujos_np)
                tir = float(valor * 100) if valor is not None and np.isfinite(valor) else 0.0
            except Exception:
                tir = 0.0

        # Payback: 0 si no hay sobrecosto que recuperar; None si nunca se recupera.
        if sobrecosto_inicial <= 0:
            payback = 0.0
        else:
            payback = None
            acumulado = 0.0
            for i, flujo in enumerate(flujos[1:], start=1):
                acumulado += flujo
                if acumulado >= sobrecosto_inicial:
                    payback = float(i)
                    break

        # ROI sobre el capital realmente desplegado (el costo de construir en EPS).
        beneficio_total = diferencial_inicial + sum(flujos[1:])
        base = float(costo_total_isotex) or 1.0
        roi_nominal = (beneficio_total / base) * 100.0

        # CAGR equivalente del ROI a lo largo del horizonte.
        crecimiento = 1.0 + (roi_nominal / 100.0)
        roi_anualizado = (
            (crecimiento ** (1.0 / horizonte_anios) - 1.0) * 100.0
            if crecimiento > 0 and horizonte_anios > 0
            else 0.0
        )

        # TCO ahora incluye energía, como especifica SPEC.md (antes se omitía).
        energia_isotex_anual = (
            cls.calcular_ahorro_energia_mensual(area_m2, "isotex")["costo_mes_rd"] * 12
        )
        energia_trad_anual = (
            cls.calcular_ahorro_energia_mensual(area_m2, "tradicional")["costo_mes_rd"] * 12
        )
        tco_isotex = (costo_total_isotex
                      + (mantenimiento_isotex + energia_isotex_anual) * horizonte_anios)
        tco_tradicional = (costo_tradicional
                           + (mantenimiento_tradicional + energia_trad_anual) * horizonte_anios)

        return ResultadoFinanciero(
            roi_nominal=roi_nominal,
            roi_anualizado=roi_anualizado,
            payback_anios=payback,
            van=van,
            tir=tir,
            tco=tco_isotex,
            ahorro_acumulado=tco_tradicional - tco_isotex,
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

        MIGRACIÓN (revisión de pantallas, 2026-07-26): antes usaba el motor
        clásico (`BudgetCalculator`), que da 9.6% de obra terminada y un
        ahorro fijo del 83.6% para cualquier área. Ahora usa `MotorQTO`
        (motor de cantidades, Fase 1 de la auditoría), cuyo ahorro varía
        genuinamente con el proyecto.
        """
        from utils.geometria import Geometria
        from utils.qto import MotorQTO

        resultados = []
        areas = np.arange(area_min, area_max + paso, paso)
        precios = DEFAULT_PRICEBOOK
        sistema_qto = "icf" if sistema.lower() == "icf" else "isotex"

        for area in areas:
            motor = MotorQTO(Geometria(area_m2=float(area)), precios,
                             sistema=sistema_qto, calidad=calidad)
            comp = motor.comparar_con_tradicional()

            total_isotex = comp["eps"]["costo_total"]
            total_tradicional = comp["tradicional"]["costo_total"]

            resultados.append({
                'Area_m2': area,
                'Costo_Isotex_RD': total_isotex,
                'Costo_Tradicional_RD': total_tradicional,
                'Costo_m2_Isotex': comp["eps"]["costo_m2"],
                'Costo_m2_Tradicional': comp["tradicional"]["costo_m2"],
                'Ahorro_RD': comp["ahorro"]["total_rd"],
                'Ahorro_Pct': comp["ahorro"]["total_pct"],
                'Tiempo_Construccion_Dias': comp["eps"]["dias"]
            })

        return pd.DataFrame(resultados)

    @classmethod
    def analizar_sensibilidad_precio_materiales(cls, area_m2: float = 120,
                                                 variacion_pct: list[float] = None,
                                                 sistema: str = "isotex") -> pd.DataFrame:
        """
        Analiza sensibilidad a variaciones en precios de materiales

        Args:
            area_m2: Área de construcción
            variacion_pct: Lista de variaciones porcentuales [(-20,), (-10,), 0, 10, 20]
            sistema: Sistema constructivo

        Returns:
            DataFrame con análisis de sensibilidad

        MIGRACIÓN (revisión de pantallas, 2026-07-26): ver nota en
        `analizar_sensibilidad_area`.
        """
        if variacion_pct is None:
            variacion_pct = [-20, -10, 0, 10, 20]

        from utils.geometria import Geometria
        from utils.qto import MotorQTO

        resultados = []
        precios = DEFAULT_PRICEBOOK
        sistema_qto = "icf" if sistema.lower() == "icf" else "isotex"
        geo = Geometria(area_m2=area_m2)

        # Calcular baseline
        costo_base = MotorQTO(geo, precios, sistema=sistema_qto).total()

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
                                      tasa_descuento: float = None,
                                      costo_tradicional: float = None) -> pd.DataFrame:
        """
        Genera proyección de flujo de caja año por año

        Args:
            area_m2: Área de construcción
            costo_total: Costo total del proyecto (EPS/ICF)
            horizonte_anios: Período de proyección
            tasa_crecimiento_energia: Crecimiento anual del costo de energía
            tasa_descuento: Tasa de descuento
            costo_tradicional: Costo de la alternativa tradicional, para calcular
                el diferencial real (ver nota de corrección abajo)

        Returns:
            DataFrame con proyección anual

        CORRECCIÓN (revisión de pantallas, 2026-07-26)
        ------------------------------------------------
        Antes: `acumulado = flujo_neto - costo_total` restaba el costo TOTAL de
        construir la casa en el año 1, no el diferencial frente a la
        alternativa tradicional. El resultado: la curva "Flujo de Caja
        Acumulado" nunca se acercaba a cero en 20 años (quedaba en varios
        millones de pesos negativos), contradiciendo directamente el ROI
        positivo que la misma página mostraba arriba, calculado con
        `calcular_roi()` (ya corregido en la Fase 1 de la auditoría). Dos
        funciones, los mismos datos de entrada, dos historias contradictorias.

        Ahora se resta el mismo diferencial que usa `calcular_roi()`: si EPS
        es más barato que lo tradicional, no hay sobrecosto que recuperar
        (diferencial >= 0) y el año 1 no debe partir de un hueco de millones
        de pesos que nunca se llena.
        """
        if tasa_descuento is None:
            tasa_descuento = cls.TASA_DESCUENTO_DEFAULT

        if costo_tradicional is not None:
            diferencial_inicial = costo_tradicional - costo_total
        else:
            # Sin punto de comparación, no se puede saber si hay sobrecosto.
            # Antes esto asumía implícitamente costo_tradicional=0 (peor caso
            # posible); ahora se asume 0 explícitamente y se documenta.
            diferencial_inicial = 0.0

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

            # Acumulado: parte del diferencial real (0 si EPS ya es más barato),
            # no del costo total de la construcción.
            if anio == 1:
                acumulado = flujo_neto + diferencial_inicial
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
            DataFrame comparativo, con una columna `nota` explicando que el
            costo no varía por densidad en el modelo actual.

        HALLAZGO (revisión de pantallas, 2026-07-26)
        -----------------------------------------------
        Esta función mostraba tres filas ("15kg", "20kg", "25kg") con
        **costo idéntico** en las tres — la densidad se recibía como
        parámetro pero nunca entraba en ningún cálculo, así que el gráfico
        de la Dashboard sugería una comparación real donde no había ninguna.
        Además, "15kg/20kg/25kg" no corresponde a ninguna especificación real
        de panel Covintec (sus fichas técnicas dan 2.6-2.8 kg/m² de peso sin
        aplanar para 3"/4", ver `utils/fuentes.py::FICHA_COVINTEC`) — parece
        una etiqueta inventada desde el origen, no solo un cálculo faltante.

        Mientras el pricebook no tenga precios reales por espesor de panel,
        esta función devuelve el costo real (vía MotorQTO) IDÉNTICO para las
        tres filas, con una columna `nota` que lo explica en vez de fingir
        una diferencia que no existe.
        """
        from utils.geometria import Geometria
        from utils.qto import MotorQTO

        precios = DEFAULT_PRICEBOOK
        densidades = ["15kg", "20kg", "25kg"]
        resultados = []

        sistema_qto = "icf" if "icf" in sistema.lower() else "isotex"
        motor = MotorQTO(Geometria(area_m2=area_m2), precios, sistema=sistema_qto)
        comp = motor.comparar_con_tradicional()
        total = comp["eps"]["costo_total"]

        for densidad in densidades:
            resultados.append({
                'Densidad_Panel': densidad,
                'Costo_Total_RD': total,
                'Costo_m2_RD': total / area_m2,
                'Ahorro_vs_Tradicional_RD': comp["ahorro"]["total_rd"],
                'Ahorro_Pct': comp["ahorro"]["total_pct"],
                'Peso_kg_m2': None,  # sin fuente real para este dato por densidad
                'nota': ("El pricebook actual no distingue precio por espesor de "
                        "panel; el costo es el mismo para las tres densidades "
                        "hasta contar con precios reales por espesor."),
            })

        return pd.DataFrame(resultados)

    @classmethod
    def calcular_costo_financiamiento(cls, monto: float, tasa_anual: float = 0.15,
                                     plazo_meses: int = 60) -> dict:
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


def calcular_costo_unitario_por_sistema(area_m2: float) -> dict[str, dict]:
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

    # La tabla y el algoritmo de tarifa viven ahora en utils/tarifa.py (fuente
    # única compartida con utils/energia.py). Se conservan estos alias para no
    # romper los llamadores existentes.
    TARIFA_BTS2 = TARIFA_BLOQUES

    @classmethod
    def calcular_costo_energia_rd(cls, kwh_mensuales: float) -> float:
        """Costo mensual en RD$ según la estructura marginal por bloques."""
        return calcular_costo_energia_rd(kwh_mensuales)

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
