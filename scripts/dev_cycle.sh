#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
npm run build --prefix dashboard
python3 scripts/sync_server.py
ssh -o BatchMode=yes 5090 'cd /root/autodl-tmp/AgentSentry && make verify'
python3 scripts/pull_evidence.py
python3 scripts/sync_server.py
