# -*- coding: utf-8 -*-
"""
Módulo de cálculos avanzados para IsoSmart Titanium
"""

import math
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class TipoSistema(Enum):
    ISOTEX = "isotex"
    ICF = "icf"


class TipoElemento(Enum):
    VIGA = "viga"
    COLUMNA = "columna"
    LOSA = "losa"
    MURO = "muro"


@dataclass
class ResultadoCalculo:
    cantidad: float
    unidad: str
    costo_unitario: float
    costo_total: float
    descripcion: str


class CalculadoraEstructural:
    """Cálculos estructurales para construcción con EPS"""

    # Factores técnicos basados en normas
    FACTOR_SEGURIDAD = 1.5
    RESISTENCIA_EPS_20 = 200  # kPa
    RESISTENCIA_CONCRETO_3000 = 20.7  # MPa

    @staticmethod
    def calcular_carga_muerta(area: float, tipo_losa: str) -> float:
        """
        Calcula carga muerta en kg/m²

        Args:
            area: Área en m²
            tipo_losa: 'isotex' o 'icf'

        Returns:
            Carga muerta total en kg
        """
        cargas_por_m2 = {
            'isotex': 180,  # kg/m² (panel + concreto + acabado)
            'icf': 220,     # kg/m² (mayor espesor de concreto)
            'convencional': 350
        }

        carga_unitaria = cargas_por_m2.get(tipo_losa.lower(), 200)
        return area * carga_unitaria

    @staticmethod
    def calcular_carga_viva(area: float, uso: str) -> float:
        """
        Calcula carga viva según uso del inmueble

        Args:
            area: Área en m²
            uso: 'vivienda', 'comercial', 'industrial'

        Returns:
            Carga viva total en kg
        """
        cargas_vivas = {
            'vivienda': 150,      # kg/m² (norma típica)
            'comercial': 250,
            'industrial': 500,
            'azotea': 100
        }

        carga_unitaria = cargas_vivas.get(uso.lower(), 150)
        return area * carga_unitaria

    @staticmethod
    def calcular_espesor_losa(luz_maxima: float, tipo: str) -> float:
        """
        Calcula espesor mínimo de losa en cm

        Args:
            luz_maxima: Luz máxima en metros
            tipo: 'isotex' o 'icf'

        Returns:
            Espesor en cm
        """
        if tipo.lower() == 'isotex':
            # L/20 para losas aligeradas
            espesor = (luz_maxima * 100) / 20
        elif tipo.lower() == 'icf':
            # L/25 para ICF
            espesor = (luz_maxima * 100) / 25
        else:
            espesor = (luz_maxima * 100) / 20

        return max(espesor, 12)  # Mínimo 12 cm

    @staticmethod
    def calcular_acero_losa(area: float, luz: float) -> Dict[str, float]:
        """
        Calcula acero de refuerzo para losa

        Args:
            area: Área en m²
            luz: Luz máxima en metros

        Returns:
            Diccionario con cantidades de acero
        """
        # Acero principal (varilla #3 o #4)
        acero_principal_kg = area * 4.5  # kg/m² típico

        # Acero de temperatura
        acero_temp_kg = area * 1.5

        # Acero adicional por luz
        acero_adicional = 0
        if luz > 4:
            acero_adicional = area * 2.0

        total_kg = acero_principal_kg + acero_temp_kg + acero_adicional

        return {
            'acero_principal_kg': round(acero_principal_kg, 2),
            'acero_temperatura_kg': round(acero_temp_kg, 2),
            'acero_adicional_kg': round(acero_adicional, 2),
            'total_kg': round(total_kg, 2),
            'barras_6m': round(total_kg / 5.5, 1),  # Varilla #3 de 6m ≈ 5.5kg
            'barras_12m': round(total_kg / 11, 1)   # Varilla #3 de 12m ≈ 11kg
        }

    @staticmethod
    def calcular_volumen_concreto(area_muros: float, area_losa: float,
                                  espesor_muro: float = 0.12,
                                  espesor_losa: float = 0.12) -> Dict[str, float]:
        """
        Calcula volumen de concreto necesario

        Args:
            area_muros: Área de muros en m²
            area_losa: Área de losa en m²
            espesor_muro: Espesor de muro en metros
            espesor_losa: Espesor de losa en metros

        Returns:
            Diccionario con volúmenes en m³
        """
        volumen_muros = area_muros * espesor_muro
        volumen_losa = area_losa * espesor_losa
        volumen_total = volumen_muros + volumen_losa

        # Factor de desperdicio (8%)
        factor_desperdicio = 1.08

        return {
            'volumen_muros_m3': round(volumen_muros, 2),
            'volumen_losa_m3': round(volumen_losa, 2),
            'volumen_total_m3': round(volumen_total, 2),
            'volumen_con_desperdicio': round(volumen_total * factor_desperdicio, 2),
            'bolsas_cemento': round(volumen_total * 7, 0),  # ~7 bolsas por m³
            'viajes_concretero': math.ceil(volumen_total / 3)  # Camión estándar ≈ 3m³
        }


class CalculadoraMateriales:
    """Cálculo detallado de materiales"""

    @staticmethod
    def calcular_materiales_muro(area_muros: float, sistema: str) -> Dict[str, float]:
        """
        Calcula materiales necesarios para muros

        Args:
            area_muros: Área de muros en m²
            sistema: 'isotex' o 'icf'

        Returns:
            Diccionario con cantidades de materiales
        """
        resultados = {}

        if sistema.lower() == 'isotex':
            # Paneles Isotex estándar (1.2m x 3m = 3.6m²)
            panel_area = 3.6
            num_paneles = math.ceil(area_muros / panel_area * 1.05)  # 5% desperdicio

            resultados.update({
                'paneles_isotex': num_paneles,
                'area_paneles_m2': round(num_paneles * panel_area, 2),
                'malla_electrosoldada_m2': round(area_muros * 1.1, 2),  # 10% traslape
                'conectores_metolicos': num_paneles * 4,
                'perfileria_ml': round(area_muros ** 0.5 * 4, 2)  # Perímetro
            })

        elif sistema.lower() == 'icf':
            # Bloques ICF estándar
            bloques_por_m2 = 0.85  # Bloques por m² de muro
            num_bloques = math.ceil(area_muros * bloques_por_m2 * 1.03)  # 3% desperdicio

            resultados.update({
                'bloques_icf': num_bloques,
                'conectores_icf': num_bloques * 2,
                'rieles_superior_inferior_ml': round(area_muros ** 0.5 * 4 * 1.05, 2),
                'cintas_adhesiva_rollos': math.ceil(area_muros / 50)  # 1 rollo por 50m²
            })

        return resultados

    @staticmethod
    def calcular_acabados(area_construida: float, area_muros: float) -> Dict[str, float]:
        """
        Calcula materiales de acabados

        Args:
            area_construida: Área construida en m²
            area_muros: Área de muros en m²

        Returns:
            Diccionario con cantidades
        """
        # Yeso o drywall para interiores
        area_interior = area_construida * 2.5  # Factor aproximado

        # Pintura (2 manos + imprimación)
        rendimiento_pintura = 10  # m² por galón
        galones_pintura = area_muros / rendimiento_pintura * 3  # 3 manos

        # Piso (cerámica/vinil)
        area_piso = area_construida * 1.05  # 5% desperdicio

        return {
            'pintura_galones': round(galones_pintura, 1),
            'imprimacion_galones': round(area_muros / 15, 1),
            'piso_ceramica_m2': round(area_piso, 2),
            'pegamento_piso_sacos': round(area_piso / 20, 1),  # 1 saco por 20m²
            'fragüe_piso_sacos': round(area_piso / 25, 1),
            'yeso_sacos': round(area_interior / 15, 1),  # 1 saco por 15m²
            'masilla_sacos': round(area_muros / 30, 1)
        }


def calcular_costo_unitario_compuesto(materiales: Dict[str, Tuple[float, float]]) -> float:
    """
    Calcula costo unitario compuesto

    Args:
        materiales: Diccionario {nombre: (cantidad, precio_unitario)}

    Returns:
        Costo total
    """
    total = 0
    for nombre, (cantidad, precio) in materiales.items():
        total += cantidad * precio
    return total


# ============================================================================
# PRUEBAS RÁPIDAS
# ============================================================================

if __name__ == "__main__":
    # Ejemplo de uso
    calc = CalculadoraEstructural()

    area = 120
    luz = 5

    print(f"=== Cálculos para {area}m² ===")
    print(f"Carga muerta: {calc.calcular_carga_muerta(area, 'isotex')} kg")
    print(f"Carga viva: {calc.calcular_carga_viva(area, 'vivienda')} kg")
    print(f"Espesor losa: {calc.calcular_espesor_losa(luz, 'isotex')} cm")
    print(f"Acero losa: {calc.calcular_acero_losa(area, luz)}")

    calc_mat = CalculadoraMateriales()
    print(f"\nMateriales muro: {calc_mat.calcular_materiales_muro(area * 2.2, 'isotex')}")
