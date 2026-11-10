"""El lanzador reconoce los pesos de Gemma de la demo y los instala desde el ZIP o sus dos partes."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

import socket

from iniciar import GEMMA_PESOS, elegir_puerto, instalar_pesos, revisar_gemma


def manifiesto(carpeta, digest):
    ruta = Path(carpeta) / "manifests" / "registry.ollama.ai" / "library" / "gemma3" / "4b"
    ruta.parent.mkdir(parents=True)
    ruta.write_text(json.dumps({"layers": [{"mediaType": "application/vnd.ollama.image.model", "digest": digest},
                                           {"mediaType": "application/vnd.ollama.image.license", "digest": "sha256:0"}]}))


class PesosGemma(unittest.TestCase):
    def test_mismos_pesos(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifiesto(tmp, GEMMA_PESOS)
            self.assertTrue(revisar_gemma({"GEMMA_MODEL": "gemma3:4b", "OLLAMA_MODELS": tmp}))

    def test_otros_pesos(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifiesto(tmp, "sha256:" + "1" * 64)
            self.assertFalse(revisar_gemma({"GEMMA_MODEL": "gemma3:4b", "OLLAMA_MODELS": tmp}))

    def test_sin_manifiesto_u_otro_modelo(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(revisar_gemma({"GEMMA_MODEL": "gemma3:4b", "OLLAMA_MODELS": tmp}))
            self.assertIsNone(revisar_gemma({"GEMMA_MODEL": "otro:1b", "OLLAMA_MODELS": tmp}))


class CopiaSinInternet(unittest.TestCase):
    """Misma estructura que Gemma3-4B-Q4KM-AIOROS.zip, en pequeño."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.zip = self.dir / "Gemma.zip"
        with zipfile.ZipFile(self.zip, "w") as z:
            z.writestr("Gemma/LEEME.txt", "guía")
            z.writestr("Gemma/ollama/blobs/sha256-abc", b"pesos" * 4000)
            z.writestr("Gemma/ollama/manifests/registry.ollama.ai/library/gemma3/4b", "{}")
        datos = self.zip.read_bytes()
        self.sha = hashlib.sha256(datos).hexdigest()
        corte = len(datos) // 2
        (self.dir / "Gemma.zip.001").write_bytes(datos[:corte])
        (self.dir / "Gemma.zip.002").write_bytes(datos[corte:])
        self.bytes = (corte, len(datos) - corte)
        self.destino = self.dir / "ollama"

    def tearDown(self):
        self.tmp.cleanup()

    def instalar(self, ruta, **kw):
        return instalar_pesos(ruta, self.destino, sha=kw.get("sha", self.sha), bytes_partes=self.bytes)

    def test_desde_las_dos_partes_o_el_zip(self):
        for ruta in ("Gemma.zip.001", "Gemma.zip.002", "Gemma.zip"):
            with self.subTest(ruta=ruta):
                self.instalar(self.dir / ruta)
                self.assertEqual((self.destino / "blobs" / "sha256-abc").read_bytes(), b"pesos" * 4000)
                self.assertTrue((self.destino / "manifests" / "registry.ollama.ai" / "library" / "gemma3" / "4b").exists())
                self.assertFalse((self.destino / "LEEME.txt").exists())

    def test_parte_incompleta_o_faltante(self):
        parte2 = self.dir / "Gemma.zip.002"
        parte2.write_bytes(parte2.read_bytes()[:-10])
        with self.assertRaisesRegex(RuntimeError, "parte 2"):
            self.instalar(self.dir / "Gemma.zip.001")
        parte2.unlink()
        with self.assertRaisesRegex(RuntimeError, "Falta la parte 2"):
            self.instalar(self.dir / "Gemma.zip.001")

    def test_copia_dañada(self):
        with self.assertRaisesRegex(RuntimeError, "no coincide"):
            self.instalar(self.zip, sha="0" * 64)
        self.assertFalse(self.destino.exists())

    def test_ruta_fuera_de_la_carpeta(self):
        malo = self.dir / "malo.zip"
        with zipfile.ZipFile(malo, "w") as z:
            z.writestr("Gemma/ollama/../../fuera.txt", "x")
        with self.assertRaisesRegex(RuntimeError, "no permitida"):
            instalar_pesos(malo, self.destino, sha=hashlib.sha256(malo.read_bytes()).hexdigest())
        self.assertFalse((self.dir / "fuera.txt").exists())


class Windows(unittest.TestCase):
    def test_hora_de_panama_sin_tzdata(self):
        from datetime import datetime, timedelta
        from unittest.mock import patch
        from zoneinfo import ZoneInfoNotFoundError
        from gamma_core import zona_panama
        with patch("zoneinfo.ZoneInfo", side_effect=ZoneInfoNotFoundError("sin tzdata")):
            zona = zona_panama()
        self.assertEqual(zona.utcoffset(None), timedelta(hours=-5))
        self.assertEqual(datetime(2026, 7, 1, 12, tzinfo=zona_panama()).utcoffset(), timedelta(hours=-5))


class Puerto(unittest.TestCase):
    def test_salta_el_puerto_ocupado_por_otro_programa(self):
        with socket.socket() as ocupado:
            ocupado.bind(("127.0.0.1", 0))
            ocupado.listen()
            puerto = ocupado.getsockname()[1]
            elegido, abierto = elegir_puerto(puerto, 5)
            self.assertNotEqual(elegido, puerto)
            self.assertFalse(abierto)
            with self.assertRaisesRegex(RuntimeError, "ocupados"):
                elegir_puerto(puerto, 1)


if __name__ == "__main__":
    unittest.main()
