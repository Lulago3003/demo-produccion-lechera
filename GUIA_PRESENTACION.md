# Guía para presentar el dashboard

Recorrido de unos 15 minutos, pestaña por pestaña: qué tocar y qué decir.
Las cifras son las de la versión actual de los datos.

## Antes de empezar

- **Si lo muestras con el link** (https://lulago3003.github.io/demo-produccion-lechera/):
  funciona en cualquier navegador. En las pestañas Gemma y Sensores se ven ejemplos ya calculados.
- **Si la persona lo va a revisar sola:** mándale https://lulago3003.github.io/demo-produccion-lechera/#recorrido.
  Se abre un recorrido guiado de 9 pasos que explica cada pestaña. También se abre con el botón
  "Ver recorrido guiado" de la portada.
- **Si lo muestras en tu PC con Gemma en vivo:** abre `iniciar.command` unos minutos antes,
  porque Gemma tarda en cargar la primera vez. Espera a que se abra http://127.0.0.1:8765 y a que
  la pestaña Asistente Gemma diga "Gemma 3 de 4B, en este equipo". Si quieres demostrar que
  funciona sin internet, apaga el wifi antes de preguntar.

## 1. Hato (2 min): el problema y los datos

**Qué mostrar:** primero las tres cifras de arriba (vacas a revisar, dinero y toros), después
el titular y la gráfica de curvas.

**Qué decir:**
- "En tres cifras: 146 vacas a revisar antes de su próxima lactancia, unos USD 37,000 en leche que
  faltó y 3 toros cuyas hijas dan más leche. Cada tarjeta lleva a su detalle."
- "Son datos públicos de 1,051 vacas Holstein, con 2,178 lactancias válidas. Todavía no son de
  una finca de Panamá; sirven para probar el sistema."
- "El registro solo trae el total, el pico y el día del pico de cada lactancia. Con eso
  reconstruimos la curva diaria con el modelo de Wood."
- "Desde la segunda lactancia, el pico sube de unos 31 a unos 41 kg de leche por día."

**Baja a las dos listas:**
- "146 vacas a vigilar en su próxima lactancia": el modelo prevé que queden en el 20 % más bajo
  de su grupo. Se puede descargar en Excel.
- "61 vacas produjeron menos de lo esperado": son lactancias pasadas inusuales.
- Recalca que **son listas distintas**: una mira al futuro y la otra al pasado.

## 2. Vacas (2 min): la ficha de una vaca

**Qué mostrar:** abre la ficha que aparece (803530, Aniya) o busca otra por arete o nombre.

**Qué decir:**
- "La línea continua es lo que produjo; la discontinua es lo que el modelo esperaba; la franja
  es el margen del modelo. En la validación, 8 de cada 10 vacas quedaron dentro."
- "En su 3.ª lactancia dio 32 % menos de lo esperado. Eso es lo que hay que revisar."
- "Abajo está cuánto vale en dinero su próxima lactancia."

## 3. Sementales (2 min): con qué toros conviene inseminar

**Qué mostrar:** la gráfica de barras de las hijas frente al promedio.

**Qué decir:**
- "Cada barra dice cuánta leche dan las hijas de un toro frente al promedio de su grupo."
- "Las hijas de O.S.Elmer-XA dan unos 1,006 kg más por lactancia."
- "Si el intervalo cruza el cero, con estos datos no se puede decir que ese toro sea distinto."
- "No es una evaluación genética oficial: no controla año, alimentación ni manejo."

## 4. Dinero (2 min): cuánta plata representa

**Qué mostrar:** las tres cifras de arriba y luego **cambia el precio** en vivo para que vea
cómo se recalcula.

**Qué decir:**
- "A USD 0.45 por litro, el precio de la leche grado C de julio de 2026, la leche que faltó en
  las lactancias bajas equivale a unos 83,000 litros, unos USD 37,000 de ingreso bruto."
- "Es ingreso bruto, no ganancia, y suma varios años del histórico; no es una pérdida anual."
- "Si me das el precio del contrato de la finca, se pone aquí y todo se recalcula."

## 5. Asistente Gemma (4 min): preguntarle como un ganadero

**Con el link:** toca las preguntas sugeridas ("Valor económico", "Comparar sementales",
"Vacas a vigilar"). Cada una muestra un ejemplo con las cifras, la gráfica y los hallazgos
verificados.

**En tu PC:** escribe preguntas como las diría un ganadero:
- "¿Cuánta plata se perdió?"
- "¿Con qué toros me conviene inseminar?"
- "¿Qué vacas tengo que revisar?"
- Para mostrar el límite: "¿Qué antibiótico le doy a la vaca 803530?" Gemma responde que eso lo
  decide un veterinario, porque el registro no tiene datos de salud.

**Qué decir:**
- "Gemma 3 de 4B corre en el equipo de la finca, sin internet. Los datos no salen de la finca."
- "Gemma no inventa números: elige entre hallazgos que calcula el código, y cada cifra que
  escribe se comprueba contra el registro. Si una no cuadra, se muestra el hallazgo tal cual."

## 6. Sensores (2 min): lo que viene en la finca

**Qué mostrar:** toca **Cargar escenario simulado**.

**Qué decir:**
- "Los sensores mandan datos por MQTT al equipo de la finca: producción diaria, temperatura y
  humedad."
- "Aquí hay dos alertas de ejemplo: una vaca con dos días seguidos de caída de más del 20 %, y
  un índice de calor (THI) por encima de 68, el umbral de revisión."
- "Con los primeros 30 a 60 días de una lactancia, hace una proyección experimental de cuánto
  va a dar a 305 días."
- "Son datos simulados. Las reglas hay que validarlas con una finca real."

## 7. Cierre (1 min): qué falta

- "Hoy corre en mi PC; el siguiente paso es instalarlo en la Jetson de la finca."
- "Para que las alertas sean a tiempo hacen falta registros diarios o por ordeño de una finca real.
  Con eso se valida el modelo y se ajustan los umbrales."
- "La pestaña **Cómo se calculó** explica cada número para quien quiera revisarlo."

## Preguntas que te pueden hacer

| Pregunta | Respuesta corta |
|---|---|
| ¿Qué tan preciso es? | El error medio es de unos 813 kg por lactancia. De las vacas que terminaron más bajas en su 2.ª lactancia, el modelo había señalado el 44 % desde la 1.ª; al azar sería el 20 %. Sirve para priorizar, no para diagnosticar. |
| ¿Los datos son de Panamá? | No. Son vacas Holstein de Indonesia, públicas (Mendeley Data, CC BY 4.0), y se validó con vacas de República Checa. Falta una finca real. |
| ¿Necesita internet? | No. Gemma y los sensores corren en el equipo de la finca. El link web es solo para mostrar el análisis. |
| ¿Diagnostica enfermedades? | No. Señala producción baja; la causa la determina el manejo y el veterinario. |
| ¿Qué hace falta para instalarlo? | Un equipo en la finca (PC o Jetson), los sensores con MQTT y el precio del contrato de la leche. Ver JETSON.md e INTEGRACION.md. |
