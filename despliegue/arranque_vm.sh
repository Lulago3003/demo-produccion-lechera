#!/bin/bash
# Script de arranque de la VM de Gamma en Google Cloud (corre como root en cada encendido).
# La primera vez instala Docker; siempre trae la última versión del código y levanta Gamma con Gemma y HTTPS.
# Registro: /var/log/gamma-arranque.log. Opcional, en los metadatos de la VM:
#   gamma-dominio   dominio propio que ya apunta a la IP (si no, IP-con-guiones.sslip.io)
#   gamma-origenes  dashboards autorizados, separados por comas (por defecto https://gamma.aioros.tech)
set -euo pipefail
exec >>/var/log/gamma-arranque.log 2>&1
echo "== $(date -Is) =="

metadato() { curl -sf -H 'Metadata-Flavor: Google' "http://metadata.google.internal/computeMetadata/v1/instance/$1"; }

if ! command -v docker >/dev/null; then
  apt-get update
  apt-get install -y ca-certificates curl git openssl
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
command -v git >/dev/null || { apt-get update; apt-get install -y git; }

if [ -d /opt/gamma/.git ]; then
  git -C /opt/gamma pull --ff-only
else
  git clone https://github.com/Lulago3003/demo-produccion-lechera /opt/gamma
fi
cd /opt/gamma

ip=$(metadato network-interfaces/0/access-configs/0/external-ip)
dominio=$(metadato attributes/gamma-dominio || echo "${ip//./-}.sslip.io")
origenes=$(metadato attributes/gamma-origenes || echo "https://gamma.aioros.tech")
clave=$(sed -n 's/^GAMMA_CLAVE=//p' .env 2>/dev/null || true)
[ -n "$clave" ] || clave=$(openssl rand -hex 32)
umask 077
printf 'GAMMA_DOMINIO=%s\nGAMMA_ORIGENES=%s\nGAMMA_CLAVE=%s\n' "$dominio" "$origenes" "$clave" > .env

docker compose --profile https up -d --build --remove-orphans
echo "Gamma: https://$dominio"
