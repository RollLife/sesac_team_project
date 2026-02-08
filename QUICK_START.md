# Quick Start Guide

## 시스템 아키텍처

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ PostgreSQL  │────▶│Cache-Worker │────▶│    Redis    │
│  (원본 DB)  │     │(분리적재50초)│     │ (1000건)    │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
      ┌────────────────────────────────────────┘
      ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Producer   │────▶│   Kafka     │────▶│  Consumers  │
│(성향기반선택)│     │ (3 brokers) │     │(9 instances)│
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
┌─────────────┐                                ▼
│Grade Updater│                         ┌─────────────┐
│ (10분 배치) │                         │ PostgreSQL  │
└─────────────┘                         │   (저장)    │
                                        └─────────────┘
```

### 데이터 흐름
1. **Cache-Worker** → DB에서 구매이력/미구매 분리 적재로 1,000건씩 Redis로 캐싱 (50초마다)
2. **Producer** → Redis 캐시에서 구매 성향 상위 200명 선택 → Kafka 발행 (DB 저장 X)
3. **Consumers** → Kafka에서 소비 → PostgreSQL에 저장
4. **Grade Updater** → 10분마다 6개월 누적 기준 등급 갱신

### Redis 캐싱 - 구매이력/미구매 분리 적재
- **고객**: 구매이력 600명 (last_ordered_at ASC) + 미구매 400명 (created_at DESC)
- **상품**: 인기상품 700개 (order_count DESC) + 신상품 300개 (created_at DESC)
- **성능 향상**: DB 쿼리 98% 감소, 조회 속도 100배 향상
- **Consumer 그룹**: users_group(3), products_group(3), orders_group(3)

### 데이터 생성 주기
| 데이터 | 간격 | 수량 |
|--------|------|------|
| 주문 | 3~5초 | 1건 (성향 기반 선택) |
| 상품 | 6~8초 | 1개 |
| 고객 | S커브 감쇄 (초기 10명/10초 → 점진적 감소) | 가변 |

## 전체 시스템 시작

```bash
# 1. deploy 디렉토리로 이동
cd deploy

# 2. 모든 서비스 시작
docker-compose build
docker-compose up -d

# 3. 로그 확인
docker-compose logs -f
```

## 개발 환경 (python-dev 포함)

```bash
# 개발 컨테이너 포함하여 시작
docker-compose --profile dev up -d

# 개발 컨테이너 접속
docker exec -it python_dev bash

# 컨테이너 내부에서 작업
python apps/seeders/initial_seeder.py
python apps/benchmarks/kafka_comparison.py
```

## 주요 명령어

### 서비스 관리
```bash
# 전체 시작
docker-compose up -d

# 전체 중지
docker-compose down

# 로그 확인
docker-compose logs -f

# 서비스 상태 확인
docker-compose ps
```

### Redis 캐시 모니터링
```bash
# Redis Monitor 로그 확인 (실시간 캐시 상태)
docker logs -f redis_monitor

# 출력 예시:
# [11:45:35] [15/50s ######--------------] | MEM: 2.25M | OPS/s: 1 | HIT: 100.0% | CACHE: users=1000, products=1000 | 교체: 1회

# Cache Worker 로그 확인
docker logs -f cache_worker
```

### 등급 갱신 확인
```bash
# Grade Updater 로그 확인
docker logs -f grade_updater

# DB에서 등급 분포 확인
docker exec local_postgres psql -U postgres -d sesac_db -c "
  SELECT grade, COUNT(*) FROM users GROUP BY grade ORDER BY COUNT(*) DESC;"
```

### Kafka
```bash
# 토픽 목록 확인
docker-compose exec kafka1 kafka-topics --list --bootstrap-server localhost:9092

# 메시지 확인
docker-compose exec kafka1 kafka-console-consumer --bootstrap-server localhost:9092 --topic orders --from-beginning --max-messages 5

# Consumer Lag 확인
docker exec kafka1 kafka-consumer-groups \
  --bootstrap-server kafka1:29092 \
  --describe --group orders_group
```

### 데이터베이스
```bash
# Adminer 접속
http://localhost:8081
# 로그인: postgres / password / sesac_db

# PostgreSQL 직접 접속
docker-compose exec postgres psql -U postgres -d sesac_db

# 데이터 확인
SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM products;
SELECT COUNT(*) FROM orders;

# 등급별 분포
SELECT grade, COUNT(*) FROM users GROUP BY grade ORDER BY COUNT(*) DESC;

# 구매이력/미구매 고객 수
SELECT
  COUNT(*) FILTER (WHERE last_ordered_at IS NOT NULL) as purchased,
  COUNT(*) FILTER (WHERE last_ordered_at IS NULL) as new_users
FROM users;
```

## 모니터링

### 웹 UI
| 서비스 | URL | 설명 |
|--------|-----|------|
| Kafka UI | http://localhost:8080 | Kafka 토픽/메시지 |
| Adminer | http://localhost:8081 | PostgreSQL 관리 |

### CLI 모니터링

**1. Redis 캐시 상태**
```bash
docker logs -f redis_monitor
```

**2. Consumer Lag 확인 (LAG=0이면 실시간 처리 중)**
```bash
# orders_group
docker exec kafka1 kafka-consumer-groups \
  --bootstrap-server kafka1:29092 \
  --describe --group orders_group
```

**3. DB 데이터 증가 확인**
```bash
docker exec local_postgres psql -U postgres -d sesac_db -c "
  SELECT 'users' as table_name, COUNT(*) FROM users
  UNION ALL SELECT 'products', COUNT(*) FROM products
  UNION ALL SELECT 'orders', COUNT(*) FROM orders;"
```

**4. Consumer 로그 확인**
```bash
docker logs --tail 50 order_consumer_1
docker logs --tail 50 product_consumer_1
docker logs --tail 50 user_consumer_1
```

## 환경 설정

### Redis 캐시 설정
```env
# docker-compose.yml의 cache-worker 환경변수
CACHE_REFRESH_INTERVAL: 50     # 캐시 갱신 주기 (초)
CACHE_BATCH_SIZE: 1000         # 캐시 배치 크기
```

### 운영 DB로 전환
```env
# deploy/.env
DB_TYPE=production
POSTGRES_HOST=prod-db.example.com
POSTGRES_PASSWORD=secure_password
```

## 과거 데이터 생성

```bash
# 1년치 과거 주문 데이터 생성 (Grafana 분석용)
python scripts/generate_historical_data.py
```

- 첫 7일: random_seed 기반 랜덤 풀
- 이후: 구매이력 600 + 미구매 400 분리 풀
- 7일마다 등급 갱신 (6개월 누적 기준)
- 구매 성향 기반 고객 선택

## 문제 해결

### 컨테이너 재시작
```bash
# 특정 서비스만
docker-compose restart producer
docker-compose restart cache-worker
docker-compose restart grade-updater

# 전체 재시작
docker-compose restart
```

### Redis 캐시 문제
```bash
# Redis 상태 확인
docker exec local_redis redis-cli ping

# 캐시 데이터 확인
docker exec local_redis redis-cli hlen cache:users
docker exec local_redis redis-cli hlen cache:products

# Redis 재시작
docker-compose restart redis cache-worker
```

### 깨끗하게 재시작
```bash
# 모든 컨테이너 중지 및 삭제
docker-compose down

# 볼륨까지 삭제 (데이터 초기화)
docker-compose down -v

# 다시 시작
docker-compose build
docker-compose up -d
```

## 디렉토리 구조

```
.
├── deploy/                 # Docker 관련 파일
│   ├── docker-compose.yml  # 서비스 정의 (21개 컨테이너)
│   ├── Dockerfile          # Python 이미지
│   └── requirements.txt    # Python 의존성
├── apps/                   # 애플리케이션
│   ├── batch/              # 배치 작업
│   │   └── grade_updater.py  # 등급 갱신 (10분 배치)
│   ├── benchmarks/         # 벤치마크 스크립트
│   └── seeders/            # 데이터 생성
│       ├── realtime_generator.py      # 주문/상품 생성 (성향 기반)
│       └── realtime_generator_user.py # 고객 생성 (S커브 감쇄)
├── kafka/                  # Kafka 관련 코드
│   ├── producer.py         # Kafka Producer
│   ├── consumers/          # Consumers
│   └── admin/              # Admin 유틸리티
├── cache/                  # Redis 캐시 모듈
│   ├── client.py           # Redis 클라이언트
│   ├── config.py           # 캐시 설정
│   ├── cache_worker.py     # 분리 적재 캐시 워커
│   └── redis_monitor.py    # 실시간 모니터링
├── database/               # 데이터베이스
│   ├── models.py           # SQLAlchemy 모델
│   └── crud.py             # CRUD 함수
├── collect/                # 데이터 생성기
│   ├── user_generator.py        # 고객 생성 (전원 BRONZE)
│   ├── product_generator.py     # 상품 생성
│   ├── order_generator.py       # 주문 생성
│   ├── purchase_propensity.py   # 구매 성향 점수 시스템
│   └── scenario_engine.py       # 20가지 시나리오 정의
└── scripts/                # 유틸리티 스크립트
    └── generate_historical_data.py  # 과거 1년치 데이터 생성
```

## 참고 문서

- [GUIDE/DB_README.md](GUIDE/DB_README.md) - DB 구조 및 캐시 적재 가이드
- [GUIDE/DOCKER_DEPLOYMENT_GUIDE.md](GUIDE/DOCKER_DEPLOYMENT_GUIDE.md) - Docker 배포 가이드 (상세)
- [GUIDE/KAFKA_SETUP_GUIDE.md](GUIDE/KAFKA_SETUP_GUIDE.md) - Kafka 설정 가이드
- [GUIDE/HISTORICAL_DATA_GUIDE.md](GUIDE/HISTORICAL_DATA_GUIDE.md) - 과거 데이터 생성 가이드
- [GUIDE/PYTHON_DEV_GUIDE.md](GUIDE/PYTHON_DEV_GUIDE.md) - 개발 컨테이너 사용법
