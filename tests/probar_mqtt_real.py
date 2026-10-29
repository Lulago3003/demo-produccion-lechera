"""Prueba optativa con broker MQTT real, aislado en loopback y almacenamiento temporal.

Ejecutar con el entorno de pruebas que contiene amqtt==0.11.3 y paho-mqtt==2.1.0.
No necesita servicios remotos ni credenciales de un cliente.
"""
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from amqtt.broker import Broker
import paho.mqtt.client as mqtt
from gamma_core import RAIZ
from gamma_sensores import Registro
from servidor import crear_servidor
from mqtt_bridge import Bandeja


def hasta(condicion, segundos=20):
    inicio=time.monotonic()
    while time.monotonic()-inicio < segundos:
        if condicion():return
        time.sleep(0.2)
    raise AssertionError('La condición no se cumplió dentro del plazo')


def main():
    with socket.socket() as s:
        s.bind(('127.0.0.1',0));puerto=s.getsockname()[1]
    listo=threading.Event();fin=threading.Event()
    async def broker_loop():
        broker=Broker({'listeners':{'default':{'type':'tcp','bind':f'127.0.0.1:{puerto}'}},
                       'plugins':{'amqtt.plugins.authentication.AnonymousAuthPlugin':{'allow_anonymous':True}}})
        await broker.start();listo.set()
        while not fin.is_set():await asyncio.sleep(0.1)
        await broker.shutdown()
    bt=threading.Thread(target=lambda:asyncio.run(broker_loop()),daemon=True);bt.start()
    if not listo.wait(10):raise AssertionError('No arrancó el broker de prueba')
    with tempfile.TemporaryDirectory() as tmp:
        tmp=Path(tmp);reg=Registro(tmp/'eventos.db');api=crear_servidor(0,reg)
        at=threading.Thread(target=api.serve_forever,daemon=True);at.start()
        url=f'http://127.0.0.1:{api.server_port}'
        env={**os.environ,'MQTT_HOST':'127.0.0.1','MQTT_TLS':'0','MQTT_PORT':str(puerto),
             'MQTT_FARM':'prueba-e2e','MQTT_CLIENT_ID':'gamma-prueba-e2e',
             'GAMMA_API_URL':url,'GAMMA_MQTT_DB':str(tmp/'cola.db')}
        log=(tmp/'mqtt.log').open('wb')
        puente=subprocess.Popen([sys.executable,str(RAIZ/'mqtt_bridge.py')],env=env,stdout=log,stderr=subprocess.STDOUT)
        pub=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        pub.connect('127.0.0.1',puerto);pub.loop_start()
        def snapshot():
            with urlopen(url+'/api/sensores?finca=prueba-e2e&simulado=true') as r:return json.load(r)
        def enviar(e):
            msg=pub.publish(f"aioros/prueba-e2e/entrada/{e['tipo']}",json.dumps(e),qos=1)
            msg.wait_for_publish(timeout=5)
        try:
            hasta(lambda:'Suscrito' in (tmp/'mqtt.log').read_text())
            t=datetime.now(timezone.utc).isoformat()
            clima={'id':'mqtt-clima','finca':'prueba-e2e','simulado':True,'tipo':'ambiente','zona':'corral','timestamp':t,'temperatura_c':32,'humedad_pct':80}
            enviar(clima);enviar(clima)
            enviar({'id':'mqtt-dia','finca':'prueba-e2e','simulado':True,'tipo':'produccion_diaria','vaca':'P-1','fecha':'2026-10-20','dia_lactancia':20,'lactancia':2,'cantidad':30,'unidad':'litros','completo':True})
            enviar({'id':'mqtt-cerrada','finca':'prueba-e2e','simulado':True,'tipo':'lactancia_cerrada','vaca':'P-2','fecha':'2026-10-20',
                    'rasgos':{'corregida':5801,'pico':24.4,'dias_pico':56,'duracion':271,'dias_secos':69,'lact':1,'media_hist':5801,'semental':'Coyne PlanetET'}})
            hasta(lambda:snapshot()['eventos']==3)
            s=snapshot()
            assert s['predicciones'][0]['kg_corregidos']==6343.08
            assert s['vacas'][0]['ultimo_kg']==30.9
            assert s['ambiente'][0]['thi']==86.08
            assert len(s['alertas'])==1
            print('PASS MQTT real: publicación QoS 1 → cola durable → API → predicción ML + THI + conversión, sin duplicado.',flush=True)
            port=api.server_port;api.shutdown();api.server_close();at.join()
            enviar({**clima,'id':'durante-corte','zona':'corral-dos'})
            cola=Bandeja(tmp/'cola.db')
            def pendiente():
                with cola.db() as db:return db.execute("SELECT count(*) FROM cola WHERE estado='pendiente'").fetchone()[0]>0
            hasta(pendiente)
            api=crear_servidor(port,reg);at=threading.Thread(target=api.serve_forever,daemon=True);at.start()
            hasta(lambda:snapshot()['eventos']==4)
            print('PASS recuperación: mensaje recibido durante la caída HTTP y entregado tras reconexión.',flush=True)
        finally:
            pub.disconnect();pub.loop_stop();puente.terminate();puente.wait(timeout=10)
            api.shutdown();api.server_close();at.join();fin.set();bt.join(timeout=10);log.close()


if __name__=='__main__':main()
