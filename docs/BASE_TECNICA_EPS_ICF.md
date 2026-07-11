# Base Técnica Constructiva — Sistemas EPS/ICF (Isotex / Covintec)

> Fuente: Notebook LM del usuario (50 videos YouTube) + Covintec.com (sección "¿Cómo construir?").
> Recolectado 2026-07. Usar para corregir `utils/calculador.py` (precisión física real).

## 1. Ahorro real vs construcción tradicional
- **EPS/ICF ahorra 20-40% en OBRA GRIS** (no en acabados, que son iguales en ambos sistemas).
- **Default sugerido en app: 27.5%** (promedio 25-30% según usuario).
- ⚠️ El "83%" viejo comparaba obra gris EPS vs obra TERMINADA tradicional (peras con manzanas). Corregir a comparación gris vs gris.

## 2. Espesores de mortero/concreto (iguales para todos los paneles Isotex=Covintec)
- **Muro:** 2.5 cm de mortero por cara (1ª capa ~2 cm cubre malla + 2ª 1-1.5 cm acabado).
- **Losa azotea:** capa de compresión 5 cm.
- **Losa entrepiso:** 6-7 cm.
- **Resistencia mínima losa:** 200 kg/cm² (microconcreto 220-250 kg/cm²).
- **Resistencia cimentación/zapata:** 250 kg/cm².

## 3. Rendimientos y proporciones de mezcla
- **Cemento 50 kg → 138-148 L** de concreto (resistencia 250 kg/cm²). 1 bulto = 50 L en seco.
- **Proporción resistencia 250:** 1 bulto cemento : 3.5 botes arena : 5.5 botes grava (bote 19 L). Agua ~148 L total.
- **Microconcreto:** 6 L agua/bulto, resistencia 220-250 kg/cm² (ya dosificado).
- **Replantillo (cimentación):** capa 12-15 cm de mezcla en fondo de excavación.

## 4. Anclaje y refuerzos
- **Anclas/bastones:** varilla 3/8", cada 40 cm, 3 por panel (panel = 1.22 m ancho), 5 cm dentro de cimentación.
- **Malla zigzag (vanos):** ventana 90x90 = 12 piezas; puerta 215x90 = 13 piezas. **Ambos lados (×2)**.
- **Malla esquinera:** (nº esquinas × altura muro) / 2.40 m.
- **Malla unión:** 10 cm × 2.40 m, ambos lados, en cortes de panel.
- **Panel estándar:** 1.22 m × 2.44 m (fabricable hasta 6.10 m).
- **Qualylosa:** losa prefabricada, claros hasta 6.10 m sin vigas intermedias.

## 5. Mano de obra (rendimientos)
- **Aplanado manual:** 15-20 m²/día. **Lanzadora neumática:** 60-70 m²/día (hasta 100 industrial).
- Aplanado en 2 capas: 1ª cubre malla (~2 cm) + 2ª alineación 1-1.5 cm.

## 6. Reglas de materiales
- ❌ **Prohibido usar CAL** en revoque (daña la malla de acero).
- ✅ Usar microfibra sintética + impermeabilizante integral (1 kg/bulto; 2 kg en cisternas/albercas).
- ✅ Mezclas prefabricadas (Mezcla Brava, Fermix) ya traen aditivos.

## 7. Cálculo de materiales (fórmulas del sistema)
- **Muros:** metros lineales / 1.22 m → piezas de panel (redondear hacia arriba). No descontar vanos.
- **Losas:** largo del claro / 1.22 m → piezas (redondear hacia arriba).
- **Mortero muros:** espesor 2.5 cm/cara; proporción 1 bulto mortero : 7 botes arena (19 L).
- **Concreto losas:** azotea 5 cm, entrepiso 6-7 cm, resistencia ≥200 kg/cm².

## 9. Tips del usuario (requisitos de diseño para el calculador)
- **Incorporar MALLAS en el presupuesto:** malla zigzag (vanos), malla esquinera, malla unión (cortes), malla electrosoldada 10x10 en cimentación. Ver fórmulas en sección 4.
- **Incorporar CIMENTACIÓN completa:** losa de cimentación/platea (10-15 cm), replantillo (12-15 cm), plantilla de concreto pobre (5-10 cm), barrera de polietileno, anclas/bastones (3/panel, cada 40 cm).
- **Opciones de TIPO de construcción:** la app debe ofrecer selección (EPS Isotex / ICF / tradicional bloque) para realizar los cálculos con sus parámetros propios. No hardcodear un solo sistema.
- **Margen de error del 5%:** el presupuesto debe ser exhaustivo (que no se escape DETALLE alguno: mallas, cimentación, mortero, concreto, acero, instalaciones, acabados). El objetivo es que el cálculo real caiga dentro de ±5% del costo ejecutado. Por eso toda partida debe estar presente y dosificada con datos reales (secciones 1-7).

## 11. Estrategia de precios (decisión 2026-07)
- **Placeholder:** precios de REFERENCIA Covintex (México/Brasil) convertidos a RD$ + impuestos aproximados.
- **Definitivo:** precios reales se ingresan cuando el usuario visite Covintex/Isotex.
- El panel de precios (`ui_calculadora.py` / `data/pricebook.json`) ya tiene aviso "precios de referencia".
- NO inventar cifras: mientras tanto, referencia Covintex convertida.

