#!/usr/bin/env bash
# Coleta, registra e publica a medição. O token vem só do ambiente (GITHUB_TOKEN).
set -euo pipefail
cd "$(dirname "$0")"
python3 coletar.py
git add data/historico.json
git -c user.name=Jered -c user.email=bemvindo@bnbee.com.br commit -m "medicao $(TZ=America/Sao_Paulo date '+%Y-%m-%d %H:%M')"
: "${GITHUB_TOKEN:?GITHUB_TOKEN ausente}"
git push "https://x-access-token:${GITHUB_TOKEN}@github.com/lopescdiogo/velocidade-c10.git" HEAD:main 2>&1 | sed "s/${GITHUB_TOKEN}/***/g"
exit "${PIPESTATUS[0]}"
