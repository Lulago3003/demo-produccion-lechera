# -*- coding: utf-8 -*-
"""Genera index.html (autocontenido, sin CDN) desde salida/datos_demo.json y plantilla.html."""
import base64
import json
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RAIZ = Path(__file__).parent
D = json.loads((RAIZ / "salida" / "datos_demo.json").read_text(encoding="utf-8"))

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
hoy = datetime.now(ZoneInfo("America/Panama")).date()
fecha = f"{DIAS[hoy.weekday()]} {hoy.day} de {MESES[hoy.month - 1]} de {hoy.year}"

r, m = D["resumen"], D["modelo"]

# titular a partir de los datos: pico de la curva mediana en 1.ª lactancia vs 2.ª a 4.ª
picos = {n: max(x for x in D["curvas_mediana"][str(n)] if x is not None) for n in (1, 2, 3, 4)}
p1, p234 = picos[1], sum(picos[n] for n in (2, 3, 4)) / 3
titular = (f"Desde la segunda lactancia, el pico de producción sube de {p1:.0f} "
           f"a unos {p234:.0f} kg de leche por día")
# titular de sementales: entre los que se distinguen del promedio, el de hijas más y menos productoras
toros = D["sementales"]["lista"]
distintos = [s for s in toros if s["bajo"] > 0 or s["alto"] < 0]
mejor, peor = max(distintos, key=lambda s: s["kg"], default=None), min(distintos, key=lambda s: s["kg"], default=None)
if mejor and peor and mejor["kg"] > 0 > peor["kg"]:
    titular_toros = (f"Las hijas del mejor semental dan {mejor['kg'] - peor['kg']:,} kg más de leche por lactancia "
                     f"que las del peor")
else:
    titular_toros = f"{len(distintos)} de {len(toros)} sementales marcan diferencia en la leche de sus hijas"
# Barlow incrustada (licencia OFL en fuentes/OFL.txt): el dashboard se ve igual sin internet
FUENTES = [("Barlow", 400, "Barlow-400"), ("Barlow", 500, "Barlow-500"), ("Barlow", 600, "Barlow-600"),
           ("Barlow Condensed", 600, "BarlowCondensed-600"), ("Barlow Condensed", 700, "BarlowCondensed-700")]
fuentes_css = "".join(
    f"@font-face{{font-family:'{fam}';font-style:normal;font-weight:{peso};font-display:swap;"
    f"src:url(data:font/woff2;base64,{base64.b64encode((RAIZ / 'fuentes' / (archivo + '.woff2')).read_bytes()).decode()}) format('woff2')}}\n"
    for fam, peso, archivo in FUENTES)


def ejemplos_web():
    """La versión web no tiene Gemma ni sensores: guarda las mismas cifras, gráficas y hallazgos verificados
    que calcula el equipo de la finca para cada pregunta sugerida, y el escenario simulado de sensores."""
    from gamma_asistente import contexto, hallazgos_verificados
    from gamma_sensores import Registro, simular
    vaca = str((D["anomalias"] or D["vigilancia"])[0]["vaca"])  # la misma vaca que abre la ficha
    elegidos = {"resumen": ["panorama", "cuantas", "precision"],
                "vigilancia": ["primeras", "vigilar", "precision"],
                "economia": ["monto", "valor", "precio"],
                "sementales": ["destacados", "comparacion", "genetica"],
                "sensores": ["estado", "aviso_0", "aviso_1", "proyeccion"],
                "vaca": ["resumen_vaca", "pasado", "futuro"]}
    with tempfile.TemporaryDirectory() as tmp:
        registro = Registro(Path(tmp) / "sensores.sqlite3")
        sensores = simular(registro, D)
        chat = {}
        for tema, claves in elegidos.items():
            c = contexto(D, registro, {"pregunta": tema, "tema": tema, "vaca": vaca if tema == "vaca" else None,
                                       "finca": "demo", "simulado": True})
            h = hallazgos_verificados(c)
            chat[tema] = {**{k: c[k] for k in ("ambito", "hechos", "grafica", "tabla", "notas", "vaca_consultada")},
                          "motor": "ejemplo", "respuesta": "\n\n".join(h[k] for k in claves if k in h)}
    return {"chat": chat, "sensores": sensores}


reemplazos = {
    "{{FUENTES}}": fuentes_css,
    "{{FECHA}}": fecha,
    "{{VACAS}}": f"{r['vacas']:,}",
    "{{LACTS}}": f"{r['lactancias_validas']:,}",
    "{{CRUDOS}}": f"{r['registros_crudos']:,}",
    "{{SEMENTALES}}": str(r["sementales"]),
    "{{TITULAR}}": titular,
    "{{CURVAS}}": f"{r['curvas_reconstruidas']:,}",
    "{{N_VIGILAR}}": str(len(D["vigilancia"])),
    "{{N_ANOM_VACAS}}": str(len({a["vaca"] for a in D["anomalias"]})),
    "{{N_CHECA}}": str(r["lactancias_checas"]),
    "{{TOROS_TITULAR}}": titular_toros,
    "{{MIN_HIJAS}}": str(D["sementales"]["min_hijas"]),
    "{{DET_L12}}": f"{100 * m['resultados'][m['elegido']]['deteccion_l1_l2']:.0f}",
    "{{SELLO}}": hoy.strftime("%Y%m%d"),
    "{{DATOS}}": json.dumps(D, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c"),
    "{{GAMMA_CSS}}": (RAIZ / "gamma.css").read_text(encoding="utf-8"),
    "{{GAMMA_ECONOMIA}}": (RAIZ / "gamma_economia.html").read_text(encoding="utf-8"),
    "{{GAMMA_PANELES}}": (RAIZ / "gamma_paneles.html").read_text(encoding="utf-8"),
    "{{GAMMA_CONFIG}}": (RAIZ / "configuracion.json").read_text(encoding="utf-8").replace("<", "\\u003c"),
    "{{GAMMA_JS}}": (RAIZ / "gamma.js").read_text(encoding="utf-8"),
    "{{GAMMA_EJEMPLOS}}": json.dumps(ejemplos_web(), ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c"),
}
html = (RAIZ / "plantilla.html").read_text(encoding="utf-8")
for k, v in reemplazos.items():
    html = html.replace(k, v)
assert "{{" not in html, "quedó un marcador sin reemplazar"
(RAIZ / "index.html").write_text(html, encoding="utf-8")
print(f"index.html generado ({len(html) // 1024} KB) · {fecha}")
