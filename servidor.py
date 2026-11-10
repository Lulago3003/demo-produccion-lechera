#!/usr/bin/env python3
"""Servidor Gamma. Python estándar; no expone carpetas, modelos ni credenciales.

Modo local (por defecto): escucha en 127.0.0.1 para el dashboard de este equipo.
Modo servidor (--host 0.0.0.0, por ejemplo con Docker): cualquiera que abra el dashboard puede
preguntar a Gemma, con un límite por minuto; guardar registros de sensores exige GAMMA_CLAVE."""
import argparse
from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import secrets
import threading
import time
from urllib.parse import parse_qs, urlparse

from gamma_core import RAIZ, economia, leer, predecir
from gamma_sensores import Registro, simular
from gamma_asistente import estado, responder


def normalizar_origen(origen):
    """Origen de un dashboard externo autorizado: esquema y dominio, sin ruta (https://panel.ejemplo.com)."""
    u = urlparse(origen.strip())
    if (u.scheme not in ("http", "https") or not u.hostname or u.path not in ("", "/")
            or u.query or u.fragment or u.username or u.password):
        raise ValueError(f"Origen no válido: {origen!r}. Usa solo esquema y dominio, por ejemplo https://panel.ejemplo.com")
    return f"{u.scheme}://{u.netloc.lower()}"


def origenes_del_entorno():
    return [o for o in os.environ.get("GAMMA_ORIGENES", "").split(",") if o.strip()]


LOCALES = ("127.0.0.1", "localhost", "::1")


class Limite:
    """Preguntas por minuto: por cliente y en total, para que nadie acapare a Gemma en modo servidor."""
    def __init__(self, por_cliente, total):
        self.por_cliente, self.total = por_cliente, total
        self.marcas, self.todas, self.cerrojo = {}, deque(), threading.Lock()

    def permitir(self, cliente):
        ahora = time.monotonic()
        with self.cerrojo:
            for cola in (self.todas, *self.marcas.values()):
                while cola and ahora - cola[0] > 60:
                    cola.popleft()
            self.marcas = {k: v for k, v in self.marcas.items() if v}
            propia = self.marcas.setdefault(cliente, deque())
            if len(propia) >= self.por_cliente or len(self.todas) >= self.total:
                return False
            propia.append(ahora)
            self.todas.append(ahora)
            return True


def crear_servidor(port=8765, registro=None, origenes=(), host="127.0.0.1", publico=None, clave=None,
                   preguntas_por_minuto=8, preguntas_totales_por_minuto=30):
    # Dashboards de otro origen (por ejemplo, el de AIOROS) que pueden usar a Gemma o insertar este dashboard
    externos = frozenset(normalizar_origen(o) for o in origenes)
    publico = host not in LOCALES if publico is None else publico
    clave = clave or None
    limite = Limite(preguntas_por_minuto, preguntas_totales_por_minuto)
    ancestros = " ".join(["'self'", *sorted(externos)]) if externos else "'none'"
    datos = leer("salida/datos_demo.json")
    cfg = leer("configuracion.json")
    registro = registro or Registro()
    token_path = RAIZ / ".local" / "api-token"
    token_path.parent.mkdir(exist_ok=True)
    if not token_path.exists():
        fd = os.open(token_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(secrets.token_urlsafe(32))
    token = token_path.read_text().strip()
    # En modo servidor el navegador recibe una sesión que solo sirve para consultar; la clave no sale del servidor
    token_lectura = secrets.token_urlsafe(32) if publico else token

    def con_permiso(recibido, ruta):
        if publico:
            validos = [clave] if ruta == "/api/sensores" else [token_lectura, clave]
        else:
            validos = [token]
        return any(v and secrets.compare_digest(recibido, v) for v in validos)

    class Manejador(BaseHTTPRequestHandler):
        server_version = "Gamma/1.0"

        def log_message(self, formato, *args):
            # No preguntas, cuerpos, tokens ni parámetros de consultas en el log.
            print(f"{self.command} {urlparse(self.path).path} {args[1] if len(args)>1 else ''}", flush=True)

        def responder_bytes(self, contenido, tipo, status=200):
            self.send_response(status)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(contenido)))
            self.send_header("Cache-Control", "no-store")
            self.cors()
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            if not externos:
                self.send_header("X-Frame-Options", "DENY")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; connect-src 'self'; frame-ancestors " + ancestros + "; base-uri 'none'")
            self.end_headers()
            try:
                self.wfile.write(contenido)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def json(self, contenido, status=200):
            self.responder_bytes(json.dumps(contenido, ensure_ascii=False, allow_nan=False).encode(), "application/json; charset=utf-8", status)

        def cors(self):
            origin = self.headers.get("Origin")
            if origin in externos:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")

        def origen_valido(self):
            host = self.headers.get("Host", "")
            origin = self.headers.get("Origin")
            if publico:
                # Detrás del proxy HTTPS: la propia página (mismo dominio) o un dashboard autorizado
                propio = bool(origin) and urlparse(origin).netloc.lower() == host.lower()
                valido = not origin or propio or origin in externos
            else:
                # En el equipo: solo 127.0.0.1, para que otra web no pueda llegar por cambio de DNS
                allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
                valido = host in allowed and (not origin or origin in {"http://" + a for a in allowed} or origin in externos)
            if not valido:
                self.json({"error": "Origen no autorizado; agrégalo con --origen o GAMMA_ORIGENES"}, 403)
            return valido

        def cliente(self):
            # Detrás del proxy, la IP real es la última que agregó el proxy
            reenviado = self.headers.get("X-Forwarded-For", "")
            return reenviado.split(",")[-1].strip() if reenviado else self.client_address[0]

        def do_OPTIONS(self):
            # Consulta previa del navegador antes de que un dashboard autorizado envíe JSON con el token
            if not self.origen_valido():
                return
            self.send_response(204)
            self.cors()
            self.send_header("Access-Control-Allow-Methods", "GET, POST")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Gamma-Token")
            self.send_header("Access-Control-Max-Age", "600")
            if self.headers.get("Access-Control-Request-Private-Network") == "true" and self.headers.get("Origin") in externos:
                self.send_header("Access-Control-Allow-Private-Network", "true")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self):
            if not self.origen_valido():
                return
            ruta = urlparse(self.path)
            qs = parse_qs(ruta.query)
            try:
                if ruta.path in ("/", "/index.html"):
                    return self.responder_bytes((RAIZ / "index.html").read_bytes(), "text/html; charset=utf-8")
                if ruta.path == "/favicon.ico":
                    return self.responder_bytes(b"", "image/x-icon", 204)
                if ruta.path == "/api/sesion":
                    return self.json({"token": token_lectura, "modo": "servidor" if publico else "local"})
                if ruta.path == "/api/estado":
                    g = estado()
                    if publico:
                        g["mensaje"] = "Gemma disponible en el servidor" if g["disponible"] else "Gemma todavía no está listo en el servidor"
                    # En Cloud Run (K_SERVICE) el contenedor se apaga sin uso: el dashboard no consulta en segundo plano
                    return self.json({"servicio": "Gamma", "version": "1.0", "modo": "servidor" if publico else "local",
                                      "bajo_demanda": "K_SERVICE" in os.environ,
                                      "gemma": g, "hora": datetime.now(timezone.utc).isoformat()})
                if ruta.path == "/api/configuracion":
                    return self.json(cfg)
                if ruta.path == "/api/sensores":
                    sim = qs.get("simulado", ["false"])[0]
                    if sim not in ("true", "false"):
                        raise ValueError("simulado debe ser true o false")
                    return self.json(registro.resumen(datos, qs.get("finca", ["demo"])[0], sim == "true"))
                if ruta.path == "/api/economia":
                    p = float(qs["precio"][0]) if "precio" in qs else None
                    rho = float(qs["densidad"][0]) if "densidad" in qs else None
                    return self.json(economia(datos, p, rho))
                self.json({"error": "Ruta no encontrada"}, 404)
            except (ValueError, TypeError) as exc:
                self.json({"error": str(exc)}, 400)

        def do_POST(self):
            if not self.origen_valido():
                return
            ruta = urlparse(self.path).path
            if publico and ruta == "/api/sensores" and not clave:
                return self.json({"error": "Este servidor no recibe registros: define GAMMA_CLAVE"}, 403)
            if not con_permiso(self.headers.get("X-Gamma-Token", ""), ruta):
                return self.json({"error": "Token de sesión requerido"}, 401)
            if publico and ruta in ("/api/chat", "/api/simular") and not limite.permitir(self.cliente()):
                return self.json({"error": "Hay muchas preguntas seguidas; espera un minuto y vuelve a intentarlo."}, 429)
            if self.headers.get_content_type() != "application/json":
                return self.json({"error": "Content-Type debe ser application/json"}, 415)
            try:
                n = int(self.headers.get("Content-Length", "0"))
                if not 0 < n <= 65536:
                    return self.json({"error": "Cuerpo vacío o mayor de 64 KiB"}, 413)
                self.connection.settimeout(150)
                cuerpo = json.loads(self.rfile.read(n), parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Número JSON no finito")))
                if not isinstance(cuerpo, dict):
                    raise ValueError("Se requiere un objeto JSON")
                if ruta == "/api/chat":
                    return self.json(responder(datos, registro, cuerpo))
                if ruta == "/api/predecir":
                    return self.json(predecir(datos, cuerpo))
                if ruta == "/api/sensores":
                    r = registro.insertar(cuerpo)
                    r["evaluacion"] = registro.resumen(datos, r["evento"]["finca"], r["evento"]["simulado"])
                    return self.json(r, 201 if r["insertado"] else 200)
                if ruta == "/api/simular":
                    return self.json(simular(registro, datos))
                self.json({"error": "Ruta no encontrada"}, 404)
            except (ValueError, TypeError, KeyError) as exc:
                self.json({"error": str(exc)}, 400)
            except TimeoutError:
                self.json({"error": "Tiempo de espera agotado"}, 408)
            except Exception:
                self.json({"error": "No se pudo completar la operación; consultar el registro del servidor"}, 500)
                import traceback
                traceback.print_exc()

    servidor = ThreadingHTTPServer((host, port), Manejador)
    servidor.daemon_threads = True
    return servidor


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8765)),
                        help="Puerto; Cloud Run lo indica en la variable PORT")
    parser.add_argument("--host", default=os.environ.get("GAMMA_HOST", "127.0.0.1"),
                        help="127.0.0.1 en el equipo; 0.0.0.0 en un servidor detrás de un proxy HTTPS")
    parser.add_argument("--origen", action="append", default=origenes_del_entorno(),
                        help="Dashboard de otro origen autorizado a usar a Gemma; se puede repetir")
    args = parser.parse_args()
    # La clave solo por variable de entorno: en la línea de comandos la verían otros procesos
    server = crear_servidor(args.port, origenes=args.origen, host=args.host, clave=os.environ.get("GAMMA_CLAVE"))
    modo = "local" if args.host in LOCALES else "servidor"
    print(f"Gamma listo en http://{args.host}:{server.server_port} (modo {modo})", flush=True)
    if modo == "servidor" and not os.environ.get("GAMMA_CLAVE"):
        print("Sin GAMMA_CLAVE: se puede preguntar a Gemma, pero no se reciben registros de sensores.", flush=True)
    for o in sorted({normalizar_origen(o) for o in args.origen}):
        print(f"Dashboard autorizado: {o}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
