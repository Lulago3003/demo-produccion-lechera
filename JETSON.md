# Preparación para Jetson Orin Nano

El código de inferencia y el servicio local están preparados, pero **esta entrega se probó
en macOS ARM64, no en una Jetson física**. No se han medido memoria, GPU, temperatura,
latencia sostenida ni consumo en la placa.

## Instalar y ejecutar

1. Preparar JetPack compatible con la placa y verificar el almacenamiento disponible.
2. Copiar el repositorio, incluidos `modelos/`, `salida/` y el HTML. No copiar `.runtime/`:
   contiene ejecutables de macOS y un entorno de pruebas de ese equipo.
3. Instalar Python 3.11 o posterior. El servidor, la regresión lineal y las reglas de
   sensores solo necesitan la biblioteca estándar. Para MQTT instalar
   `python3 -m pip install -r requirements-mqtt.txt` dentro de un entorno virtual.
4. Instalar Ollama para **Linux ARM64** siguiendo sus [instrucciones oficiales](https://docs.ollama.com/linux).
   Configurar `OLLAMA_HOST=127.0.0.1:11435`, `OLLAMA_MODELS` con el directorio local del
   proyecto y `OLLAMA_NO_CLOUD=1`. Si ya existe un servicio Ollama en el puerto 11434,
   usar `OLLAMA_URL=http://127.0.0.1:11434` al iniciar Gamma.
5. Descargar `gemma3:4b` mientras haya internet. Mantener la cuantización Q4 y un contexto
   inicial acotado; el servidor solicita 8192 tokens y una sola consulta simultánea.
6. Ejecutar `python3 iniciar.py --sin-abrir`. El dashboard queda en
   `http://127.0.0.1:8765`. Añadir `--mqtt` cuando las variables del broker estén configuradas.

La [documentación oficial de Ollama para Docker](https://docs.ollama.com/docker) indica
que una instalación JetPack en contenedor debe especificar `JETSON_JETPACK=5` o `6`
según corresponda. Esa ruta requiere además NVIDIA Container Toolkit. No elegir la
versión de JetPack sin comprobar la instalación de la placa.

Los pesos se pueden descargar directamente en la Jetson o trasladar desde un directorio
de modelos de Ollama compatible. No hace falta volver a entrenar la regresión lineal.
Para usar XGBoost en la placa, instalar una versión compatible con el modelo exportado
y verificar su carga antes de cambiar el modelo elegido.

## Validación necesaria en la placa

- Ejecutar `python3 -m unittest discover -s tests -v` y el caso de predicción documentado.
- Comprobar con `ollama ps` y `tegrastats` que el modelo se ejecuta como se espera y cabe
  en RAM junto con el servidor y el resto de servicios del cliente.
- Medir arranque en frío, latencia de preguntas típicas, tiempo de cálculo del modelo y
  retraso hasta la actualización del dashboard. Registrar percentiles y número de pruebas.
- Probar mensajes duplicados, fuera de orden, campos inválidos, caída del broker, corte
  de internet, reinicio de Gamma y recuperación de la cola.
- Probar operación sostenida y recuperación tras corte de energía; SQLite necesita disco
  fiable y espacio libre. Hacer copias de `.local/sensores.sqlite3` y `.local/mqtt.sqlite3`
  con la API de backup de SQLite o con los servicios detenidos.
- Evaluar los umbrales y las proyecciones con datos reales antes de usarlos como criterio
  operativo. Los resultados del dataset de Indonesia no validan automáticamente Panamá.

Después de descargar modelos y dependencias, las consultas y los cálculos funcionan
sin internet. Si el broker MQTT está en la nube, no habrá nuevas lecturas durante un
corte de red; para autonomía completa hace falta almacenamiento en el gateway o un
broker local en la finca.

El servicio escucha en loopback. Para abrirlo desde otro equipo, usar un túnel autenticado
o integrar la API detrás del backend de AIOROS. Antes de exponerlo en internet hay que
añadir autenticación de usuarios, permisos por finca, TLS, límites de recursos y una
configuración de proxy revisada; no publicar directamente el servidor de desarrollo.

La instalación física de LoRaWAN y el suministro de una Jetson por cliente dependen del
equipo de AIOROS. La titularidad o préstamo de la placa no altera el software entregado.
