.PHONY: help docs-check doctor test eval-smoke perf-cpu contracts progress verify dev frontend
PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
help:
	@echo "Targets: dev test eval-smoke perf-cpu contracts progress docs-check doctor verify frontend"
docs-check:
	$(PYTHON) scripts/validate_docs.py
doctor:
	$(PYTHON) scripts/doctor.py --output artifacts/environment.json
test:
	$(PYTHON) -m pytest -q --cov=agentsentry --cov-report=json:artifacts/coverage.json
eval-smoke:
	$(PYTHON) scripts/eval_smoke.py
perf-cpu:
	$(PYTHON) scripts/perf_cpu.py
contracts:
	$(PYTHON) scripts/export_contracts.py
progress:
	$(PYTHON) scripts/update_progress.py
verify:
	$(MAKE) test
	$(MAKE) eval-smoke
	$(MAKE) contracts
	$(MAKE) progress
	$(MAKE) docs-check
dev:
	$(PYTHON) -m agentsentry.cli init-demo
	$(PYTHON) -m agentsentry.cli serve
frontend:
	npm ci --prefix dashboard
	npm run build --prefix dashboard
