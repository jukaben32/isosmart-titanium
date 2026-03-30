# 🏗️ IsoSmart Titanium v4.0

**Sistema Inteligente de Presupuestos y Visualización BIM para Construcción con Poliestireno Expandido**

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.32+-FF4B4B.svg)](https://streamlit.io)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

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

### Motor de Presupuestos
- Precios actualizables del mercado dominicano
- Cálculo automático de materiales
- Integración con proveedores (Cemex, Isotex)
- Exportación a Excel y PDF

### Asistente IA
- Análisis de planos
- Recomendaciones técnicas
- Cálculo de cantidades

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

### Secrets de Streamlit

Para producción, configura `.streamlit/secrets.toml`:

```toml
[gemini]
api_key = "tu_api_key"

[precios]
panel_muro = 925.00
panel_techo = 1125.00
hormigon_3000 = 7350.00
hormigon_3500 = 7950.00
```

## 📖 Uso

1. **Configuración del Proyecto**: Ingresa los datos del cliente y área en m²
2. **Selección de Sistema**: Elige entre Paneles Isotex o ICF Proform
3. **Visualización 3D**: Explora el modelo BIM en la pestaña "Visor BIM 3D"
4. **Análisis IA**: Consulta con el asistente sobre aspectos técnicos
5. **Presupuesto**: Genera cotización y descarga el PDF

## 🛠️ Tecnologías

- **Frontend**: Streamlit
- **Visualización 3D**: Plotly
- **IA**: Google Gemini
- **PDF**: ReportLab / FPDF
- **Datos**: Pandas

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
