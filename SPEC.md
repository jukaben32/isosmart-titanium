# IsoSmart Titanium - Especificación de Funcionalidades

## Versión: 4.5.1

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
- Opciones de pago分期 (cuotas)
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

## 3. Módulo de Ahorro Energético (Futuro)

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

## 5. Visor BIM 3D Mejorado (Futuro)

### Mejoras
- Exportación a GLB/OBJ para Blender/AutoCAD
- Secciones transversales interactivas
- Realidad aumentada (AR) via QR
- Mediciones directas en el modelo

---

## 6. Estructura de Archivos Propuesta

```
isosmart-titanium/
├── app.py                    # Aplicación principal
├── pages/
│   ├── 1_Dashboard_Financiero.py
│   ├── 2_Calculadora.py
│   ├── 3_Visor_BIM.py
│   ├── 4_Contacto.py
├── utils/
│   ├── calculations.py      # Cálculos estructurales
│   ├── financiera.py         # Análisis financiero (NUEVO)
│   ├── energia.py            # Cálculos energéticos (NUEVO)
│   ├── __init__.py
├── requirements.txt
└── README.md
```

---

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
- **Almacenamiento**: JSON (local) / SQLite (futuro)

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
