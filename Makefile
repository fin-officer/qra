.PHONY: help install install-dev test test-cov lint format clean build run

# Default target
help:
	@echo "Available commands:"
	@echo "  install     - Install production dependencies"
	@echo "  install-dev - Install development dependencies"
	@echo "  test        - Run tests"
	@echo "  test-cov    - Run tests with coverage"
	@echo "  lint        - Run linting checks"
	@echo "  format      - Format code"
	@echo "  clean       - Clean temporary files"
	@echo "  build       - Build the package"
	@echo "  run         - Run the application locally"

# Installation
install:
	poetry install --no-dev

install-dev:
	poetry install
	poetry run pre-commit install

# Testing
test:
	poetry run pytest tests/ -v

test-cov:
	poetry run pytest tests/ -v --cov=qra --cov-report=html --cov-report=term

# Code quality
lint:
	poetry run flake8 qra/ tests/
	poetry run mypy qra/
	poetry run black --check qra/ tests/
	poetry run isort --check-only qra/ tests/

format:
	poetry run black qra/ tests/
	poetry run isort qra/ tests/

# Cleanup
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/ dist/ htmlcov/ .coverage .pytest_cache/ .mypy_cache/

# Build and run
build:
	poetry version patch
	poetry build

run:
	poetry run python -m qra

# Publishing
publish: build
	poetry publish