#!/bin/bash
# ============================================
# IsoSmart Titanium - Inicio Rápido (Linux/Mac)
# ============================================

echo "============================================"
echo "  IsoSmart Titanium v4.0"
echo "  Iniciando aplicación..."
echo "============================================"
echo ""

# Verificar si existe el entorno virtual
if [ ! -d "venv" ]; then
    echo "[INFO] Creando entorno virtual..."
    python3 -m venv venv
    echo "[INFO] Instalando dependencias..."
    source venv/bin/activate
    pip install -r requirements.txt
    echo ""
    echo "[INFO] Instalación completada!"
    echo ""
fi

# Activar entorno virtual
source venv/bin/activate

# Ejecutar Streamlit
echo "[INFO] Iniciando servidor..."
echo ""
streamlit run app.py
