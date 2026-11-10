#!/usr/bin/env python3
"""Arranque local reproducible. Ctrl+C detiene únicamente los procesos que abrió."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import shutil
import socket
import subprocess
import sys
import tarfile
import time
from urllib.request import urlopen
import webbrowser
import zipfile

RAIZ = Path(__file__).resolve().parent
VERSION_OLLAMA = "0.40.13"
SHA_MAC = "bae29252232b9e1358cf5801a7d65a07442af18fb5467cb68c7fc3711f59c511"
# Pesos de Gemma 3 de 4B (Q4_K_M) con los que se probó la demo; ver modelos/GEMMA.md
GEMMA_PESOS = "sha256:f06e91e18fc74295d0c781bf91622508c75655e2c18ed869d52447ffe1e667e1"
# Copia sin internet de esos pesos (Drive o versión publicada en GitHub, en dos partes)
ZIP_PESOS_SHA = "37bf74b306599a5a0714b6c33bf8793713690aca02b4a473305e065ecfce24ac"
PARTES_BYTES = (1782579200, 1567717425)


def get(url):
    with urlopen(url, timeout=3) as r:
        return json.load(r)


def revisar_gemma(env):
    """Avisa si los pesos descargados no son los mismos con los que se probó la demo. No bloquea:
    otra versión de gemma3:4b también funciona, pero sus respuestas pueden variar."""
    if env["GEMMA_MODEL"] != "gemma3:4b":
        return None
    manifiesto = Path(env["OLLAMA_MODELS"]) / "manifests" / "registry.ollama.ai" / "library" / "gemma3" / "4b"
    try:
        capas = json.loads(manifiesto.read_text())["layers"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    pesos = next((c.get("digest") for c in capas if str(c.get("mediaType", "")).endswith(".model")), None)
    if pesos == GEMMA_PESOS:
        print(f"Gemma: mismos pesos con los que se probó la demo ({pesos[7:19]}).", flush=True)
        return True
    print(f"Aviso: los pesos de Gemma ({(pesos or 'desconocidos')[:19]}) no son los de la demo ({GEMMA_PESOS[:19]}). "
          "Funciona igual, pero las respuestas pueden variar. Ver modelos/GEMMA.md.", flush=True)
    return False


class Unidas(io.RawIOBase):
    """Lee las partes .001, .002… como un solo archivo, sin unirlas en disco."""
    def __init__(self, rutas):
        self.archivos = [open(r, "rb") for r in rutas]
        self.tamanos = [os.fstat(f.fileno()).st_size for f in self.archivos]
        self.total, self.pos = sum(self.tamanos), 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, desplazamiento, desde=io.SEEK_SET):
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self.pos, io.SEEK_END: self.total}[desde]
        self.pos = max(0, base + desplazamiento)
        return self.pos

    def readinto(self, destino):
        hecho, inicio = 0, 0
        for f, n in zip(self.archivos, self.tamanos):
            if hecho < len(destino) and inicio <= self.pos < inicio + n:
                f.seek(self.pos - inicio)
                leido = f.readinto(memoryview(destino)[hecho:hecho + inicio + n - self.pos])
                hecho += leido
                self.pos += leido
            inicio += n
        return hecho

    def close(self):
        for f in self.archivos:
            f.close()
        super().close()


def partes_de(ruta):
    """Gemma3-…zip.001 → [.001, .002, …]; un .zip normal → [zip]."""
    ruta = Path(ruta).expanduser()
    if not ruta.exists():
        raise RuntimeError(f"No encuentro {ruta}.")
    if not ruta.suffix.lstrip(".").isdigit():
        return [ruta]
    base, partes = ruta.with_suffix(""), []
    while (siguiente := base.with_name(f"{base.name}.{len(partes) + 1:03d}")).exists():
        partes.append(siguiente)
    if not partes:
        raise RuntimeError(f"No encuentro {base.name}.001 junto a {ruta.name}.")
    return partes


def instalar_pesos(ruta, destino, sha=ZIP_PESOS_SHA, bytes_partes=PARTES_BYTES):
    """Instala los pesos de Gemma desde el ZIP de Drive o desde sus dos partes de GitHub, ya comprobados."""
    destino = Path(destino)
    partes = partes_de(ruta)
    if Path(ruta).suffix.lstrip(".").isdigit():
        for i, (parte, esperado) in enumerate(zip(partes, bytes_partes), 1):
            if parte.stat().st_size != esperado:
                raise RuntimeError(f"La parte {i} ({parte.name}) está incompleta: tiene {parte.stat().st_size:,} bytes "
                                   f"y debe tener {esperado:,}. Vuelve a descargarla.")
        if len(partes) < len(bytes_partes):
            raise RuntimeError(f"Falta la parte {len(partes) + 1}: descárgala en la misma carpeta que {partes[0].name}.")
    print("Comprobando la copia de Gemma…", flush=True)
    h = hashlib.sha256()
    with Unidas(partes) as f:
        while bloque := f.read(1 << 22):
            h.update(bloque)
    if h.hexdigest() != sha:
        raise RuntimeError("La copia de Gemma no coincide con la publicada: la descarga quedó incompleta o dañada. "
                           "Vuelve a descargarla.")
    print(f"Copia correcta. Instalando los pesos en {destino}…", flush=True)
    with Unidas(partes) as f, zipfile.ZipFile(f) as z:
        for m in z.infolist():
            nombre = m.filename.replace("\\", "/")
            if "/ollama/" not in "/" + nombre or m.is_dir():
                continue
            relativo = Path(nombre.split("ollama/", 1)[1])
            if relativo.is_absolute() or ".." in relativo.parts:
                raise RuntimeError(f"Ruta no permitida dentro del ZIP: {m.filename}")
            salida = destino / relativo
            salida.parent.mkdir(parents=True, exist_ok=True)
            with z.open(m) as src, salida.open("wb") as dst:
                shutil.copyfileobj(src, dst, 1 << 22)
    return destino


def elegir_puerto(preferido=8765, intentos=5):
    """Primer puerto desde el preferido con Gamma ya abierto (se reutiliza) o libre. Otros programas,
    como el servicio de Logitech, a veces ocupan el 8765."""
    for puerto in range(preferido, preferido + intentos):
        try:
            if get(f"http://127.0.0.1:{puerto}/api/estado").get("servicio") == "Gamma":
                return puerto, True
        except (OSError, ValueError, AttributeError):
            pass
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", puerto))
                return puerto, False
            except OSError:
                continue
    raise RuntimeError(f"Los puertos {preferido} a {preferido + intentos - 1} están ocupados por otros programas. "
                       "Usa --port con otro número.")


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
    sistema = platform.system()
    if sistema == "Windows":
        raise RuntimeError("Instala Ollama para Windows desde https://ollama.com/download y vuelve a ejecutar "
                           "python iniciar.py.")
    if sistema == "Linux" and platform.machine().lower() in ("aarch64", "arm64"):
        raise RuntimeError("Instala Ollama para Linux ARM64 según JETSON.md y vuelve a ejecutar el arranque.")
    if sistema != "Darwin":
        raise RuntimeError("Instala Ollama para Linux desde https://ollama.com/download/linux y vuelve a ejecutar "
                           "python3 iniciar.py.")
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
    p.add_argument("--port", type=int, help="Puerto del dashboard; por defecto el 8765 o el siguiente libre")
    p.add_argument("--origen", action="append", default=[], metavar="URL",
                   help="Dashboard de otro origen que puede usar a Gemma, por ejemplo https://panel.aioros.tech; se puede repetir")
    p.add_argument("--pesos", metavar="ZIP",
                   help="Instalar Gemma sin descargarlo: el ZIP de Drive o la parte .001 de GitHub (con la .002 al lado)")
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
    procesos, archivos = [], []
    def lanzar(cmd, log):
        f = (carpeta / log).open("ab")
        archivos.append(f)
        proc = subprocess.Popen(cmd, env=env, stdout=f, stderr=subprocess.STDOUT)
        procesos.append(proc)
        return proc
    try:
        if args.origen:
            from servidor import normalizar_origen
            env["GAMMA_ORIGENES"] = ",".join(sorted({normalizar_origen(o) for o in args.origen}))
        if args.pesos:
            instalar_pesos(args.pesos, env["OLLAMA_MODELS"])
        ollama = obtener_ollama()
        try:
            modelos = get(env["OLLAMA_URL"] + "/api/tags")
        except (OSError, ValueError):
            proc = lanzar([ollama, "serve"], "ollama.log")
            modelos = esperar(env["OLLAMA_URL"] + "/api/tags", proc)
        if not any(m.get("name") == env["GEMMA_MODEL"] for m in modelos.get("models", [])):
            print("Descargando Gemma (aproximadamente 3,4 GB; después funciona sin internet)…", flush=True)
            subprocess.run([ollama, "pull", env["GEMMA_MODEL"]], env=env, check=True)
        revisar_gemma(env)
        subprocess.run([sys.executable, "construir_dashboard.py"], check=True)
        puerto, abierto = elegir_puerto(args.port or 8765, 1 if args.port else 5)
        if args.port is None and puerto != 8765:
            print(f"El puerto 8765 lo usa otro programa; Gamma usará el {puerto}.", flush=True)
        url = env.setdefault("GAMMA_API_URL", f"http://127.0.0.1:{puerto}")
        if abierto:
            print("Gamma ya estaba iniciado; se reutiliza esa sesión.", flush=True)
            if args.origen:
                print("Aviso: para autorizar otro dashboard, cierra el Gamma que ya estaba abierto y vuelve a iniciarlo.",
                      flush=True)
        else:
            proc = lanzar([sys.executable, "servidor.py", "--port", str(puerto)], "servidor.log")
            esperar(url + "/api/estado", proc)
        if args.mqtt:
            try:
                import paho.mqtt.client  # noqa: F401
            except ImportError:
                raise RuntimeError("Instala requirements-mqtt.txt en este Python para activar MQTT.") from None
            lanzar([sys.executable, "mqtt_bridge.py"], "mqtt.log")
        print(f"\nGamma listo: {url}\nGemma: {env['GEMMA_MODEL']} · Ctrl+C para cerrar esta sesión.", flush=True)
        for o in env.get("GAMMA_ORIGENES", "").split(","):
            if o:
                print(f"Dashboard autorizado a usar a Gemma: {o} (ábrelo con ?gemma=local al final de la dirección)",
                      flush=True)
        print(flush=True)
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
