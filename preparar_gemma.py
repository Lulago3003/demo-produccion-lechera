#!/usr/bin/env python3
"""Deja a Gemma listo en el servicio Ollama del servidor (docker compose).

Si en la carpeta pesos/ está la copia sin internet (el ZIP de Drive o las partes de GitHub), la
comprueba y la instala; si no, descarga gemma3:4b de Ollama. Termina cuando el modelo está cargado."""
import json
import os
from pathlib import Path
import sys
import time
from urllib.request import Request, urlopen

from iniciar import instalar_pesos, revisar_gemma

OLLAMA = os.environ.get("OLLAMA_URL", "http://ollama:11434").rstrip("/")
MODELO = os.environ.get("GEMMA_MODEL", "gemma3:4b")
MODELOS = Path(os.environ.get("OLLAMA_MODELS", "/modelos/models"))
PESOS = Path(os.environ.get("GAMMA_PESOS_DIR", "/pesos"))


def pedir(ruta, cuerpo=None, timeout=10):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    return urlopen(Request(OLLAMA + ruta, data=datos, headers={"Content-Type": "application/json"}), timeout=timeout)


def presente():
    with pedir("/api/tags") as r:
        return any(MODELO in (m.get("name"), m.get("model")) for m in json.load(r).get("models", []))


def esperar_ollama():
    for _ in range(120):
        try:
            return presente()
        except OSError:
            time.sleep(1)
    raise RuntimeError("Ollama no respondió en 2 minutos; revisa: docker compose logs ollama")


def descargar():
    print(f"Descargando {MODELO} de Ollama (unos 3.4 GB, solo la primera vez)…", flush=True)
    visto = set()
    with pedir("/api/pull", {"model": MODELO}, timeout=3600) as r:
        for linea in r:
            evento = json.loads(linea)
            if "error" in evento:
                raise RuntimeError(f"Ollama no pudo descargar {MODELO}: {evento['error']}")
            estado = evento.get("status", "")
            if estado and not estado.startswith("pulling") and estado not in visto:
                print(estado, flush=True)
                visto.add(estado)


def main():
    if esperar_ollama():
        print(f"{MODELO} ya estaba instalado.", flush=True)
    else:
        copias = sorted(PESOS.glob("*.zip")) + sorted(PESOS.glob("*.zip.001")) if PESOS.is_dir() else []
        if copias and MODELO == "gemma3:4b":
            print(f"Instalando Gemma desde {copias[0].name}, sin internet.", flush=True)
            instalar_pesos(copias[0], MODELOS)
        else:
            descargar()
        if not presente():
            raise RuntimeError(f"{MODELO} no quedó instalado; revisa: docker compose logs preparar ollama")
    revisar_gemma({"GEMMA_MODEL": MODELO, "OLLAMA_MODELS": str(MODELOS)})
    print("Cargando Gemma en memoria…", flush=True)
    with pedir("/api/generate", {"model": MODELO, "prompt": "", "keep_alive": "24h"}, timeout=600):
        pass
    print("Gemma listo.", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"No se pudo preparar Gemma: {exc}", file=sys.stderr)
        sys.exit(1)
