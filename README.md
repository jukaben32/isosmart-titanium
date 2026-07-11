# 🏗️ IsoSmart Titanium v4.5

**Sistema Inteligente de Presupuestos y Visualización BIM para Construcción con Poliestireno Expandido**

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.32+-FF4B4B.svg)](https://streamlit.io)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Paso%204%20%E2%9C%85-brightgreen.svg)]()
[![Last Updated](https://img.shields.io/badge/Updated-2026--07--10-blue.svg)]()

---

## 📋 Descripción

IsoSmart Titanium es una aplicación profesional para la industria de la construcción que permite:

- 📐 **Cálculo automático** de presupuestos para sistemas Isotex e ICF
- 🏠 **Visualización BIM 3D** interactiva de estructuras
- 🤖 **Asistente IA** integrado para consultas técnicas
- 📄 **Generación de PDF** con propuestas comerciales detalladas
- 💾 **Gestión de proyectos** con historial y exportación

## 🚀 Características Principales

### Módulo 3D BIM
- Visualización de muros, techos y estructuras
- Capas eléctricas y sanitarias configurables
- Exportación a formatos CAD

### Motor de Presupuestos (Paso 3 ✅)
- **Precios Dinámicos**: Sincronización en tiempo real desde `data/pricebook.json`
- Cálculo automático de materiales y residuos
- Integración con proveedores (Cemex, Isotex)
- Panel de control para actualizar precios
- Exportación a Excel y PDF
- **27 materiales base** del mercado RD actualizados

### Asistente IA
- Análisis de planos con Visión (Google Gemini)
- Recomendaciones técnicas
- Cálculo de cantidades
- Generación de títulos y contenido de marketing

### Sistema de Estados Global
- Session state centralizado para múltiples capas
- Sincronización de precios entre módulos
- Persistencia en JSON atómico
- Escalable y mantenible

## 📊 Estado del Proyecto

| Módulo | Estado | Detalles |
|--------|--------|----------|
| Paso 1: Canvas + Visión IA | ✅ Completado | Análisis de planos, cálculo de áreas |
| Paso 2: Motor Financiero RD | ✅ Completado | Análisis de densidades, comparativas |
| Paso 3A: Session State Global | ✅ Completado | Inicialización de precios dinámicos |
| Paso 3B: Panel de Precios | ✅ Completado | Edición interactiva de costos |
| Paso 3C: Integración de Llamadas | ✅ Completado | Calculadora unificada en `utils/calculador.py` |
| Paso 3D: Correcciones de Bugs | ✅ Completado | Fix desperdicio hormigón y equipos AC |
| **Paso 4: Refactor + Tests** | **✅ Completado** | **UI modular (`ui_*.py`), 23 tests, cacheo de APIs** |

## 📦 Instalación

```bash
# Clonar repositorio
git clone https://github.com/jukaben32/isosmart-titanium.git
cd isosmart-titanium

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar aplicación
streamlit run app.py
```

## 🔑 Configuración

### Variables de Entorno

Crea un archivo `.env` en la raíz del proyecto:

```env
GEMINI_API_KEY=tu_api_key_aqui
DEFAULT_CURRENCY=RD$
COMPANY_NAME=Tu Empresa
```

### Precios Base (data/pricebook.json)

La aplicación carga automáticamente los precios desde `data/pricebook.json`:

```json
{
  "Panel_Muro": 925.00,
  "Panel_Techo": 1125.00,
  "H_3000_PSI": 7350.00,
  "H_3500_PSI": 7950.00,
  "Acero_Varilla": 85.00,
  ...
}
```

**Para modificar precios**: Usa el panel "⚙️ Configuración de Precios" en la aplicación.

## 📖 Uso

1. **Configuración del Proyecto**: Ingresa los datos del cliente y área en m²
2. **Selección de Sistema**: Elige entre Paneles Isotex o ICF Proform
3. **Visualización 3D**: Explora el modelo BIM en la pestaña "Visor BIM 3D"
4. **Análisis IA**: Consulta con el asistente sobre aspectos técnicos
5. **Análisis de Precios**: Configura costos desde la pestaña "⚙️ Configuración"
6. **Presupuesto**: Genera cotización con precios dinámicos y descarga el PDF

## 📚 Documentación

### Guías de uso
- [Instalación](docs/INSTALACION.md) - Puesta en marcha paso a paso
- [Resumen del proyecto](docs/RESUMEN.md) - Visión general

### Histórico de desarrollo
- [Bitácoras del Paso 3](docs/historico/) - Roadmap y resúmenes de implementación del pricebook dinámico

## 🏛️ Arquitectura

La interfaz está **modularizada por dominio** (refactor Paso 4) para facilitar el mantenimiento:

```
app.py              → Solo orquestación y navegación (main)
ui_core.py          → Helpers compartidos (PDF, Gemini, keys, sincronización)
ui_inicio.py        → Página de inicio
ui_calculadora.py   → Calculadora, plano estructural, contacto, config precios
ui_visor_bim.py     → Visor 3D BIM
ui_presupuesto.py   → Pricebook, presupuesto y ROI
ui_team.py          → Página de equipo
ui_vision.py        → Módulo de visión artificial
utils/calculador.py → BudgetCalculator (única fuente de verdad de precios)
utils/financiera.py → Análisis financiero RD (ROI, VAN, TIR)
utils/energia.py    → Análisis energético (tarifa BTS2, ahorro térmico)
```

## 🧪 Testing

La lógica de negocio está protegida por **23 tests** (sin dependencia de Streamlit):

```bash
python tests/comparar_calculadoras.py   # Regresión de precios
python tests/test_financiera.py         # ROI, VAN, TIR, financiamiento
python tests/test_energia.py            # Consumo, ahorro, dimensionado AC
```

## 🛠️ Tecnologías

- **Frontend**: Streamlit
- **Visualización 3D**: Plotly
- **IA**: Google Gemini
- **PDF**: ReportLab / FPDF
- **Datos**: Pandas
- **Almacenamiento**: JSON atómico con `write_json_atomic()`

## 📄 Licencia

MIT License - ver archivo [LICENSE](LICENSE) para más detalles.

## 👤 Autor

**jukaben32**

## 🤝 Contribuciones

Las contribuciones son bienvenidas. Por favor:

1. Fork el repositorio
2. Crea una rama (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

---

<p align="center">
  <strong>Construyendo el futuro con tecnología inteligente</strong>
</p>
