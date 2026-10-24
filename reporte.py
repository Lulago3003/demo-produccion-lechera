# -*- coding: utf-8 -*-
"""Reporte corto (PDF, negro y Arial) de la demo de producción lechera. Todas las cifras
salen de salida/datos_demo.json; ninguna está escrita a mano."""
import json
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

RAIZ = Path(__file__).parent
D = json.loads((RAIZ / "salida" / "datos_demo.json").read_text(encoding="utf-8"))
SALIDA = RAIZ.parent / "Reporte_demo_produccion_lechera.pdf"
URL = "https://lulago3003.github.io/demo-produccion-lechera/"
REPO = "https://github.com/Lulago3003/demo-produccion-lechera"

F = "/System/Library/Fonts/Supplemental/"
for n, a in [("Arial", "Arial.ttf"), ("Arial-Bold", "Arial Bold.ttf"),
             ("Arial-Italic", "Arial Italic.ttf"), ("Arial-BoldItalic", "Arial Bold Italic.ttf")]:
    pdfmetrics.registerFont(TTFont(n, F + a))
pdfmetrics.registerFontFamily("Arial", normal="Arial", bold="Arial-Bold", italic="Arial-Italic",
                              boldItalic="Arial-BoldItalic")

NEGRO, GRIS, TENUE = colors.HexColor("#111111"), colors.HexColor("#3A3A3A"), colors.HexColor("#767676")
CLARO, LINEA = colors.HexColor("#F1F1F1"), colors.HexColor("#D6D6D6")


def S(**k):
    b = dict(fontName="Arial", bulletFontName="Arial", fontSize=9.6, leading=13.4, textColor=GRIS)
    b.update(k)
    return ParagraphStyle("s", **b)


P = S(alignment=TA_JUSTIFY, spaceAfter=5)
H = S(fontName="Arial-Bold", fontSize=12, leading=15, textColor=NEGRO, spaceBefore=11, spaceAfter=5)
B = S(alignment=TA_JUSTIFY, leftIndent=11, bulletIndent=2, spaceAfter=3)
CEL, CELB = S(fontSize=8.8, leading=11.5), S(fontName="Arial-Bold", fontSize=8.8, leading=11.5, textColor=NEGRO)

r, m = D["resumen"], D["modelo"]
R, el = m["resultados"], m["elegido"]
n_anom = len({a["vaca"] for a in D["anomalias"]})
picos = {n: max(x for x in D["curvas_mediana"][str(n)] if x is not None) for n in (1, 2, 3, 4)}
p234 = sum(picos[n] for n in (2, 3, 4)) / 3
pct = lambda x: f"{x * 100:.0f}%"

dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
         "octubre", "noviembre", "diciembre"]
hoy = date.today()

E = [Paragraph("Demo: producción lechera por vaca", S(fontName="Arial-Bold", fontSize=19, leading=23, textColor=NEGRO)),
     Paragraph(f"Para Miguel Torres-Miranda, AIOROS. {dias[hoy.weekday()].capitalize()} {hoy.day} de "
               f"{meses[hoy.month - 1]} de {hoy.year}.", S(fontSize=9.5, textColor=TENUE, spaceAfter=12))]

E.append(Paragraph("Qué se hizo", H))
E.append(Paragraph(
    f"Con el dataset de Indonesia (Holstein, Mendeley) se armó la demo completa. De {r['registros_crudos']:,} filas "
    f"quedaron <b>{r['lactancias_validas']:,} lactancias válidas de {r['vacas']:,} vacas</b>, hijas de "
    f"{r['sementales']} sementales. Las hojas originales traen 5 filas de estadísticas al pie (mínimo, máximo, "
    f"promedio, desviación y coeficiente de variación) que no son vacas y se retiraron.", P))
for t in [
    f"<b>Curva diaria de cada lactancia.</b> El dataset no trae datos diarios, pero con el pico, el día del pico y el "
    f"total se reconstruye la curva con el modelo de Wood. Salió en {r['curvas_reconstruidas']:,} de "
    f"{r['lactancias_validas']:,} lactancias. Muestra que desde la 2.ª lactancia el pico sube de {picos[1]:.0f} a unos "
    f"{p234:.0f} kg por día.",
    "<b>a) Predicción.</b> Se estima la producción de la siguiente lactancia a partir de la anterior, comparando "
    "XGBoost regularizado contra regresión lineal, con validación cruzada que separa vacas. En la ficha de cada vaca "
    "se dibuja además la curva que esperaba el modelo y su próxima lactancia prevista, en kilos reales por día.",
    "<b>b) Anomalías.</b> Isolation Forest sobre la diferencia entre lo producido y lo esperado, comparando a cada "
    "vaca con su propio historial, con lo que predijo el modelo y con el resto del hato.",
    f"<b>Validación.</b> Los rangos de producción e intervalo entre partos se compararon con "
    f"{r['lactancias_checas']} lactancias de República Checa y son coherentes.",
]:
    E.append(Paragraph(t, B, bulletText="•"))

E.append(Paragraph("Resultados", H))
filas = [["Modelo", "Error medio", "Anticipa, 1.ª → 2.ª lactancia"]]
for k, v in R.items():
    filas.append([k + ("  (elegido)" if k == el else ""), f"{v['mae']:,.0f} kg", pct(v["deteccion_l1_l2"])])
filas.append(["Usar el promedio (referencia)", f"{m['mae_promedio']:,.0f} kg", "20% (azar)"])
t = Table([[Paragraph(c, CELB if i == 0 else CEL) for c in f] for i, f in enumerate(filas)],
          colWidths=[8.4 * cm, 3.6 * cm, 5.6 * cm])
t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), CLARO), ("LINEBELOW", (0, 0), (-1, 0), 1, NEGRO),
                       ("LINEBELOW", (0, 1), (-1, -1), .4, LINEA), ("TOPPADDING", (0, 0), (-1, -1), 5),
                       ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("ALIGN", (1, 0), (-1, -1), "RIGHT")]))
E.append(t)
E.append(Spacer(1, 7))
E.append(Paragraph(
    f"<b>Respuesta a tu pregunta del punto b):</b> sí, desde la 1.ª lactancia se puede anticipar qué vacas van a "
    f"producir poco en la 2.ª. El modelo elegido señala el {pct(R[el]['deteccion_l1_l2'])} de las que terminan en el "
    f"20% más bajo, cuando al azar sería el 20%. Sirve como lista para revisar alimentación y salud antes del parto, "
    f"no como diagnóstico.", P))
E.append(Paragraph(
    f"Con eso la demo arma dos listas: <b>{len(D['vigilancia'])} vacas a vigilar</b> en su próxima lactancia y "
    f"<b>{n_anom} vacas</b> que produjeron menos de lo esperado, cada una con el motivo calculado. Con tan pocos datos, "
    f"la regresión lineal superó ligeramente a XGBoost; XGBoost sin regularizar se aprende los casos de memoria.", P))

E.append(Paragraph("Límites y siguiente paso", H))
for t in [
    "El dataset trae un registro por lactancia, sin datos diarios, fechas ni clima: las curvas diarias son una "
    "reconstrucción y las anomalías se ven cuando la lactancia ya terminó.",
    "Para alertas a tiempo hacen falta registros diarios o por ordeño, con temperatura y humedad. El dataset de Bonn "
    "tiene justo eso, pero no es público: habría que pedírselo a los autores.",
    "En cuanto la finca tenga datos de producción, el mismo código corre cambiando el archivo de entrada.",
]:
    E.append(Paragraph(t, B, bulletText="•"))

E.append(Spacer(1, 8))
E.append(Paragraph(f"<b>Dashboard:</b> <link href='{URL}' color='#111111'>{URL}</link><br/>"
                   f"<b>Código:</b> <link href='{REPO}' color='#111111'>{REPO}</link>", S(fontSize=9.2, leading=13)))

SimpleDocTemplate(str(SALIDA), pagesize=letter, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.7 * cm,
                  bottomMargin=1.6 * cm, title="Demo: producción lechera por vaca").build(E)
print(f"{SALIDA.name} generado")
