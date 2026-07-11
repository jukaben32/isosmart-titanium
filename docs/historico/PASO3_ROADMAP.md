# ROADMAP PASO 3: PRICEBOOK DINÁMICO (FASES COMPLETAS)

## Estado Actual: ✅ FASE 1 COMPLETADA

### FASE 1: Inicialización de Session State ✅
- [x] Reemplazar inicialización estática de session_state
- [x] Crear archivo `data/pricebook.json` con precios base RD
- [x] Cargar precios al iniciar la sesión
- [x] Instanciar objeto Pricebook
- [x] Validar sintaxis Python
- [x] Commit a git

**Commit**: `8fcb33a` - feat: Inicializar session_state global con sincronización de precios

---

## PRÓXIMAS FASES

### FASE 2: Panel de Control de Precios (Paso 3B) ⏳

**Objetivo**: Agregar pestaña interactiva en la UI para editar precios dinámicamente

**Tareas**:
1. Crear función `render_pestana_configuracion_precios()` en `app.py`
2. Dividir en dos sub-pestañas:
   - `🏗️ Estructura y Obra Gris` (Panel, Hormigón, Acero)
   - `🎨 Terminaciones y Acabados` (Cerámica, Pintura, Baños)
3. Inputs de número para cada material
4. Botones de acción:
   - `💾 Guardar Cambios` → `write_json_atomic()`
   - `🔄 Recargar Valores por Defecto`
   - `📋 Ver JSON Completo`
5. Sincronizar cambios con session_state
6. Validación de valores mínimos

**Código proporcionado en**: `PROMPT_PASO3_COMPLETO.md` (sección PASO 3B)

---

### FASE 3: Integrar Llamadas al Calculador (Paso 3C) ⏳

**Objetivo**: Reemplazar todas las llamadas a `BudgetCalculator` para usar precios dinámicos

**Tareas**:
1. Buscar **TODAS** las ocurrencias de `calcular_presupuesto_completo()`
2. Agregar parámetro `precios=st.session_state["precios_sincronizados"]`
3. Actualizar `utils/financiera.py` para pasar precios dinámicos
4. Buscar usos de `PRECIOS_BASE` estático y reemplazar
5. Validar que presupuestos reflejan cambios de precios

**Búsqueda regex**: `calcular_presupuesto_completo\(`

**Ficheros afectados**:
- `app.py` (varias secciones)
- `utils/financiera.py` (función `comparar_financiero_densidades`)
- `utils/presupuesto.py` (si existe)

---

### FASE 4: Correcciones de Bugs (Paso 3D) ⏳

**Objetivo**: Arreglar bug conocido de desperdicio de hormigón

**Tareas**:
1. Reemplazar clase `BudgetCalculator` estática
2. Cambiar: `vol_hormigon *= (1 + desperdicio_panel)` 
3. Por: `vol_hormigon *= (1 + desperdicio_hormigon)`
4. Validar desperdicio_hormigon = 0.08 (8%)
5. Validar desperdicio_panel = 0.05 (5%)
6. Ejecutar test de presupuesto completo

**Código proporcionado en**: `PROMPT_PASO3_COMPLETO.md` (sección PASO 3A - BudgetCalculator)

---

## 📋 CHECKLIST DE IMPLEMENTACIÓN

### Antes de empezar Fase 2:
- [ ] Leer `docs/PASO3_SESSION_STATE_INTEGRATION.md`
- [ ] Verificar que `data/pricebook.json` existe
- [ ] Ejecutar: `streamlit run app.py` (sin errores)
- [ ] Confirmar que session_state se inicializa

### Antes de empezar Fase 3:
- [ ] Completar Fase 2
- [ ] Verificar que panel de precios funciona
- [ ] Cambiar un precio y guardar
- [ ] Confirmar que `data/pricebook.json` se actualizó

### Antes de empezar Fase 4:
- [ ] Completar Fase 3
- [ ] Generar presupuesto con nuevos precios
- [ ] Verificar que presupuesto refleja cambios
- [ ] Ejecutar `python -m py_compile` en todo código nuevo

---

## 🎬 FLUJO DE TRABAJO POR FASE

### FASE 2 - Workflow:
```bash
# 1. Agregar función render_pestana_configuracion_precios()
#    (código completo en PROMPT_PASO3_COMPLETO.md sección PASO 3B)

# 2. Integrar en el menú de pestañas (buscar st.tabs(...))
#    tab_config = st.tab("⚙️ Configuración de Precios")
#    with tab_config:
#        render_pestana_configuracion_precios()

# 3. Validar sintaxis
python -m py_compile app.py

# 4. Probar en navegador
streamlit run app.py

# 5. Commit
git add . && git commit -m "feat: Agregar panel de control interactivo de precios (Paso 3B)"
```

### FASE 3 - Workflow:
```bash
# 1. Buscar todas las llamadas a calcular_presupuesto_completo()
grep -n "calcular_presupuesto_completo" app.py utils/*.py

# 2. Reemplazar cada ocurrencia:
#    ANTES: BudgetCalculator.calcular_presupuesto_completo(m2, sistema, ...)
#    DESPUÉS: BudgetCalculator.calcular_presupuesto_completo(
#                m2=m2, 
#                sistema=sistema,
#                precios=st.session_state["precios_sincronizados"],  # ← NUEVO
#                ...)

# 3. Validar y commit
python -m py_compile app.py utils/financiera.py
git add . && git commit -m "feat: Actualizar llamadas a BudgetCalculator con precios dinámicos (Paso 3C)"
```

### FASE 4 - Workflow:
```bash
# 1. Reemplazar clase BudgetCalculator completa
#    (código en PROMPT_PASO3_COMPLETO.md sección PASO 3A)

# 2. Cambiar PRECIOS_BASE → parámetro precios
# 3. Arreglar bug de desperdicio_hormigon

# 4. Validar
python -m py_compile app.py

# 5. Probar presupuesto
streamlit run app.py

# 6. Commit
git add . && git commit -m "fix: Corregir BudgetCalculator y bug de desperdicio hormigón (Paso 3D)"
```

---

## 🧪 TESTING POR FASE

### Después de Fase 1 (YA HECHO):
```python
import streamlit as st
import os
from utils.storage import read_json

# Verificar que pricebook cargó
st.write(st.session_state["precios_sincronizados"])
st.write(f"Total de items: {len(st.session_state['precios_sincronizados'])}")
```

### Después de Fase 2:
```python
# 1. Ir a pestaña "⚙️ Configuración de Precios"
# 2. Cambiar "Panel Isotex Muro" a 950
# 3. Click "💾 Guardar Cambios"
# 4. Verificar:
#    os.path.exists("data/pricebook.json")  # True
#    read_json("data/pricebook.json")["Panel_Muro"]  # 950.0
```

### Después de Fase 3:
```python
# 1. Calcular presupuesto normal
# 2. Ir a precios y cambiar uno
# 3. Calcular nuevo presupuesto
# 4. Verificar que subtotal del material cambió
# 5. Costo total debe ser diferente
```

### Después de Fase 4:
```bash
# 1. Crear presupuesto para 100m², Isotex
# 2. Verificar: vol_hormigon ≈ 33.6 m³ (con 8% desperdicio)
# 3. NO debe ser 32 m³ (sin desperdicio correcto)
# 4. Subtotal hormigón = vol_hormigon * precio
```

---

## 📚 REFERENCIAS

| Archivo | Sección | Contenido |
|---------|---------|-----------|
| `PROMPT_PASO3_COMPLETO.md` | PASO 3A | Clase BudgetCalculator refactorizada |
| `PROMPT_PASO3_COMPLETO.md` | PASO 3B | Función panel de precios |
| `PROMPT_PASO3_COMPLETO.md` | PASO 3C | Cómo integrar llamadas dinámicas |
| `PROMPT_PASO3_COMPLETO.md` | PASO 3D | Correcciones de bugs |
| `docs/PASO3_SESSION_STATE_INTEGRATION.md` | Fase 1 | Detalles de inicialización (YA HECHO) |
| `data/pricebook.json` | - | Matriz de precios (YA CREADO) |

---

## 🚀 ORDEN SUGERIDO

1. ✅ **FASE 1** (HOY) - Inicialización Session State
2. ⏳ **FASE 2** (PRÓXIMO) - Panel de Control
3. ⏳ **FASE 3** - Integrar Llamadas
4. ⏳ **FASE 4** - Corregir Bugs

**Cada fase debe testearse completamente antes de pasar a la siguiente.**

---

**Notas finales**:
- Si hay dudas en alguna fase, revisar `PROMPT_PASO3_COMPLETO.md`
- Todos los cambios son quirúrgicos (no rompen código existente)
- Los tests de validación están listados en cada fase
- Los commits son atómicos y descriptivos
