.PHONY: install dev-setup pull-models run run-fast build-frontend sanity test lint clean

install:
	pip install -r requirements.txt
	cd frontend && npm install 2>/dev/null || true

dev-setup:
	pip install -r requirements.txt
	make pull-models
	python scripts/init_db.py 2>/dev/null || true

pull-models:
	ollama pull llama3.1:8b
	ollama pull mistral:7b
	ollama pull nomic-embed-text

build-frontend:
	cd frontend && npm run build

run:
	uvicorn app.main:app --reload --reload-exclude "tests/*" --host 0.0.0.0 --port 8000

run-fast:
	uvicorn app.main:app --workers 4 --host 0.0.0.0 --port 8000

sanity:
	mkdir -p artifacts
	bash scripts/sanity_check.sh

lint:
	ruff check app/ scripts/
	mypy app/ --ignore-missing-imports

test:
	pytest tests/ -v --asyncio-mode=auto

clean:
	rm -rf vectorstore/ memory/ data/ artifacts/ __pycache__ .pytest_cache
