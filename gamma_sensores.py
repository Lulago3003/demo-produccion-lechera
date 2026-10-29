"""Recepción persistente y evaluación de registros diarios y sensores ambientales."""
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
import re
import sqlite3
from statistics import mean
from zoneinfo import ZoneInfo

from gamma_core import RAIZ, leer, numero, predecir

PANAMA = ZoneInfo("America/Panama")


def identificador(v, nombre):
    if not isinstance(v, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", v):
        raise ValueError(f"{nombre}: usar de 1 a 80 letras, números, puntos, guiones o guiones bajos")
    return v


def validar_evento(e):
    if not isinstance(e, dict):
        raise ValueError("El evento debe ser un objeto JSON")
    e = dict(e)
    for k in ("id", "finca"):
        e[k] = identificador(e.get(k), k)
    if type(e.get("simulado", False)) is not bool:
        raise ValueError("simulado debe ser booleano")
    e["simulado"] = e.get("simulado", False)
    tipo = e.get("tipo")
    if tipo == "produccion_diaria":
        e["vaca"] = identificador(e.get("vaca"), "vaca")
        try:
            fecha = date.fromisoformat(e["fecha"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("fecha debe tener formato AAAA-MM-DD") from None
        if fecha > datetime.now(PANAMA).date():
            raise ValueError("No se admiten totales diarios futuros")
        if e.get("completo") is not True:
            raise ValueError("Enviar el total diario completo (completo: true), no un ordeño parcial")
        for k, mx in (("dia_lactancia", 700), ("lactancia", 4)):
            n = numero(e.get(k), k, 1, mx)
            if n != int(n):
                raise ValueError(f"{k} debe ser entero")
            e[k] = int(n)
        valor = numero(e.get("cantidad"), "cantidad", 0, 100)
        if e.get("unidad") not in ("kg", "litros"):
            raise ValueError("unidad debe ser kg o litros")
        densidad = numero(e.get("densidad_kg_litro", leer("configuracion.json")["densidad_kg_litro"]),
                          "densidad_kg_litro", 1, 1.1)
        e["kg"] = round(valor * (densidad if e["unidad"] == "litros" else 1), 4)
        e["fecha"] = fecha.isoformat()
        e["parto_estimado"] = (fecha - timedelta(days=e["dia_lactancia"] - 1)).isoformat()
        e["clave"] = f"{e['vaca']}:{e['fecha']}"
        e["orden"] = fecha.isoformat()
    elif tipo == "lactancia_cerrada":
        e["vaca"] = identificador(e.get("vaca"), "vaca")
        try:
            fecha = date.fromisoformat(e["fecha"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("fecha debe tener formato AAAA-MM-DD") from None
        if fecha > datetime.now(PANAMA).date():
            raise ValueError("No se admiten lactancias cerradas futuras")
        e["prediccion"] = predecir(leer("salida/datos_demo.json"), e.get("rasgos"))
        e["clave"] = f"{e['vaca']}:{fecha}:{e['rasgos']['lact']}"
        e["orden"] = fecha.isoformat()
    elif tipo == "ambiente":
        e["zona"] = identificador(e.get("zona"), "zona")
        e["temperatura_c"] = numero(e.get("temperatura_c"), "temperatura_c", -20, 60)
        e["humedad_pct"] = numero(e.get("humedad_pct"), "humedad_pct", 0, 100)
        try:
            t = datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00"))
            if t.tzinfo is None:
                raise ValueError()
        except (KeyError, TypeError, ValueError, AttributeError):
            raise ValueError("timestamp ISO 8601 debe incluir zona horaria") from None
        if t > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("El sensor está fechado en el futuro; revisar su reloj")
        e["timestamp"] = t.astimezone(timezone.utc).isoformat()
        e["clave"] = f"{e['zona']}:{e['timestamp']}"
        e["orden"] = e["timestamp"]
        e["thi"] = round(0.8 * e["temperatura_c"] + e["humedad_pct"] / 100 * (e["temperatura_c"] - 14.4) + 46.4, 2)
    else:
        raise ValueError("tipo debe ser produccion_diaria, lactancia_cerrada o ambiente")
    return e


class Registro:
    def __init__(self, path=None):
        self.path = str(path or RAIZ / ".local" / "sensores.sqlite3")
        from pathlib import Path
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.conexion() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS eventos (
                finca TEXT NOT NULL, simulado INTEGER NOT NULL, id TEXT NOT NULL,
                tipo TEXT NOT NULL, clave TEXT NOT NULL, orden TEXT NOT NULL,
                cuerpo TEXT NOT NULL, huella TEXT NOT NULL,
                PRIMARY KEY(finca,simulado,id), UNIQUE(finca,simulado,tipo,clave))""")
            db.execute("CREATE INDEX IF NOT EXISTS eventos_orden ON eventos(finca,simulado,orden)")

    def conexion(self):
        return sqlite3.connect(self.path, timeout=10)

    def insertar(self, entrada):
        e = validar_evento(entrada)
        cuerpo = json.dumps(e, sort_keys=True, ensure_ascii=False, allow_nan=False)
        huella = hashlib.sha256(cuerpo.encode()).hexdigest()
        with self.conexion() as db:
            try:
                db.execute("INSERT INTO eventos VALUES (?,?,?,?,?,?,?,?)",
                           (e["finca"], int(e["simulado"]), e["id"], e["tipo"], e["clave"], e["orden"], cuerpo, huella))
            except sqlite3.IntegrityError:
                previo = db.execute("SELECT huella FROM eventos WHERE finca=? AND simulado=? AND id=?",
                                    (e["finca"], int(e["simulado"]), e["id"])).fetchone()
                if previo and previo[0] == huella:
                    return {"insertado": False, "duplicado": True, "evento": e}
                raise ValueError("Conflicto: ya existe ese id, día de esa vaca o lectura de esa zona; no se sobrescribió") from None
        return {"insertado": True, "duplicado": False, "evento": e}

    def eventos(self, finca, simulado=False):
        identificador(finca, "finca")
        with self.conexion() as db:
            filas = db.execute("SELECT cuerpo FROM eventos WHERE finca=? AND simulado=? ORDER BY orden, id",
                               (finca, int(simulado))).fetchall()
        return [json.loads(r[0]) for r in filas]

    def resumen(self, datos, finca, simulado=False):
        eventos = self.eventos(finca, simulado)
        cfg = leer("configuracion.json")
        grupos, ambiente, predicciones = {}, {}, []
        for e in eventos:
            if e["tipo"] == "ambiente":
                ambiente[e["zona"]] = e
            elif e["tipo"] == "lactancia_cerrada":
                predicciones.append({"vaca": e["vaca"], "fecha": e["fecha"], **e["prediccion"]})
            else:
                clave = (e["vaca"], e["lactancia"], e["parto_estimado"])
                grupos.setdefault(clave, []).append(e)
        alertas, vacas = [], []
        hoy = datetime.now(PANAMA).date()
        for zona, e in ambiente.items():
            edad = (datetime.now(timezone.utc) - datetime.fromisoformat(e["timestamp"])).total_seconds()
            e["desactualizado"] = edad > 900
            e["sobre_umbral"] = e["thi"] >= cfg["thi_umbral"]
            if e["sobre_umbral"] and not e["desactualizado"]:
                alertas.append({"tipo": "calor", "referencia": zona,
                                "mensaje": "THI por encima del umbral de revisión; comprobar agua, sombra y ventilación.",
                                "valor": e["thi"], "umbral": cfg["thi_umbral"]})
        for (arete, lact, parto), serie in grupos.items():
            serie.sort(key=lambda e: e["dia_lactancia"])
            ultimo = serie[-1]
            actual = (hoy - date.fromisoformat(ultimo["fecha"])).days <= 2
            bajas = []
            for i in range(max(0, len(serie)-2), len(serie)):
                previos = serie[max(0, i-7):i]
                continuidad = len(previos) == 7 and serie[i]["dia_lactancia"] - previos[0]["dia_lactancia"] == 7
                base = mean(e["kg"] for e in previos) if previos else 0
                bajas.append(bool(continuidad and base > 0 and serie[i]["kg"] < base * (1-cfg["caida_diaria_umbral"])))
            alerta = len(bajas) == 2 and all(bajas) and actual
            if alerta:
                alertas.append({"tipo": "produccion", "referencia": arete,
                                "mensaje": "Dos días con caída superior al 20% frente a los siete días previos. Revisar el registro y el manejo; no identifica la causa.",
                                "valor": ultimo["kg"], "unidad": "kg/día"})
            proyectado = proyeccion_temprana(serie, datos["curvas_mediana"][str(lact)])
            vacas.append({"vaca": arete, "lactancia": lact, "parto_estimado": parto,
                          "fecha": ultimo["fecha"], "ultimo_kg": ultimo["kg"], "desactualizado": not actual,
                          "alerta": alerta, "registros": len(serie), "proyeccion": proyectado,
                          "serie": [{"dia": e["dia_lactancia"], "kg": e["kg"], "fecha": e["fecha"]} for e in serie]})
        return {"finca": finca, "simulado": bool(simulado), "eventos": len(eventos),
                "ambiente": list(ambiente.values()), "vacas": vacas, "alertas": alertas, "predicciones": predicciones,
                "nota": "Reglas exploratorias sin validación de campo. No diagnostican mastitis ni otras enfermedades. "
                        "Los datos simulados se almacenan separados de los reales.",
                "actualizado": datetime.now(timezone.utc).isoformat()}


def proyeccion_temprana(serie, curva):
    """Baseline de forma de curva, NO TimesFM/Chronos ni modelo validado en datos diarios."""
    puntos = {e["dia_lactancia"]: e["kg"] for e in serie if e["dia_lactancia"] <= 305}
    n = max(puntos, default=0)
    if n < 30:
        return {"disponible": False, "motivo": "Se necesitan al menos 30 totales diarios desde el parto."}
    if any(i not in puntos for i in range(1, n+1)):
        return {"disponible": False, "motivo": "Hay días faltantes desde el parto; no se rellenan con datos inventados."}
    ajuste = min(n, 60)
    base = sum(curva[:ajuste])
    if base <= 0:
        return {"disponible": False, "motivo": "No hay una curva de referencia utilizable."}
    factor = sum(puntos[i] for i in range(1, ajuste+1)) / base
    total = sum(puntos.values()) + sum(curva[n:305]) * factor
    return {"disponible": True, "kg_305": round(total, 2), "dias_observados": n, "dias_ajuste": ajuste,
            "metodo": "Curva del hato escalada con los primeros 30–60 días; proyección experimental sin intervalo validado.",
            "curva": [round(v * factor, 2) for v in curva]}


def simular(registro, datos):
    """Escenario explícito, repetible e idempotente: no modifica el dataset original."""
    hoy = datetime.now(PANAMA).date()
    # Se reemplaza únicamente el escenario sintético reservado, nunca registros reales.
    with registro.conexion() as db:
        db.execute("DELETE FROM eventos WHERE finca='demo' AND simulado=1")
    for i in range(1, 46):
        fecha = hoy - timedelta(days=45-i)
        kg = datos["curvas_mediana"]["2"][i-1] * (0.55 if i >= 44 else 0.92 + 0.025 * math.sin(i))
        registro.insertar({"id": f"demo-{hoy}-{i}", "finca": "demo", "simulado": True,
                           "tipo": "produccion_diaria", "vaca": "DEMO-001", "fecha": fecha.isoformat(),
                           "lactancia": 2, "dia_lactancia": i, "cantidad": round(kg, 2), "unidad": "kg", "completo": True})
    t = datetime.now(timezone.utc).replace(microsecond=0)
    registro.insertar({"id": "clima-" + t.strftime("%Y%m%dT%H%M%S"), "finca": "demo", "simulado": True,
                       "tipo": "ambiente", "zona": "corral-demo", "timestamp": t.isoformat(),
                       "temperatura_c": 32, "humedad_pct": 80})
    return registro.resumen(datos, "demo", True)
