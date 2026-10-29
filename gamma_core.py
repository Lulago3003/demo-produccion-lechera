"""Cálculos auditables. Sin acceso a la red ni dependencia del modelo de lenguaje."""
import json
import math
from pathlib import Path

RAIZ = Path(__file__).resolve().parent


def leer(nombre):
    return json.loads((RAIZ / nombre).read_text(encoding="utf-8"))


def numero(valor, nombre, minimo, maximo):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ValueError(f"{nombre} debe ser numérico")
    if not math.isfinite(valor) or not minimo <= valor <= maximo:
        raise ValueError(f"{nombre} debe estar entre {minimo} y {maximo}")
    return float(valor)


def parametros(precio=None, densidad=None):
    c = leer("configuracion.json")
    p = numero(c["precio_litro"] if precio is None else precio, "precio_litro", 0, 10)
    rho = numero(c["densidad_kg_litro"] if densidad is None else densidad, "densidad_kg_litro", 1, 1.1)
    return p, rho


def wood(w, dias):
    return [w[0] * t ** w[1] * math.exp(-w[2] * t) for t in range(1, dias + 1)]


def economia(datos, precio=None, densidad=None, vaca=None):
    """Compara kilos reales reconstruidos y esperados sobre el MISMO horizonte.

    Nunca monetiza directamente kg corregidos ni llama pérdida a una causalidad probada.
    El total es histórico, mezcla lactancias/fechas y no equivale a un ingreso anual.
    """
    p, rho = parametros(precio, densidad)
    registros, futuras, sin_base = [], [], 0
    for arete, v in datos["vacas"].items():
        if vaca is not None and str(vaca) != arete:
            continue
        for l in v["lacts"]:
            if not l.get("anom"):
                continue
            if not l.get("w") or l.get("e305") is None:
                sin_base += 1
                continue
            dias = min(305, l["dur"])
            real = sum(wood(l["w"], dias))
            esperada = l["e305"]
            brecha = max(0, esperada - real)
            registros.append({"vaca": arete, "nombre": v["nombre"], "lactancia": l["n"],
                              "dias": dias, "kg_reconstruidos": round(real, 2),
                              "kg_esperados": round(esperada, 2), "litros_brecha": round(brecha / rho, 2),
                              "valor_brecha": round(brecha / rho * p, 2)})
        prox = v.get("prox")
        if prox:
            litros = prox["p305"] / rho
            margen = datos["modelo"]["margen"]
            futuras.append({"vaca": arete, "nombre": v["nombre"], "lactancia": prox["n"],
                            "litros": round(litros, 2), "valor": round(litros * p, 2),
                            "valor_bajo": round(litros * p * (1 - margen), 2),
                            "valor_alto": round(litros * p * (1 + margen), 2)})
    return {"precio_litro": p, "densidad_kg_litro": rho,
            "brecha_historica_usd": round(sum(r["valor_brecha"] for r in registros), 2),
            "litros_brecha": round(sum(r["litros_brecha"] for r in registros), 2),
            "lactancias_comparables": len(registros), "sin_base_comparable": sin_base,
            "registros": sorted(registros, key=lambda r: -r["valor_brecha"]), "proximas": futuras,
            "nota": "Escenario de ingreso bruto a precio constante; no es pérdida demostrada, ganancia ni total anual. "
                    "Solo lactancias anómalas con curva y predicción comparables, hasta 305 días. "
                    "Datos públicos de Indonesia; el precio ilustrativo es de Panamá."}


def predecir(datos, entrada):
    """Inferencia del modelo elegido al entrenar. No requiere volver a entrenar."""
    if not isinstance(entrada, dict):
        raise ValueError("Se requiere un objeto con los rasgos de la última lactancia completa")
    limites = {"corregida": (2000, 25000), "pico": (0.01, 80), "dias_pico": (1, 460),
               "duracion": (150, 700), "dias_secos": (0, 365), "lact": (1, 3), "media_hist": (2000, 25000)}
    x = {k: numero(entrada.get(k), k, *v) for k, v in limites.items()}
    if x["lact"] != int(x["lact"]) or x["dias_pico"] >= x["duracion"]:
        raise ValueError("Lactancia entera de 1 a 3 y día del pico anterior al final de lactancia")
    niveles = leer("modelos/nivel_semental.json")["niveles"]
    sire = entrada.get("semental", "")
    if not isinstance(sire, str):
        raise ValueError("semental debe ser texto")
    x["nivel_semental"] = niveles.get(sire, 0)
    lin = leer("modelos/regresion_lineal.json")
    if datos["modelo"]["elegido"] == "XGBoost regularizado":
        import numpy as np
        import xgboost as xgb
        model = xgb.XGBRegressor()
        model.load_model(RAIZ / "modelos/xgboost.json")
        pred = float(model.predict(np.array([[x[k] for k in lin["rasgos"]]]))[0])
    else:
        pred = lin["intercepto"] + sum(lin["coeficientes"][k] * x[k] for k in lin["rasgos"])
    if pred <= 0:
        raise ValueError("La combinación de rasgos produjo una predicción fuera de rango")
    n = int(x["lact"]) + 1
    real = pred * datos["factor_real_corregida"][str(n)]
    p, rho = parametros(entrada.get("precio_litro"), entrada.get("densidad_kg_litro"))
    m = datos["modelo"]["margen"]
    return {"modelo": datos["modelo"]["elegido"], "lactancia": n, "kg_corregidos": round(pred, 2),
            "kg_reales_305_estimados": round(real, 2), "litros_estimados": round(real / rho, 2),
            "valor_bruto_usd": round(real / rho * p, 2),
            "intervalo_kg_corregidos": [round(pred * (1-m), 2), round(pred * (1+m), 2)],
            "semental_conocido": sire in niveles,
            "nota": "Validado en el dataset público, pendiente de validación en la finca de destino."}
