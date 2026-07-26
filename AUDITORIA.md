# Auditoría arquitectónica y estructural — IsoSmart Titanium v4.5

**Repositorio:** `jukaben32/isosmart-titanium` (rama `main`, commit `5d19ad1`)
**Alcance:** 30 archivos Python, ~6,480 LOC, Streamlit + Plotly + Gemini
**Fecha:** 26 de julio de 2026
**Método:** clonado del repo, análisis estático (pyflakes), ejecución de la suite de tests, y ejecución numérica del motor de cálculo con casos reales (60 / 120 / 300 m²).

---

## 0. Veredicto ejecutivo

El proyecto tiene **buena intención arquitectónica** y decisiones acertadas que hay que preservar: motor de presupuesto desacoplado de Streamlit (`utils/calculador.py`), escritura atómica de JSON (`write_json_atomic`), separación de UI por dominio, y un `docs/BASE_TECNICA_EPS_ICF.md` que es oro puro — el autor ya diagnosticó el problema central antes que yo.

Pero hoy la app **no es desplegable como herramienta comercial**, por tres razones independientes:

| # | Problema | Severidad |
|---|---|---|
| 1 | **Tres páginas fallan con `NameError`** en cuanto el usuario sube una imagen | 🔴 Bloqueante |
| 2 | **La generación de PDF está 100% rota** con la versión de `fpdf2` que instala `requirements.txt` | 🔴 Bloqueante |
| 3 | **El presupuesto subestima el costo real ~3–4×** y afirma un ahorro constante del 83.6% | 🔴 Riesgo de negocio |

El #3 es el más grave y el menos visible: la app no se cae, simplemente **entrega cifras equivocadas con apariencia profesional**. Una cotización 3× baja entregada a un cliente en PDF es un pasivo comercial y legal, no un bug.

La buena noticia: la corrección de #3 ya está escrita por el propio autor en `docs/BASE_TECNICA_EPS_ICF.md`. Solo falta implementarla.

---

## 1. Bloqueantes — la app se rompe en producción (P0)

### 1.1 `st_canvas` no está definido en los módulos que lo usan

El refactor "Paso 4" copió el bloque de imports de `app.py` a cada `ui_*.py`, **pero no el `try/except` que importa `st_canvas`**. Ese import quedó solo en `app.py`:

```python
# app.py — línea 60. Único sitio donde existe.
try:
    from streamlit_drawable_canvas import st_canvas
except Exception:
    st_canvas = None
```

Y sin embargo se usa en 7 sitios de otros dos archivos:

```
ui_calculadora.py:100, 118, 764, 773, 793, 827, 846   → undefined name 'st_canvas'
ui_vision.py:95, 111                                   → undefined name 'st_canvas'
```

La ironía es que el código *intenta* protegerse:

```python
if st_canvas is None:            # ← NameError aquí mismo, antes de poder comparar
    st.error("El componente `streamlit-drawable-canvas` no está instalado.")
    return
```

**Impacto:** las páginas *Plano → Estructura* y *Panel Operativo* revientan en cuanto el usuario sube un plano. Es exactamente el flujo estrella de la app.

**Fix (2 minutos):** mover el bloque `try/except` a `ui_core.py` y hacer `from ui_core import st_canvas` en `ui_calculadora.py` y `ui_vision.py`.

### 1.2 `render_integradora_vision_canvas` no está importada en `ui_presupuesto.py`

```
ui_presupuesto.py:144: undefined name 'render_integradora_vision_canvas'
```

La pestaña "📐 Visión & Geometría" del Panel Operativo la llama sin importarla. `NameError` garantizado.

### 1.3 El generador de PDF está roto (verificado en ejecución)

```python
# ui_core.py:161
return self.pdf.output(dest='S').encode('latin-1')
```

En `fpdf2 >= 2.7`, `output()` devuelve un `bytearray`, no un `str`. Lo verifiqué instalando lo que instala tu `requirements.txt` (`fpdf2>=2.7.0` → resuelve a 2.8.7):

```
tipo devuelto por output(dest="S"): <class 'bytearray'>
*** FALLA: AttributeError 'bytearray' object has no attribute 'encode'
```

**Impacto:** ningún cliente ha recibido nunca un PDF de esta app. Además esto rompe en cascada el envío por correo (Resend), porque el PDF se genera antes de armar el email.

**Fix:**
```python
return bytes(self.pdf.output())
```

De paso: `set_font('Arial', ...)` está deprecado (fpdf2 lo sustituye por Helvetica y avisa), el parámetro `ln=True` está deprecado desde 2.2.0 (usar `new_x`/`new_y`), y `latin-1` habría explotado igual ante cualquier carácter fuera de ese charset (un cliente llamado "Peña Ñúñez" con una comilla tipográfica, un emoji pegado en un campo de texto). Migrar a `bytes(self.pdf.output())` + fuente TTF Unicode resuelve las tres cosas.

### 1.4 `sistema_sel` no existe (envío de correo)

```python
# ui_calculadora.py:516
"html": f"<p>...sistema {sistema_sel}.</p>",   # NameError
```

La variable correcta en ese scope es `sistema_seleccionado`. Está dentro de un `try/except Exception`, así que no tumba la app pero **el envío de correo nunca funciona**: siempre muestra "❌ Excepción: name 'sistema_sel' is not defined".

### 1.5 La calidad "económica" se ignora silenciosamente

```python
# pages/1_Dashboard_Financiero.py:299
calidad = st.selectbox("🎨 Calidad", ["económica", "media", "alta", "lujo"])   # con tilde
```
```python
# utils/calculador.py:164
factores = {"economica": 0.8, "media": 1.0, "alta": 1.5, "lujo": 2.5}          # sin tilde
```

`.get(calidad, 1.0)` no falla: devuelve el factor de "media". Verificado:

```
economica    -> RD$ 1,478,009
económica    -> RD$ 1,493,009   ← idéntico a "media"
media        -> RD$ 1,493,009
```

Este es el patrón más peligroso de todo el código: **strings mágicos comparados con `.get(x, default)`**. Cualquier desalineación produce un número plausible y equivocado, sin traza. Aparece también en `sistema == "Paneles Isotex"` (comparación exacta contra un literal, cualquier variante cae al `else` de ICF) y en `zona_riesgo`. La solución estructural es `Enum` o `Literal` + validación explícita que **lance excepción** ante un valor desconocido.

### 1.6 Función duplicada

`sincronizar_parametros_globales` está definida dos veces en `ui_core.py` (líneas 366 y 377). La primera es código muerto que Python descarta en silencio. Alguien mantendrá la equivocada.

### 1.7 Un archivo de tests está roto

`tests/test_ai_text_design.py` falla con `KeyError: 'estilo_arquitectura'`. El README anuncia "23 tests ✅"; en realidad una de las cinco suites no corre.

---

## 2. La integridad del cálculo — el problema real del negocio (P0)

Esta sección es la razón por la que escribí la auditoría en este orden. Los `NameError` se arreglan en una tarde. Esto no.

### 2.1 El presupuesto está incompleto en ~75%

Ejecuté el motor para una casa de 120 m², sistema Isotex, calidad media, precios por defecto:

```
OBRA GRIS
  Paneles Isotex (Muros)      277.20 m²      256,410
  Paneles Isotex (Techo)      138.60 m²      155,925
  Hormigón Cemex 3000 PSI      51.32 m³      377,214
  Cimentación Armada           18.00 m³      158,760
  Vigas H Estructurales      3,000.00 kg     315,000
  Acero de Refuerzo          1,020.00 kg      86,700
                                          ───────────
                              subtotal     1,350,009   (11,250 RD$/m²)

OBRA TERMINADA
  Cerámica/Porcelanato          108.0 m²       48,600
  Pintura Interior/Exterior      22.0 gal      26,400
  Puertas Interiores              8.0 ud       68,000
                                          ───────────
                              subtotal       143,000   (1,192 RD$/m²)

TOTAL: RD$ 1,493,009  →  12,442 RD$/m²
```

**La obra terminada es el 9.6% del presupuesto.** En una vivienda real es el 35–50%. Aquí faltan, en su totalidad:

instalación eléctrica · instalación sanitaria y agua potable · ventanas · puertas exteriores · cocina (gabinetes, mesón, fregadero) · baños (inodoros, lavamanos, duchas, grifería) · impermeabilización de azotea · mortero de acabado de muros · cielo raso · closets · **mano de obra** · transporte · dirección técnica · permisos.

12,442 RD$/m² para una vivienda terminada en República Dominicana no es un presupuesto ajustado: es un presupuesto que **omite tres cuartas partes de la obra**.

### 2.2 18 de los 27 materiales del pricebook nunca se usan

```
Claves en pricebook: 27
Usadas por el motor:  9  (Panel_Muro, Panel_Techo, H_3000_PSI, H_3500_PSI,
                          Viga_H_kg, Acero_Varilla, Ceramica_m2,
                          Pintura_galon, Puerta_interior)
Nunca usadas:        18  (Inodoro, Lavamanos, Ducha, Griferia_bano,
                          Ventana_aluminio_m2, Gabinete_cocina_ml,
                          Meson_granito_ml, Fregadero_cocina, Yeso_saco,
                          Malla_Electrosoldada, Poliestireno_EPS, Fibra_Acero,
                          Aditivo_Impermeabilizante, Cemento_Saco, Arena_m3,
                          Piedra_m3, Ladrillo_unidad, Porcelanato_m2)
```

El usuario puede editar el precio del inodoro en el panel de precios, guardarlo, ver el mensaje "¡Libro de precios sincronizado!"… y el presupuesto no cambia en un peso. Es una promesa de interfaz que el motor no cumple.

*Bonus:* el código tiene `"Ladrillounidad"` (`utils/pricebook.py:24`) y el JSON tiene `"Ladrillo_unidad"`. Como `Pricebook.load()` hace merge, el diccionario resultante tiene **28 claves con dos variantes del mismo material**. Nadie lo nota porque ninguna de las dos se usa.

### 2.3 El "83.6% de ahorro" compara peras con manzanas

```
--- 60 m² ---   Isotex 12,442 RD$/m²  vs  Tradicional 60,000 RD$/m²  →  83.6%
--- 120 m² ---  Isotex 12,442 RD$/m²  vs  Tradicional 60,000 RD$/m²  →  83.6%
--- 300 m² ---  Isotex 12,442 RD$/m²  vs  Tradicional 60,000 RD$/m²  →  83.6%
```

El porcentaje es **constante para cualquier área**, lo que delata que no es un cálculo: es el cociente de dos constantes. El lado "tradicional" es una matriz hardcodeada (`35,000 + 25,000 = 60,000 RD$/m²` para calidad media) que sí incluye obra terminada completa; el lado Isotex es una obra gris incompleta.

Tu propio `docs/BASE_TECNICA_EPS_ICF.md` ya lo dice con precisión quirúrgica:

> ⚠️ El "83%" viejo comparaba obra gris EPS vs obra TERMINADA tradicional (peras con manzanas). Corregir a comparación gris vs gris.
> **EPS/ICF ahorra 20-40% en OBRA GRIS** (no en acabados, que son iguales en ambos sistemas). **Default sugerido: 27.5%**.

Implementa eso. Un 27.5% verificable vende mejor que un 83% que cualquier maestro constructor descarta en diez segundos.

### 2.4 Los espesores de concreto contradicen tu propia base técnica

```python
vol_hormigon = (area_muros + area_techo) * 0.12 * (1 + 0.08)   # calculador.py:90
```

0.12 m de concreto sobre muros **y** techo. Tu documento técnico dice:

- Muro: **2.5 cm de mortero por cara** → 0.05 m total
- Losa azotea: **5 cm** de capa de compresión
- Losa entrepiso: 6–7 cm

Con los valores correctos: `277.2 × 0.05 + 138.6 × 0.05 ≈ 20.8 m³`. El código calcula **51.3 m³**. Sobreestima el concreto en ~2.5× (RD$ 377,214 vs ~RD$ 153,000 reales). Curiosamente, este error compensa parcialmente las partidas faltantes — lo cual es peor, porque hace que el total parezca menos absurdo de lo que es.

### 2.5 Vigas H de acero: 3,000 kg en una casa de paneles EPS

`kg_vigas = m2 * 25` → 25 kg/m² de perfil A36, activado **por defecto** (`incluir_vigas=True`). Son RD$ 315,000, el 23% del presupuesto, en un sistema constructivo cuyo argumento de venta es precisamente **no necesitar estructura de acero**. O el parámetro debería estar en `False` por defecto, o debería estar gobernado por la luz libre / número de niveles, no por el área.

### 2.6 Toda la extracción geométrica se escribe en un agujero negro

Este es el hallazgo arquitectónico más importante de la auditoría.

La app tiene tres vías para obtener la geometría del proyecto: canvas con calibración de escala, visión Gemini sobre el plano, y Text-to-Design. Las tres terminan llamando a `sincronizar_parametros_globales()`, que escribe:

```python
st.session_state["calc_perimetro_m"]    = ...
st.session_state["calc_niveles"]        = ...
st.session_state["calc_altura_muro_m"]  = ...
st.session_state["calc_espesor_muro_m"] = ...
```

Busqué quién **lee** esas claves en todo el repositorio:

```
$ grep -rn "calc_perimetro_m|calc_niveles|calc_altura_muro_m|calc_espesor_muro_m" .
ui_core.py:374   → escritura
ui_core.py:391   → escritura
ui_core.py:393   → escritura
ui_core.py:395   → escritura
ui_core.py:397   → escritura
```

**Cinco escrituras. Cero lecturas.** El motor no las acepta siquiera:

```python
def calcular_presupuesto_completo(cls, m2, sistema, precios, incluir_vigas=True,
                                  calidad_terminados="media",
                                  espesor_muro_m=0.12,      # ← recibido y jamás usado
                                  zona_riesgo="Moderado (Base)"):
```

En su lugar usa `area_muros = m2 * 2.2`, una constante. Es decir: el usuario calibra la escala, traza el polígono, la IA lee las cotas… y el presupuesto sale del mismo `m2 × 2.2` que habría salido escribiendo el área a mano. **Toda la capa de visión artificial es decorativa.**

Y `zona_riesgo` — el factor sísmico/huracán, un diferenciador genuino para RD — nunca se pasa desde ningún llamador. Siempre corre en "Moderado (Base)". Código muerto disfrazado de feature.

### 2.7 Tres modelos energéticos incompatibles conviviendo

Para la **misma** casa de 120 m², los tres módulos que calculan ahorro energético responden:

| Módulo | Consumo tradicional | Ahorro mensual |
|---|---|---|
| `financiera.AnalisisFinanciero` | 5,400 kWh/mes | **RD$ 36,936** |
| `financiera.AnalisisFinancieroRD` | 510 kWh/mes | **RD$ 5,522** |
| `energia.AnalisisEnergetico` | ~270 kWh/mes | **RD$ 1,022** |

Un factor de **36× entre el primero y el tercero**, en el mismo repositorio, sobre el mismo input.

Peor: el que alimenta el ROI del Dashboard es el primero, y es el menos defendible. 5,400 kWh/mes (45 kWh/m²/mes × 120) implica una factura eléctrica de RD$ 43,779 mensuales. Una vivienda dominicana típica de 120 m² consume 300–800 kWh/mes. El modelo está inflado ~8×, y ese número inflado es el que produce el ROI que ve el cliente.

### 2.8 El modelo de ROI tiene el signo invertido

```python
inversion_inicial = costo_tradicional - costo_total_isotex
if inversion_inicial < 0:
    inversion_inicial = costo_total_isotex - costo_tradicional   # se voltea
flujos.append(-inversion_inicial)                                # siempre negativo
```

Ambas ramas producen un flujo negativo en el año 0. Traducido: **si Isotex es más barato, el modelo trata el ahorro inicial como si fuera un desembolso**. El VAN, la TIR y el payback se calculan sobre una inversión que no existe. Detalles adicionales:

- `flujos.append(flujo_anual * anio if anio == 1 else flujo_anual)` — `× 1` cuando `anio == 1`. Es un no-op residual de alguna versión anterior; deja la intención ilegible.
- `payback` se inicializa en `horizonte_anios`, así que un proyecto que nunca se recupera reporta "payback = 10 años" en lugar de ∞.
- `roi_anualizado` se fuerza a `0` si `payback >= horizonte`, ocultando un ROI negativo detrás de un cero neutro.
- El TCO no incluye energía, pese a que `SPEC.md` la lista como componente.

### 2.9 Los tests fijan el error en lugar de detectarlo

`tests/comparar_calculadoras.py` verifica que 120 m² dé exactamente `RD$ 1,493,008.76`. Pasa ✅. Pero ese número es precisamente el que está mal. El test garantiza que **el error no cambie nunca**.

Es un test de regresión sin test de validación. Falta la otra mitad: comparar contra presupuestos reales ejecutados. El objetivo que tú mismo fijaste en `BASE_TECNICA` es ±5% del costo ejecutado — eso es un test, y es el único que importa.

---

## 3. Arquitectura (P1)

### 3.1 El refactor "modular" duplicó el acoplamiento

Los siete `ui_*.py` empiezan con **el mismo bloque idéntico de ~50 líneas de imports**. `pyflakes` reporta **379 avisos**, de los cuales ~356 son imports sin usar. `ui_inicio.py` — una página estática de marketing — importa Plotly, Gemini, FPDF, PIL, el calculador financiero, el módulo energético y trece helpers de `ui_core`. Usa cero.

Esto no es cosmético:

- **Arranque lento y frágil:** cada página carga `google.generativeai`, `plotly`, `PIL` y `fitz` aunque no los toque. En Streamlit Cloud (1 GB de RAM en el tier gratuito) esto importa.
- **Falsa señal de dependencia:** es imposible saber qué necesita realmente cada módulo, así que nadie se atreve a borrar nada.
- **Ocultó el bug 1.1:** el bloque copiado *parecía* completo, y por eso nadie notó que faltaba `st_canvas`.

Módulos como `ui_inicio.py` y `ui_team.py` deberían tener exactamente un import: `import streamlit as st`.

### 3.2 Cuatro fuentes de verdad para los precios

| Ubicación | Contenido |
|---|---|
| `utils/pricebook.py::DEFAULT_PRICEBOOK` | 27 items — el canónico |
| `data/pricebook.json` | 27 items (con una clave desalineada) |
| `ui_presupuesto.py:60` | 8 items hardcodeados |
| `pages/1_Dashboard_Financiero.py:319` | 8 items hardcodeados |

Existe una clase `Pricebook` con `load()`, `save()` y escritura atómica. `render_pestana_pricebook()` la ignora y usa `open(ruta, "w")` + `json.dump` directo — sin `encoding="utf-8"` (rompe en Windows con cp1252), sin validación, sin atomicidad. Toda la infraestructura correcta existe y está sin conectar.

### 3.3 Dos namespaces paralelos de estado

`calc_area_m2` / `plan_area_m2`, `calc_perimetro_m` / `plan_perimetro_m`, `calc_niveles` / `plan_niveles`… El mismo concepto en dos familias de claves que se escriben desde sitios distintos y divergen. No hay contrato, no hay validación, no hay inicialización central. `st.session_state` se está usando como variables globales.

### 3.4 Navegación duplicada

`app.py` implementa un menú propio con `st.radio` (7 páginas). A la vez existe `pages/`, que Streamlit convierte automáticamente en navegación multipágina (3 páginas más). El usuario ve **dos sistemas de navegación simultáneos con contenidos distintos**, y las páginas de `pages/` no comparten el estado que construye el menú de `app.py` — el Dashboard Financiero pide el área otra vez con un slider propio.

Hay que elegir uno. Con `st.navigation` / `st.Page` (Streamlit ≥ 1.36) se puede tener un router único y programático.

### 3.5 `SPEC.md` describe una app distinta

La estructura propuesta en `SPEC.md` (`pages/2_Calculadora.py`, `pages/3_Visor_BIM.py`, `pages/4_Contacto.py`) no corresponde con la realidad. También contiene un residuo de traducción automática: *"Opciones de pago分期 (cuotas)"* — caracteres chinos en la especificación. Detalle menor, pero es el documento que un colaborador nuevo lee primero.

---

## 4. Seguridad y datos (P1)

### 4.1 Contraseña de administrador por defecto

```python
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")  # Fallback a admin123
```

Y `.env.example` lo publica: `ADMIN_PASSWORD=admin123`.

Si se despliega sin definir la variable, **cualquiera con la URL accede al CRM completo de leads**: nombres, correos, teléfonos, ubicaciones de clientes. En Streamlit Cloud la página aparece listada en la barra lateral para todo visitante.

Además: comparación de strings en texto plano (vulnerable a timing, aunque sea marginal aquí), sin rate limiting, sin bloqueo tras N intentos, sin expiración de sesión.

**Mínimo aceptable:** sin variable definida → la página se niega a cargar (`st.stop()`), nunca un fallback. Mejor: hash con `hmac.compare_digest`, o directamente `st.secrets` + el sistema de autenticación nativo de Streamlit.

### 4.2 Los leads (PII) pueden terminar en el repositorio público

`ProjectManager` escribe `data/leads_db.json` y `data/projects_db.json`. El `.gitignore` **no los excluye**:

```
$ git check-ignore -v data/leads_db.json
(sin salida) → NO IGNORADO
```

Un `git add .` desde la máquina donde se probó la app publica datos personales de clientes en un repositorio público. Añadir ya:

```gitignore
data/leads_db.json
data/projects_db.json
data/*_db.json
```

### 4.3 Persistencia en disco efímero

Streamlit Community Cloud reinicia contenedores y no conserva el sistema de archivos. Cada redeploy o hibernación **borra todos los leads capturados**. La app promete un CRM y entrega una caché.

Para el volumen esperado, la opción más barata y correcta es SQLite en un volumen persistente, o directamente Supabase / Google Sheets vía API. `SPEC.md` ya contempla "SQLite (futuro)" — ese futuro es ahora, porque hoy se están perdiendo datos comerciales reales.

### 4.4 Envío de correo sin autenticación ni saneamiento

El botón "Enviar Presupuesto PDF" acepta cualquier destinatario de cualquier visitante anónimo. Con la `RESEND_API_KEY` configurada, la app es un **relay de correo abierto** atado a tu dominio y tu cuota. Un bot puede quemar el plan y la reputación del dominio en una tarde.

Además el nombre del cliente se interpola sin escapar en el HTML del correo:

```python
"html": f"<p>Hola {cliente},</p>..."
```

Lo mismo ocurre en los ~43 bloques `unsafe_allow_html=True` de la interfaz, varios de los cuales interpolan entradas del usuario (`cliente.replace(" ", "_")` en el nombre del archivo Excel, por ejemplo). No es crítico en una app de un solo usuario, pero sí lo es en una app pública con captura de leads.

### 4.5 Las API keys se piden en la interfaz y se cachean

`render_text_design_assistant` muestra tres `st.text_input(type="password")` para Gemini, Fal y Luma. Y luego:

```python
@st.cache_data(show_spinner=False)
def generate_facade_image_fal(prompt: str, api_key: str) -> Optional[str]:
```

`st.cache_data` es **global a todo el proceso, compartido entre sesiones y usuarios**. La clave entra en la firma de la caché. Un usuario podría recibir el resultado generado con la clave de otro. La convención de Streamlit para esto es prefijar con guion bajo (`_api_key`) para excluir el argumento del hash — pero lo correcto de plano es no cachear llamadas autenticadas y leer las claves solo de `st.secrets` / entorno.

### 4.6 `.gitignore` se ignora a sí mismo

La regla `.env.*` también cubre `.env.example`, que sí debe versionarse. Funciona hoy porque el archivo ya está trackeado, pero es una trampa para el próximo clon. Usar `!.env.example` como excepción explícita.

---

## 5. Dependencias, despliegue y calidad (P2)

- **Sin pines de versión.** `streamlit>=1.32.0`, `fpdf2>=2.7.0`, `pandas<3.1.0`… El bug 1.3 es exactamente esto: el código se escribió contra `fpdf` clásico y `pip` instala `fpdf2` 2.8.7. Un despliegue hoy y otro mañana pueden dar apps distintas. Congelar con `pip freeze > requirements.lock` o usar `uv` / Poetry.
- **Sin CI.** No hay `.github/workflows`. Los cinco archivos de test son scripts sueltos con `assert` y `print("[OK]")`, invocados a mano. Nadie iba a notar que `test_ai_text_design.py` se rompió. Migrar a `pytest` + un workflow de GitHub Actions que corra `pytest` y `ruff` en cada push es media hora de trabajo y habría atrapado todos los bugs de la sección 1.
- **Sin linter.** No hay `pyproject.toml`, `ruff.toml` ni `.pre-commit-config.yaml`. `ruff check` habría señalado los 379 avisos y los siete `st_canvas` indefinidos antes del commit.
- **Modelo Gemini obsoleto.** `gemini-1.5-flash` está en retiro y el SDK `google-generativeai` fue reemplazado por `google-genai`. Migrar a `gemini-2.x-flash` con el SDK nuevo, y centralizar el nombre del modelo en **una** constante (hoy está hardcodeado en `ui_core.py` dos veces).
- **APIs de Streamlit deprecadas.** Un `use_column_width=True` (`ui_core.py:324`) y 45 `use_container_width=True`; ambos están en camino de ser sustituidos por `width=`. Funciona hoy, avisa hoy, romperá algún día.
- **Sin manejo de errores en las llamadas a IA.** `analyze_plan_image_with_gemini` hace `model.generate_content(...)` sin `try/except`, sin timeout y sin reintentos. Un fallo de red muestra el traceback crudo de Streamlit al cliente.
- **Cimentación duplicada.** `estimate_foundation_volume_m3()` en `ui_core.py` calcula `area × 0.15` y el motor calcula `m2 × 0.15 × factor`. Dos implementaciones del mismo concepto, una de ellas huérfana.

---

## 6. Plan de acción

### Fase 0 — Que no se caiga (1 día)

1. Mover `try/except st_canvas` a `ui_core.py`; importar desde ahí en `ui_calculadora.py` y `ui_vision.py`.
2. Importar `render_integradora_vision_canvas` en `ui_presupuesto.py`.
3. `return bytes(self.pdf.output())` en `PDFGenerator`.
4. `sistema_sel` → `sistema_seleccionado`.
5. Borrar la primera `sincronizar_parametros_globales` duplicada.
6. `.gitignore`: añadir `data/*_db.json`; excepción `!.env.example`.
7. `ADMIN_PASSWORD` sin fallback → `st.stop()` si no está definida.
8. `pip freeze > requirements.txt` con versiones exactas.

### Fase 1 — Que el número sea defendible (1–2 semanas)

Esta fase es el producto. Todo lo demás es andamiaje.

9. **Separar cantidades de precios.** Hoy `calcular_obra_grisa` mezcla geometría, rendimientos, desperdicios y precios en un solo bucle de `data.append({...})`. Partir en dos etapas:

    ```
    geometría → [QTO: cantidades por partida] → × pricebook → [presupuesto]
    ```

    El cómputo de cantidades se vuelve testeable contra la realidad física sin depender de precios, y los precios se vuelven un dato puro que cambia sin tocar código.

10. **Mover el catálogo de partidas a datos declarativos.** Cada partida como una fila con: `código, descripción, unidad, fórmula de cantidad, factor de desperdicio, clave de precio, categoría`. Un `partidas.yaml` en vez de cien líneas de `data.append`. Añadir el inodoro deja de ser un cambio de código.

11. **Consumir la geometría real.** Que el motor reciba `perimetro_m`, `altura_muro_m`, `niveles`, `espesor_muro_m` y `luz_libre_m`, y calcule `area_muros = perímetro × altura × niveles` en vez de `m2 × 2.2`. Esto es lo que convierte la visión artificial de demo a herramienta.

12. **Implementar `BASE_TECNICA_EPS_ICF.md` literalmente:** mortero 2.5 cm/cara, losa azotea 5 cm, entrepiso 6–7 cm, mallas (zigzag por vano, esquinera, de unión), cimentación completa (platea, replantillo, plantilla, polietileno, anclas cada 40 cm), y **mano de obra** con los rendimientos de la sección 5 (15–20 m²/día manual, 60–70 con lanzadora).

13. **Comparación gris vs gris al 27.5%.** Eliminar la matriz `matriz_tradicional` hardcodeada y calcular el lado tradicional con su propio motor de partidas (bloque, columnas, vigas, losa). Mostrar el desglose lado a lado.

14. **Un solo modelo energético.** Borrar dos de los tres. Recomiendo conservar `AnalisisEnergetico` (parte de carga térmica física: volumen × BTU/h/m³ ÷ SEER) y hacer que `AnalisisFinanciero` lo consuma en lugar de tener su propia constante de 45 kWh/m²/mes. Documentar la fuente de cada coeficiente y verificar la tarifa contra el pliego vigente de la SIE (nota: en RD la tarifa residencial es **BTS1**; BTS2 es de uso general — vale la pena confirmarlo antes de mostrarla a un cliente).

15. **Reescribir el ROI.** Año 0 = diferencial de inversión con su signo real (negativo solo si EPS es más caro). `payback = None` si no se recupera. TCO con energía incluida. Tests de propiedades: si `costo_isotex < costo_tradicional` y el ahorro es positivo, la TIR debe ser positiva.

16. **Validación estricta.** `Enum` para sistema, calidad y zona de riesgo. Que un valor desconocido **lance excepción**, no que caiga a un default silencioso.

17. **Tests de validación, no solo de regresión.** Recolectar 3–5 presupuestos reales ejecutados y escribir un test que exija ±5% — el objetivo que ya fijaste.

### Fase 2 — Salud estructural (1 semana)

18. Limpiar imports: `ruff check --select F401 --fix`. `ui_inicio.py` y `ui_team.py` deben quedar con un solo import.
19. Unificar el pricebook: todos los accesos vía la clase `Pricebook`. Borrar los tres diccionarios hardcodeados.
20. Unificar el estado: un módulo `state.py` con una dataclass `ProyectoState`, inicialización única, y las claves `plan_*` eliminadas.
21. Unificar la navegación: `st.navigation` / `st.Page` o carpeta `pages/`. Uno de los dos.
22. `pytest` + GitHub Actions (`pytest` + `ruff check`) en cada push. Arreglar `test_ai_text_design.py`.
23. Extraer los ~43 bloques `unsafe_allow_html` a un único `styles.py` o `.streamlit/style.css`.
24. SQLite (o Supabase) para leads y proyectos.
25. Actualizar `SPEC.md` y `README.md` para que describan la app que existe. Quitar los `分期`.

### Fase 3 — De herramienta a producto

26. Multi-sistema real: EPS Isotex / ICF / bloque tradicional como tres motores de partidas paralelos con parámetros propios, no un `if/else` de dos ramas.
27. Versionado del pricebook con fecha de vigencia (`precios_2026-07.json`) y trazabilidad: qué cotización se emitió con qué versión de precios. Indispensable cuando un cliente reclame.
28. Exportación del presupuesto a Excel con fórmulas vivas (no valores planos) para que el maestro constructor pueda ajustar en obra.
29. Migrar el visor BIM a exportación GLB/IFC, como plantea `SPEC.md`.

---

## 7. Lo que hay que preservar

No todo es deuda. Estas decisiones son correctas y hay que defenderlas durante el refactor:

- **`utils/calculador.py` desacoplado de Streamlit.** Es la razón por la que pude ejecutar el motor y auditarlo numéricamente sin levantar la app. Mantener esa regla en todo `utils/`.
- **`write_json_atomic()`** con `tempfile` + `os.replace`. Es la implementación correcta. Solo falta usarla en todas partes.
- **`utils/gemini_plan.py` como shim de compatibilidad** que reexporta desde `utils/vision.py`, con el motivo documentado en el docstring. Manejo maduro de una migración.
- **`_extract_json()` tolerante a bloques ```` ```json ````.** Los LLM devuelven basura alrededor del JSON; este parser lo asume. Correcto. (Aunque está duplicado en `vision.py` y `ai_text_design.py` — unificarlo.)
- **`docs/BASE_TECNICA_EPS_ICF.md`.** Es el mejor artefacto del repositorio: datos de fuente primaria, con el diagnóstico del error del 83% y el objetivo de ±5% ya escritos. La Fase 1 completa es, básicamente, implementar este documento.

---

## Resumen en una línea

La arquitectura está bien pensada y mal conectada: el motor está desacoplado pero no recibe la geometría que la app extrae, el pricebook tiene 27 materiales pero el cálculo usa 9, los tests pasan pero fijan un error del 300%, y el PDF —el entregable comercial— nunca se generó. Arregla los cinco `NameError` esta semana; dedica el mes siguiente a la Fase 1, porque un presupuesto correcto al ±5% es el único diferenciador que ninguna app de la competencia puede copiarte.
