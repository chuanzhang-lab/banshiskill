.PHONY: help install test lint format skill skill-tree skill-xml snapshot clean

help:
	@echo "Skill Compressor Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  install      - Install dependencies"
	@echo "  test         - Run all tests"
	@echo "  lint         - Run linter"
	@echo "  format       - Format code"
	@echo "  skill        - Generate all skill artifacts"
	@echo "  skill-tree    - Generate skill_tree.json"
	@echo "  skill-xml     - Generate skill_compressed.xml"
	@echo "  snapshot      - Generate context snapshot"
	@echo "  clean         - Clean generated files"
	@echo "  ci           - Run CI checks (test + lint)"
	@echo "  publish       - Publish artifacts"

install:
	pip install --upgrade pip
	pip install ruff mypy types-python-dateutil pytest pytest-cov

test:
	python -m pytest test_compress.py -v --tb=short

lint:
	ruff check . --output-format=github

format:
	ruff format .

skill: skill-tree skill-xml

skill-tree:
	python3 parse_skill.py

skill-xml:
	python3 skill_compressor.py

snapshot:
	python3 compress.py --skill-md ~/Desktop/banshi2/SKILL.md

clean:
	rm -f skill_tree.json skill_compressed.xml CONTEXT_SNAPSHOT.md
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .ruff_cache

ci: test lint

publish: skill
	@echo "Artifacts generated:"
	@ls -la skill_tree.json skill_compressed.xml
