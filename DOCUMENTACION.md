# Documentación técnica: producción lechera por vaca

Para el equipo de AIOROS. Explica de dónde salen los datos, cómo se obtiene cada modelo y
cómo se dibuja cada gráfica del dashboard, para poder publicarlo en la web de AIOROS y
mantenerlo. Las cifras corresponden a la corrida actual de `pipeline.py`; si cambian los datos,
el código las recalcula todas.

Autor: Luis Lasso. Dashboard en vivo: https://lulago3003.github.io/demo-produccion-lechera/

---

## 1. Qué hay en la carpeta

| Archivo | Qué es |
|---|---|
| `index.html` | El dashboard terminado. Un solo archivo con los datos, el estilo y el código dentro. Es lo que se sube a la web. |
| `pipeline.py` | Limpia los datos, ajusta las curvas, entrena y valida los modelos, detecta anomalías y escribe los resultados. |
| `construir_dashboard.py` | Inserta los resultados en `plantilla.html` y genera `index.html`. |
| `plantilla.html` | Diseño del dashboard con marcadores `{{...}}` que se rellenan con los datos. |
| `reporte.py` | Genera un reporte PDF de una página con las mismas cifras (opcional). |
| `modelos/regresion_lineal.json` | Modelo de predicción elegido: intercepto y coeficientes. |
| `modelos/xgboost.json` | Modelo XGBoost regularizado, en el formato nativo de XGBoost. |
| `salida/datos_demo.json` | Todo lo que dibuja el dashboard (ver sección 7). |
| `salida/metricas.json` | Resumen de la limpieza, los modelos y la validación. |
| `data/indonesia_holstein_lactancias.xlsx` | Datos de entrenamiento (sección 2.1). |
| `data/checa_desempeno_vacas.xlsx` | Datos de validación (sección 2.2). |

El flujo es siempre el mismo:

```
data/*.xlsx ──► pipeline.py ──► salida/datos_demo.json + modelos/*.json
                                        │
plantilla.html ─► construir_dashboard.py ┴──► index.html
```

---

## 2. De dónde salen los datos

Los dos datasets son públicos, de Mendeley Data, con licencia **CC BY 4.0**: se pueden usar,
modificar y publicar citando a los autores. El pie del dashboard ya los cita; conviene dejarlo así
al publicarlo. Los archivos de `data/` son copias sin modificar de los originales (solo cambió el
nombre del archivo); el SHA-256 coincide con el que publica Mendeley.

### 2.1 Entrenamiento: vacas Holstein de Indonesia

- **Cita:** Prafangasti Sarah, Didin Supriat Tasrifin, Heni Indrijani y Dedi Ruswandi,
  «Dataset for Performance of Superior Dairy Cattle Sires», Mendeley Data, versión 2, publicado
  el 22 de enero de 2024. https://doi.org/10.17632/2sm93h8t7y.2
- **Archivo original:** `raw data for performance of superior dairy cattle sires_2.xlsx`
  (SHA-256 `304b8f2f…6ab6`).
- **Contenido:** un registro por vaca y lactancia, en cuatro hojas: `1st Lactation`,
  `2nd Lactation`, `3rd Lactation` y `4rd Lactation` (así viene escrito). Vacas nacidas entre
  2017 y 2021.
- **Columnas usadas:**

| Columna original | Nombre en el código | Significado |
|---|---|---|
| Animal Number | `vaca` | Número de arete |
| Animal Name | `nombre` | Nombre de la vaca |
| Dam, Official Reg. Number (ORN) | `madre` | Registro de la madre |
| Sire Bull ID/ORN | `semental` | Toro padre |
| Total Milk Yield (Kg) | `total` | Leche total de la lactancia, kg reales |
| Corrected Milk (Kg) | `corregida` | Producción corregida a 305 días, kg |
| Length of Lactation | `duracion` | Días en ordeño |
| Days Dry (Days) | `dias_secos` | Días secos antes del siguiente parto |
| Peak Yield (Kg) | `pico` | Producción del día de máxima, kg/día |
| Days To Peak (Days) | `dias_pico` | Día de la lactancia en que llegó al pico |

- **Lo que no trae:** registros diarios, fechas ni clima. Por eso las curvas diarias se
  reconstruyen (sección 3.1).

### 2.2 Validación: vacas de República Checa

- **Cita:** Marek Vrhel, Jaromír Ducháček, Matúš Gašparík, Mojmír Vacek, Radim Codl y Jan Pytlík,
  «Dataset for study: Association between production and reproduction parameters based on parity
  and breed of dairy cows in the Czech Republic», Mendeley Data, versión 1, publicado el 18 de
  abril de 2024. https://doi.org/10.17632/6vy2tvv7jn.1
- **Archivo original:** `Dataset cow performance.xlsx` (SHA-256 `2f2cc5da…33c0`), hoja `Dataset`.
- **Contenido:** 723 registros de lactancia; según los autores, 659 vacas (Fleckvieh checa, Holstein y cruces), datos de enero
  a diciembre de 2018.
- **Uso:** no entrena nada; solo sirve para comprobar que los rangos de Indonesia
  son razonables y para fijar límites plausibles con los que revisar los datos de una finca.

### 2.3 Limpieza

De 2,203 filas quedan **2,178 lactancias válidas de 1,051 vacas**, hijas de 96 sementales. Las
reglas se aplican en este orden y el dashboard las muestra en «Cómo se calculó»:

| Regla | Filas retiradas |
|---|---|
| Filas de resumen al pie de cada hoja (mínimo, máximo, promedio, desviación, CV): no son vacas | 20 |
| Filas vacías (sin vaca o sin producción) | 4 |
| Registro duplicado de la misma vaca y lactancia | 0 |
| Lactancia de menos de 150 días | 0 |
| Producción corregida menor a 2,000 kg | 0 |
| Pico fuera de rango (0 o más de 80 kg/día) | 1 |
| Día del pico imposible (0 o después del fin de la lactancia) | 0 |

---

## 3. Cómo se obtienen los modelos

Hay tres piezas distintas. Solo la segunda y la tercera son aprendizaje automático.

### 3.1 Curva diaria de cada lactancia: modelo de Wood

Es una fórmula clásica de la ganadería lechera, no un modelo entrenado:

```
y(t) = a · t^b · e^(−c·t)        t = día de la lactancia, y = kg de leche ese día
```

Cada lactancia trae tres datos (pico, día del pico y total) y la fórmula tiene tres parámetros,
así que hay una sola curva que los cumple:

- El pico de la curva está en `t = b/c`, por lo tanto `c = b / día_del_pico`.
- La altura del pico es `a · (b/c)^b · e^(−b)`, de donde sale `a`.
- El área bajo la curva hasta el último día de ordeño, `a · c^−(b+1) · Γ(b+1) · P(b+1, c·L)`,
  debe ser igual al total. `P` es la función gamma incompleta regularizada y `L` la duración.
  Se despeja `b` numéricamente (`scipy.optimize.brentq`, entre 0.001 y 5).

Sale curva en **2,176 de 2,178 lactancias**; en 2 no existe una curva de Wood que cumpla los tres
datos a la vez. Código: `ajustar_wood()` y `curva()` en `pipeline.py`. Los parámetros `[a, b, c]`
de cada lactancia se guardan con 8 cifras significativas en `vacas[id].lacts[].w`.

### 3.2 Predicción de la siguiente lactancia

**Qué predice:** la producción corregida a 305 días de la lactancia siguiente de una vaca, a
partir de su lactancia actual.

**Con qué variables** (`RASGOS` en `pipeline.py`):

| Variable | Significado |
|---|---|
| `corregida` | Producción corregida a 305 días de la lactancia actual |
| `pico` | Pico, kg/día |
| `dias_pico` | Día del pico |
| `duracion` | Días en ordeño |
| `dias_secos` | Días secos |
| `lact` | Número de lactancia (1 a 3) |
| `media_hist` | Promedio de su producción corregida en todas sus lactancias hasta la actual |

**Datos de entrenamiento:** cada par de lactancias seguidas de la misma vaca (1.ª→2.ª, 2.ª→3.ª,
3.ª→4.ª). Son **1,024 pares**.

**Modelos comparados:**

- Regresión lineal (`sklearn.linear_model.LinearRegression`, sin ajustes).
- XGBoost regularizado: `n_estimators=300, learning_rate=0.03, max_depth=2, min_child_weight=10,
  subsample=0.8, colsample_bytree=0.8, reg_lambda=5, random_state=0`. Va regularizado porque con
  tan pocos datos un XGBoost normal se aprende los casos de memoria.

**Validación:** validación cruzada de 5 partes agrupada por vaca (`GroupKFold`). La misma vaca
nunca está a la vez en entrenamiento y en prueba, así que el error medido es el que se esperaría
con vacas nuevas.

**Resultados:**

| Modelo | Error medio (MAE) | R² | Anticipa, 1.ª→2.ª |
|---|---|---|---|
| Regresión lineal (elegido) | 820 kg | 0.22 | 41% |
| XGBoost regularizado | 838 kg | 0.20 | 38% |
| Usar el promedio del hato (referencia) | 930 kg | — | 20% (azar) |

«Anticipa» es la parte de las vacas que terminaron en el 20% más bajo de su 2.ª lactancia y que el
modelo ya había señalado desde la 1.ª.

**Cuál se usa.** Por defecto el pipeline usa el de menor error en la validación. Con estos datos
gana la regresión lineal por poco. Con más datos, XGBoost suele mejorar; como la elección es
automática, el día que gane pasa a usarse solo. Para forzar uno:

```bash
python pipeline.py --modelo xgboost    # o --modelo lineal
python construir_dashboard.py
```

Si se fuerza, el dashboard dice «se usa XGBoost regularizado por decisión del equipo» en lugar de
«se eligió el de menor error». Con los datos actuales, forzar XGBoost deja 116 de las 146 vacas a
vigilar iguales y marca 62 lactancias anómalas en 59 vacas (59 coinciden con las 64 actuales).

**Modelos guardados.** Después de validar, los dos modelos se entrenan con los 1,024 pares y se
guardan en `modelos/`. Para usarlos fuera del pipeline, con las variables en el orden de `rasgos`:

```python
import json, numpy as np, xgboost as xgb

lin = json.load(open("modelos/regresion_lineal.json"))
vaca = {"corregida": 5801, "pico": 24.4, "dias_pico": 56, "duracion": 271,
        "dias_secos": 69, "lact": 1, "media_hist": 5801}          # vaca 805464, 1.ª lactancia

pred_lineal = lin["intercepto"] + sum(lin["coeficientes"][k] * vaca[k] for k in lin["rasgos"])

modelo = xgb.XGBRegressor()
modelo.load_model("modelos/xgboost.json")
pred_xgb = modelo.predict(np.array([[vaca[k] for k in lin["rasgos"]]], dtype=float))[0]
# pred_lineal ≈ 6,421 kg, pred_xgb ≈ 6,621 kg (corregidos a 305 días, 2.ª lactancia)
```

### 3.3 Lista de vacas a vigilar

1. Se toma la última lactancia registrada de cada vaca que todavía puede tener otra (de la 1.ª a
   la 3.ª): 738 vacas.
2. El modelo elegido predice su siguiente lactancia.
3. Se ordena dentro de cada grupo (las que van a 2.ª entre sí, las que van a 3.ª entre sí, etc.).
4. Las que quedan en el **20% más bajo** de su grupo pasan a la lista: **146 vacas**.

Los motivos de cada vaca (producción prevista, pico y duración frente a la mediana) los escribe
`motivos_vigilancia()` con cifras calculadas, no a mano.

### 3.4 Anomalías de baja producción: Isolation Forest

Isolation Forest (`sklearn.ensemble.IsolationForest`) busca lactancias inusuales sin necesitar
ejemplos etiquetados. Se usan dos modelos, porque una 1.ª lactancia no tiene historial con qué
compararse:

| Grupo | Variables |
|---|---|
| 1.ª lactancia | Desvío frente a su grupo (z) en producción, pico, duración y día del pico |
| 2.ª a 4.ª | z de producción, pico y duración; diferencia contra lo que esperaba el modelo (%); diferencia contra su propio promedio anterior (%) |

- «Lo que esperaba el modelo» es la predicción fuera de muestra de la validación cruzada: el modelo
  nunca vio a esa vaca al predecirla.
- Las variables se estandarizan antes de entrenar. Parámetros: `n_estimators=400`,
  `contamination=0.06` (se espera ~6% de rarezas), `random_state=0`.
- Isolation Forest marca rarezas en los dos sentidos. Solo se conservan las de **baja**
  producción: por debajo de lo esperado, o por debajo de su grupo si es 1.ª lactancia.
- Resultado: **64 lactancias en 62 vacas**. Los motivos los escribe `motivos()`.

Isolation Forest se vuelve a entrenar en cada corrida porque describe a este hato en particular;
por eso no se guarda en `modelos/`.

### 3.5 De producción corregida a kilos reales

El modelo predice producción **corregida a 305 días**, pero las curvas están en **kilos reales por
día**. La corrección sube a las primerizas y baja a las adultas, así que para dibujar lo esperado
hay que convertir:

- Para cada lactancia se calcula `s305`: los kilos reales de su curva de Wood en sus primeros
  305 días (o menos, si duró menos).
- El factor de cada lactancia es `s305 / corregida`. En mediana: **0.90** en 1.ª, **1.04** en 2.ª,
  **1.10** en 3.ª y **1.15** en 4.ª (`factor_real_corregida` en el JSON).
- Lactancias pasadas: `e305 = esperado × s305 / corregida`, con el factor de esa misma lactancia.
- Próxima lactancia: `p305 = predicción × factor mediano` de la lactancia que viene.

---

## 4. Cómo se obtiene cada gráfica y tabla del dashboard

Todo lo dibuja `plantilla.html` en el navegador (SVG hecho a mano, sin librerías) a partir de
`salida/datos_demo.json`, que va incrustado en `index.html`.

| Elemento | Qué muestra | Datos | Cálculo |
|---|---|---|---|
| Titular | «Desde la segunda lactancia, el pico sube de 31 a unos 41 kg por día» | `curvas_mediana` | Máximo de la curva mediana de 1.ª contra el promedio de los máximos de 2.ª a 4.ª. Lo escribe `construir_dashboard.py`. |
| Gráfica principal | Curva típica de cada lactancia, día 1 a 305 | `curvas_mediana["1".."4"]`, `n_curvas` | Se evalúan las 2,176 curvas de Wood del día 1 al 305 y se toma la mediana día a día por número de lactancia (673, 599, 591 y 313 curvas). Picos: 31.5 kg el día 89 (1.ª), 39.6 el día 57 (2.ª), 42.2 el día 67 (3.ª) y 42.1 el día 67 (4.ª). |
| «Ver los valores en una tabla» | La misma curva en números | `curvas_mediana` | Valores de los días 1, 15, 30, 45, 60, 90, 120 … 305. |
| Lista «vacas a vigilar» | 146 vacas con motivo | `vigilancia[]` | Sección 3.3. |
| Lista «produjeron menos de lo esperado» | 62 vacas con motivo | `anomalias[]` | Sección 3.4. |
| Ficha: línea continua | Curva real de cada lactancia de la vaca | `vacas[id].lacts[].w`, `dur` | Fórmula de Wood con sus `[a, b, c]`, del día 1 al último día de ordeño. |
| Ficha: línea discontinua | Lo que esperaba el modelo para una lactancia pasada | `curvas_mediana[n]`, `lacts[].e305` | Forma de la curva mediana de esa lactancia, escalada para que sus primeros días (los mismos que duró la real, hasta 305) sumen `e305`. Se dibuja en las lactancias anómalas; si la vaca no tiene alertas, en su última lactancia. |
| Ficha: línea de puntos | Próxima lactancia prevista | `curvas_mediana[prox.n]`, `prox.p305` | Curva mediana de la lactancia que viene, escalada para sumar `p305` en 305 días. Se dibuja en las vacas a vigilar, y en las vacas sin alertas que solo tienen la 1.ª lactancia. |
| Ficha: discontinua gris | Mediana del hato | `curvas_mediana[n]` | Solo si la vaca no tiene ninguna línea del modelo. |
| Ficha: tabla | Producción, esperado, mediana del hato, pico y días por lactancia | `lacts[].corr`, `esp`, `pico`, `dur`; `prox.pred` | La «mediana del hato» es la mediana de la producción corregida de todas las vacas en esa lactancia. La tabla va en producción corregida; la gráfica, en kilos reales. |
| Ficha: notas | Motivo de cada alerta y cómo leer la gráfica | `vigilancia[].motivos`, `anomalias[].motivos` | Texto armado según qué líneas se dibujaron. |
| «Cómo se calculó» | Limpieza, modelos y validación | `resumen.removidos`, `modelo.resultados`, `validacion` | Secciones 2.3 y 3.2. |
| Validación | Rangos de Indonesia contra República Checa | `validacion.tabla`, `validacion.limites` | Percentiles 10, 50 y 90 de producción e intervalo entre partos; límites plausibles con los percentiles 1 y 99 checos de grasa, proteína, lactosa e intervalo entre partos. |
| «Descargar lista en Excel» | Las dos listas | `vigilancia[]`, `anomalias[]` | CSV con separador `;` y coma decimal, que Excel en español abre directo. |

---

## 5. Cómo publicarlo en la web de AIOROS

`index.html` funciona solo: no necesita servidor, base de datos ni librerías. Lo único externo es
la tipografía Barlow de Google Fonts; si no carga, el navegador usa su letra sin serifa por
defecto y todo sigue funcionando. Pesa unos 520 KB y se adapta desde 320 px de ancho.

**Opción A, como página propia (recomendada).** La web de AIOROS está en Firebase Hosting con
`"public": "."` y `"cleanUrls": true`. Basta con copiar el archivo así:

```
demos/produccion-lechera/index.html
```

y se sirve en `https://<dominio-de-aioros>/demos/produccion-lechera`. El `firebase.json` actual no
define una política de contenido (CSP) que bloquee el script incrustado.

**Opción B, dentro de otra página.**

```html
<iframe src="/demos/produccion-lechera" title="Producción lechera por vaca"
        style="width:100%;height:100vh;border:0" loading="lazy"></iframe>
```

**Opción C, enlazar la versión en vivo:** https://lulago3003.github.io/demo-produccion-lechera/

Al publicarlo, mantener el pie con la cita de los datos (lo exige la licencia CC BY 4.0).

---

## 6. Cómo actualizarlo o correrlo con datos de una finca

```bash
pip install pandas openpyxl scipy scikit-learn xgboost   # en macOS, XGBoost necesita: brew install libomp
python pipeline.py              # salida/*.json y modelos/*.json
python construir_dashboard.py   # index.html
python reporte.py               # PDF opcional
```

Probado con Python 3.14, pandas, scikit-learn y XGBoost 3.4. Los resultados son reproducibles:
todas las semillas están fijas en 0.

Para usar los datos de una finca, el Excel debe tener una hoja por número de lactancia con las
columnas de la sección 2.1. Si los nombres son otros, se cambian `HOJAS` y `COLUMNAS` al inicio de
`pipeline.py`; el resto del código no cambia. Los umbrales también están arriba: `CUANTIL_BAJO`
(20% para la lista de vigilancia) y `CONTAMINACION` (6% para Isolation Forest).

---

## 7. Contenido de `salida/datos_demo.json`

| Clave | Contenido |
|---|---|
| `resumen` | Filas crudas, lactancias válidas, vacas, sementales, curvas reconstruidas, reglas de limpieza con cuántas filas quitó cada una, pares de entrenamiento y lactancias checas. |
| `curvas_mediana` | Por lactancia (`"1"` a `"4"`): 305 valores, kg/día del día 1 al 305. |
| `n_curvas` | Cuántas curvas entran en cada mediana. |
| `factor_real_corregida` | Factor mediano kilos reales / corregida por lactancia. |
| `modelo` | MAE, R² y «anticipa» de cada modelo; `elegido`; `forzado` (true si se eligió con `--modelo`); MAE de la referencia; umbrales. |
| `vigilancia[]` | `vaca`, `nombre`, `semental`, `lact` (última), `pred` (kg corregidos de la siguiente), `percentil`, `motivos`. |
| `anomalias[]` | `vaca`, `nombre`, `semental`, `lact`, `corr`, `esp`, `puntaje` (más alto = más inusual), `motivos`. |
| `validacion` | `tabla` de rangos y `limites` plausibles. |
| `vacas{arete}` | `nombre`, `semental`, `prox` (`n`, `pred`, `p305`) y `lacts[]` con `n`, `total`, `corr`, `dur`, `pico`, `dpico`, `secos`, `esp`, `e305`, `w` = `[a, b, c]`, `anom`. |

---

## 8. Límites

- El dataset trae un registro por lactancia, sin datos diarios, fechas ni clima. Las curvas
  diarias son una reconstrucción y las anomalías solo se ven cuando la lactancia ya terminó.
- La lista de vigilancia anticipa alrededor del 41% de las vacas que terminan entre las más bajas,
  cuando al azar sería el 20%. Sirve para priorizar revisiones, no para diagnosticar.
- Para alertas a tiempo hacen falta registros diarios o por ordeño, con temperatura y humedad.
