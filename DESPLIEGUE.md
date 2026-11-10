# Gemma en un servidor (dashboard de demostración)

Con los clientes, Gemma corre en la Jetson de la finca, sin internet (`iniciar.py`, ver
[JETSON.md](JETSON.md)). Para el dashboard de demostración corre en un servidor, para que cualquiera
que abra el dashboard vea a Gemma explicar los resultados del modelo sin instalar nada.

## Recomendado para la demostración: Cloud Run con GPU, encendido solo al usarlo

Gemma corre en Cloud Run con una GPU NVIDIA L4 en `us-central1` (Iowa). No hay nada encendido mientras nadie
pregunta: la primera pregunta enciende el contenedor (Gemma va dentro de la imagen y se carga en la GPU), las
siguientes responden en segundos, y sin preguntas Cloud Run lo apaga solo. Google cobra por segundo solo
mientras está encendido. No usa VMs ni IP pública.

En Cloud Shell, con el proyecto elegido:

```bash
git clone https://github.com/Lulago3003/demo-produccion-lechera && cd demo-produccion-lechera && bash despliegue/cloudrun.sh
```

El script activa Cloud Run, Cloud Build y Artifact Registry, construye la imagen (unos 7 GB; la primera vez
tarda) y publica el servicio `gamma-gemma` con: 1 GPU L4 sin redundancia zonal, 8 vCPU, 32 GiB, mínimo 0 y
máximo 1 instancia, y acceso público sin depender de `allUsers` (`--no-invoker-iam-check`, la opción que Google
indica cuando la organización restringe los dominios). El primer despliegue con GPU en la región recibe cupo
automáticamente.

En organizaciones creadas desde 2024, la cuenta de servicio que construye la imagen no tiene permisos por
defecto. El script no cambia permisos: si falta `roles/run.builder`, muestra el comando para que lo corra el
administrador del proyecto.

Al final imprime la dirección del servicio. En el dashboard publicado se pone en `servidor_gemma` (ver abajo).
Con esa configuración, el dashboard no consulta al servidor al abrirse: Gemma solo se enciende cuando alguien
escribe una pregunta, y si se apagó por falta de uso, se vuelve a encender sola en la siguiente.

## En una VM de Google Cloud, siempre encendida

En la consola de Google Cloud, con el proyecto elegido arriba, abrir **Cloud Shell** (el ícono `>_`) y pegar:

```bash
git clone https://github.com/Lulago3003/demo-produccion-lechera && cd demo-produccion-lechera && bash despliegue/gcp.sh
```

El script muestra qué va a crear y pide confirmación. Crea solo recursos propios, con nombre `gamma-gemma`:

| Recurso | Para qué |
|---|---|
| VM `gamma-gemma` (Debian 12, `e2-standard-8`, 50 GB, sin GPU) | Corre Gemma, el modelo de producción y el dashboard |
| IP fija `gamma-gemma-ip` | Para que la dirección no cambie al reiniciar |
| Regla de firewall `gamma-gemma-https` (puertos 80 y 443) | Solo aplica a esa VM |

No toca otras VMs ni servicios del proyecto. Al terminar imprime la dirección con HTTPS, por
ejemplo `https://34-1-2-3.sslip.io` (la IP con guiones; el certificado es de Let's Encrypt). Volver a
correrlo actualiza el código en la misma VM y conserva los registros.

Opciones, delante del comando: `ZONA=us-east1-b`, `TIPO=n2-standard-8`, `VM=otro-nombre`,
`GAMMA_DOMINIO=gemma.aioros.tech` (si ese dominio ya apunta a la IP fija),
`GAMMA_ORIGENES=https://gamma.aioros.tech` (dashboards autorizados, separados por comas).

Para no gastar mientras no se usa: `gcloud compute instances stop gamma-gemma --zone us-central1-a`.
Con `start` vuelve en un par de minutos, con la misma dirección.

### Sin Cloud Shell: desde la consola

Si Cloud Shell no tiene credenciales (por ejemplo, una cuenta sin verificación en dos pasos), en
*Compute Engine → Crear instancia*: nombre `gamma-gemma`, `e2-standard-8`, Debian 12 con disco de 50 GB,
**Permitir tráfico HTTP y HTTPS**, IP externa estática y, en *Opciones avanzadas → Automatización →
Secuencia de comandos de inicio*:

```bash
#!/bin/bash
curl -fsSL https://raw.githubusercontent.com/Lulago3003/demo-produccion-lechera/main/despliegue/arranque_vm.sh | bash
```

En cada encendido instala lo que falte, trae la última versión del código y levanta Gamma. La dirección
queda en `https://IP-CON-GUIONES.sslip.io`; el registro, en `/var/log/gamma-arranque.log` de la VM.

## Conectar el dashboard que ya está publicado

El dashboard de `gamma.aioros.tech/lechera` necesita saber dónde está Gemma. En `configuracion.json`:

```json
"servidor_gemma": "https://LA-DIRECCION-QUE-IMPRIMIÓ-EL-SCRIPT"
```

Después `python3 construir_dashboard.py` y volver a publicar el `index.html`. Al abrirlo, la pestaña
Asistente Gemma dice «Gemma disponible en el servidor». El origen `https://gamma.aioros.tech` ya está
autorizado por defecto. También se puede insertar entero en otra página con
`<iframe src="https://LA-DIRECCION/#gemma">`, que solo se permite a los orígenes autorizados.

## Qué queda público y qué no

- **Preguntar a Gemma:** cualquiera que tenga la dirección, con un límite de 8 preguntas por minuto
  por persona y 30 en total, para que nadie acapare el servidor. Gemma atiende una consulta a la vez.
- **Enviar registros de sensores:** solo con `GAMMA_CLAVE`, que se genera en la VM
  (`/opt/gamma/.env`) y nunca llega al navegador. El puente MQTT la lee de la misma variable.
- **Escenario simulado:** se puede cargar desde el dashboard; usa la finca reservada `demo`, separada
  de los datos reales.

## Velocidad: con o sin GPU

Sin GPU, Gemma responde más lento que en una Mac o una Jetson con GPU. Para una demostración con
clientes conviene medirlo en la VM y, si hace falta, pasar a una VM con GPU (por ejemplo una NVIDIA L4).
Muchos proyectos tienen la cuota de GPU en cero y hay que pedirla en *IAM y administración → Cuotas*.

## En otro servidor con Docker

```bash
cp .env.example .env            # completar la sección "Servidor con Docker"
docker compose --profile https up -d --build
```

Sin `--profile https`, Gamma queda solo en `http://127.0.0.1:8765` del servidor, para ponerlo detrás de un
proxy propio. Con GPU NVIDIA, agregar al servicio `ollama` de `docker-compose.yml` la reserva de GPU de
Docker (`deploy.resources.reservations.devices`).

Revisar: `docker compose ps` y `docker compose logs --tail 50 preparar gamma ollama`.
