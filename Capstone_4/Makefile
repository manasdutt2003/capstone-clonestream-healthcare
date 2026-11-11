# One command rebuilds everything:  make all
PY ?= python
export PYTHONPATH := src

.PHONY: all ingest clean-data dq flash rootcause recon backfill validate alerts notify audit powerbi docs lint test test-fast cov clean

all: ingest clean-data dq flash rootcause recon backfill validate alerts notify audit powerbi docs

ingest:
	$(PY) -m hcls ingest

clean-data:
	$(PY) -m hcls clean

dq:
	$(PY) -m hcls dq

flash:
	$(PY) -m hcls flash

rootcause:
	$(PY) -m hcls rootcause

recon:
	$(PY) -m hcls recon

backfill:
	$(PY) -m hcls backfill

validate:
	$(PY) -m hcls validate

alerts:
	$(PY) -m hcls alerts

notify:
	$(PY) -m hcls notify

audit:
	$(PY) -m hcls audit

powerbi:
	$(PY) -m hcls powerbi

verify:
	$(PY) -m hcls.audit.verify

docs:
	$(PY) -m hcls docs

lint:
	ruff check src tests
	ruff format --check src tests
	sqlfluff lint sql --dialect duckdb

test:
	pytest

test-fast:
	pytest -m "not realdata"

cov:
	pytest --cov=src/hcls --cov-report=term-missing --cov-fail-under=80

clean:
	rm -rf outputs
