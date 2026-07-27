# IsoSmart Titanium - Especificación de Funcionalidades

## Versión: 4.6.0 — actualizado 2026-07-26

> Este documento describía una aplicación que no existía: proponía una estructura
> de archivos (`pages/2_Calculadora.py`, `pages/3_Visor_BIM.py`...) que nunca se
> implementó. La sección 6 refleja ahora el árbol real del repositorio.

---

## 1. Problema de Despliegue en Vercel

**Causa**: Vercel es una plataforma optimizada para aplicaciones frontend (Next.js, React, etc.). Streamlit es un framework Python que requiere un servidor Python personalizado.

**Solución recomendada**: Desplegar en **Streamlit Cloud** (gratuito) o **HuggingFace Spaces** (gratuito).

---

## 2. Dashboard Financiero Avanzado (Nueva Funcionalidad)

### Objetivo
Proporcionar análisis financieros profundos para la toma de decisiones en proyectos de construcción con sistemas ISOTEX/ICF.

### Funcionalidades

#### 2.1 Análisis de ROI (Retorno sobre Inversión)
- **ROI a 5, 10, 15, 20 años**
- Comparación del costo total de propiedad (TCO)
- Beneficio neto considerando ahorro energético y mantenimiento

#### 2.2 Análisis de Sensibilidad
- Variación de costos según área del proyecto (50m² - 1000m²)
- Impacto de fluctuación de precios de materiales (±10%, ±20%)
- Comparación de costos por densidad de panel (15kg, 20kg, 25kg)

#### 2.3 Proyección de Costos de Ciclo de Vida
- Costos iniciales de construcción
- Costos de mantenimiento estimado (anual)
- Costos de energía (aire acondicionado, iluminación)
- Costos de seguros y depreciación

#### 2.4 Análisis de Financiamiento
- Opciones de pago en cuotas
- Estimación de costos de financiamiento bancario
- Cash flow projection para construcción en fases

#### 2.5 Gráficos Avanzados
- Gráfico de barras: Costo por categoría de material
- Gráfico de líneas: Proyección de ROI a lo largo del tiempo
- Gráfico de áreas: Comparativa de costos acumulados Isotex vs Tradicional
- Heatmap: Sensibilidad de costos vs área
- Gráfico radar: Comparativa multidimensional de sistemas

### Datos de Entrada
- Área de construcción (m²)
- Sistema constructivo (Isotex / ICF / Tradicional)
- Calidad de terminados (económica / media / alta / lujo)
- Tasa de financiamiento (%)
- Horizonte de inversión (años)

### Métricas de Salida
- **ROI nominal y anualizado**
- **Período de recuperación de inversión (payback)**
- **Valor Actual Neto (VAN)** con tasa de descuento configurable
- **Tasa Interna de Retorno (TIR)** comparada
- **Costo Total de Propiedad (TCO)**
- **Ahorro acumulado vs construcción tradicional**

---

## 3. Módulo de Ahorro Energético — ✅ implementado (`utils/energia.py`)

### Funcionalidades
- Cálculo de carga térmica del edificio
- Estimación de consumo de aire acondicionado (kWh/mes)
- Ahorro comparado con construcción tradicional
- Retorno de inversión en aislamiento térmico

---

## 4. Módulo de Impacto Ambiental (Futuro)

### Funcionalidades
- Huella de carbono comparada (kg CO2/m²)
- Energía embebida de materiales
- Beneficios de eficiencia energética

---

## 5. Visor BIM 3D Mejorado (pendiente)

### Mejoras
- Exportación a GLB/OBJ para Blender/AutoCAD
- Secciones transversales interactivas
- Realidad aumentada (AR) via QR
- Mediciones directas en el modelo

---

## 6. Estructura de Archivos (real)

```
isosmart-titanium/
├── app.py                       # Router ÚNICO de navegación
├── ui_core.py                   # Helpers compartidos, ProjectManager
├── ui_inicio.py  ui_team.py  ui_calculadora.py
├── ui_presupuesto.py  ui_visor_bim.py  ui_vision.py
│
├── paginas/                     # Páginas enrutadas desde app.py
│   ├── dashboard_financiero.py
│   └── analisis_energetico.py
├── pages/                       # Streamlit multipágina (solo el CRM protegido)
│   └── 3_Admin_Leads.py
│
├── utils/                       # Dominio puro — SIN Streamlit
│   ├── dominio.py               # Enums: Sistema, Calidad, ZonaRiesgo
│   ├── geometria.py             # Geometría del proyecto (perímetro, niveles...)
│   ├── parametros.py            # Carga de parametros_tecnicos.yaml
│   ├── qto.py                   # ★ Motor de cantidades (fuente de verdad)
│   ├── calculador.py            # Motor clásico (legado, en retirada)
│   ├── pricebook.py  catalog.py
│   ├── financiera.py  energia.py  tarifa.py
│   ├── vision.py  plan_geometry.py  ai_text_design.py  ai_media.py
│   ├── pdf_propuesta.py         # PDF sin dependencia de Streamlit
│   ├── repositorio.py           # SQLite / Supabase
│   ├── estado.py                # ProyectoState (session_state unificado)
│   ├── estilos.py               # Hoja de estilos compartida
│   └── storage.py  pdf_utils.py
│
├── data/
│   ├── pricebook.json           # Precios (39 materiales)
│   └── parametros_tecnicos.yaml # ★ Espesores, rendimientos, mallas
│
├── tests/                       # 87 tests (pytest)
├── docs/BASE_TECNICA_EPS_ICF.md # ★ Fuente técnica del motor QTO
├── AUDITORIA.md                 # Informe de auditoría 2026-07-26
├── .streamlit/estilos.css
├── .github/workflows/ci.yml     # ruff + pytest
└── pyproject.toml
```

### Principio arquitectónico

`utils/` **no importa Streamlit**. Esa regla es lo que permite ejecutar y validar
el motor de presupuesto sin levantar la interfaz, y es la razón por la que el
bug del PDF pasó años sin detectarse: `PDFGenerator` vivía dentro de `ui_core.py`.

Excepciones toleradas y acotadas: `vision.py`, `ai_text_design.py` y `ai_media.py`
usan `st.cache_data`; `estado.py` y `estilos.py` importan Streamlit de forma
diferida, dentro de las funciones.

## 6.b Motor de cantidades (QTO)

Implementa `docs/BASE_TECNICA_EPS_ICF.md`. Reemplaza progresivamente a
`utils/calculador.py`.

```python
from utils.geometria import Geometria
from utils.qto import MotorQTO

geo   = Geometria(area_m2=120, perimetro_m=44, altura_muro_m=2.8, niveles=1)
motor = MotorQTO(geo, precios, sistema="Paneles Isotex", calidad="media")

motor.presupuesto()              # DataFrame de partidas con trazabilidad
motor.resumen_por_categoria()
motor.comparar_con_tradicional() # gris vs gris (27.5%), NO gris vs terminada
motor.partidas_por_verificar()   # precios que aún son referencia
```

**Objetivo de precisión:** ±5% frente al costo ejecutado. Requiere sustituir los
precios de referencia por cotizaciones de proveedor.

## 7. API de Datos

### Endpoints Internos (funciones Python)

```python
# Análisis Financiero
def calcular_roi(area_m2, sistema, calidad, horizonte_anios):
    """Retorna métricas de ROI y payback"""

def analizar_sensibilidad(area_min, area_max, paso):
    """Retorna DataFrame con análisis de sensibilidad"""

def proyectar_flujo_caja(area_m2, sistema, tasa_descuento, horizonte):
    """Retorna proyección de flujos anuales"""

# Energía
def calcular_carga_termica(area_m2, sistema):
    """Retorna carga térmica en BTU/h"""

def estimar_consumo_energia(area_m2, sistema):
    """Retorna consumo mensual en kWh y costo RD$"""
```

---

## 8. Tech Stack

- **Framework**: Streamlit
- **Gráficos**: Plotly
- **Datos**: Pandas, NumPy
- **PDF**: ReportLab, FPDF
- **Almacenamiento**: SQLite (`utils/repositorio.py`) / Supabase opcional

---

## 9. Deployment

### Opción Recomendada: Streamlit Cloud
1. Subir código a GitHub
2. Conectar en [streamlit.io/cloud](https://streamlit.io/cloud)
3. Seleccionar repositorio y rama
4. Configurar secrets (API keys)
5. Deploy automático

### Alternativa: HuggingFace Spaces
1. Crear Space en huggingface.co
2. Subir código
3. Runtime: Docker con Python

### Alternativa: Railway/Render
1. Crear archivo `Procfile` o `runtime.txt`
2. Configurar build command: `pip install -r requirements.txt`
3. Start command: `streamlit run app.py --server.port=$PORT`
