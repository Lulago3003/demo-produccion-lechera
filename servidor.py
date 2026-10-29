#!/usr/bin/env python3
"""Servidor local Gamma. Python estándar; no expone carpetas, modelos ni credenciales."""
import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import secrets
from urllib.parse import parse_qs, urlparse

from gamma_core import RAIZ, economia, leer, predecir
from gamma_sensores import Registro, simular
from gamma_asistente import estado, responder


def crear_servidor(port=8765, registro=None):
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

    class Manejador(BaseHTTPRequestHandler):
        server_version = "GammaLocal/1.0"

        def log_message(self, formato, *args):
            # No preguntas, cuerpos, tokens ni parámetros de consultas en el log.
            print(f"{self.command} {urlparse(self.path).path} {args[1] if len(args)>1 else ''}", flush=True)

        def responder_bytes(self, contenido, tipo, status=200):
            self.send_response(status)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(contenido)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            try:
                self.wfile.write(contenido)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def json(self, contenido, status=200):
            self.responder_bytes(json.dumps(contenido, ensure_ascii=False, allow_nan=False).encode(), "application/json; charset=utf-8", status)

        def origen_valido(self):
            allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            host = self.headers.get("Host", "")
            origin = self.headers.get("Origin")
            if host not in allowed or (origin and origin not in {"http://" + a for a in allowed}):
                self.json({"error": "Solo se admite el origen local del dashboard"}, 403)
                return False
            return True

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
                    return self.json({"token": token})
                if ruta.path == "/api/estado":
                    return self.json({"servicio": "Gamma", "version": "1.0", "gemma": estado(),
                                      "hora": datetime.now(timezone.utc).isoformat()})
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
            if not secrets.compare_digest(self.headers.get("X-Gamma-Token", ""), token):
                return self.json({"error": "Token de sesión requerido"}, 401)
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
                ruta = urlparse(self.path).path
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

    return ThreadingHTTPServer(("127.0.0.1", port), Manejador)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = crear_servidor(args.port)
    print(f"Gamma listo en http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
