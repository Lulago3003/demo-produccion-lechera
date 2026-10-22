# -*- coding: utf-8 -*-
"""Genera index.html (autocontenido, sin CDN) desde salida/datos_demo.json y plantilla.html."""
import json
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).parent
D = json.loads((RAIZ / "salida" / "datos_demo.json").read_text(encoding="utf-8"))

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
hoy = date.today()
fecha = f"{DIAS[hoy.weekday()]} {hoy.day} de {MESES[hoy.month - 1]} de {hoy.year}"

r, m = D["resumen"], D["modelo"]

# titular a partir de los datos: pico de la curva mediana en 1.ª lactancia vs 2.ª a 4.ª
picos = {n: max(x for x in D["curvas_mediana"][str(n)] if x is not None) for n in (1, 2, 3, 4)}
p1, p234 = picos[1], sum(picos[n] for n in (2, 3, 4)) / 3
titular = (f"Desde la segunda lactancia, el pico de producción sube de {p1:.0f} "
           f"a unos {p234:.0f} kg de leche por día")
reemplazos = {
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
    "{{DET_L12}}": f"{100 * m['resultados'][m['elegido']]['deteccion_l1_l2']:.0f}",
    "{{SELLO}}": hoy.strftime("%Y%m%d"),
    "{{DATOS}}": json.dumps(D, ensure_ascii=False, separators=(",", ":")),
}
html = (RAIZ / "plantilla.html").read_text(encoding="utf-8")
for k, v in reemplazos.items():
    html = html.replace(k, v)
assert "{{" not in html, "quedó un marcador sin reemplazar"
(RAIZ / "index.html").write_text(html, encoding="utf-8")
print(f"index.html generado ({len(html) // 1024} KB) · {fecha}")
