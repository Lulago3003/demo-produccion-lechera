#!/usr/bin/env bash
# Pone Gamma con Gemma en una VM nueva de Google Cloud, con HTTPS. Correr en Cloud Shell:
#   bash despliegue/gcp.sh
# Solo crea recursos propios con el nombre de VM (por defecto gamma-gemma): la VM, su IP fija y
# una regla de firewall que aplica únicamente a esa VM. No toca otras VMs ni servicios del proyecto.
# Volver a correrlo actualiza el código en la misma VM.
set -euo pipefail

PROYECTO="${PROYECTO:-$(gcloud config get-value project 2>/dev/null)}"
ZONA="${ZONA:-us-central1-a}"
REGION="${ZONA%-*}"
VM="${VM:-gamma-gemma}"
TIPO="${TIPO:-e2-standard-8}"
ORIGENES="${GAMMA_ORIGENES:-https://gamma.aioros.tech}"
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
G=(--project "$PROYECTO")

[ -n "$PROYECTO" ] || { echo "Elige el proyecto primero: gcloud config set project ID_DEL_PROYECTO"; exit 1; }

existe() { gcloud compute instances describe "$VM" --zone "$ZONA" "${G[@]}" >/dev/null 2>&1; }

echo "Proyecto: $PROYECTO"
echo "VM: $VM en $ZONA, $TIPO, sin GPU$(existe && echo ' (ya existe: se actualiza)')"
echo "Dashboard autorizado a usar a Gemma: $ORIGENES"
echo "La VM genera costo mientras esté encendida."
read -r -p "¿Continuar? (s/n) " respuesta
[ "$respuesta" = "s" ] || { echo "Cancelado."; exit 1; }

gcloud services enable compute.googleapis.com "${G[@]}"

if ! gcloud compute addresses describe "$VM-ip" --region "$REGION" "${G[@]}" >/dev/null 2>&1; then
  gcloud compute addresses create "$VM-ip" --region "$REGION" "${G[@]}"
fi
IP=$(gcloud compute addresses describe "$VM-ip" --region "$REGION" "${G[@]}" --format='value(address)')
DOMINIO="${GAMMA_DOMINIO:-${IP//./-}.sslip.io}"

if ! gcloud compute firewall-rules describe "$VM-https" "${G[@]}" >/dev/null 2>&1; then
  gcloud compute firewall-rules create "$VM-https" "${G[@]}" --allow tcp:80,tcp:443 \
    --target-tags "$VM" --description "Gamma: HTTPS del dashboard con Gemma (solo la VM $VM)"
fi

if ! existe; then
  cat > /tmp/gamma-arranque.sh <<'ARRANQUE'
#!/bin/bash
# Instala Docker desde el repositorio oficial la primera vez que arranca la VM
command -v docker >/dev/null && exit 0
apt-get update && apt-get install -y ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list
apt-get update && apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
ARRANQUE
  gcloud compute instances create "$VM" "${G[@]}" --zone "$ZONA" --machine-type "$TIPO" \
    --image-family debian-12 --image-project debian-cloud --boot-disk-size 50GB --boot-disk-type pd-balanced \
    --address "$IP" --tags "$VM" --metadata-from-file startup-script=/tmp/gamma-arranque.sh
fi

echo "Copiando el proyecto a la VM…"
tar czf /tmp/gamma.tgz -C "$RAIZ" --exclude=.git --exclude=.env --exclude=.local --exclude=.runtime \
  --exclude=pesos --exclude=artifacts --exclude='__pycache__' .
for intento in $(seq 1 30); do
  gcloud compute scp /tmp/gamma.tgz "$VM":/tmp/gamma.tgz --zone "$ZONA" "${G[@]}" --quiet 2>/dev/null && break
  echo "La VM todavía está arrancando… ($intento)"; sleep 10
done
gcloud compute ssh "$VM" --zone "$ZONA" "${G[@]}" --quiet -- \
  "sudo DOMINIO='$DOMINIO' ORIGENES='$ORIGENES' bash -s" < "$RAIZ/despliegue/en_la_vm.sh"

echo "Esperando a que Gemma quede listo (la primera vez descarga 3.4 GB; unos minutos)…"
for intento in $(seq 1 90); do
  estado=$(curl -s -m 10 "https://$DOMINIO/api/estado" || true)
  if echo "$estado" | grep -q '"disponible": true'; then
    cat <<LISTO

Listo. Gamma con Gemma: https://$DOMINIO

Para el dashboard de $ORIGENES: en configuracion.json poner
  "servidor_gemma": "https://$DOMINIO"
y volver a publicar el index.html (python3 construir_dashboard.py).

La clave para enviar registros de sensores quedó en /opt/gamma/.env dentro de la VM.
Apagar la VM:   gcloud compute instances stop $VM --zone $ZONA --project $PROYECTO
Encenderla:     gcloud compute instances start $VM --zone $ZONA --project $PROYECTO
LISTO
    exit 0
  fi
  sleep 10
done
echo "Gemma no respondió a tiempo. Revisa: gcloud compute ssh $VM --zone $ZONA -- 'cd /opt/gamma && sudo docker compose logs --tail 50'"
exit 1
