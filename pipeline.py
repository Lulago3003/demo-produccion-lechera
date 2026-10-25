# -*- coding: utf-8 -*-
"""
Demo de producción lechera por vaca — AIOROS.

  1. Limpieza de datos (Holstein, Indonesia, un registro por lactancia)
  2. Curva diaria de cada lactancia (modelo de Wood) a partir de pico, día del pico y total
  3. a) Predicción de la siguiente lactancia: XGBoost regularizado vs regresión lineal
  4. b) Anomalías de baja producción con Isolation Forest, comparando a cada vaca con su
        historial, con lo que esperaba el modelo y con el resto del hato
  5. Validación de rangos contra el dataset de República Checa

Todas las cifras y los motivos de cada alerta los calcula este código; nada los inventa.
Salida: salida/datos_demo.json (alimenta el dashboard), salida/metricas.json y los dos modelos
entrenados en modelos/.

Uso:  python pipeline.py                    # elige el modelo de menor error en la validación
      python pipeline.py --modelo xgboost   # fuerza XGBoost (o --modelo lineal)
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from scipy.optimize import brentq
from scipy.special import gamma, gammainc
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import GroupKFold

RAIZ = Path(__file__).parent
IND = RAIZ / "data" / "indonesia_holstein_lactancias.xlsx"
CHE = RAIZ / "data" / "checa_desempeno_vacas.xlsx"
SAL = RAIZ / "salida"
MOD = RAIZ / "modelos"
SAL.mkdir(exist_ok=True)
MOD.mkdir(exist_ok=True)

HOJAS = {1: "1st Lactation", 2: "2nd Lactation", 3: "3rd Lactation", 4: "4rd Lactation"}
COLUMNAS = {"Animal Number": "vaca", "Animal Name": "nombre",
            "Dam, Official Reg. Number (ORN)": "madre", "Sire Bull ID/ORN": "semental",
            "Total Milk Yield (Kg)": "total", "Corrected Milk (Kg)": "corregida",
            "Length of Lactation": "duracion", "Days Dry (Days)": "dias_secos",
            "Peak Yield (Kg)": "pico", "Days To Peak (Days)": "dias_pico"}
DIAS_CURVA = 305
SEMILLA = 0
CUANTIL_BAJO = 0.20       # "entre las más bajas" = 20 % inferior
CONTAMINACION = 0.06      # proporción esperada de anomalías para Isolation Forest


# ───────────────────────────────────────────── 1. limpieza
def cargar_y_limpiar():
    partes = []
    for n, hoja in HOJAS.items():
        d = pd.read_excel(IND, sheet_name=hoja).rename(columns=COLUMNAS)
        d["lact"] = n
        partes.append(d[list(COLUMNAS.values()) + ["lact"]])
    crudo = pd.concat(partes, ignore_index=True)

    reglas = [
        ("Filas de resumen al pie de cada hoja (mínimo, máximo, promedio, desviación, CV)",
         lambda d: d["vaca"].notna() & pd.to_numeric(d["vaca"], errors="coerce").isna()),
        ("Filas vacías (sin vaca o sin producción)",
         lambda d: d["vaca"].isna() | d["corregida"].isna() | d["total"].isna()),
        ("Registro duplicado de la misma vaca y lactancia",
         lambda d: d.duplicated(subset=["vaca", "lact"], keep="first")),
        ("Lactancia de menos de 150 días (incompleta)", lambda d: d["duracion"] < 150),
        ("Producción corregida menor a 2,000 kg", lambda d: d["corregida"] < 2000),
        ("Pico fuera de rango (0 o más de 80 kg/día)", lambda d: (d["pico"] <= 0) | (d["pico"] > 80)),
        ("Día del pico imposible", lambda d: (d["dias_pico"] <= 0) | (d["dias_pico"] >= d["duracion"])),
    ]
    d, removidos = crudo.copy(), []
    for motivo, regla in reglas:
        mascara = regla(d).fillna(False)
        removidos.append({"motivo": motivo, "n": int(mascara.sum())})
        d = d[~mascara]
    d["vaca"] = pd.to_numeric(d["vaca"]).astype(int)
    d["nombre"] = d["nombre"].fillna("").astype(str).str.strip()
    d["semental"] = d["semental"].fillna("sin registro").astype(str).str.strip()
    return crudo, d.sort_values(["vaca", "lact"]).reset_index(drop=True), removidos


# ───────────────────────────────────────────── 2. curva de Wood
def _total_wood(b, tp, yp, L):
    c = b / tp
    a = yp / (tp ** b * np.exp(-b))
    return a * c ** (-(b + 1)) * gamma(b + 1) * gammainc(b + 1, c * L)


def ajustar_wood(tp, yp, total, L):
    """y(t) = a·t^b·e^(-c·t). El pico fija dos ecuaciones y el total la tercera."""
    try:
        b = brentq(lambda b: _total_wood(b, tp, yp, L) - total, 1e-3, 5.0)
    except ValueError:
        return None
    c = b / tp
    return yp / (tp ** b * np.exp(-b)), b, c


def curva(a, b, c, dias):
    t = np.arange(1, dias + 1, dtype=float)
    return a * t ** b * np.exp(-c * t)


# ───────────────────────────────────────────── 3. predicción de la siguiente lactancia
RASGOS = ["corregida", "pico", "dias_pico", "duracion", "dias_secos", "lact", "media_hist"]
MODELOS = {"lineal": "Regresión lineal", "xgboost": "XGBoost regularizado"}


def pares_consecutivos(d):
    d = d.copy()
    d["media_hist"] = d.groupby("vaca")["corregida"].transform(lambda s: s.expanding().mean())
    sig = d[["vaca", "lact", "corregida"]].rename(columns={"corregida": "objetivo"})
    sig["lact"] -= 1
    pares = d.merge(sig, on=["vaca", "lact"], how="inner")
    return d, pares


def modelo_xgb():
    return xgb.XGBRegressor(n_estimators=300, learning_rate=0.03, max_depth=2, min_child_weight=10,
                            subsample=0.8, colsample_bytree=0.8, reg_lambda=5.0, random_state=SEMILLA)


def deteccion_bajas(y, p):
    bajo, anticipado = y <= np.quantile(y, CUANTIL_BAJO), p <= np.quantile(p, CUANTIL_BAJO)
    return float((bajo & anticipado).sum() / bajo.sum())


def evaluar_modelos(pares, forzado=None):
    X, y, grupos = pares[RASGOS].values, pares["objetivo"].values, pares["vaca"].values
    cv = GroupKFold(n_splits=5)                  # la misma vaca nunca está en entrenamiento y prueba
    oof, resultados = {}, {}
    for nombre, fabrica in [(MODELOS["lineal"], LinearRegression), (MODELOS["xgboost"], modelo_xgb)]:
        p = np.zeros(len(y))
        for tr, te in cv.split(X, y, grupos):
            p[te] = fabrica().fit(X[tr], y[tr]).predict(X[te])
        oof[nombre] = p
        l12 = pares["lact"].values == 1
        resultados[nombre] = {
            "mae": float(np.abs(p - y).mean()),
            "r2": float(1 - ((p - y) ** 2).sum() / ((y - y.mean()) ** 2).sum()),
            "deteccion": float(np.mean([deteccion_bajas(y[pares["lact"].values == n], p[pares["lact"].values == n])
                                        for n in sorted(pares["lact"].unique())])),
            "mae_l1_l2": float(np.abs(p[l12] - y[l12]).mean()),
            "deteccion_l1_l2": deteccion_bajas(y[l12], p[l12]),
        }
    elegido = MODELOS[forzado] if forzado else min(resultados, key=lambda k: resultados[k]["mae"])
    base = float(np.abs(y.mean() - y).mean())
    return resultados, elegido, oof[elegido], base


def entrenar_y_guardar(pares):
    """Entrena los dos modelos con todos los pares y los guarda en modelos/ para usarlos fuera."""
    X, y = pares[RASGOS].values, pares["objetivo"].values
    lineal, arboles = LinearRegression().fit(X, y), modelo_xgb().fit(X, y)
    (MOD / "regresion_lineal.json").write_text(json.dumps(
        {"rasgos": RASGOS, "objetivo": "producción corregida a 305 días de la siguiente lactancia (kg)",
         "intercepto": float(lineal.intercept_),
         "coeficientes": {k: float(c) for k, c in zip(RASGOS, lineal.coef_)},
         "pares_de_entrenamiento": int(len(y))}, ensure_ascii=False, indent=2), encoding="utf-8")
    arboles.save_model(MOD / "xgboost.json")
    return {MODELOS["lineal"]: lineal, MODELOS["xgboost"]: arboles}


# ───────────────────────────────────────────── 4. anomalías
def anomalias(d, pares, oof):
    d = d.copy()
    g = d.groupby("lact")
    for col in ["corregida", "pico", "duracion", "dias_pico"]:
        d[f"z_{col}"] = (d[col] - g[col].transform("mean")) / g[col].transform("std")
    d["percentil_par"] = g["corregida"].rank(pct=True)

    # esperado por el modelo (fuera de muestra) para cada lactancia que tiene una anterior
    esp = pares[["vaca", "lact"]].copy()
    esp["lact"] += 1
    esp["esperado"] = oof
    d = d.merge(esp, on=["vaca", "lact"], how="left")
    d["resid_kg"] = d["corregida"] - d["esperado"]
    d["resid_pct"] = d["resid_kg"] / d["esperado"]
    previa = d.groupby("vaca")["corregida"].transform(lambda s: s.shift().expanding().mean())
    d["hist_pct"] = d["corregida"] / previa - 1

    d["puntaje"], d["anomala"] = np.nan, False
    grupos = [("primera", d["lact"] == 1, ["z_corregida", "z_pico", "z_duracion", "z_dias_pico"]),
              ("siguientes", (d["lact"] > 1) & d["esperado"].notna(),
               ["z_corregida", "z_pico", "z_duracion", "resid_pct", "hist_pct"])]
    for _, mascara, cols in grupos:
        sub = d.loc[mascara, cols].astype(float)
        sub = (sub - sub.mean()) / sub.std()
        iso = IsolationForest(n_estimators=400, contamination=CONTAMINACION, random_state=SEMILLA).fit(sub.values)
        d.loc[mascara, "puntaje"] = -iso.decision_function(sub.values)
        d.loc[mascara, "anomala"] = iso.predict(sub.values) == -1
    # solo interesan las de BAJA producción: Isolation Forest marca rarezas en ambos sentidos
    baja = np.where(d["esperado"].notna(), d["resid_kg"] < 0, d["z_corregida"] < 0)
    d["anomala"] = d["anomala"] & baja
    return d


def motivos(r, medianas):
    m = []
    if pd.notna(r["resid_kg"]) and r["resid_kg"] < 0:
        m.append(f"{abs(r['resid_kg']):,.0f} kg ({abs(r['resid_pct'])*100:.0f}%) menos de lo que el modelo "
                 f"esperaba por su lactancia anterior")
    if pd.notna(r["hist_pct"]) and r["hist_pct"] < -0.05:
        m.append(f"{abs(r['hist_pct'])*100:.0f}% por debajo de su promedio en lactancias anteriores")
    if r["percentil_par"] <= 0.25:
        m.append(f"en el {max(1, round(r['percentil_par']*100))}% más bajo de las vacas en "
                 f"{int(r['lact'])}.ª lactancia")
    med = medianas.loc[r["lact"]]
    if r["z_pico"] < -1:
        m.append(f"pico de {r['pico']:.1f} kg/día, por debajo de la mediana de {med['pico']:.1f}")
    if r["z_duracion"] < -1:
        m.append(f"lactancia corta: {r['duracion']:.0f} días contra {med['duracion']:.0f} de mediana")
    return m or ["combinación inusual de pico, duración y producción frente al hato"]


# ───────────────────────────────────────────── 5. validación con República Checa
def validar(d):
    che = pd.read_excel(CHE, sheet_name="Dataset")
    che_int = che.loc[che["CalvInt"] > 0, "CalvInt"]
    ind_int = (d["duracion"] + d["dias_secos"]).dropna()
    rng = lambda s: {"p10": float(s.quantile(.1)), "mediana": float(s.median()), "p90": float(s.quantile(.9))}
    tabla = [
        {"variable": "Producción por lactancia (kg)", "indonesia": rng(d["corregida"]), "checa": rng(che["MY (kg)"])},
        {"variable": "Intervalo entre partos (días)", "indonesia": rng(ind_int), "checa": rng(che_int),
         "nota": "En Indonesia se aproxima como duración de la lactancia + días secos."},
    ]
    limites = {"Grasa (%)": [float(che["F (%)"].quantile(.01)), float(che["F (%)"].quantile(.99))],
               "Proteína (%)": [float(che["P (%)"].quantile(.01)), float(che["P (%)"].quantile(.99))],
               "Lactosa (%)": [float(che["L (%)"].quantile(.01)), float(che["L (%)"].quantile(.99))],
               "Intervalo entre partos (días)": [float(che_int.quantile(.01)), float(che_int.quantile(.99))]}
    return tabla, limites, int(len(che))


# ───────────────────────────────────────────── main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modelo", choices=["auto", *MODELOS], default="auto",
                    help="auto: el de menor error en la validación cruzada (por defecto)")
    forzado = None if (m := ap.parse_args().modelo) == "auto" else m

    crudo, d, removidos = cargar_y_limpiar()
    print(f"[1] {len(crudo)} registros -> {len(d)} válidos ({d['vaca'].nunique()} vacas)")

    params, curvas = {}, {n: [] for n in HOJAS}
    for i, r in d.iterrows():
        w = ajustar_wood(r["dias_pico"], r["pico"], r["total"], r["duracion"])
        if w:
            params[i] = w
            # todas hasta 305 días (estándar lechero): así la mediana usa siempre las mismas
            # vacas y no se quiebra al final, cuando muchas lactancias ya terminaron
            curvas[r["lact"]].append(curva(*w, DIAS_CURVA))
    mediana_curva = {n: np.nanmedian(np.vstack(v), axis=0) for n, v in curvas.items()}
    # kilos reales en los primeros 305 días de cada lactancia (para comparar real contra esperado)
    s305 = {i: float(curva(*w, min(int(d.loc[i, "duracion"]), DIAS_CURVA)).sum()) for i, w in params.items()}
    print(f"[2] curva reconstruida en {len(params)} de {len(d)} lactancias")

    d, pares = pares_consecutivos(d)
    resultados, elegido, oof, base = evaluar_modelos(pares, forzado)
    for k, v in resultados.items():
        print(f"[3] {k:22s} MAE {v['mae']:.0f} kg | R2 {v['r2']:.2f} | anticipa {v['deteccion']*100:.0f}% "
              f"| 1ra->2da: MAE {v['mae_l1_l2']:.0f}, anticipa {v['deteccion_l1_l2']*100:.0f}%")
    print(f"    elegido: {elegido} ({'forzado' if forzado else 'menor error'}) | referencia (promedio): "
          f"MAE {base:.0f} kg | {len(pares)} pares")

    # lista de vigilancia: siguiente lactancia de cada vaca, con el modelo elegido entrenado con todo
    final = entrenar_y_guardar(pares)[elegido]
    print(f"[3] modelos guardados en {MOD.name}/: regresion_lineal.json y xgboost.json")
    ultima = d.loc[d.groupby("vaca")["lact"].idxmax()]
    ultima = ultima[ultima["lact"] < 4].copy()
    ultima["pred_siguiente"] = final.predict(ultima[RASGOS].values)
    ultima["percentil_pred"] = ultima.groupby("lact")["pred_siguiente"].rank(pct=True)
    vigilar = ultima[ultima["percentil_pred"] <= CUANTIL_BAJO].sort_values("percentil_pred")
    print(f"[3] lista de vigilancia: {len(vigilar)} vacas de {len(ultima)} con una lactancia siguiente posible")

    d = anomalias(d, pares, oof)
    medianas = d.groupby("lact")[["pico", "duracion"]].median()
    anom = d[d["anomala"]].sort_values("puntaje", ascending=False)
    print(f"[4] anomalías de baja producción: {len(anom)} lactancias en {anom['vaca'].nunique()} vacas")

    # El modelo predice producción CORREGIDA a 305 días; las curvas están en kilos REALES.
    # La corrección sube a las primerizas y baja a las adultas, así que se convierte con el
    # factor de esa misma lactancia (pasadas) o la mediana de su grupo (próxima lactancia).
    d["s305"] = pd.Series(s305)
    k305 = (d["s305"] / d["corregida"]).groupby(d["lact"]).median()
    prox = {str(int(r["vaca"])): {"n": int(r["lact"]) + 1, "pred": round(r["pred_siguiente"]),
                                   "p305": round(r["pred_siguiente"] * k305[int(r["lact"]) + 1])}
            for _, r in ultima.iterrows()}
    print(f"[3] curva prevista para {len(prox)} vacas | factor real/corregida por lactancia: "
          + ", ".join(f"{int(n)}.ª {k:.2f}" for n, k in k305.items()))

    tabla, limites, n_checa = validar(d)
    print(f"[5] validación contra {n_checa} lactancias de República Checa")

    def motivos_vigilancia(r):
        m = [f"producción prevista en {int(r['lact'])+1}.ª lactancia: {r['pred_siguiente']:,.0f} kg, "
             f"en el {max(1, round(r['percentil_pred']*100))}% más bajo del grupo"]
        med = medianas.loc[r["lact"]]
        if r["pico"] < med["pico"]:
            m.append(f"pico de {r['pico']:.1f} kg/día en su {int(r['lact'])}.ª lactancia (mediana {med['pico']:.1f})")
        if r["duracion"] < med["duracion"]:
            m.append(f"lactancia de {r['duracion']:.0f} días (mediana {med['duracion']:.0f})")
        return m

    vacas = {}
    for i, r in d.iterrows():
        v = vacas.setdefault(str(r["vaca"]), {"nombre": r["nombre"], "semental": r["semental"], "lacts": [],
                                              "prox": prox.get(str(r["vaca"]))})
        w = params.get(i)
        v["lacts"].append({"n": int(r["lact"]), "total": round(r["total"]), "corr": round(r["corregida"]),
                           "dur": int(r["duracion"]), "pico": round(r["pico"], 1), "dpico": int(r["dias_pico"]),
                           "secos": None if pd.isna(r["dias_secos"]) else int(r["dias_secos"]),
                           "esp": None if pd.isna(r["esperado"]) else round(r["esperado"]),
                           "e305": None if pd.isna(r["esperado"]) or pd.isna(r["s305"])
                                   else round(r["esperado"] * r["s305"] / r["corregida"]),
                           # cifras significativas, no decimales fijos: 'a' puede ser del orden de 1e-5
                           "w": None if w is None else [float(f"{x:.8g}") for x in w],
                           "anom": bool(r["anomala"])})

    salida = {
        "resumen": {"registros_crudos": int(len(crudo)), "lactancias_validas": int(len(d)),
                    "vacas": int(d["vaca"].nunique()),
                    "sementales": int(d.loc[d["semental"] != "sin registro", "semental"].nunique()),
                    "curvas_reconstruidas": len(params), "removidos": removidos,
                    "pares": int(len(pares)), "lactancias_checas": n_checa},
        "curvas_mediana": {str(n): [None if np.isnan(x) else round(float(x), 2) for x in c]
                           for n, c in mediana_curva.items()},
        "n_curvas": {str(n): len(v) for n, v in curvas.items()},
        "factor_real_corregida": {str(int(n)): round(float(k), 4) for n, k in k305.items()},
        "modelo": {"resultados": resultados, "elegido": elegido, "forzado": bool(forzado), "mae_promedio": base,
                   "cuantil_bajo": CUANTIL_BAJO, "contaminacion": CONTAMINACION},
        "vigilancia": [{"vaca": str(r["vaca"]), "nombre": r["nombre"], "semental": r["semental"],
                        "lact": int(r["lact"]), "pred": round(r["pred_siguiente"]),
                        "percentil": round(r["percentil_pred"] * 100), "motivos": motivos_vigilancia(r)}
                       for _, r in vigilar.iterrows()],
        "anomalias": [{"vaca": str(r["vaca"]), "nombre": r["nombre"], "semental": r["semental"],
                       "lact": int(r["lact"]), "corr": round(r["corregida"]),
                       "esp": None if pd.isna(r["esperado"]) else round(r["esperado"]),
                       "puntaje": round(float(r["puntaje"]), 3), "motivos": motivos(r, medianas)}
                      for _, r in anom.iterrows()],
        "validacion": {"tabla": tabla, "limites": limites},
        "vacas": vacas,
    }
    (SAL / "datos_demo.json").write_text(json.dumps(salida, ensure_ascii=False, separators=(",", ":")),
                                         encoding="utf-8")
    (SAL / "metricas.json").write_text(json.dumps({"resumen": salida["resumen"], "modelo": salida["modelo"],
                                                    "validacion": salida["validacion"]},
                                                   ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"listo: salida/datos_demo.json ({(SAL / 'datos_demo.json').stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
