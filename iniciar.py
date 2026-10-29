#!/usr/bin/env python3
"""Arranque local reproducible. Ctrl+C detiene únicamente los procesos que abrió."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import time
from urllib.request import urlopen
import webbrowser

RAIZ = Path(__file__).resolve().parent
VERSION_OLLAMA = "0.40.13"
SHA_MAC = "bae29252232b9e1358cf5801a7d65a07442af18fb5467cb68c7fc3711f59c511"


def get(url):
    with urlopen(url, timeout=3) as r:
        return json.load(r)


def esperar(url, proceso, segundos=30):
    for _ in range(segundos * 2):
        if proceso.poll() is not None:
            raise RuntimeError("El proceso terminó al arrancar. Consulta .local/ para ver su registro.")
        try:
            return get(url)
        except (OSError, ValueError):
            time.sleep(0.5)
    raise RuntimeError("El servicio no respondió a tiempo; consulta los registros en .local/.")


def obtener_ollama():
    local = RAIZ / ".runtime" / "ollama"
    if local.exists():
        return str(local)
    instalado = shutil.which("ollama")
    if instalado:
        return instalado
    if platform.system() != "Darwin":
        raise RuntimeError("Instala Ollama para Linux ARM64 según JETSON.md y vuelve a ejecutar el arranque.")
    print("Descargando Ollama oficial para macOS (solo la primera vez)…", flush=True)
    local.parent.mkdir(exist_ok=True)
    archivo = local.parent / "ollama-darwin.tgz"
    url = f"https://github.com/ollama/ollama/releases/download/v{VERSION_OLLAMA}/ollama-darwin.tgz"
    with urlopen(url, timeout=120) as r, archivo.open("wb") as f:
        shutil.copyfileobj(r, f)
    if hashlib.sha256(archivo.read_bytes()).hexdigest() != SHA_MAC:
        raise RuntimeError("La descarga no coincide con el SHA-256 oficial; no se ejecutó.")
    with tarfile.open(archivo) as tf:
        tf.extractall(local.parent, filter="data")
    return str(local)


def main():
    p = argparse.ArgumentParser(description="Inicia Gamma y Gemma en este equipo")
    p.add_argument("--sin-abrir", action="store_true", help="No abrir el navegador automáticamente")
    p.add_argument("--mqtt", action="store_true", help="Iniciar también el puente con la configuración MQTT del entorno")
    p.add_argument("--port", type=int, default=8765)
    args = p.parse_args()
    if sys.version_info < (3, 11):
        raise SystemExit("Se requiere Python 3.11 o posterior.")
    os.chdir(RAIZ)
    carpeta = RAIZ / ".local"
    carpeta.mkdir(exist_ok=True, mode=0o700)
    env = os.environ.copy()
    env.setdefault("OLLAMA_URL", "http://127.0.0.1:11435")
    env.setdefault("GEMMA_MODEL", "gemma3:4b")
    env.setdefault("OLLAMA_HOST", env["OLLAMA_URL"].removeprefix("http://"))
    env.setdefault("OLLAMA_MODELS", str(carpeta / "ollama"))
    env.setdefault("OLLAMA_NO_CLOUD", "1")
    env.setdefault("OLLAMA_NUM_PARALLEL", "1")
    env.setdefault("GAMMA_API_URL", f"http://127.0.0.1:{args.port}")
    procesos, archivos = [], []
    def lanzar(cmd, log):
        f = (carpeta / log).open("ab")
        archivos.append(f)
        proc = subprocess.Popen(cmd, env=env, stdout=f, stderr=subprocess.STDOUT)
        procesos.append(proc)
        return proc
    try:
        ollama = obtener_ollama()
        try:
            modelos = get(env["OLLAMA_URL"] + "/api/tags")
        except (OSError, ValueError):
            proc = lanzar([ollama, "serve"], "ollama.log")
            modelos = esperar(env["OLLAMA_URL"] + "/api/tags", proc)
        if not any(m.get("name") == env["GEMMA_MODEL"] for m in modelos.get("models", [])):
            print("Descargando Gemma (aproximadamente 3,4 GB; después funciona sin internet)…", flush=True)
            subprocess.run([ollama, "pull", env["GEMMA_MODEL"]], env=env, check=True)
        subprocess.run([sys.executable, "construir_dashboard.py"], check=True)
        url = env["GAMMA_API_URL"]
        try:
            previo = get(url + "/api/estado")
            if previo.get("servicio") != "Gamma":
                raise RuntimeError("El puerto elegido está ocupado por otro servicio")
            print("Gamma ya estaba iniciado; se reutiliza esa sesión.", flush=True)
        except OSError:
            proc = lanzar([sys.executable, "servidor.py", "--port", str(args.port)], "servidor.log")
            esperar(url + "/api/estado", proc)
        if args.mqtt:
            try:
                import paho.mqtt.client  # noqa: F401
            except ImportError:
                raise RuntimeError("Instala requirements-mqtt.txt en este Python para activar MQTT.") from None
            lanzar([sys.executable, "mqtt_bridge.py"], "mqtt.log")
        print(f"\nGamma listo: {url}\nGemma: {env['GEMMA_MODEL']} · Ctrl+C para cerrar esta sesión.\n", flush=True)
        if not args.sin_abrir:
            webbrowser.open(url)
        while True:
            if any(proc.poll() is not None for proc in procesos):
                raise RuntimeError("Un servicio terminó inesperadamente. Consulta .local/*.log.")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nCerrando los servicios iniciados por esta sesión…")
    finally:
        for proc in reversed(procesos):
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
        for f in archivos:
            f.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"No se pudo iniciar Gamma: {exc}", file=sys.stderr)
        sys.exit(1)
