.PHONY: dev down test eval fmt lint

API_DIR := src/UnifiedIQ-api
UI_DIR  := products/UnifiedIQ-ui

dev:
	docker compose up --build

down:
	docker compose down

# Run backend and frontend test suites in parallel.
test:
	$(MAKE) -j2 test-api test-ui

test-api:
	cd $(API_DIR) && pytest

test-ui:
	cd $(UI_DIR) && npm test

eval:
	cd $(API_DIR) && python eval/run_eval.py --golden eval/golden_test_set.json --write-report

fmt:
	cd $(API_DIR) && ruff format .
	cd $(UI_DIR) && npx prettier --write .

lint:
	cd $(API_DIR) && ruff check .
	cd $(UI_DIR) && npm run lint
