# Producción lechera por vaca — demo de AIOROS

Predicción de la producción por lactancia y detección de vacas con baja producción,
con datos públicos de 1,051 vacas Holstein.

**Dashboard:** https://lulago3003.github.io/demo-produccion-lechera/

## Qué hace

1. **Limpia los datos.** De 2,203 filas del archivo quedan 2,178 lactancias válidas.
   Las hojas originales traen 5 filas de estadísticas al pie (mínimo, máximo, promedio,
   desviación y coeficiente de variación) que no son vacas y se retiran.
2. **Reconstruye la curva diaria de cada lactancia** con el modelo de Wood,
   `y(t) = a·t^b·e^(-c·t)`, a partir del pico, el día del pico y el total.
   El dataset no trae registros diarios.
3. **Predice la siguiente lactancia** a partir de la anterior. Compara XGBoost
   regularizado contra regresión lineal con validación cruzada agrupada por vaca y se
   queda con el de menor error.
4. **Detecta baja producción** con Isolation Forest sobre la diferencia entre lo
   producido y lo esperado, frente al historial de la vaca y al resto del hato.
5. **Valida rangos** contra 723 lactancias de República Checa.

## Resultados

| Modelo | Error medio | Anticipa, 1.ª→2.ª lactancia |
|---|---|---|
| Regresión lineal (elegido) | 820 kg | 41% |
| XGBoost regularizado | 838 kg | 38% |
| Usar el promedio | 930 kg | 20% (azar) |

"Anticipa" es la parte de las vacas que terminaron en el 20% más bajo de su 2.ª
lactancia y que el modelo ya había señalado desde la 1.ª.

## Límites

- Un registro por lactancia: sin datos diarios, fechas ni clima. Las curvas diarias son
  una reconstrucción, no una medición.
- La lista de vigilancia sirve para priorizar, no para diagnosticar.
- Para alertas a tiempo hacen falta registros diarios o por ordeño, con temperatura y humedad.

## Cómo correrlo

```bash
pip install pandas openpyxl scipy scikit-learn xgboost   # en macOS, XGBoost necesita: brew install libomp
python pipeline.py              # genera salida/datos_demo.json y salida/metricas.json
python construir_dashboard.py   # genera index.html
```

## Datos y licencias

- Prafangasti Sarah, Didin Supriat Tasrifin, Heni Indrijani y Dedi Ruswandi,
  «Dataset for Performance of Superior Dairy Cattle Sires», Mendeley Data, v2, 2024,
  doi:10.17632/2sm93h8t7y.2 — licencia CC BY 4.0.
- «Dataset cow performance», Mendeley Data, doi:10.17632/6vy2tvv7jn.1 (República Checa, 2018).
