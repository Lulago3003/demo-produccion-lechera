#!/usr/bin/env bash
# Gemma en Cloud Run con GPU NVIDIA L4: se enciende solo cuando alguien pregunta y se apaga solo sin uso.
# Correr en Cloud Shell, desde la raíz del proyecto:
#   bash despliegue/cloudrun.sh
# No crea VMs ni IPs públicas y no toca otros servicios del proyecto. Volver a correrlo publica la versión nueva.
set -euo pipefail

PROYECTO="${PROYECTO:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${REGION:-us-central1}"
SERVICIO="${SERVICIO:-gamma-gemma}"
ORIGENES="${GAMMA_ORIGENES:-https://gamma.aioros.tech,https://gamma-aioros.web.app}"
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
G=(--project "$PROYECTO")

[ -n "$PROYECTO" ] || { echo "Elige el proyecto primero: gcloud config set project ID_DEL_PROYECTO"; exit 1; }
gcloud auth list --filter=status:ACTIVE --format='value(account)' | grep -q . \
  || { echo "Cloud Shell no tiene una cuenta activa (revisa la verificación en dos pasos de la cuenta)."; exit 1; }

echo "Proyecto: $PROYECTO · región: $REGION · servicio: $SERVICIO"
echo "GPU NVIDIA L4, 4 vCPU, 16 GiB (unos 1,05 USD por hora encendido). Mínimo 0 instancias (apagado sin uso), máximo 1."
echo "Dashboard autorizado: $ORIGENES"
echo "Cobra por segundo solo mientras está encendido."
read -r -p "¿Continuar? (s/n) " respuesta
[ "$respuesta" = "s" ] || { echo "Cancelado."; exit 1; }

gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com "${G[@]}"

# Organizaciones creadas desde 2024 no dan permisos automáticos a la cuenta de servicio que construye la imagen.
# Este script no cambia permisos: si falta el rol, muestra el comando para que lo corra el administrador.
numero=$(gcloud projects describe "$PROYECTO" --format='value(projectNumber)')
cuenta="$numero-compute@developer.gserviceaccount.com"
if ! gcloud projects get-iam-policy "$PROYECTO" --flatten='bindings[].members' \
     --filter="bindings.members:serviceAccount:$cuenta AND bindings.role:roles/run.builder" \
     --format='value(bindings.role)' | grep -q run.builder; then
  cat <<FALTA

Falta un permiso para construir la imagen. Que lo otorgue el administrador del proyecto con:
  gcloud projects add-iam-policy-binding $PROYECTO --member=serviceAccount:$cuenta --role=roles/run.builder
y luego volver a correr este script.
FALTA
  exit 1
fi

# Carpeta de construcción: el proyecto con el Dockerfile de Cloud Run en la raíz
construccion=$(mktemp -d)
tar cf - -C "$RAIZ" --exclude=.git --exclude=.env --exclude=.local --exclude=.runtime --exclude=pesos \
  --exclude=artifacts --exclude=tests --exclude=data --exclude='__pycache__' . | tar xf - -C "$construccion"
cp "$RAIZ/despliegue/nube/Dockerfile" "$construccion/Dockerfile"
rm -f "$construccion/.dockerignore" "$construccion/.gcloudignore"

# La imagen pesa unos 7 GB (Ollama con CUDA y Gemma): hasta una hora para construirla
CLOUDSDK_BUILDS_TIMEOUT=3600 gcloud beta run deploy "$SERVICIO" "${G[@]}" --region "$REGION" --source "$construccion" --quiet \
  --gpu 1 --gpu-type nvidia-l4 --no-gpu-zonal-redundancy \
  --cpu 4 --memory 16Gi --no-cpu-throttling \
  --min-instances 0 --max-instances 1 --concurrency 4 --timeout 300 \
  --startup-probe tcpSocket.port=8080,initialDelaySeconds=0,failureThreshold=1,timeoutSeconds=240,periodSeconds=240 \
  --no-invoker-iam-check \
  --set-env-vars "^@^GAMMA_ORIGENES=$ORIGENES"
rm -rf "$construccion"

URL=$(gcloud run services describe "$SERVICIO" "${G[@]}" --region "$REGION" --format='value(status.url)')
cat <<LISTO

Listo. Gamma con Gemma: $URL
(La primera visita enciende la GPU y tarda un poco; después responde en segundos.)

Para el dashboard de $ORIGENES: en configuracion.json poner
  "servidor_gemma": "$URL"
y volver a publicar el index.html (python3 construir_dashboard.py).
LISTO
