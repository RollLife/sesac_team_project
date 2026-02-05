# Quick Start Guide

## 시스템 아키텍처

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ PostgreSQL  │────▶│Cache-Worker │────▶│    Redis    │
│  (원본 DB)  │     │(Aging 50초) │     │ (1000건)    │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
      ┌────────────────────────────────────────┘
      ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Producer   │────▶│   Kafka     │────▶│  Consumers  │
│(Redis조회)  │     │ (3 brokers) │     │(9 instances)│
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                                               ▼
                                        ┌─────────────┐
                                        │ PostgreSQL  │
                                        │   (저장)    │
                                        └─────────────┘
```

### 데이터 흐름
1. **Cache-Worker** → DB에서 Aging 기법으로 1,000건씩 Redis로 캐싱 (50초마다)
2. **Producer** → Redis 캐시에서 랜덤 조회 → Kafka 발행 (DB 저장 X)
3. **Consumers** → Kafka에서 소비 → PostgreSQL에 저장

### Redis 캐싱 + Aging 기법
- **Aging 기법**: 50% 신규 데이터 + 50% 기존 데이터 (기아 방지)
- **성능 향상**: DB 쿼리 98% 감소, 조회 속도 100배 향상
- **Consumer 그룹**: users_group(3), products_group(3), orders_group(3)

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
CACHE_NEW_DATA_RATIO: 0.5      # 신규 데이터 비율 (Aging)
```

### 운영 DB로 전환
```env
# deploy/.env
DB_TYPE=production
POSTGRES_HOST=prod-db.example.com
POSTGRES_PASSWORD=secure_password
```

## 문제 해결

### 컨테이너 재시작
```bash
# 특정 서비스만
docker-compose restart producer
docker-compose restart cache-worker

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
│   ├── docker-compose.yml  # 서비스 정의 (20개 컨테이너)
│   ├── Dockerfile          # Python 이미지
│   └── requirements.txt    # Python 의존성
├── apps/                   # 애플리케이션
│   ├── benchmarks/         # 벤치마크 스크립트
│   └── seeders/            # 데이터 생성
├── kafka/                  # Kafka 관련 코드
│   ├── producer.py         # Kafka Producer
│   ├── consumers/          # Consumers
│   └── admin/              # Admin 유틸리티
├── cache/                  # Redis 캐시 모듈
│   ├── client.py           # Redis 클라이언트
│   ├── config.py           # 캐시 설정
│   ├── cache_worker.py     # Aging 기법 캐시 워커
│   └── redis_monitor.py    # 실시간 모니터링
├── database/               # 데이터베이스
│   ├── models.py           # SQLAlchemy 모델
│   └── crud.py             # CRUD 함수
└── collect/                # 데이터 생성기
    ├── user_generator.py
    ├── product_generator.py
    └── order_generator.py
```

## 참고 문서

- [GUIDE/DOCKER_DEPLOYMENT_GUIDE.md](GUIDE/DOCKER_DEPLOYMENT_GUIDE.md) - Docker 배포 가이드 (상세)
- [GUIDE/KAFKA_SETUP_GUIDE.md](GUIDE/KAFKA_SETUP_GUIDE.md) - Kafka 설정 가이드
- [deploy/PYTHON_DEV_GUIDE.md](deploy/PYTHON_DEV_GUIDE.md) - 개발 컨테이너 사용법
