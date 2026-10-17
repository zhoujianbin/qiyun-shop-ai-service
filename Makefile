.PHONY: install db seed run test contract openapi web-install web-build eval eval-report clean

install:
	python -m pip install -r requirements.txt

db:
	python scripts/create_db.py --db qiyun_shop_dev --reset

seed:
	python scripts/seed.py --orders 60

run:
	python -m uvicorn app.main:app --reload --port 8000

test:
	python -m pytest -q

eval:
	python -m pytest -q -k eval

cleanup-assistant:
	.venv/bin/python scripts/cleanup_assistant.py --apply

eval-report:
	python scripts/eval_report.py

contract:
	python scripts/check_frontend_contract.py

openapi:
	python scripts/export_openapi.py

web-install:
	cd web && npm install

web-build:
	cd web && npm run typecheck && npm run build

clean:
	rm -rf var __pycache__ .pytest_cache openapi.json openapi.yaml
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
