# Kafka 데이터 파이프라인 Makefile
# Docker Compose 래퍼 - 기존 명령어 유지

COMPOSE_FILE := deploy/docker-compose.yml
DC := docker-compose -f $(COMPOSE_FILE)

.PHONY: help build up down restart logs ps

# 기본 타겟
help:
	@echo "Kafka 데이터 파이프라인 명령어:"
	@echo ""
	@echo "  make build          - 모든 이미지 빌드"
	@echo "  make up             - 모든 서비스 시작"
	@echo "  make down           - 모든 서비스 중지 및 제거"
	@echo "  make restart        - 모든 서비스 재시작"
	@echo "  make logs           - 모든 로그 실시간 확인"
	@echo "  make ps             - 실행 중인 서비스 목록"
	@echo ""
	@echo "  make topics         - Kafka 토픽 생성"
	@echo "  make seed           - 초기 데이터 생성"
	@echo "  make test           - 환경 테스트"
	@echo ""
	@echo "  make start-all      - 전체 시작 (빌드 + 실행 + 토픽 + 데이터)"
	@echo "  make clean          - 모든 컨테이너/볼륨 제거"

# Docker Compose 기본 명령어
build:
	$(DC) build

up:
	$(DC) up -d

down:
	$(DC) down

restart:
	$(DC) restart

logs:
	$(DC) logs -f

ps:
	$(DC) ps

# Kafka 관련
topics:
	$(DC) exec producer python kafka/admin/setup_topics.py

seed:
	$(DC) run --rm producer python apps/seeders/initial_seeder.py

# 테스트
test:
	$(DC) --profile dev up -d python-dev
	$(DC) exec python-dev python tests/test_environment.py

# 벤치마크
benchmark-kafka:
	python apps/benchmarks/kafka_comparison.py

benchmark-realtime:
	python apps/benchmarks/realtime_comparison.py

# 통합 명령어
start-all: build up topics seed
	@echo "✅ 모든 서비스가 시작되었습니다!"
	@echo "🌐 Kafka UI: http://localhost:8080"

clean:
	$(DC) down -v --remove-orphans

# 개별 서비스 관리
start-producer:
	$(DC) up -d producer

start-consumers:
	$(DC) up -d \
		user-consumer-1 user-consumer-2 user-consumer-3 \
		product-consumer-1 product-consumer-2 product-consumer-3 \
		order-consumer-1 order-consumer-2 order-consumer-3

stop-producer:
	$(DC) stop producer

stop-consumers:
	$(DC) stop \
		user-consumer-1 user-consumer-2 user-consumer-3 \
		product-consumer-1 product-consumer-2 product-consumer-3 \
		order-consumer-1 order-consumer-2 order-consumer-3

# 로그 확인
logs-producer:
	$(DC) logs -f producer

logs-consumers:
	$(DC) logs -f \
		user-consumer-1 user-consumer-2 user-consumer-3 \
		product-consumer-1 product-consumer-2 product-consumer-3 \
		order-consumer-1 order-consumer-2 order-consumer-3

logs-kafka:
	$(DC) logs -f kafka1 kafka2 kafka3
