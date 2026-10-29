import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from gamma_core import economia, leer, parametros, predecir
from gamma_sensores import PANAMA, Registro, proyeccion_temprana, simular, validar_evento
from gamma_asistente import contexto, responder
from mqtt_bridge import Bandeja
from servidor import crear_servidor

D = leer("salida/datos_demo.json")
RASGOS = {"corregida":5801,"pico":24.4,"dias_pico":56,"duracion":271,"dias_secos":69,
          "lact":1,"media_hist":5801,"semental":"Coyne PlanetET"}


def diario(i=1, **kw):
    hoy = datetime.now(PANAMA).date()
    return {"id":f"d-{i}","finca":"prueba","simulado":False,"tipo":"produccion_diaria",
            "vaca":"A-1","fecha":(hoy-timedelta(days=45-i)).isoformat(),"lactancia":2,
            "dia_lactancia":i,"cantidad":30,"unidad":"kg","completo":True, **kw}


def ambiente(**kw):
    return {"id":"a-1","finca":"prueba","tipo":"ambiente","zona":"corral",
            "timestamp":datetime.now(timezone.utc).isoformat(),"temperatura_c":32,"humedad_pct":80, **kw}


class Economia(unittest.TestCase):
    def setUp(self):
        self.d = {"vacas":{"1":{"nombre":"Prueba","lacts":[{"n":1,"anom":True,"w":[1,0,0],"dur":10,"e305":20}],
                                 "prox":{"n":2,"p305":1030}}},"modelo":{"margen":0.2}}

    def test_mismo_horizonte_y_densidad(self):
        e=economia(self.d,0.4,1.03)
        self.assertEqual(e["registros"][0]["kg_reconstruidos"],10)
        self.assertAlmostEqual(e["brecha_historica_usd"],3.88)
        self.assertEqual(e["proximas"][0]["litros"],1000)
        self.assertEqual(e["proximas"][0]["valor_bajo"],320)

    def test_no_monetizar_corregida(self):
        antes=economia(self.d)["brecha_historica_usd"]
        self.d["vacas"]["1"]["lacts"][0]["corr"]=999999
        self.assertEqual(economia(self.d)["brecha_historica_usd"],antes)

    def test_precio_cero(self):
        self.assertEqual(economia(self.d,0)["brecha_historica_usd"],0)

    def test_no_brecha_negativa(self):
        self.d["vacas"]["1"]["lacts"][0]["e305"]=5
        self.assertEqual(economia(self.d)["brecha_historica_usd"],0)

    def test_sin_base_se_excluye(self):
        self.d["vacas"]["1"]["lacts"][0]["e305"]=None
        e=economia(self.d)
        self.assertEqual(e["lactancias_comparables"],0)
        self.assertEqual(e["sin_base_comparable"],1)

    def test_cap_305(self):
        self.d["vacas"]["1"]["lacts"][0]["dur"]=500
        self.assertEqual(economia(self.d)["registros"][0]["kg_reconstruidos"],305)

    def test_precio_invalido(self):
        for p in (float('nan'),float('inf'),-1,True,'0.4',11):
            with self.subTest(p=p),self.assertRaises(ValueError):parametros(p)

    def test_densidad_invalida(self):
        for rho in (0,1.2,float('nan'),False):
            with self.subTest(rho=rho),self.assertRaises(ValueError):parametros(0.4,rho)

    def test_datos_reales_y_exclusiones(self):
        e=economia(D)
        self.assertEqual(e["lactancias_comparables"]+e["sin_base_comparable"],len(D["anomalias"]))
        self.assertEqual(e["lactancias_comparables"],37)
        self.assertGreater(e["brecha_historica_usd"],0)


class Inferencia(unittest.TestCase):
    def test_caso_documentado(self):
        r=predecir(D,RASGOS)
        self.assertAlmostEqual(r["kg_corregidos"],6343.08,places=2)
        self.assertEqual(r["lactancia"],2)
        self.assertTrue(r["semental_conocido"])

    def test_semental_desconocido(self):
        self.assertFalse(predecir(D,{**RASGOS,"semental":"nuevo"})["semental_conocido"])

    def test_entrada_incompleta(self):
        with self.assertRaises(ValueError):predecir(D,{})

    def test_pico_incoherente(self):
        with self.assertRaises(ValueError):predecir(D,{**RASGOS,"dias_pico":300})

    def test_no_extrapolar_quinta(self):
        with self.assertRaises(ValueError):predecir(D,{**RASGOS,"lact":4})


class Sensores(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'reg.sqlite3'
        self.r=Registro(self.path)

    def tearDown(self):self.tmp.cleanup()

    def test_persistencia(self):
        self.r.insertar(diario())
        self.assertEqual(len(Registro(self.path).eventos('prueba')),1)

    def test_idempotencia(self):
        self.assertTrue(self.r.insertar(diario())["insertado"])
        self.assertTrue(self.r.insertar(diario())["duplicado"])

    def test_conflicto_no_sobrescribe(self):
        self.r.insertar(diario())
        with self.assertRaises(ValueError):self.r.insertar(diario(cantidad=20))
        self.assertEqual(self.r.eventos('prueba')[0]['kg'],30)

    def test_no_sumar_total_repetido(self):
        self.r.insertar(diario())
        with self.assertRaises(ValueError):self.r.insertar(diario(id='otro-id'))

    def test_aislamiento_finca_y_simulacion(self):
        self.r.insertar(diario())
        self.r.insertar(diario(simulado=True))
        self.r.insertar(diario(finca='otra'))
        self.assertEqual(len(self.r.eventos('prueba')),1)
        self.assertEqual(len(self.r.eventos('prueba',True)),1)
        self.assertEqual(len(self.r.eventos('otra')),1)

    def test_litros_a_kg(self):
        self.assertAlmostEqual(validar_evento(diario(cantidad=10,unidad='litros'))['kg'],10.3)

    def test_cero_es_observacion(self):
        self.assertEqual(validar_evento(diario(cantidad=0))['kg'],0)

    def test_rechazo_eventos_invalidos(self):
        for cambios in ({'cantidad':-1},{'cantidad':float('nan')},{'cantidad':True},{'completo':False},
                        {'unidad':'galones'},{'lactancia':1.5},{'dia_lactancia':0},{'simulado':'false'},
                        {'finca':'../x'},{'fecha':'2099-01-01'}):
            with self.subTest(cambios=cambios),self.assertRaises(ValueError):validar_evento(diario(**cambios))

    def test_thi(self):self.assertAlmostEqual(validar_evento(ambiente())['thi'],86.08)

    def test_humedad_y_zona_horaria(self):
        for kw in ({'humedad_pct':101},{'timestamp':'2026-10-29T12:00:00'}):
            with self.subTest(kw=kw),self.assertRaises(ValueError):validar_evento(ambiente(**kw))

    def test_lectura_vieja_no_alerta_actual(self):
        self.r.insertar(ambiente(timestamp=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat()))
        s=self.r.resumen(D,'prueba')
        self.assertTrue(s['ambiente'][0]['desactualizado'])
        self.assertEqual(s['alertas'],[])

    def test_fuera_de_orden_usa_fecha(self):
        self.r.insertar(ambiente(id='nuevo',temperatura_c=20))
        self.r.insertar(ambiente(id='viejo',timestamp=(datetime.now(timezone.utc)-timedelta(hours=2)).isoformat()))
        self.assertEqual(self.r.resumen(D,'prueba')['ambiente'][0]['id'],'nuevo')

    def test_simulador_prueba_alertas(self):
        s=simular(self.r,D)
        self.assertEqual({a['tipo'] for a in s['alertas']},{'calor','produccion'})
        self.assertTrue(s['vacas'][0]['proyeccion']['disponible'])
        self.assertEqual(self.r.resumen(D,'demo',False)['eventos'],0)

    def test_simular_no_borra_reales(self):
        self.r.insertar(diario(finca='demo'))
        simular(self.r,D);simular(self.r,D)
        self.assertEqual(self.r.resumen(D,'demo',False)['eventos'],1)
        self.assertEqual(self.r.resumen(D,'demo',True)['eventos'],46)

    def test_hueco_no_proyecta(self):
        serie=[validar_evento(diario(i)) for i in range(1,46) if i!=20]
        self.assertFalse(proyeccion_temprana(serie,D['curvas_mediana']['2'])['disponible'])

    def test_menos_30_no_proyecta(self):
        serie=[validar_evento(diario(i)) for i in range(1,30)]
        self.assertFalse(proyeccion_temprana(serie,D['curvas_mediana']['2'])['disponible'])

    def test_modelo_sobre_evento_cerrado(self):
        self.r.insertar({'id':'cerrada','finca':'prueba','vaca':'A-1','tipo':'lactancia_cerrada',
                         'fecha':datetime.now(PANAMA).date().isoformat(),'rasgos':RASGOS})
        p=self.r.resumen(D,'prueba')['predicciones'][0]
        self.assertAlmostEqual(p['kg_corregidos'],6343.08,places=2)


class Asistente(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.r=Registro(Path(self.tmp.name)/'s.db')
    def tearDown(self):self.tmp.cleanup()

    def test_vaca_desconocida(self):
        with self.assertRaises(ValueError):contexto(D,self.r,{'pregunta':'Consulta la vaca 999999999'})

    def test_ambito_sensores_sin_datos(self):
        c=contexto(D,self.r,{'pregunta':'¿Cómo está el calor?','finca':'real'})
        self.assertEqual(c['tema'],'sensores')
        self.assertIsNone(c['grafica'])
        self.assertTrue(any('No hay registros' in n for n in c['notas']))

    def test_contexto_cuenta_precio_cero(self):
        c=contexto(D,self.r,{'pregunta':'¿Cuánto dinero?','precio_litro':0})
        self.assertEqual(c['hechos'][0]['valor'],0)

    @patch('gamma_asistente.peticion',side_effect=OSError('sin conexión'))
    def test_caida_modelo_es_explicita(self,_):
        r=responder(D,self.r,{'pregunta':'Resumen'})
        self.assertEqual(r['motor'],'sin_modelo');self.assertTrue(r['hechos'])

    @patch('gamma_asistente.peticion',return_value={'message':{'content':'{"respuesta":"La pérdida es de 999999 USD"}'}})
    def test_cifra_inventada_no_se_muestra(self,_):
        r=responder(D,self.r,{'pregunta':'¿Cuánto dinero?'})
        self.assertEqual(r['motor'],'verificacion');self.assertNotIn('999999',r['respuesta'])

    @patch('gamma_asistente.peticion',return_value={'message':{'content':'{"hallazgos":["panorama"]}\ntexto no usado'}})
    def test_solo_extraer_json(self,_):
        r=responder(D,self.r,{'pregunta':'Resumen'})
        self.assertEqual(r['motor'],'gemma');self.assertNotIn('no usado',r['respuesta'])


class API(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.registro=Registro(Path(cls.tmp.name)/'api.db')
        cls.server=crear_servidor(0,cls.registro)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.url=f'http://127.0.0.1:{cls.server.server_port}'
        with urlopen(cls.url+'/api/sesion') as r:cls.token=json.load(r)['token']

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.tmp.cleanup()

    def post(self,ruta,body,**headers):
        req=Request(self.url+ruta,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','X-Gamma-Token':self.token,**headers})
        return urlopen(req,timeout=5)

    def test_html(self):
        with urlopen(self.url) as r:
            self.assertEqual(r.status,200);self.assertIn(b'Asistente Gemma',r.read())
            self.assertIn("frame-ancestors 'none'",r.headers['Content-Security-Policy'])

    def test_secretos_no_servidos(self):
        for p in ('/.local/api-token','/.git/config','/modelos/regresion_lineal.json','/../configuracion.json'):
            with self.subTest(p=p),self.assertRaises(HTTPError) as ctx:urlopen(self.url+p)
            self.assertEqual(ctx.exception.code,404)

    def test_sin_token(self):
        with self.assertRaises(HTTPError) as ctx:self.post('/api/sensores',diario(),**{'X-Gamma-Token':''})
        self.assertEqual(ctx.exception.code,401)

    def test_origen_ajeno(self):
        with self.assertRaises(HTTPError) as ctx:self.post('/api/sensores',diario(),Origin='https://otro.invalid')
        self.assertEqual(ctx.exception.code,403)

    def test_host_ajeno(self):
        with self.assertRaises(HTTPError) as ctx:urlopen(Request(self.url+'/api/sesion',headers={'Host':'otro.invalid'}))
        self.assertEqual(ctx.exception.code,403)

    def test_evento_invalido(self):
        with self.assertRaises(HTTPError) as ctx:self.post('/api/sensores',diario(cantidad=-5))
        self.assertEqual(ctx.exception.code,400)

    def test_inferencia(self):
        with self.post('/api/predecir',RASGOS) as r:self.assertAlmostEqual(json.load(r)['kg_corregidos'],6343.08,places=2)

    def test_cola_mqtt_y_duplicado(self):
        with tempfile.TemporaryDirectory() as tmp:
            cola=Bandeja(Path(tmp)/'cola.db')
            payload=json.dumps(ambiente(id='mqtt',finca='mqtt-test')).encode()
            tema='aioros/mqtt-test/entrada/ambiente'
            cola.guardar(tema,payload);cola.guardar(tema,payload)
            self.assertTrue(cola.enviar_uno(self.url,self.token,'mqtt-test'))
            self.assertFalse(cola.enviar_uno(self.url,self.token,'mqtt-test'))
            self.assertEqual(len(self.registro.eventos('mqtt-test')),1)

    def test_cola_rechaza_finca_ajena(self):
        with tempfile.TemporaryDirectory() as tmp:
            cola=Bandeja(Path(tmp)/'cola.db');cola.guardar('aioros/ajena/entrada/ambiente',json.dumps(ambiente(finca='ajena')).encode())
            cola.enviar_uno(self.url,self.token,'mia')
            with cola.db() as db:self.assertEqual(db.execute('SELECT estado FROM cola').fetchone()[0],'rechazado')

    def test_cola_reintenta_y_persiste(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'cola.db';cola=Bandeja(path)
            cola.guardar('aioros/prueba/entrada/ambiente',json.dumps(ambiente()).encode())
            with patch('mqtt_bridge.urlopen',side_effect=OSError('offline')):cola.enviar_uno(self.url,self.token,'prueba')
            with Bandeja(path).db() as db:
                estado,intentos,error=db.execute('SELECT estado,intentos,error FROM cola').fetchone()
            self.assertEqual(estado,'pendiente');self.assertEqual(intentos,1);self.assertTrue(error)


if __name__=='__main__':unittest.main()
