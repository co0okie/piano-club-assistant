# ========= Config =========
PROJECT ?= piano-club-assistant
ENV ?= dev# dev 或 prod
COMPOSE_FILE ?= src/compose.$(ENV).yml
DC := sudo docker compose -p $(PROJECT) -f $(COMPOSE_FILE)

# ========= Helpers =========
.PHONY: help
help:
	@echo "Usage: make <target> [ENV=dev|prod]"
	@echo
	@echo "Core:"
	@echo "  up           - 啟動所有服務 (-d)"
	@echo "  stop         - 停止所有容器"
	@echo "  down         - 停止並刪除容器/網路"
	@echo "  downv        - 同上，且刪除 volumes (⚠️ 會清空 DB)"
	@echo "  restart      - 重新啟動 (down → up)"
	@echo "  logs         - 追蹤所有服務 log"
	@echo "  ps           - 顯示服務狀態"
	@echo "  pull         - 拉取最新 images"
	@echo "  rebuild      - 重新 build (no-cache) 並啟動"

# ========= Core =========
.PHONY: up upd stop down downv restart restartv logs ps pull rebuild
up:
	$(DC) up
upd:
	$(DC) up -d
stop:
	$(DC) stop
down:
	$(DC) down
downv:
	$(DC) down -v
restart: down up
restartv: downv up
logs:
	$(DC) logs -f --tail=200
ps:
	$(DC) ps
pull:
	$(DC) pull
rebuild:
	$(DC) build
	$(DC) down -v
	$(DC) up