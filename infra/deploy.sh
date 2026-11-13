#!/bin/bash
# Constrói a imagem do código que está na pasta e sobe o painel. Roda na máquina da nuvem:
# na criação (instalar.sh.tftpl) e a cada deploy do pipeline (via AWS Systems Manager).
set -euo pipefail
cd "$(dirname "$0")/.."

echo "Deploy do commit $(git rev-parse --short HEAD)"
docker build --tag energia-painel:local .
docker compose up --detach --no-build --remove-orphans
docker image prune --force > /dev/null

# Só termina com sucesso quando o painel responde.
for tentativa in $(seq 1 30); do
  if curl --fail --silent --max-time 3 http://127.0.0.1/health > /dev/null; then
    echo "Painel no ar."
    exit 0
  fi
  sleep 4
done
echo "O painel não respondeu depois do deploy." >&2
docker compose ps
docker compose logs --tail 30 api
exit 1
