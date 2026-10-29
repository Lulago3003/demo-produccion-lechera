# Gamma · entrega local del 29 de octubre de 2026

La ampliación funciona en el equipo local con **Gemma 3 de 4B cuantizado Q4_K_M**, el modelo
de producción ya entrenado y el dashboard existente. El código y los datos permanecen en
esta carpeta. Los repositorios remotos y la versión pública de GitHub Pages no se han actualizado.

## Abrirlo

En macOS, abre **`iniciar.command`** con doble clic. También puedes ejecutar:

```bash
cd demo_ganaderia
../.venv/bin/python iniciar.py
```

El lanzador comprueba Ollama y Gemma, genera el dashboard, inicia el servidor y abre
`http://127.0.0.1:8765`. Conserva esa terminal abierta; **Ctrl+C** cierra los procesos
que inició. `--sin-abrir` evita abrir otra pestaña. Si ya existe un servicio Gamma en ese
puerto, reutiliza esa sesión y no la cierra al salir.

En este equipo el ejecutable ya está en `.runtime/ollama` y el modelo está descargado en
`.local/ollama/`. En una instalación nueva de macOS, el lanzador descarga el ejecutable
oficial de Ollama 0.40.13, verifica su SHA-256 y descarga el modelo. Se requieren Python
3.11 o posterior y unos 4 GB de disco para el modelo y el motor. La memoria y la velocidad
dependen del equipo; la Jetson debe medirse aparte.

Tras la descarga, el sistema puede funcionar sin internet. La tipografía Barlow va incrustada en el
HTML (licencia OFL, `fuentes/OFL.txt`); los enlaces a las fuentes bibliográficas requieren internet solo si se abren.

## Qué está implementado

| Función | Estado y alcance |
|---|---|
| Kilos → litros → dinero | Funciona en el HTML estático y en la aplicación local. Precio y densidad editables, ficha por vaca, total histórico comparable y exportación CSV para Excel. |
| Gemma 3 de 4B | Instalado y probado con preguntas reales en este Mac. Identifica los hallazgos pertinentes para cada pregunta; las explicaciones se construyen con textos verificables. |
| Texto y gráficas en otra vista | Panel «Asistente Gemma», con historial de la sesión, alcance por vaca o hato, cifras, gráfica y tabla de evidencia. |
| Inferencia del modelo entrenado | API para una lactancia completa; usa el modelo elegido por el pipeline, actualmente regresión lineal. Incluye intervalo y valor económico. |
| Entrada MQTT | Puente con TLS para brokers remotos, QoS 1, reconexión y cola persistente. Probado con un broker local real y recuperación ante caída HTTP. |
| Avisos de la aplicación | Alertas dentro del dashboard, actualizadas cada tres segundos; interpretación opcional automática de Gemma al cambiar los datos del ámbito seleccionado. |
| Producción diaria | Guarda totales diarios completos, identifica caídas persistentes y muestra la serie. Regla exploratoria, no un diagnóstico ni un modelo validado en campo. |
| Calor | Calcula THI desde temperatura/humedad; identifica lecturas recientes por encima del umbral. Fórmula y fuente documentadas. |
| Proyección con 30–60 días | Baseline experimental de forma de curva, con bloqueo si faltan días desde el parto. No se presenta como TimesFM/Chronos ni como pronóstico validado. |
| Jetson | Código portable y guía de instalación preparados. Falta el equipo físico para medir GPU, RAM, latencia y operación continua. |

El dashboard de captura de datos que construye el compañero de AIOROS puede enviar eventos
a la API descrita en `INTEGRACION.md`. No se duplica ese producto. Los avisos pertenecen a
esta aplicación; no hay envíos por WhatsApp ni contactos automáticos con clientes.

## Demostración sugerida

El dashboard está organizado en pestañas: **Hato, Vacas, Sementales, Dinero, Asistente Gemma,
Sensores y Cómo se calculó**. Cada una tiene su propio enlace (`#hato`, `#vacas`, `#toros`,
`#dinero`, `#gemma`, `#sensores`, `#metodo`) y el botón atrás del navegador vuelve a la anterior.

1. **Hato:** la curva de lactancia típica y las dos listas. Un clic en una vaca abre su ficha.
2. **Vacas:** la curva real contra la esperada, con la franja del margen y su valor en dinero.
3. **Sementales:** quién da hijas más y menos productoras.
4. **Dinero:** cambia el precio de la leche y todo se recalcula.
5. **Asistente Gemma:** pregunta como lo haría un ganadero, por ejemplo «¿Cuánta plata se perdió
   por las vacas que produjeron menos?» o «¿Con qué toros me conviene inseminar?».
6. **Sensores:** «Cargar escenario simulado» trae 45 días de producción y una lectura de calor;
   la pestaña muestra en rojo cuántas alertas hay activas. El aviso de simulación sigue visible
   y esos datos se guardan separados de los reales.

El botón de simulación reemplaza **solo** los registros sintéticos de la finca reservada
`demo`, con `simulado=true`. Nunca borra los registros reales. Para una finca real, introduce
su identificador, elige «Registros reales recibidos» y pulsa «Consultar finca».

## Cálculo económico y fuente de precio

El precio inicial es **USD 0,45 por litro**: el pago por leche grado C que las acopiadoras
notificaron en Los Santos y Herrera en julio de 2026, cuando bajó de 48–50 a 45 centavos. Es
una referencia pública, no el precio de una finca concreta; se cambia en la pestaña Dinero o en
`configuracion.json`.

- [Panamá América, 22 de julio de 2026: recorte a 45 centavos por litro](https://www.panamaamerica.com.pa/provincias/rios-secos-en-pleno-julio-sequia-y-recorte-al-precio-de-la-leche-asfixian-al-sector).
- [TVN, 16 de febrero de 2025: unos 40 centavos de la industria más 10 de subsidio](https://www.tvn-2.com/contenido-exclusivo/produccion-leche-grado-c-franca-decadencia-produccion-agropecuaria-panama_1_2177493.html).
- [FAO: densidad de la leche](https://www.fao.org/4/y3548e/y3548e06.htm). Se usa **1,03 kg/L** como supuesto editable dentro del rango orientativo descrito.

Para una lactancia anómala con curva de Wood y `e305`, el sistema suma la curva reconstruida
hasta `min(duración, 305)` y compara con lo esperado en esos mismos días. Solo monetiza
la diferencia positiva, dividiéndola por la densidad y multiplicándola por el precio.
No monetiza directamente producción corregida a 305 días.

Con el dataset actual hay **37 lactancias comparables** y **27 sin base suficiente** para
este cálculo. A USD 0,45/L y 1,03 kg/L, la brecha histórica comparable representa
**USD 37.375,44** y **83.056,56 litros**. Es un escenario bruto acumulado entre lactancias,
no una pérdida demostrada ni un total anual. El reporte original y sus métricas predictivas
no han cambiado.

Para la siguiente lactancia se monetiza `p305`: kilos reales estimados, no `prox.pred`
(corregidos). El rango mostrado hereda el margen del modelo, con precio y densidad fijos;
no es un intervalo validado de ingresos ni de precios.

## Cómo se controla Gemma

Gemma interpreta la pregunta y redacta la respuesta con sus palabras, pero no puede inventar
cifras ni nombres:

1. **Tema.** El código reconoce el tema por palabras, incluidas las de Panamá («plata»,
   «pajilla», «perdió»). Si ninguna coincide, Gemma elige el tema de una lista cerrada.
2. **Evidencia.** El código consulta el registro y arma un catálogo de hallazgos con las
   cifras ya calculadas (por ejemplo, el monto en dinero o los toros que se distinguen).
3. **Selección.** Gemma elige y ordena los hallazgos que responden la pregunta (salida JSON).
4. **Redacción.** Gemma escribe dos a cuatro oraciones usando solo esa evidencia.
5. **Comprobación.** Cada número de la respuesta debe estar en la evidencia (se admite el
   redondeo) y no puede nombrar un semental que no esté en ella. Si algo no cuadra, se
   descarta la redacción y se muestran los hallazgos verificados tal cual. La pantalla
   indica cuál de los dos casos ocurrió.
6. **Salud.** Preguntas sobre medicamentos, tratamientos o diagnósticos reciben siempre la
   misma respuesta, sin pasar por Gemma: el registro no tiene datos de salud y eso lo decide
   un veterinario.

En las pruebas con preguntas reales, la comprobación rechazó una frase de Gemma que decía que
tres toros «promedian más de 600 kg» cuando uno tenía +302: en ese caso se mostró el texto
verificado. Las pruebas automáticas cubren estos casos en `tests/test_conversacion.py`.

El historial breve se usa como contexto; el navegador conserva hasta diez consultas durante
la sesión. No se guarda un historial de conversaciones en SQLite. El servidor escucha solo
en loopback, exige token para escrituras y chat, valida Host/Origin y sirve únicamente las
rutas públicas definidas. No es un servidor público multiusuario.

## Verificación

```bash
../.venv/bin/python -m unittest discover -s tests -v
node --check gamma.js
../.venv/bin/python construir_dashboard.py
```

La integración MQTT real se prueba aparte, con un entorno aislado:

```bash
python3 -m venv .runtime/mqtt-test
.runtime/mqtt-test/bin/python -m pip install amqtt==0.11.3 paho-mqtt==2.1.0
.runtime/mqtt-test/bin/python tests/probar_mqtt_real.py
```

El broker de esa prueba solo escucha en localhost y termina al finalizar. La aplicación
normal no requiere `amqtt`. El cliente MQTT de operación usa `requirements-mqtt.txt`.

## Pendientes externos para producción

- Broker, temas y credenciales de la finca; no se proporcionaron en la conversación.
- Contrato de datos y conexión con la aplicación de captura del compañero.
- Registros diarios reales para validar umbrales, el modelo temprano y el desempeño local.
- Jetson física para verificar memoria, GPU, latencias y resistencia a cortes.
- Despliegue del backend con autenticación y aislamiento de clientes antes de exponerlo en internet.
- Publicación de esta ampliación en los repositorios y en la web de AIOROS cuando corresponda.

Estos puntos no se presentan como completados: el resultado entregado es una aplicación
local funcional y verificada, con interfaces listas para integrar.
