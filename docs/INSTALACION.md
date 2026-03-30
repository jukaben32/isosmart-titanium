# 📖 Guía de Instalación - IsoSmart Titanium

## Requisitos Previos

- Python 3.9 o superior
- pip (gestor de paquetes de Python)
- Conexión a internet (para API de Gemini)

## Paso 1: Verificar Python

Abre una terminal y ejecuta:

```bash
python --version
```

Debería mostrar Python 3.9 o superior. Si no tienes Python instalado:

1. Descarga desde https://python.org/downloads
2. Durante la instalación, marca "Add Python to PATH"

## Paso 2: Clonar o Descargar el Proyecto

### Opción A - Con Git:
```bash
git clone https://github.com/jukaben32/isosmart-titanium.git
cd isosmart-titanium
```

### Opción B - Sin Git:
1. Descarga el ZIP desde GitHub
2. Extrae en una carpeta
3. Abre terminal en esa carpeta

## Paso 3: Crear Entorno Virtual (Recomendado)

### Windows:
```bash
python -m venv venv
venv\Scripts\activate
```

### Mac/Linux:
```bash
python3 -m venv venv
source venv/bin/activate
```

## Paso 4: Instalar Dependencias

```bash
pip install -r requirements.txt
```

Esto instalará:
- Streamlit (interfaz web)
- Pandas (datos)
- Plotly (gráficos 3D)
- google-generativeai (IA)
- fpdf2 (PDFs)
- reportlab (documentos)
- openpyxl (Excel)

## Paso 5: Configurar API Key (Opcional)

Para usar el asistente IA:

1. Ve a https://makersuite.google.com/app/apikey
2. Crea una API Key gratuita
3. En la app, ingresa la key en la barra lateral

## Paso 6: Ejecutar la Aplicación

```bash
streamlit run app.py
```

La aplicación se abrirá automáticamente en tu navegador en:
`http://localhost:8501`

## Solución de Problemas

### Error: "streamlit: command not found"
```bash
pip install --upgrade streamlit
```

### Error: "No module named 'plotly'"
```bash
pip install plotly
```

### La app no abre automáticamente
Abre manualmente: `http://localhost:8501`

### Error de permisos en Windows
Ejecuta la terminal como Administrador

## Actualización

Para actualizar la aplicación:

```bash
git pull origin main
pip install -r requirements.txt --upgrade
```

## Próximos Pasos

1. Explora las 4 pestañas principales
2. Configura los precios en la pestaña "Configuración"
3. Guarda tu primer proyecto
4. Genera tu primera propuesta PDF

---

**¿Necesitas ayuda?** Abre un issue en GitHub: https://github.com/jukaben32/isosmart-titanium/issues
