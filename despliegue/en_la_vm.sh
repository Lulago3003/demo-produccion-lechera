#!/usr/bin/env bash
# Corre dentro de la VM (lo llama gcp.sh). Instala o actualiza Gamma en /opt/gamma y lo arranca con HTTPS.
# Recibe DOMINIO y ORIGENES por el entorno. La clave de sensores se crea una vez y se conserva.
set -euo pipefail
: "${DOMINIO:?falta DOMINIO}" "${ORIGENES:?falta ORIGENES}"

until command -v docker >/dev/null && docker compose version >/dev/null 2>&1; do
  echo "Esperando a que termine de instalarse Docker en la VM…"; sleep 10
done

mkdir -p /opt/gamma
tar xzf /tmp/gamma.tgz -C /opt/gamma
rm -f /tmp/gamma.tgz
cd /opt/gamma

clave=""
[ -f .env ] && clave=$(sed -n 's/^GAMMA_CLAVE=//p' .env)
[ -n "$clave" ] || clave=$(openssl rand -hex 32)
umask 077
printf 'GAMMA_DOMINIO=%s\nGAMMA_ORIGENES=%s\nGAMMA_CLAVE=%s\n' "$DOMINIO" "$ORIGENES" "$clave" > .env

docker compose --profile https up -d --build --remove-orphans
docker compose ps
