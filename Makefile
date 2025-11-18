.PHONY: help build up down logs restart status clean test

help:
	@echo ""
	@echo "Доступні команди:"
	@echo "  make build    - Збудувати Docker образ"
	@echo "  make up       - Запустити контейнер (daemon mode)"
	@echo "  make down     - Зупинити контейнер"
	@echo "  make logs     - Показати логи (в реальному часі)"
	@echo "  make restart  - Перезапустити контейнер"
	@echo "  make status   - Показати статус контейнера"
	@echo "  make clean    - Видалити контейнер та образи"
	@echo "  make test     - Запустити в тестовому режимі (foreground)"
	@echo ""

build:
	docker compose build

up:
	docker compose up -d
	@echo "✓ Контейнер запущено в фоновому режимі"
	@echo "Перегляд логів: make logs"

down:
	docker compose down

logs:
	docker compose logs -f

restart:
	docker compose restart
	@echo "✓ Контейнер перезапущено"

status:
	docker compose ps

clean:
	docker compose down -v
	docker rmi deye-fayree-control_deye-feyree-control 2>/dev/null || true
	@echo "✓ Контейнер та образи видалено"

test:
	docker compose up
