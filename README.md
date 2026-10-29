# Producción lechera por vaca — demo de AIOROS

Predicción de la producción por lactancia y detección de vacas con baja producción,
con datos públicos de 1,051 vacas Holstein.

El dashboard está organizado en pestañas: **Hato, Vacas, Sementales, Dinero, Asistente Gemma,
Sensores y Cómo se calculó**. Suma el valor económico de la leche (USD 0.45 por litro,
editable), un asistente con **Gemma 3 de 4B** que responde con cifras comprobadas contra el
registro, el seguimiento de producción diaria y calor, y la entrada de sensores por MQTT.

**Versión web:** https://lulago3003.github.io/demo-produccion-lechera/
Muestra todo el análisis. Gemma y los sensores funcionan en el equipo de la finca, sin internet;
en la web, las preguntas sugeridas y el escenario simulado de sensores muestran ejemplos calculados
al generar la página.
Con https://lulago3003.github.io/demo-produccion-lechera/#recorrido se abre un recorrido guiado
que explica cada pestaña.

**Versión completa, en el equipo:** abre `iniciar.command` en macOS o ejecuta
`python3 iniciar.py`; se abre en http://127.0.0.1:8765 con Gemma y los sensores activos.

- [Guía para presentar el dashboard, pestaña por pestaña](GUIA_PRESENTACION.md)
- [Entrega, uso, alcance y pendientes reales](ENTREGA.md)
- [API e integración con la aplicación de captura y MQTT](INTEGRACION.md)
- [Preparación y validación pendiente en Jetson](JETSON.md)

**Documentación completa** (datos, modelos y cómo se obtiene cada gráfica): [DOCUMENTACION.md](DOCUMENTACION.md)

## Qué hace

1. **Limpia los datos.** De 2,203 filas del archivo quedan 2,178 lactancias válidas.
   Las hojas originales traen 5 filas de estadísticas al pie (mínimo, máximo, promedio,
   desviación y coeficiente de variación) que no son vacas y se retiran.
2. **Reconstruye la curva diaria de cada lactancia** con el modelo de Wood,
   `y(t) = a·t^b·e^(-c·t)`, a partir del pico, el día del pico y el total.
   El dataset no trae registros diarios.
3. **Predice la siguiente lactancia** a partir de la anterior y del nivel de su semental
   (cuánto producen sus otras hijas), con un margen de ±17% que contiene a 8 de cada 10
   vacas. Compara XGBoost regularizado contra regresión lineal con validación cruzada agrupada por vaca y se
   queda con el de menor error (se puede forzar con `--modelo xgboost`). Los dos modelos
   entrenados quedan en `modelos/`.
4. **Dibuja la curva esperada de cada vaca.** El modelo predice el total de la lactancia
   corregido a 305 días; se pasa a kilos reales con el factor de corrección de esa lactancia
   (0.90 en la 1.ª, 1.04 en la 2.ª, 1.10 en la 3.ª y 1.15 en la 4.ª, en mediana) y se reparte
   día a día con la forma de la curva del hato. Así se ve la real contra la esperada, y la
   próxima lactancia prevista de las vacas a vigilar.
5. **Detecta baja producción** con Isolation Forest sobre la diferencia entre lo
   producido y lo esperado, frente al historial de la vaca y al resto del hato.
6. **Valida rangos** contra 723 lactancias de República Checa.
7. **Compara sementales**: cuánto producen las hijas de cada toro con 10 hijas o más frente al
   promedio del hato, con su intervalo del 90%.

## Resultados

| Modelo | Error medio | Anticipa, 1.ª→2.ª lactancia |
|---|---|---|
| Regresión lineal (elegido) | 813 kg | 44% |
| XGBoost regularizado | 833 kg | 37% |
| Usar el promedio | 930 kg | 20% (azar) |

"Anticipa" es la parte de las vacas que terminaron en el 20% más bajo de su 2.ª
lactancia y que el modelo ya había señalado desde la 1.ª.

## Límites

- Un registro por lactancia: sin datos diarios, fechas ni clima. Las curvas diarias son
  una reconstrucción, no una medición.
- La lista de vigilancia sirve para priorizar, no para diagnosticar.
- Para alertas a tiempo hacen falta registros diarios o por ordeño, con temperatura y humedad.

## Cómo correrlo

Para usar la aplicación con los modelos ya guardados no hace falta reentrenar:

```bash
python3 iniciar.py                 # Python 3.11 o posterior
python3 -m unittest discover -s tests -v
```

Para regenerar los modelos desde los Excel:

```bash
pip install pandas openpyxl scipy scikit-learn xgboost   # en macOS, XGBoost necesita: brew install libomp
python pipeline.py              # genera salida/*.json y modelos/*.json
python pipeline.py --modelo xgboost   # igual, pero usando XGBoost aunque tenga más error
python construir_dashboard.py   # genera index.html
```

## Datos y licencias

- Prafangasti Sarah, Didin Supriat Tasrifin, Heni Indrijani y Dedi Ruswandi,
  «Dataset for Performance of Superior Dairy Cattle Sires», Mendeley Data, v2, 2024,
  doi:10.17632/2sm93h8t7y.2 — licencia CC BY 4.0.
- Marek Vrhel, Jaromír Ducháček, Matúš Gašparík, Mojmír Vacek, Radim Codl y Jan Pytlík,
  «Dataset for study: Association between production and reproduction parameters based on parity
  and breed of dairy cows in the Czech Republic», Mendeley Data, v1, 2024,
  doi:10.17632/6vy2tvv7jn.1 — licencia CC BY 4.0.
