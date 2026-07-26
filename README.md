# 🏗️ IsoSmart Titanium v4.6

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
| Paso 1: Canvas + Visión IA | ✅ | Análisis de planos, cálculo de áreas |
| Paso 2: Motor Financiero RD | ✅ | ROI, VAN, TIR |
| Paso 3: Pricebook dinámico | ✅ | Precios editables, persistencia atómica |
| Paso 4: Refactor UI modular | ✅ | `ui_*.py` por dominio |
| **Paso 5: Auditoría — P0/P1** | **✅** | **Bloqueantes cerrados, seguridad, CI, 75 tests** |
| **Paso 6: Motor QTO (Fase 1)** | **🟡 En curso** | **Partidas completas; faltan precios de proveedor** |
| Paso 7: Migración total al QTO | ⬜ | Retirar `utils/calculador.py` legado |

### Correcciones de la auditoría (2026-07-26)

Ver [`AUDITORIA.md`](AUDITORIA.md) para el informe completo. Resumen de lo cerrado:

**Bloqueantes**
- `st_canvas` sin importar en `ui_calculadora.py` y `ui_vision.py` (7 usos) → dos páginas
  reventaban con `NameError` al subir un plano.
- **La generación de PDF nunca funcionó**: `output(dest='S').encode('latin-1')` lanza
  `AttributeError` con fpdf2 ≥ 2.7, que devuelve `bytearray`.
- `sistema_sel` no existía → el envío de cotizaciones por correo fallaba siempre.

**Cálculo**
- La calidad **"económica"** (con tilde) cotizaba igual que "media": el motor buscaba
  "economica" y `.get(x, default)` degradaba en silencio. Ahora hay `Enum` + validación
  estricta en `utils/dominio.py`.
- **ROI con el signo invertido**: cuando EPS salía más barato, el ahorro inicial se
  trataba como un desembolso. VAN, TIR y payback se calculaban sobre una inversión
  inexistente.
- **Tres modelos energéticos incompatibles** (divergencia de 36× para la misma casa).
  Unificados en `AnalisisEnergetico`; la tarifa vive en `utils/tarifa.py`.

**Seguridad**
- `ADMIN_PASSWORD` caía a `admin123`: un despliegue sin variable exponía el CRM completo.
  Ahora sin fallback, con `hmac.compare_digest` y límite de intentos.
- `data/leads_db.json` no estaba en `.gitignore` → riesgo de publicar PII de clientes.
- Los leads se perdían en cada reinicio de Streamlit Cloud → `utils/repositorio.py`
  (SQLite / Supabase).

## 🧾 Motor de cantidades (QTO)

`utils/qto.py` implementa `docs/BASE_TECNICA_EPS_ICF.md`. Diferencias con el motor
clásico (`utils/calculador.py`, aún disponible):

| | Motor clásico | Motor QTO |
|---|---|---|
| Superficie de muro | `m² × 2.2` (constante) | perímetro × altura × niveles |
| Mortero | 12 cm de concreto | 2.5 cm por cara ([doc]) |
| Paneles | 5% de merma plana | modulación real a 1.22 m |
| Mallas, anclas, cimentación | ausentes | incluidas |
| Instalaciones, baños, cocina, mano de obra | ausentes | incluidas |
| Obra terminada | 9.6% del total | ~46% del total |
| Comparación | gris EPS vs **terminada** tradicional → 83.6% fijo | **gris vs gris** → 27.5% ([doc]) |

```python
from utils.geometria import Geometria
from utils.qto import MotorQTO

geo = Geometria(area_m2=120, perimetro_m=44, altura_muro_m=2.8, niveles=1)
motor = MotorQTO(geo, calidad="media")

motor.presupuesto()              # DataFrame de partidas
motor.comparar_con_tradicional() # gris vs gris
motor.partidas_por_verificar()   # precios que aún son referencia
```

> ⚠️ **Los precios de las partidas nuevas son de REFERENCIA, no cotizaciones.**
> `motor.partidas_por_verificar()` los identifica y la interfaz lo advierte.
> Sustituirlos por precios de proveedor es lo que falta para alcanzar el objetivo
> de ±5% frente a obra ejecutada.

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

```bash
pip install pytest ruff
pytest                                  # 75 tests
ruff check --select F821,F811 .         # errores bloqueantes
python tests/comparar_calculadoras.py   # regresión del motor clásico
```

| Archivo | Cubre |
|---|---|
| `tests/test_qto.py` | Motor de cantidades, geometría, comparación gris vs gris |
| `tests/test_auditoria_regresiones.py` | Un test por cada bug de la auditoría |
| `tests/test_financiera.py` | ROI, VAN, TIR, financiamiento |
| `tests/test_energia.py` | Carga térmica, consumo, dimensionado AC |
| `tests/test_calculations.py` | Cálculos estructurales |
| `tests/test_ai_text_design.py` | Parseo de respuestas de Gemini |

CI en `.github/workflows/ci.yml`: `ruff` + `pytest` en cada push. El chequeo `F821`
es bloqueante — es el que habría atrapado los siete `st_canvas` sin importar.

## 🛠️ Tecnologías

- **Frontend**: Streamlit
- **Visualización 3D**: Plotly
- **IA**: Google Gemini
- **PDF**: ReportLab / FPDF
- **Datos**: Pandas
- **Almacenamiento**: SQLite por defecto, Supabase opcional (`utils/repositorio.py`)

## 🚀 Despliegue en Streamlit Community Cloud

La app está lista para desplegarse gratis en [Streamlit Community Cloud](https://streamlit.io/cloud):

1. Sube este repositorio a tu GitHub (ya está en `jukaben32/isosmart-titanium`).
2. En [share.streamlit.io](https://share.streamlit.io) (o el nuevo portal de Streamlit Cloud):
   - **Repository**: `jukaben32/isosmart-titanium`
   - **Branch**: `main`
   - **Main file path**: `app.py`
3. (Opcional) En *Advanced settings → Secrets*, agrega tu API key de Gemini para activar el asistente IA:
   ```toml
   GEMINI_API_KEY = "tu_api_key_aqui"
   ```
4. Deploy y listo. La app carga los precios desde `data/pricebook.json` automáticamente.

> Nota: las funciones de IA (Gemini/Fal/Luma) requieren sus respectivas API keys.
> Sin ellas la app funciona en modo presupuesto/visor; solo se desactivan las llamadas a IA.

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
