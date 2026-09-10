"""
Módulo de Análisis de Ahorro Energético para IsoSmart Titanium
Cálculos de carga térmica, consumo de aire acondicionado y beneficios de aislamiento
"""

from dataclasses import dataclass
from typing import Dict

import numpy as np
import pandas as pd

# Antes: `from utils.financiera import AnalisisFinancieroRD` -> acoplaba el
# módulo energético al financiero. Ahora ambos dependen de utils/tarifa.py.
from utils.tarifa import KG_CO2_POR_KWH as _KG_CO2_GRID  # noqa: F401
from utils.tarifa import calcular_costo_energia_rd


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

    # NOTA: existían aquí COSTO_KWH=8.50, COSTO_KWH_PICO=12.00, HORAS_PICO_DIA
    # y HORAS_FUERA_PICO_DIA, una tarifa plana sin fuente, sin usar en ninguna
    # función del módulo (quedaron huérfanas cuando se unificó la tarifa
    # eléctrica en utils/tarifa.py, la que sí calcula por bloques marginales
    # y es la que realmente consume `calcular_consumo_mensual()`).

    # Consumo típico de equipos de aire acondicionado (BTU/h → kW)
    BTU_POR_TONELADA = 12000
    KWH_POR_BTU = 0.000293071    # 1 BTU = 0.000293071 kWh

    # Eficiencia típica de equipos AC (SEER rating)
    # NOTA: SEER_ISOTEX/SEER_TRADICIONAL eran constantes muertas -- ninguna
    # función de esta clase las leía. `calcular_ahorro_energetico()` resuelve
    # el SEER real desde `calidad_equipo` (economico/standard/inverter/premium).
    # Se conservan solo como valores de referencia para quien llame a
    # `calcular_consumo_mensual()` directamente sin especificar `seer`.
    SEER_ISOTEX = 22.0           # Mejor eficiencia por mejor aislamiento
    SEER_TRADICIONAL = 16.0      # Eficiencia estándar

    # Emisiones de CO2 por kWh (grid República Dominicana)
    KG_CO2_POR_KWH = 0.4

    # ------------------------------------------------------------------
    # Reducción de carga térmica: propiedad calculada, no constante muerta.
    #
    # ANTES existían `FACTOR_REDUCCION_ISOTEX = 0.45  # 55% menos carga
    # térmica` y `FACTOR_REDUCCION_ICF = 0.40  # 60% menos carga térmica`,
    # pero NINGUNA función de este módulo las leía. El "hasta 55%" que
    # mostraba `paginas/analisis_energetico.py` salía de ese comentario, no
    # de un cálculo. La reducción real -- la que sí determina el consumo y el
    # ahorro que ve el usuario -- surge de los coeficientes BTU/h/m³ de
    # `calcular_carga_termica()` (25 isotex / 22 icf / 45 tradicional) y da
    # 44.4% y 51.1% respectivamente. Estos coeficientes son estimaciones de
    # ingeniería sin ficha técnica local citada (a diferencia de los datos de
    # `utils/fuentes.py::FICHA_COVINTEC`, que sí tienen fuente).
    # ------------------------------------------------------------------
    @classmethod
    def reduccion_carga_termica_pct(cls, sistema: str = "isotex") -> float:
        """Porcentaje de reducción de carga térmica frente a construcción tradicional."""
        trad = cls.calcular_carga_termica(100.0, sistema="tradicional")["carga_termica_btu_h"]
        propio = cls.calcular_carga_termica(100.0, sistema=sistema)["carga_termica_btu_h"]
        return (1 - propio / trad) * 100.0

    # NOTA: existía aquí `TARIFA_NET_METERING = 6.00 RD$/kWh` (venta de
    # excedentes solares), pero `calcular_sistema_solar_recomendado()` nunca
    # la usaba -- el sistema solar se dimensiona por consumo, sin modelar
    # venta de excedentes. Se retira en vez de dejarla como adorno; si se
    # implementa venta de excedentes, debe entrar como parámetro citado con
    # su fuente (pliego tarifario de net metering de la SIE), igual que
    # `utils/tarifa.py`.

    @classmethod
    def calcular_carga_termica(cls, area_m2: float, altura: float = 2.7,
                               sistema: str = "isotex",
                               orientacion: str = "normal") -> dict[str, float]:
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
                                  horas_operacion: float = 10.0) -> dict[str, float]:
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

        # Simplificado: asume estructura tarifaria dominicana escalonada BTS2
        consumo_mes_rd = calcular_costo_energia_rd(consumo_mes_kwh)

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

        # ------------------------------------------------------------------
        # Payback del aislamiento térmico.
        #
        # ANTES: `sobrecosto_isotex = area_m2 * 500` -- un cuarto modelo de
        # ROI, desconectado tanto del motor de presupuesto (utils/qto.py)
        # como del ROI financiero ya corregido en utils/financiera.py
        # (Fase 1 de la auditoría). El "RD$500/m² de sobrecosto por
        # aislamiento" no citaba ninguna fuente.
        #
        # Con el motor QTO, EPS/ICF sale MÁS BARATO que la construcción
        # tradicional en obra gris (ver docs/BASE_TECNICA_EPS_ICF.md), así
        # que no existe, en general, un "sobrecosto" que recuperar: el
        # ahorro es inmediato. Solo si el diferencial de costo saliera
        # negativo (EPS más caro que lo tradicional para ese proyecto
        # puntual) tendría sentido hablar de un período de recuperación.
        # ------------------------------------------------------------------
        try:
            from utils.geometria import Geometria
            from utils.pricebook import DEFAULT_PRICEBOOK
            from utils.qto import MotorQTO

            geo = Geometria(area_m2=area_m2)
            motor = MotorQTO(geo, DEFAULT_PRICEBOOK,
                             sistema="icf" if sistema.lower() == "icf" else "isotex")
            comp = motor.comparar_con_tradicional()
            diferencial_inicial = comp["tradicional"]["costo_total"] - comp["eps"]["costo_total"]
        except Exception:
            diferencial_inicial = 0.0  # no bloquear el análisis energético si el QTO falla

        if diferencial_inicial >= 0:
            roi_anios = 0.0  # sin sobrecosto: el ahorro de obra gris ya cubre la diferencia
        else:
            sobrecosto = -diferencial_inicial
            roi_anios = sobrecosto / ahorro_anual_rd if ahorro_anual_rd > 0 else float('inf')

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
    def calcular_sistema_solar_recomendado(
        cls,
        area_m2: float,
        sistema: str = "isotex",
        calidad_equipo: str = "inverter",
        cobertura_pct: float = 90.0,
        potencia_panel_w: float = 580.0,
        largo_panel_m: float = 2.28,
        ancho_panel_m: float = 1.13,
        horas_pico_sol: float = 5.5,
        perdidas_sistema_pct: float = 18.0,
        consumo_base_fijo_kwh_mes: float = 120.0,
        consumo_base_kwh_m2_mes: float = 1.2,
        incluir_baterias: bool = True,
        dias_autonomia: float = 1.0,
        capacidad_bateria_kwh: float = 5.12,
        profundidad_descarga_pct: float = 80.0,
        costo_por_watt: float = 45.0,
        costo_bateria_rd: float = 0.0,
    ) -> dict:
        """
        Calcula recomendación de sistema solar residencial.

        Args:
            area_m2: Área de construcción
            sistema: Sistema constructivo usado para estimar el consumo de AC
            calidad_equipo: Eficiencia esperada del aire acondicionado
            cobertura_pct: Porcentaje del consumo mensual que cubrirá el solar
            potencia_panel_w: Potencia nominal de cada panel fotovoltaico
            largo_panel_m/ancho_panel_m: Dimensiones físicas del panel
            horas_pico_sol: Horas sol pico diarias de referencia
            perdidas_sistema_pct: Pérdidas por temperatura, inversor, cableado y suciedad
            consumo_base_*: Consumos de nevera, iluminación, bombas, equipos y enchufes
            incluir_baterias: Si dimensiona respaldo con baterías
            dias_autonomia: Días de respaldo deseados
            capacidad_bateria_kwh: Capacidad nominal por módulo de batería
            profundidad_descarga_pct: Porcentaje útil de la batería
            costo_por_watt: Referencia editable de sistema FV instalado
            costo_bateria_rd: Referencia opcional por batería, 0 si no hay precio verificado

        Returns:
            Diccionario con specs del sistema solar recomendado
        """
        if area_m2 <= 0:
            raise ValueError("area_m2 debe ser positiva")
        if potencia_panel_w <= 0:
            raise ValueError("potencia_panel_w debe ser positiva")
        if not 1 <= cobertura_pct <= 100:
            raise ValueError("cobertura_pct debe estar entre 1 y 100")

        analisis = cls.calcular_ahorro_energetico(area_m2, sistema=sistema, calidad_equipo=calidad_equipo)

        # Consumo total estimado: aire acondicionado + cargas normales de la casa.
        consumo_base = consumo_base_fijo_kwh_mes + area_m2 * consumo_base_kwh_m2_mes
        consumo_mensual = analisis.consumo_mensual_kwh + consumo_base
        consumo_objetivo = consumo_mensual * cobertura_pct / 100.0

        factor_perdidas = max(0.50, 1 - perdidas_sistema_pct / 100.0)
        energia_panel_mes_kwh = (potencia_panel_w / 1000) * horas_pico_sol * 30 * factor_perdidas
        num_paneles = max(1, int(np.ceil(consumo_objetivo / energia_panel_mes_kwh)))
        capacidad_kw = (num_paneles * potencia_panel_w) / 1000
        energia_mensual = num_paneles * energia_panel_mes_kwh

        # El inversor se escoge desde tamaños comerciales comunes.
        potencia_ac_estimada_kw = capacidad_kw * 0.85
        tamanos_inversor_kw = [3, 5, 6, 8, 10, 12, 15, 20]
        inversor_kw = next((kw for kw in tamanos_inversor_kw if kw >= potencia_ac_estimada_kw), tamanos_inversor_kw[-1])

        area_panel_m2 = largo_panel_m * ancho_panel_m
        area_techo_requerida = num_paneles * area_panel_m2 * 1.25  # 25% para separación, pasillos y sombras
        area_techo_disponible = area_m2 * 0.70  # estimación conservadora sin plano de techo
        strings = max(1, int(np.ceil(num_paneles / 8)))
        paneles_por_string = int(np.ceil(num_paneles / strings))

        consumo_diario = consumo_mensual / 30
        energia_respaldo = consumo_diario * dias_autonomia if incluir_baterias else 0.0
        capacidad_util_bateria = capacidad_bateria_kwh * profundidad_descarga_pct / 100.0
        baterias = int(np.ceil(energia_respaldo / capacidad_util_bateria)) if energia_respaldo > 0 else 0
        banco_baterias_kwh = baterias * capacidad_bateria_kwh

        costo_total = capacidad_kw * 1000 * costo_por_watt + baterias * costo_bateria_rd
        energia_aprovechable = min(consumo_mensual, energia_mensual)
        ahorro_solar_mensual_rd = calcular_costo_energia_rd(energia_aprovechable)

        componentes = [
            {"componente": "Panel fotovoltaico", "unidad": "ud", "cantidad": num_paneles,
             "detalle": f"{potencia_panel_w:.0f} W, {largo_panel_m:.2f} x {ancho_panel_m:.2f} m"},
            {"componente": "Inversor híbrido / grid-tie", "unidad": "ud", "cantidad": 1,
             "detalle": f"{inversor_kw:.0f} kW AC recomendado"},
            {"componente": "String fotovoltaico", "unidad": "circuito", "cantidad": strings,
             "detalle": f"Hasta {paneles_por_string} paneles por string"},
            {"componente": "Estructura de techo", "unidad": "m²", "cantidad": round(area_techo_requerida, 2),
             "detalle": "Rieles, grapas, pasillos técnicos y separación"},
            {"componente": "Cable solar DC", "unidad": "ml", "cantidad": round(max(30, strings * 35), 2),
             "detalle": "Circuitos positivo/negativo desde strings al inversor"},
            {"componente": "Tablero solar AC/DC", "unidad": "ud", "cantidad": 1,
             "detalle": "Protecciones, seccionadores, SPD y breakers"},
            {"componente": "Puesta a tierra solar", "unidad": "sistema", "cantidad": 1,
             "detalle": "Barra, conductor, bonding de marcos y protección"},
        ]
        if incluir_baterias:
            componentes.append(
                {"componente": "Batería LiFePO4", "unidad": "ud", "cantidad": baterias,
                 "detalle": f"{capacidad_bateria_kwh:.2f} kWh nominal por módulo"}
            )

        previsiones_electricas = [
            "Reserva de área técnica ventilada para inversor, baterías y tablero solar.",
            "Canalización DC independiente desde techo hasta cuarto eléctrico.",
            "Canalización AC desde inversor hasta tablero principal/interconexión.",
            "Breaker dedicado para sistema fotovoltaico en tablero principal.",
            "Protección contra sobretensiones DC y AC.",
            "Seccionador visible y rotulado para mantenimiento del sistema solar.",
            "Puesta a tierra equipotencial para paneles, inversor y estructura metálica.",
            "Tablero de cargas críticas si se usarán baterías para respaldo nocturno.",
        ]

        return {
            'paneles_necesarios': num_paneles,
            'potencia_panel_w': round(potencia_panel_w, 0),
            'dimension_panel_m': f"{largo_panel_m:.2f} x {ancho_panel_m:.2f}",
            'capacidad_sistema_kw': round(capacidad_kw, 2),
            'inversor_kw': round(float(inversor_kw), 2),
            'energia_mensual_kwh': round(energia_mensual, 2),
            'consumo_ac_kwh_mes': round(analisis.consumo_mensual_kwh, 2),
            'consumo_base_kwh_mes': round(consumo_base, 2),
            'consumo_total_kwh_mes': round(consumo_mensual, 2),
            'consumo_objetivo_kwh_mes': round(consumo_objetivo, 2),
            'cobertura_objetivo_pct': round(cobertura_pct, 1),
            'autoconsumo_pct': round(min(100, (energia_mensual / consumo_mensual) * 100), 1),
            'area_techo_requerida_m2': round(area_techo_requerida, 2),
            'area_techo_disponible_m2': round(area_techo_disponible, 2),
            'area_techo_suficiente': area_techo_requerida <= area_techo_disponible,
            'strings_fv': strings,
            'paneles_por_string': paneles_por_string,
            'baterias_necesarias': baterias,
            'capacidad_bateria_kwh': round(capacidad_bateria_kwh, 2),
            'banco_baterias_kwh': round(banco_baterias_kwh, 2),
            'energia_respaldo_requerida_kwh': round(energia_respaldo, 2),
            'dias_autonomia': round(dias_autonomia, 2) if incluir_baterias else 0,
            'costo_estimado_rd': round(costo_total, 2),
            'costo_por_panel_rd': round(costo_total / num_paneles, 2),
            'ahorro_solar_mensual_rd': round(ahorro_solar_mensual_rd, 2),
            'co2_evitable_solar_kg_anio': round(energia_aprovechable * 12 * cls.KG_CO2_POR_KWH, 2),
            'componentes': componentes,
            'previsiones_electricas': previsiones_electricas,
        }

    @classmethod
    def calcular_tamano_ac_recomendado(cls, area_m2: float, sistema: str = "isotex") -> dict:
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
