# MediRoute Backend — task runner
# Usage:  make validate        # run 40-case regression gate (REQUIRED before any merge)
#         make test            # run all pytest unit tests
#         make check           # validate + test (full pre-merge gate)
#         make drift           # run weekly scoring drift check against production DB
#         make diagnose        # run component dominance diagnostic against synthetic cases
#         make dev             # start the FastAPI dev server
#         make lint            # run ruff linter

PYTHON   := python
PYTEST   := pytest
RUFF     := ruff

# ── Env vars required for deterministic dispatch engine runs ──────────────────
DISPATCH_ENV := MODEL_SHA256=a46ae388b1fdc321edd355a3ae431d0eb5cd85f109227563d39c6edd8ee776b7 \
                DISABLE_DRIFT_CHECK=1 \
                DISABLE_LEARNING_UPDATE=1

.PHONY: validate test check dev lint help

## validate: Run the 40-case synthetic validation suite (regression gate).
##           Must pass 100% before merging dispatch engine changes.
validate:
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  MediRoute dispatch regression gate — 40 cases"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	$(DISPATCH_ENV) $(PYTHON) tests/test_validation.py

## test: Run pytest unit tests.
test:
	$(PYTEST) tests/ -v --tb=short -x

## check: Full pre-merge gate — validation suite then pytest.
check: validate test
	@echo "✓ All checks passed."

## dev: Start the FastAPI development server.
dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

## lint: Lint with ruff.
lint:
	$(RUFF) check app/ tests/

## diagnose: Run component score dominance diagnostic against the 40-case harness.
##            Use after scoring function changes to verify balance hasn't shifted.
diagnose:
	$(DISPATCH_ENV) $(PYTHON) scripts/diagnose_equipment_dominance.py

## drift: Run weekly scoring drift check against the production database.
##         Requires DATABASE_URL env var. Exits 1 if any alert threshold is breached.
##         Run via cron: 0 6 * * 1 cd /app && make drift >> logs/drift.log 2>&1
drift:
	$(PYTHON) scripts/weekly_drift_check.py --days 7

## help: Show this help.
help:
	@grep -E '^## ' Makefile | sed 's/## /  /'
