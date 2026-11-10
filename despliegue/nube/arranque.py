#!/usr/bin/env python3
"""Arranque del contenedor en Cloud Run: enciende Ollama, carga Gemma en la GPU y abre el servidor en $PORT.

Cloud Run no manda preguntas hasta que el puerto está abierto, así que la primera pregunta espera a que
Gemma esté cargado y no recibe una respuesta a medias. Sin preguntas, Cloud Run apaga el contenedor."""
import json
import os
import subprocess
import sys
import time
from urllib.request import Request, urlopen

OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
MODELO = os.environ.get("GEMMA_MODEL", "gemma3:4b")


def pedir(ruta, cuerpo=None, timeout=5):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    return urlopen(Request(OLLAMA + ruta, data=datos, headers={"Content-Type": "application/json"}), timeout=timeout)


def main():
    inicio = time.monotonic()
    ollama = subprocess.Popen(["ollama", "serve"])
    for _ in range(120):
        if ollama.poll() is not None:
            sys.exit("Ollama se cerró al arrancar")
        try:
            with pedir("/api/tags"):
                break
        except OSError:
            time.sleep(0.5)
    else:
        sys.exit("Ollama no respondió en 60 s")
    try:
        with pedir("/api/generate", {"model": MODELO, "prompt": "", "keep_alive": -1}, timeout=300):
            pass
        print(f"Gemma cargado en {time.monotonic() - inicio:.1f} s", flush=True)
    except OSError as exc:
        print(f"Aviso: no se pudo precargar Gemma ({exc}); se cargará con la primera pregunta", flush=True)
    puerto = os.environ.get("PORT", "8080")
    os.execvp(sys.executable, [sys.executable, "servidor.py", "--host", "0.0.0.0", "--port", puerto])


if __name__ == "__main__":
    main()
