# Contrato local de integración · Gamma v1

Base: `http://127.0.0.1:8765`. El dashboard y la API se sirven en el mismo origen.
Las escrituras requieren `Content-Type: application/json` y `X-Gamma-Token`.
El token local se genera en `.local/api-token` con permisos de propietario. No debe subirse
a Git ni incorporarse a una web pública. `/api/sesion` permite al dashboard del mismo
origen obtenerlo; **no publicar ese endpoint sin una capa de autenticación**.

| Método y ruta | Uso |
|---|---|
| `GET /api/estado` | Estado del servidor y disponibilidad del modelo Gemma. |
| `GET /api/configuracion` | Precio de referencia, densidad, fuentes y umbrales. |
| `GET /api/economia?precio=0.40&densidad=1.03` | Cálculo histórico comparable y próximas lactancias. |
| `POST /api/predecir` | Ejecutar el modelo sobre los rasgos de una lactancia completa. |
| `POST /api/sensores` | Guardar un evento, calcular resultados y devolver el estado de la finca. |
| `GET /api/sensores?finca=mi-finca&simulado=false` | Lecturas, series diarias, predicciones y alertas del ámbito exacto. |
| `POST /api/chat` | Consultar a Gemma con evidencia, tablas y gráficas. |
| `POST /api/simular` | Reemplazar el escenario sintético reservado `demo`, separado de datos reales. |

## Tres tipos de evento

Los identificadores `id`, `finca`, `vaca` y `zona` aceptan de 1 a 80 letras ASCII,
números, puntos, guiones y guiones bajos. La aplicación de captura debe asignar un `id`
estable y conservarlo en cada reintento. Un mensaje idéntico repetido devuelve `200`
y `duplicado=true`; un alta devuelve `201`. Un conflicto de ID o total diario devuelve
`400`, sin sobrescribir el registro. Los eventos son inmutables; la corrección histórica
de registros es una operación de mantenimiento, no una suma de nuevos totales.

**Producción diaria:** enviar el total de todos los ordeños de ese día, una sola vez
cuando esté completo. No enviar cada ordeño como si fuera el total diario.

```json
{
  "id": "v102-20261028",
  "finca": "mi-finca",
  "simulado": false,
  "tipo": "produccion_diaria",
  "vaca": "V102",
  "fecha": "2026-10-28",
  "lactancia": 2,
  "dia_lactancia": 45,
  "cantidad": 28.5,
  "unidad": "litros",
  "densidad_kg_litro": 1.03,
  "completo": true
}
```

`unidad` admite `kg` o `litros`. Se conserva el dato original y se normaliza a kg.
La fecha es el día local de Panamá. Se rechazan valores negativos, no finitos, futuros,
parcialidades y números de lactancia fuera de 1–4. Cero es un total válido.

**Ambiente:** el adaptador del gateway LoRaWAN debe entregar el mensaje ya decodificado
con temperatura en °C, humedad relativa en porcentaje y fecha ISO 8601 con zona horaria.

```json
{
  "id": "corral-a-20261029T110000Z",
  "finca": "mi-finca",
  "simulado": false,
  "tipo": "ambiente",
  "zona": "corral-a",
  "timestamp": "2026-10-29T11:00:00Z",
  "temperatura_c": 32,
  "humedad_pct": 80
}
```

Se calcula `THI = 0.8 × T + (HR / 100) × (T − 14.4) + 46.4`. Umbral exploratorio: 68.
Una lectura de más de 15 minutos se muestra desactualizada y no genera una alerta activa.
Una entrada fuera de orden no reemplaza la lectura más reciente.
[Fuente de fórmula y umbral: Universidad de Wisconsin](https://dairy.extension.wisc.edu/articles/heat-abatement-investment-scouter-a-new-decision-support-tool-for-dairy-heat-stress-management/).

**Lactancia cerrada:** ejecuta el modelo entrenado cuando existe una lactancia completa.
No se pasa una lectura diaria aislada al modelo de lactancias.

```json
{
  "id": "v102-cierre-l1",
  "finca": "mi-finca",
  "simulado": false,
  "tipo": "lactancia_cerrada",
  "vaca": "V102",
  "fecha": "2026-10-28",
  "rasgos": {
    "corregida": 5801,
    "pico": 24.4,
    "dias_pico": 56,
    "duracion": 271,
    "dias_secos": 69,
    "lact": 1,
    "media_hist": 5801,
    "semental": "Coyne PlanetET",
    "precio_litro": 0.40,
    "densidad_kg_litro": 1.03
  }
}
```

El mismo objeto `rasgos` se puede enviar directamente a `/api/predecir` para una consulta
sin persistencia. El caso anterior produce aproximadamente **6.343,08 kg corregidos**
para la segunda lactancia. Los sementales desconocidos usan nivel cero y quedan señalados
como desconocidos. El modelo seleccionado se lee del dataset: si es XGBoost, hacen falta
NumPy y XGBoost en el entorno; la regresión lineal guardada solo necesita Python estándar.

## MQTT

```bash
../.venv/bin/python -m pip install -r requirements-mqtt.txt
cp .env.example .env
# Editar .env con los datos proporcionados por el equipo de AIOROS.
set -a
source .env
set +a
../.venv/bin/python iniciar.py --mqtt
```

Temas de entrada:

```text
aioros/mi-finca/entrada/produccion_diaria
aioros/mi-finca/entrada/ambiente
aioros/mi-finca/entrada/lactancia_cerrada
```

`MQTT_FARM` debe coincidir con la finca del tema y del JSON. El puente no permite mezclar
otras fincas por accidente. Para servir varias, ejecutar instancias separadas con clientes
y colas distintos (`MQTT_CLIENT_ID`, `GAMMA_MQTT_DB`).

El publicador debe usar **QoS 1**. El puente persiste cada mensaje en SQLite **antes** de
confirmarlo al broker; luego lo envía al servidor local. Si el servidor cae, conserva la
cola y reintenta con espera creciente hasta un minuto. Un mensaje inválido pasa a
`rechazado`; no se reintenta indefinidamente. Los IDs y huellas impiden sumar dos veces.
La tabla `cola` de `.local/mqtt.sqlite3` permite auditar estado, intentos y causa resumida.

Se utiliza sesión MQTT persistente y reconexión. No se garantiza recepción mientras el
broker o el gateway estén apagados: el broker debe tener persistencia habilitada y el
gateway debe conservar sus lecturas durante los cortes. La cola local solo protege
mensajes ya recibidos. Un disco lleno puede detener el puente antes de confirmar.

Para brokers remotos se exige TLS con validación de certificado. `MQTT_CA_FILE` permite
una CA privada; no se desactiva la validación. Solo un broker local de prueba admite
`MQTT_TLS=0`. Las credenciales reales no fueron proporcionadas ni configuradas.

## Alertas y proyección temprana

La regla de producción exige dos días consecutivos con caída superior al 20%, comparando
cada día con sus siete días anteriores completos y consecutivos. Solo activa alertas si
el último total tiene como máximo dos días de antigüedad. Se separa por finca, vaca,
número de lactancia y fecha de parto inferida.

La proyección exige al menos 30 registros diarios consecutivos desde el primer día.
Escala la curva mediana con los primeros 30–60 días y suma lo observado más lo proyectado
hasta 305 días. No rellena días ausentes ni inventa un intervalo de confianza. Su
validación real y la incorporación de TimesFM/Chronos quedan pendientes de datos diarios.

## Chat desde otra interfaz

```json
{
  "pregunta": "Explica las alertas de esta vaca",
  "vaca": "803530",
  "tema": "auto",
  "precio_litro": 0.40,
  "densidad_kg_litro": 1.03,
  "finca": "mi-finca",
  "simulado": false,
  "historial": []
}
```

Temas: `auto`, `resumen`, `vaca`, `vigilancia`, `economia`, `sementales`, `sensores`.
Respuesta: `motor`, `respuesta`, `hechos`, `tabla`, `grafica`, `notas`, `ambito`,
`vaca_consultada`, `segundos`. Si `motor=gemma`, `modo=hallazgos_verificados` y
`hallazgos` permiten auditar qué conclusiones seleccionó el modelo. Si no responde, el
estado se indica y la evidencia calculada sigue disponible. Una sola inferencia de
Gemma se ejecuta a la vez para limitar memoria; otra consulta recibe `motor=ocupado`.

Los datos históricos de Indonesia y los datos de sensores no se fusionan automáticamente
por coincidencia de arete. El seguimiento consulta explícitamente la finca y el origen;
los pronósticos nuevos aparecen en «Inferencias de lactancias recibidas». La API y el
HTML no implementan cuentas, autenticación de ganaderos ni autorización multiusuario.
