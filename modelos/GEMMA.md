# Gemma 3 de 4B: qué es y dónde están sus pesos

## No lo entrenamos nosotros

Gemma 3 es un modelo abierto de Google que ya viene entrenado. Usamos su versión de 4B
parámetros ajustada para conversar (*instruct*), comprimida a 4 bits para que corra en una PC
o en la Jetson sin internet. No lo reentrenamos ni lo ajustamos con datos propios.

Lo que sí es nuestro:

| Qué | Dónde |
|---|---|
| Modelos entrenados con los datos del hato: predicción de la siguiente lactancia y nivel de cada semental | `modelos/regresion_lineal.json`, `modelos/xgboost.json`, `modelos/nivel_semental.json` |
| Cómo usa Gemma esos resultados: las instrucciones, los hallazgos que puede elegir y la comprobación de cada cifra y nombre que escribe | `gamma_asistente.py` |
| Pruebas de ese comportamiento | `tests/test_conversacion.py` |

Para este uso no hace falta reentrenar a Gemma: no calcula nada, solo interpreta resultados
que ya calculó el modelo de ML. Reentrenarlo tendría sentido cuando haya conversaciones reales
con ganaderos para enseñarle su forma de preguntar.

## El archivo exacto

| Dato | Valor |
|---|---|
| Nombre en Ollama | `gemma3:4b` |
| Formato | GGUF v3, cuantización Q4_K_M |
| Arquitectura | 34 capas; contexto máximo de 131,072 tokens (la demo usa 8,192) |
| Pesos del modelo | 2,499,012,288 bytes (2.5 GB), `sha256:f06e91e18fc74295d0c781bf91622508c75655e2c18ed869d52447ffe1e667e1` |
| Parte de visión | 851,251,104 bytes (0.85 GB), `sha256:7a50f9607a47389c028f2598c1f2d3e23b61913b4ce3c4a9eaaca62de1b9e098` |
| Total en disco | unos 3.35 GB |
| Licencia | [Gemma Terms of Use](https://ai.google.dev/gemma/terms), de Google |

En el equipo de desarrollo están en `.local/ollama/`, que no se sube a Git.

## Cómo obtener los mismos pesos

- **Desde la copia sin internet:** `python3 iniciar.py --pesos Gemma3-4B-Q4KM-AIOROS.zip` (el ZIP de
  Drive) o `python3 iniciar.py --pesos Gemma3-4B-Q4KM-AIOROS.zip.001` (las partes de GitHub, las dos
  en la misma carpeta, sin unirlas antes). Comprueba la huella, dice qué parte falta o está incompleta
  e instala los pesos en `.local/ollama/`.
- **Con el lanzador:** `iniciar.command` (o `python3 iniciar.py`) los descarga la primera vez
  y comprueba que la huella de los pesos sea la de la tabla. Si no coincide, avisa: otra
  versión de `gemma3:4b` funciona igual, pero sus respuestas pueden variar.
- **A mano:** `ollama pull gemma3:4b` ([ficha en Ollama](https://ollama.com/library/gemma3)).
- **Original de Google:** [google/gemma-3-4b-it](https://huggingface.co/google/gemma-3-4b-it)
  en Hugging Face, sin comprimir. Pide aceptar la licencia.
- **En la Jetson:** ver `JETSON.md`.

## Copia de los pesos en GitHub

Los pesos están en la versión publicada
[`gemma3-4b-q4km`](https://github.com/aioros-tech/AIOROS-Gamma-LuisLasso/releases/tag/gemma3-4b-q4km)
del repositorio de AIOROS, listos para usar sin internet. Sirven, por ejemplo, para instalar
una Jetson sin conexión.

GitHub no acepta archivos de más de 100 MB dentro del repositorio, y los adjuntos de una
versión publicada llegan a 2 GB por archivo. Por eso el ZIP de 3.35 GB va en dos partes. Cada
parte sola no se abre: son dos mitades del mismo ZIP. La forma más simple es no unirlas y usar
`python3 iniciar.py --pesos Gemma3-4B-Q4KM-AIOROS.zip.001`.

| Parte | Bytes |
|---|---|
| `Gemma3-4B-Q4KM-AIOROS.zip.001` | 1,782,579,200 |
| `Gemma3-4B-Q4KM-AIOROS.zip.002` | 1,567,717,425 |

Para unirlas a mano:

- **Mac o Linux:** `cat Gemma3-4B-Q4KM-AIOROS.zip.001 Gemma3-4B-Q4KM-AIOROS.zip.002 > Gemma3-4B-Q4KM-AIOROS.zip`
- **Windows:** se abre la parte `.001` con 7-Zip, o en la consola:
  `copy /b Gemma3-4B-Q4KM-AIOROS.zip.001+Gemma3-4B-Q4KM-AIOROS.zip.002 Gemma3-4B-Q4KM-AIOROS.zip`

La huella SHA-256 del ZIP unido es
`37bf74b306599a5a0714b6c33bf8793713690aca02b4a473305e065ecfce24ac`. Adentro van la carpeta
`ollama` (pesos y ficha para Ollama), `LEEME.txt` con los pasos y `LICENCIA_GEMMA.txt`. Al
redistribuirlos hay que incluir la licencia de Gemma.

Si el repositorio es privado, la descarga pide iniciar sesión en GitHub con una cuenta que
tenga acceso.
