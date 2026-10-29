#!/usr/bin/env python3
"""MQTT → cola SQLite → API Gamma. Confirmación QoS después de persistir el mensaje."""
import hashlib
import json
import logging
import os
from pathlib import Path
import sqlite3
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from gamma_core import RAIZ

LOG = logging.getLogger("gamma.mqtt")


class Bandeja:
    def __init__(self, path=None):
        self.path = str(path or RAIZ / ".local" / "mqtt.sqlite3")
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS cola (
                huella TEXT PRIMARY KEY, tema TEXT NOT NULL, contenido BLOB NOT NULL,
                estado TEXT NOT NULL DEFAULT 'pendiente', intentos INTEGER NOT NULL DEFAULT 0,
                siguiente REAL NOT NULL DEFAULT 0, error TEXT)""")

    def db(self):
        return sqlite3.connect(self.path, timeout=10)

    def guardar(self, tema, contenido):
        if len(contenido) > 65536:
            raise ValueError("Evento MQTT mayor de 64 KiB")
        huella = hashlib.sha256(tema.encode() + b"\0" + contenido).hexdigest()
        with self.db() as db:
            db.execute("INSERT OR IGNORE INTO cola (huella,tema,contenido) VALUES (?,?,?)", (huella, tema, contenido))
        return huella

    def enviar_uno(self, api, token, finca):
        with self.db() as db:
            fila = db.execute("SELECT huella,tema,contenido,intentos FROM cola WHERE estado='pendiente' AND siguiente<=? ORDER BY rowid LIMIT 1", (time.time(),)).fetchone()
        if fila is None:
            return False
        huella, tema, contenido, intentos = fila
        estado, error, siguiente = "entregado", None, 0
        try:
            e = json.loads(contenido)
            if not isinstance(e, dict) or e.get("finca") != finca:
                raise ValueError("Finca del mensaje distinta de la configurada")
            partes = tema.split("/")
            if partes != ["aioros", finca, "entrada", e.get("tipo")]:
                raise ValueError("El tema MQTT no coincide con finca y tipo del mensaje")
            req = Request(api.rstrip("/") + "/api/sensores", data=contenido,
                          headers={"Content-Type": "application/json", "X-Gamma-Token": token})
            with urlopen(req, timeout=20) as r:
                r.read()
        except (ValueError, UnicodeError):
            estado, error = "rechazado", "JSON o ámbito inválido"
        except HTTPError as exc:
            if exc.code in (400, 413, 415):
                estado, error = "rechazado", f"API rechazó evento: HTTP {exc.code}"
            else:
                estado, error = "pendiente", f"API temporalmente no disponible: HTTP {exc.code}"
        except OSError:
            estado, error = "pendiente", "API no accesible"
        if estado == "pendiente":
            siguiente = time.time() + min(60, 2 ** min(intentos, 6))
        with self.db() as db:
            db.execute("UPDATE cola SET estado=?,intentos=intentos+1,siguiente=?,error=? WHERE huella=?", (estado, siguiente, error, huella))
        LOG.info("Mensaje %s: %s", huella[:10], estado)
        return True


def main():
    import paho.mqtt.client as mqtt
    from gamma_sensores import identificador
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    finca = identificador(os.environ.get("MQTT_FARM", "demo"), "MQTT_FARM")
    host = os.environ.get("MQTT_HOST", "127.0.0.1")
    tls = os.environ.get("MQTT_TLS", "1") != "0"
    if not tls and host not in ("127.0.0.1", "localhost", "::1"):
        raise SystemExit("El broker remoto requiere MQTT_TLS=1 y un certificado válido")
    port = int(os.environ.get("MQTT_PORT", "8883" if tls else "1883"))
    token = (RAIZ / ".local" / "api-token").read_text().strip()
    cola = Bandeja(os.environ.get("GAMMA_MQTT_DB"))
    detener = threading.Event()
    def trabajador():
        while not detener.is_set():
            try:
                ocupado = cola.enviar_uno(os.environ.get("GAMMA_API_URL", "http://127.0.0.1:8765"), token, finca)
            except sqlite3.Error:
                LOG.exception("No se pudo procesar la cola local")
                ocupado = False
            detener.wait(0.05 if ocupado else 1)
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id=os.environ.get("MQTT_CLIENT_ID", "gamma-"+finca),
                         clean_session=False, manual_ack=True)
    if os.environ.get("MQTT_USERNAME"):
        client.username_pw_set(os.environ["MQTT_USERNAME"], os.environ.get("MQTT_PASSWORD"))
    if tls:
        client.tls_set(ca_certs=os.environ.get("MQTT_CA_FILE") or None)
    client.reconnect_delay_set(min_delay=1, max_delay=60)
    def conectado(c, userdata, flags, reason, properties):
        if reason.is_failure:
            LOG.error("Conexión MQTT rechazada: %s", reason)
            return
        c.subscribe(f"aioros/{finca}/entrada/+", qos=1)
        LOG.info("Suscrito a los eventos de la finca configurada")
    def mensaje(c, userdata, msg):
        try:
            cola.guardar(msg.topic, bytes(msg.payload))
            if msg.qos:
                c.ack(msg.mid, msg.qos)
        except ValueError as exc:
            LOG.warning("Mensaje rechazado: %s", exc)
            if msg.qos:
                c.ack(msg.mid, msg.qos)
        except sqlite3.Error:
            LOG.exception("No se pudo guardar el evento; se reconectará sin confirmarlo")
            # Una salida fallida permite que el supervisor reinicie la sesión persistente.
            os._exit(1)
    client.on_connect, client.on_message = conectado, mensaje
    thread = threading.Thread(target=trabajador, daemon=True)
    thread.start()
    client.connect_async(host, port, keepalive=60)
    try:
        client.loop_forever(retry_first_connection=True)
    except KeyboardInterrupt:
        pass
    finally:
        detener.set()
        client.disconnect()
        thread.join(timeout=25)


if __name__ == "__main__":
    main()
