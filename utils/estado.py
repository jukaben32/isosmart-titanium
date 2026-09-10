"""
utils/estado.py
---------------
Estado del proyecto en sesión: **una sola fuente de verdad**.

PROBLEMA QUE RESUELVE
=====================
La app mantenía DOS familias de claves paralelas para los mismos conceptos:

    calc_area_m2      /  plan_area_m2
    calc_perimetro_m  /  plan_perimetro_m
    calc_niveles      /  plan_niveles
    calc_altura_muro_m/  plan_altura_muro_m
    calc_espesor_muro_m/ plan_espesor_muro_m

Se escribían desde sitios distintos (canvas, Gemini, Text-to-Design, formularios)
y divergían sin que nadie lo notara. No había contrato, ni validación, ni
inicialización central: `st.session_state` se usaba como variables globales.

DISEÑO
======
`ProyectoState` es una dataclass validada. `cargar()` y `guardar()` la
sincronizan con `st.session_state`, manteniendo las claves `calc_*` como espejo
para no romper el código existente mientras dura la migración. Las claves
`plan_*` quedan como alias de LECTURA: se siguen leyendo si existen, pero ya no
se escriben.

Uso:
    from utils.estado import ProyectoState

    estado = ProyectoState.cargar()
    estado.aplicar_metricas({"area_m2": 180, "perimetro_m": 58}, origen="Gemini")
    estado.guardar()

    geo = estado.geometria()      # -> utils.geometria.Geometria
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Any, Dict, Optional

from .dominio import Calidad, Sistema, ZonaRiesgo, normalizar_calidad, normalizar_sistema, normalizar_zona_riesgo
from .geometria import Geometria

# Rangos de saneamiento. Un valor fuera de rango se recorta y se deja constancia
# en `avisos`, en vez de propagarse silenciosamente hasta el presupuesto.
RANGOS = {
    "area_m2": (10.0, 100_000.0),
    "perimetro_m": (4.0, 5_000.0),
    "altura_muro_m": (2.2, 6.0),
    "espesor_muro_m": (0.08, 0.30),
    "niveles": (1, 20),
}

# Claves antiguas que se siguen leyendo por compatibilidad (solo lectura).
_ALIAS_LECTURA = {
    "area_m2": ("calc_area_m2", "plan_area_m2"),
    "perimetro_m": ("calc_perimetro_m", "plan_perimetro_m"),
    "altura_muro_m": ("calc_altura_muro_m", "plan_altura_muro_m"),
    "espesor_muro_m": ("calc_espesor_muro_m", "plan_espesor_muro_m"),
    "niveles": ("calc_niveles", "plan_niveles"),
}

CLAVE_ESTADO = "proyecto_state"


def _clamp(valor: float, minimo: float, maximo: float) -> float:
    return max(minimo, min(maximo, valor))


@dataclass
class ProyectoState:
    """Parámetros del proyecto que sobreviven entre reruns de Streamlit."""

    area_m2: float = 120.0
    perimetro_m: float | None = None
    altura_muro_m: float = 2.80
    espesor_muro_m: float = 0.12
    niveles: int = 1

    sistema: str = Sistema.ISOTEX.value
    calidad: str = Calidad.MEDIA.value
    zona_riesgo: str = ZonaRiesgo.MODERADO.value

    cliente: str = ""
    origen_metricas: str = ""          # de dónde salieron las dimensiones
    avisos: list = field(default_factory=list)

    # -- programa de ambientes --------------------------------------------
    # Antes: Geometria SOLO podía estimar puertas/ventanas/baños por área
    # (geometria_defecto.yaml, una fórmula genérica). Si un lead ya
    # describió su casa ("3 dormitorios, 2 con baño"), eso es un dato real,
    # no una estimación -- este bloque lo transporta hasta Geometria.
    n_dormitorios: int | None = None
    n_banos: int | None = None          # dormitorios_con_bano + banos_comunes
    n_puertas_interiores: int | None = None
    n_puertas_exteriores: int | None = None
    n_ventanas: int | None = None
    esquinas: int | None = None
    ml_cocina: float | None = None
    ancho_ventana_m: float = 0.90
    alto_ventana_m: float = 0.90
    ancho_puerta_m: float = 0.90
    alto_puerta_m: float = 2.15
    instalaciones_detalle: dict = field(default_factory=dict)
    habitaciones: list = field(default_factory=list)  # para el esquema de planta

    # ------------------------------------------------------------------
    # Validación
    # ------------------------------------------------------------------
    def sanear(self) -> ProyectoState:
        """
        Recorta valores fuera de rango y anota lo que tocó.

        Los avisos se acumulan sin duplicar: `aplicar_metricas()` registra los
        suyos antes de llamar aquí, y un `self.avisos = []` los borraba.
        """
        previos = list(self.avisos)
        self.avisos = []

        for campo in ("area_m2", "altura_muro_m", "espesor_muro_m"):
            minimo, maximo = RANGOS[campo]
            valor = float(getattr(self, campo))
            recortado = _clamp(valor, minimo, maximo)
            if recortado != valor:
                self.avisos.append(
                    f"{campo}: {valor:g} fuera del rango [{minimo:g}, {maximo:g}], ajustado a {recortado:g}"
                )
            setattr(self, campo, recortado)

        minimo, maximo = RANGOS["niveles"]
        niveles = int(self.niveles)
        if not (minimo <= niveles <= maximo):
            self.avisos.append(f"niveles: {niveles} fuera de [{minimo}, {maximo}]")
        self.niveles = int(_clamp(niveles, minimo, maximo))

        if self.perimetro_m is not None:
            minimo, maximo = RANGOS["perimetro_m"]
            valor = float(self.perimetro_m)
            recortado = _clamp(valor, minimo, maximo)
            if recortado != valor:
                self.avisos.append(f"perimetro_m: {valor:g} ajustado a {recortado:g}")
            self.perimetro_m = recortado

        # Vocabulario del dominio: normaliza o falla ruidosamente.
        self.sistema = normalizar_sistema(self.sistema).value
        self.calidad = normalizar_calidad(self.calidad).value
        self.zona_riesgo = normalizar_zona_riesgo(self.zona_riesgo).value

        # Preserva los avisos previos, sin repetirlos.
        vistos = set()
        self.avisos = [a for a in previos + self.avisos
                       if not (a in vistos or vistos.add(a))]
        return self

    # ------------------------------------------------------------------
    # Sincronización con st.session_state
    # ------------------------------------------------------------------
    @classmethod
    def cargar(cls, estado: dict[str, Any] | None = None) -> ProyectoState:
        """
        Reconstruye el estado desde `st.session_state`.

        Si no existe todavía, migra desde las claves sueltas `calc_*` / `plan_*`
        que dejó la versión anterior, para no perder lo que el usuario ya había
        introducido.
        """
        estado = cls._estado(estado)

        guardado = estado.get(CLAVE_ESTADO)
        if isinstance(guardado, dict):
            validos = {f.name for f in fields(cls)}
            return cls(**{k: v for k, v in guardado.items() if k in validos}).sanear()

        # Migración desde las claves antiguas.
        datos: dict[str, Any] = {}
        for campo, alias in _ALIAS_LECTURA.items():
            for clave in alias:
                if estado.get(clave):
                    datos[campo] = estado[clave]
                    break
        if estado.get("calidad_terminados"):
            datos["calidad"] = estado["calidad_terminados"]

        instancia = cls(**datos) if datos else cls()
        return instancia.sanear()

    def guardar(self, estado: dict[str, Any] | None = None) -> ProyectoState:
        """Persiste en `st.session_state` y refresca el espejo `calc_*`."""
        estado = self._estado(estado)
        self.sanear()

        estado[CLAVE_ESTADO] = {f.name: getattr(self, f.name) for f in fields(self)}

        # Espejo de compatibilidad: los módulos aún no migrados siguen leyendo
        # estas claves. Se escriben desde aquí, nunca al revés.
        estado["calc_area_m2"] = self.area_m2
        estado["calc_perimetro_m"] = self.perimetro_m
        estado["calc_altura_muro_m"] = self.altura_muro_m
        estado["calc_espesor_muro_m"] = self.espesor_muro_m
        estado["calc_niveles"] = self.niveles
        estado["calidad_terminados"] = self.calidad
        return self

    @staticmethod
    def _estado(estado: dict[str, Any] | None) -> dict[str, Any]:
        if estado is not None:
            return estado
        import streamlit as st

        return st.session_state

    # ------------------------------------------------------------------
    # Entrada de métricas desde visión / IA / formularios
    # ------------------------------------------------------------------
    def aplicar_metricas(self, datos: dict[str, Any] | None, origen: str = "") -> ProyectoState:
        """
        Inyecta métricas extraídas de un plano, de Gemini o del canvas.

        Sustituye a `sincronizar_parametros_globales()`, que escribía cinco
        claves de `session_state` que nadie leía nunca.
        """
        if not datos:
            return self

        mapeo = {
            "area_m2": "area_m2",
            "perimetro_m": "perimetro_m",
            "niveles": "niveles",
            "altura_muro_m": "altura_muro_m",
            "espesor_muro_m": "espesor_muro_m",
            "ventanas": "n_ventanas",
            "puertas_interiores": "n_puertas_interiores",
            "puertas_exteriores": "n_puertas_exteriores",
            "banos": "n_banos",
            "esquinas": "esquinas",
            "ml_cocina": "ml_cocina",
            "ancho_ventana_m": "ancho_ventana_m",
            "alto_ventana_m": "alto_ventana_m",
            "ancho_puerta_m": "ancho_puerta_m",
            "alto_puerta_m": "alto_puerta_m",
        }
        for origen_clave, destino in mapeo.items():
            valor = datos.get(origen_clave)
            if valor is None or valor == "":
                continue
            try:
                if destino in {
                    "niveles",
                    "n_ventanas",
                    "n_puertas_interiores",
                    "n_puertas_exteriores",
                    "n_banos",
                    "esquinas",
                }:
                    setattr(self, destino, int(round(float(valor))))
                else:
                    setattr(self, destino, float(valor))
            except (TypeError, ValueError):
                self.avisos.append(f"{origen_clave}: valor no numérico ignorado ({valor!r})")

        if datos.get("calidad_terminados"):
            try:
                self.calidad = normalizar_calidad(datos["calidad_terminados"]).value
            except ValueError:
                self.avisos.append(f"calidad no reconocida, se mantiene {self.calidad}")

        # -- programa de ambientes (asistente Texto -> Diseño) ---------------
        # Reemplaza estimaciones genéricas por conteos reales cuando el
        # usuario ya los dio explícitamente en su descripción.
        dormitorios = datos.get("dormitorios")
        if dormitorios is not None:
            self.n_dormitorios = int(dormitorios)
            # Puertas interiores: una por dormitorio + una por baño privado,
            # como mínimo -- sigue siendo una aproximación (no cuenta closets,
            # pasillos, etc.) pero ya no depende del área sino del programa real.
            self.n_puertas_interiores = int(dormitorios) + int(
                datos.get("dormitorios_con_bano") or 0
            )

        dormitorios_con_bano = datos.get("dormitorios_con_bano") or 0
        banos_comunes = datos.get("banos_comunes") or 0
        if datos.get("dormitorios_con_bano") is not None or datos.get("banos_comunes") is not None:
            self.n_banos = int(dormitorios_con_bano) + int(banos_comunes)

        if datos.get("dormitorios") is not None:
            # Una ventana por dormitorio + una por cada ambiente social
            # declarado explícitamente (cocina/sala/comedor) -- aproximación
            # razonable, mejor que "tantas por cada 100 m²" cuando ya
            # sabemos qué ambientes existen.
            ventanas = int(dormitorios)
            for clave in ("tiene_cocina", "tiene_sala_estar", "tiene_comedor"):
                if datos.get(clave):
                    ventanas += 1
            self.n_ventanas = ventanas

        if isinstance(datos.get("habitaciones"), list) and datos["habitaciones"]:
            self.habitaciones = datos["habitaciones"]

        if isinstance(datos.get("instalaciones_detalle"), dict):
            self.instalaciones_detalle = datos["instalaciones_detalle"]

        if origen:
            self.origen_metricas = origen
        return self.sanear()

    # ------------------------------------------------------------------
    # Salida
    # ------------------------------------------------------------------
    def geometria(self) -> Geometria:
        """Convierte el estado en el modelo geométrico que consume el motor QTO."""
        return Geometria(
            area_m2=self.area_m2,
            perimetro_m=self.perimetro_m,
            altura_muro_m=self.altura_muro_m,
            niveles=self.niveles,
            esquinas=self.esquinas,
            banos=self.n_banos,
            puertas_exteriores=self.n_puertas_exteriores,
            puertas_interiores=self.n_puertas_interiores,
            ventanas=self.n_ventanas,
            ml_cocina=self.ml_cocina,
            ancho_ventana_m=self.ancho_ventana_m,
            alto_ventana_m=self.alto_ventana_m,
            ancho_puerta_m=self.ancho_puerta_m,
            alto_puerta_m=self.alto_puerta_m,
        )

    def a_dict(self) -> dict[str, Any]:
        return {f.name: getattr(self, f.name) for f in fields(self)}
