"""El lanzador reconoce si los pesos de Gemma son los mismos con los que se probó la demo."""
import json
from pathlib import Path
import tempfile
import unittest

from iniciar import GEMMA_PESOS, revisar_gemma


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


if __name__ == "__main__":
    unittest.main()
