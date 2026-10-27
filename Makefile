.PHONY: demo-seed pack init up down dev logs ps test lint migrate smoke admin new-client validate-client backup verify-backup restore upgrade doctor loadtest

COMPOSE = docker compose
COMPOSE_DEV = docker compose -f docker-compose.yml -f docker-compose.dev.yml

# .env yaratadi va tasodifiy sirlarni to'ldiradi (mavjud .env ni o'zgartirmaydi)
init:
	@test -f .env && echo ".env mavjud, tegilmadi" || ( \
	  cp .env.example .env && \
	  for k in SECRET_KEY POSTGRES_PASSWORD MINIO_ROOT_PASSWORD LIVEKIT_API_SECRET; do \
	    v=$$(openssl rand -hex 24); \
	    sed -i.bak "s|^$$k=__generate__|$$k=$$v|" .env; \
	  done && rm -f .env.bak && chmod 600 .env && echo ".env yaratildi" )

up: init
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

dev: init
	GATEWAY_BIND=0.0.0.0 $(COMPOSE_DEV) up --build

logs:
	$(COMPOSE) logs -f --tail=100

ps:
	$(COMPOSE) ps

# Backend testlari: docker ichida, haqiqiy Postgres (vaksina_test bazasi) bilan
test:
	$(COMPOSE) up -d db
	@until $(COMPOSE) exec -T db pg_isready -U $$(grep ^POSTGRES_USER .env | cut -d= -f2) >/dev/null 2>&1; do sleep 1; done
	@$(COMPOSE) exec -T db psql -U $$(grep ^POSTGRES_USER .env | cut -d= -f2) -d postgres -tc \
	  "SELECT 1 FROM pg_database WHERE datname='vaksina_test'" | grep -q 1 || \
	  $(COMPOSE) exec -T db psql -U $$(grep ^POSTGRES_USER .env | cut -d= -f2) -d postgres -c "CREATE DATABASE vaksina_test"
	docker build -q --target dev -t vaksinahr-backend-dev core/backend
	@set -a; . ./.env; set +a; docker run --rm --network vaksinahr_internal \
	  -v "$$PWD/core/backend:/srv" -e PYTHONDONTWRITEBYTECODE=1 \
	  -e DATABASE_URL="postgresql+asyncpg://$$POSTGRES_USER:$$POSTGRES_PASSWORD@db:5432/vaksina_test" \
	  vaksinahr-backend-dev sh -c "ruff check app tests && pytest -q"

# Frontend tekshiruvi
lint:
	cd core/frontend && npm run lint && npx tsc -b

migrate:
	$(COMPOSE) exec api python -m app.migrate

# Ishlayotgan stekni tekshiradi (gateway orqali)
smoke:
	@P=$$(grep -s '^GATEWAY_PORT=' .env | tail -1 | cut -d= -f2); P=$${P:-6788}; \
	curl -fsS http://localhost:$$P/healthz && \
	curl -fsS http://localhost:$$P/api/health/ready && echo && \
	curl -fsS http://localhost:$$P/api/v1/meta && echo && \
	curl -fsS -o /dev/null -w "frontend: %{http_code}\n" http://localhost:$$P/

# Birinchi Ta'sischi: make admin [LOGIN=admin] [NAME="To'liq ism"]
admin:
	$(COMPOSE) exec api python -m app.cli create-admin $(or $(LOGIN),admin) "$(or $(NAME),Administrator)"

# NAMOYISH: barcha ish ma'lumotini O'CHIRIB, namunaviy ma'lumot bilan to'ldiradi (Ta'sischi hisobi qoladi).
# make demo-seed CONFIRM=yes
demo-seed:
	@test "$(CONFIRM)" = "yes" || { echo "Bu buyruq BARCHA ish ma'lumotini o'chiradi. Tasdiqlash: make demo-seed CONFIRM=yes"; exit 1; }
	$(COMPOSE) exec -e ALLOW_DEMO_SEED=1 api python -m app.cli seed-demo-all

# Yangi mijoz: make new-client NAME=acme BRAND="Acme HR" [ARGS="--domain hr.acme.uz --env"]
new-client:
	deploy/scripts/new-client.sh $(NAME) "$(or $(BRAND),$(NAME) HR)" $(ARGS)

# client.yaml va extension tuzilmasini sxema bo'yicha tekshiradi: make validate-client [CLIENT=acme]
validate-client:
	@C=$(or $(CLIENT),$$(grep ^CLIENT_NAME .env | cut -d= -f2)); \
	docker build -q --target dev -t vaksinahr-backend-dev core/backend >/dev/null && \
	docker run --rm -v "$$PWD/core/backend:/srv" -v "$$PWD/clients/$$C:/clients/$$C:ro" vaksinahr-backend-dev python -m app.cli validate-client /clients/$$C

# Zaxira (baza + fayllar): make backup [ARGS="--keep 30 --with-env"]; tekshirish: make verify-backup FILE=backups/x.tar.gz
backup:
	deploy/scripts/backup.sh $(ARGS)

verify-backup:
	deploy/scripts/restore.sh $(FILE) --verify

restore:
	deploy/scripts/restore.sh $(FILE) $(ARGS)

upgrade:
	deploy/scripts/upgrade.sh $(TAG)

# Production tayyorlik tekshiruvi (sirlar, tarmoq, xizmatlar, zaxira, sertifikat)
# Chiqarish arxivi (git bo'lmasa): dist/vaksinahr-<versiya>.tar.gz
pack:
	deploy/scripts/pack.sh

doctor:
	deploy/scripts/preflight.sh

# Yuk testi (docs/LOADTEST.md): make loadtest [ARGS="--users 40 --duration 60"]
loadtest:
	deploy/loadtest/run.sh $(ARGS)
