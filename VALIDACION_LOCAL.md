# Verificación local · 29 de octubre de 2026

Resultado: aplicación local funcional en macOS ARM64. La validación no incluye una
Jetson física, broker del cliente, registros reales de una finca ni publicación remota.

| Comprobación | Resultado observado |
|---|---|
| Python estándar y API | **47 pruebas automáticas aprobadas** con `python -m unittest discover -s tests`. |
| MQTT de extremo a extremo | Broker local real con amqtt 0.11.3 y paho-mqtt 2.1.0: mensaje QoS 1 → cola SQLite → API → predicción/THI/producción. |
| Duplicados MQTT | Reenvío de un mensaje no incrementó el número de eventos. |
| Corte HTTP | Un mensaje recibido con Gamma detenido permaneció pendiente y fue entregado al reiniciarse la API. |
| Modelo entrenado | Caso de referencia: **6.343,08 kg corregidos**, segunda lactancia. |
| Economía | USD 0,40/L, densidad 1,03: **USD 33.222,68**; 37 lactancias comparables y 27 excluidas por falta de base. |
| Recálculo en navegador | Cambiar a USD 0,50/L mostró **USD 41.528,30**; restaurar referencia recuperó USD 33.222,68. |
| Simulación en navegador | 45 totales diarios y una lectura ambiental; alertas de caída y calor, THI **86,08**, proyección experimental **7.576,05 kg**. |
| Gemma real | Ollama 0.40.13, `gemma3:4b`, Q4_K_M, aproximadamente 3,4 GB descargados. |
| Preguntas reales | Resumen, dinero y vaca concreta respondieron con `motor=gemma` y hallazgos del catálogo validado. |
| Consulta desde la interfaz | «Explica las alertas de la vaca 803530» respondió en **0,9 s** en la prueba observada, con gráfica y estado «Fuera de la lista de vigilancia». Es una observación puntual, no un benchmark. |
| Consola del navegador | Sin errores durante las acciones probadas. |
| Interfaz | Inspección visual de paneles de asistente, economía y seguimiento en el navegador integrado. No se ejecutó emulación móvil. |
| JavaScript y Python | `node --check gamma.js`, compilación de módulos y generación del HTML completadas. |
| Integridad del diff | `git diff --check` sin errores. |
| Dependencias existentes | `pip check`: sin dependencias rotas tras aislar el broker de pruebas. |

Los registros locales de pruebas están en `.local/pruebas.log` y `.local/mqtt-e2e.log`;
la captura del asistente está en `artifacts/gamma-asistente.png`. No se incluyen las
carpetas de ejecución, bases de datos o credenciales en Git ni en el ZIP de entrega.

Las pruebas cubren conversiones y horizontes comparables, datos faltantes, números no
finitos, IDs duplicados, fechas futuras, unidades, aislamiento real/simulado, lecturas
fuera de orden, sensores desactualizados, inferencia al recibir una lactancia completa,
errores de Gemma, orígenes HTTP ajenos, protección de rutas privadas y persistencia de la cola.

El sistema de hallazgos verificados restringe lo que puede mostrar Gemma; no equivale a
validar la relevancia de todas sus selecciones posibles. Las reglas de sensores y las
proyecciones tempranas requieren datos de campo y evaluación antes de su uso productivo.
