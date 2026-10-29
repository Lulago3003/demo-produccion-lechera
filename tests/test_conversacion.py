"""Cómo entiende Gemma las preguntas y cómo se comprueba su redacción."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from gamma_core import leer
from gamma_sensores import Registro
from gamma_asistente import contexto, responder, verificar

D = leer("salida/datos_demo.json")


def gemma(*respuestas):
    """Simula las llamadas a Ollama en orden: cada una devuelve el JSON indicado."""
    cola = list(respuestas)
    return patch("gamma_asistente.peticion",
                 side_effect=lambda *a, **k: {"message": {"content": json.dumps(cola.pop(0), ensure_ascii=False)}})


class Tema(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.r = Registro(Path(self.tmp.name) / "s.db")

    def tearDown(self):
        self.tmp.cleanup()

    def tema(self, pregunta):
        return contexto(D, self.r, {"pregunta": pregunta})["tema"]

    def test_como_se_pregunta_en_panama(self):
        for pregunta, tema in [("¿Cuánta plata se perdió por las vacas que produjeron menos?", "economia"),
                               ("¿Con qué toros me conviene inseminar?", "sementales"),
                               ("¿Qué pajilla uso para la próxima monta?", "sementales"),
                               ("¿Qué vacas me deberían preocupar?", "vigilancia"),
                               ("¿Cómo está el calor en el corral?", "sensores")]:
            with self.subTest(pregunta=pregunta):
                self.assertEqual(self.tema(pregunta), tema)

    def test_ganado_no_es_dinero(self):
        self.assertNotEqual(self.tema("¿Cómo va mi ganado este año?"), "economia")

    def test_gemma_clasifica_si_no_hay_palabras(self):
        with gemma({"tema": "sementales"}, {"hallazgos": ["comparacion"]}, {"respuesta": "x"}):
            r = responder(D, self.r, {"pregunta": "¿Cuáles hijas salen mejores según quién las engendró?"})
        self.assertEqual(r["tema"], "sementales")
        self.assertEqual(r["tema_origen"], "gemma")

    def test_dato_clave_primero(self):
        with gemma({"hallazgos": ["comparacion"]}, {"respuesta": "no verificable 123456"}):
            r = responder(D, self.r, {"pregunta": "Compara los toros"})
        self.assertEqual(r["hallazgos"][0], "destacados")
        self.assertIn("O.S.Elmer-XA", r["respuesta"])


class Salud(unittest.TestCase):
    def test_tratamientos_sin_gemma(self):
        tmp = tempfile.TemporaryDirectory()
        with patch("gamma_asistente.peticion", side_effect=AssertionError("no debe llamar a Gemma")):
            r = responder(D, Registro(Path(tmp.name) / "s.db"), {"pregunta": "¿Qué antibiótico le doy a la vaca 803530?"})
        tmp.cleanup()
        self.assertEqual(r["motor"], "regla")
        self.assertIn("veterinario", r["respuesta"])


class Redaccion(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.r = Registro(Path(self.tmp.name) / "s.db")

    def tearDown(self):
        self.tmp.cleanup()

    def test_cifras_y_redondeo(self):
        ev = "La brecha equivale a 83,056.56 litros, unos USD 37,375.44. Detectó el 44.3%."
        self.assertTrue(verificar("Se perdieron unos USD 37,375, es decir 83.057 litros; el 44% se anticipó.", ev, set()))
        self.assertFalse(verificar("Se perdieron USD 50,000.", ev, set()))

    def test_toro_inventado(self):
        ev = "Por encima se distinguen O.S.Elmer-XA (+1,006 kg)."
        self.assertTrue(verificar("Conviene O.S.Elmer-XA, con 1,006 kg más.", ev, {"O.S.Elmer-XA", "Brasilia"}))
        self.assertFalse(verificar("Conviene Brasilia.", ev, {"O.S.Elmer-XA", "Brasilia"}))

    def test_redaccion_aceptada(self):
        with gemma({"hallazgos": ["destacados"]},
                   {"respuesta": "Te conviene O.S.Elmer-XA: sus hijas dan 1,006 kg más que el promedio. Evita L.S Titanic, con 665 kg menos."}):
            r = responder(D, self.r, {"pregunta": "¿Con qué toros me conviene inseminar?"})
        self.assertEqual(r["modo"], "redaccion_verificada")
        self.assertTrue(r["respuesta"].startswith("Te conviene"))

    def test_redaccion_con_cifra_inventada(self):
        with gemma({"hallazgos": ["monto"]}, {"respuesta": "Perdiste exactamente USD 99,999 por culpa de la mastitis."}):
            r = responder(D, self.r, {"pregunta": "¿Cuánta plata se perdió?"})
        self.assertEqual(r["modo"], "hallazgos_verificados")
        self.assertNotIn("99,999", r["respuesta"])
        self.assertIn("litros", r["respuesta"])


if __name__ == "__main__":
    unittest.main()
