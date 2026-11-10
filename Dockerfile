# Gamma: dashboard, API y asistente. Gemma corre en el servicio ollama de docker-compose.yml.
FROM python:3.13.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OLLAMA_URL=http://ollama:11434 \
    GEMMA_MODEL=gemma3:4b

WORKDIR /app
COPY . .
# Usuario sin privilegios; .local guarda los registros de sensores y el dashboard se regenera al arrancar
RUN useradd --system --uid 10001 --home-dir /app gamma \
    && mkdir -p .local \
    && python construir_dashboard.py \
    && chown -R gamma:gamma .local index.html

USER gamma
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/estado', timeout=4)"]
CMD ["sh", "-c", "python construir_dashboard.py && exec python servidor.py --host 0.0.0.0 --port 8765"]
