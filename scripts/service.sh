#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p artifacts
case "${1:-status}" in
 start)
   if [[ -f artifacts/service.pid ]] && kill -0 "$(cat artifacts/service.pid)" 2>/dev/null; then echo 'Service already running'; exit 0; fi
   .venv/bin/agentsentry init-demo
   nohup .venv/bin/agentsentry serve > artifacts/service.log 2>&1 &
   echo $! > artifacts/service.pid
   for attempt in {1..40}; do
     if ! kill -0 "$(cat artifacts/service.pid)" 2>/dev/null; then echo 'Service exited during startup; inspect artifacts/service.log'; exit 1; fi
     if curl --fail --silent http://127.0.0.1:8080/healthz >/dev/null; then echo 'Service ready on http://127.0.0.1:8080'; exit 0; fi
     sleep 0.25
   done
   echo 'Service readiness timed out; inspect artifacts/service.log'
   exit 1
   ;;
 stop)
   if [[ -f artifacts/service.pid ]]; then
     pid=$(cat artifacts/service.pid)
     if [[ "$pid" =~ ^[0-9]+$ ]] && [[ -r /proc/$pid/cmdline ]] && [[ "$(tr '\0' ' ' < "/proc/$pid/cmdline")" == *"agentsentry serve"* ]]; then kill -TERM "$pid"; fi
   fi
   ;;
 status) curl --fail --silent http://127.0.0.1:8080/healthz ;;
 *) echo 'Usage: service.sh start|stop|status'; exit 2 ;;
esac
