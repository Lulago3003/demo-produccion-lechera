# Gamma en Cloud Run con GPU: Gemma (Ollama) y el servidor en un solo contenedor.
# Se construye desde la raíz del proyecto con despliegue/cloudrun.sh. Gemma va dentro de la imagen,
# así que al encenderse no descarga nada: carga el modelo en la GPU y abre el servidor en $PORT.
FROM ollama/ollama:0.40.13

ENV OLLAMA_HOST=127.0.0.1:11434 \
    OLLAMA_URL=http://127.0.0.1:11434 \
    OLLAMA_MODELS=/modelos \
    OLLAMA_KEEP_ALIVE=-1 \
    OLLAMA_NUM_PARALLEL=1 \
    OLLAMA_NO_CLOUD=1 \
    GEMMA_MODEL=gemma3:4b \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Capa propia para Gemma: cambiar el código no vuelve a descargar el modelo
RUN ollama serve >/tmp/ollama.log 2>&1 & pid=$!; \
    for i in $(seq 1 60); do ollama list >/dev/null 2>&1 && break; sleep 1; done; \
    ollama pull "$GEMMA_MODEL" && kill $pid

WORKDIR /app
COPY . .
RUN python3 construir_dashboard.py \
    && python3 -c "from iniciar import revisar_gemma; import os; revisar_gemma(dict(os.environ))"

ENTRYPOINT []
CMD ["python3", "despliegue/nube/arranque.py"]
