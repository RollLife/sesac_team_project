# Docker 배포 가이드

## 개요

모든 애플리케이션이 Docker 컨테이너로 실행됩니다. Redis 캐싱 + Aging 기법을 통해 대용량 데이터 환경에서도 효율적인 성능을 제공합니다.

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

## 서비스 구성 (20개 컨테이너)

### 인프라 (7개)
- `postgres`: PostgreSQL 데이터베이스
- `kafka1`, `kafka2`, `kafka3`: Kafka 클러스터 (3 브로커)
- `kafka-ui`: Kafka 모니터링 UI
- `redis`: Redis 캐시 서버
- `grafana`: 데이터 시각화 대시보드
- `adminer`: DB 관리 UI


### 캐시 서비스 (2개)
- `cache-worker`: Redis 캐시 갱신 (Aging 기법, 50초마다)
- `redis-monitor`: Redis 실시간 모니터링

### 데이터 생성 (3개)
- `initial-seeder`: 초기 데이터 생성 (one-time job)
- `producer`: 실시간 주문/상품 생성 (Redis에서 조회)
- `user-seeder`: 실시간 고객 생성

### Consumer (9개)
- `user-consumer-1/2/3`: 유저 토픽 컨슈머 (3개)
- `product-consumer-1/2/3`: 상품 토픽 컨슈머 (3개)
- `order-consumer-1/2/3`: 주문 토픽 컨슈머 (3개)


**총 20개 컨테이너**

### 개발 (1개, 선택적)
- `python-dev`: 개발 컨테이너 (dev 프로파일)

## 빠른 시작

### 1. 전체 서비스 실행

```bash
cd deploy

# 1. 도커 이미지 빌드
docker-compose build

# 2. 모든 서비스 시작
docker-compose up -d

# 3. 로그 확인
docker-compose logs -f
```

### 2. 서비스 확인

```bash
# 실행 중인 컨테이너 확인
docker-compose ps

```

**웹 UI 접속:**
| 서비스 | URL | 비고 |
|--------|-----|------|
| Kafka UI | http://localhost:8080 | 카프카 모니터링 |
| Grafana | http://localhost:3000 | admin / admin |
| Adminer | http://localhost:8081 | DB 관리 |

```

## Redis 캐싱 + Aging 기법

### 개념
- **50초마다** DB에서 1,000건의 유저/상품 데이터를 Redis로 캐싱
- **Aging 기법**: 50% 신규 데이터 + 50% 기존 데이터로 기아(Starvation) 방지
- **Producer**: Redis 캐시에서 랜덤 조회 → Kafka 발행

#### 1단계: 인프라만 시작
```bash
# PostgreSQL + Kafka 클러스터 + 모니터링 시작
docker-compose up -d postgres kafka1 kafka2 kafka3 kafka-ui grafana adminer

# 상태 확인
docker-compose ps
```

#### 2단계: 초기화 (자동 실행)
```bash
# db-init과 kafka-init은 depends_on으로 자동 실행됨
# 수동 실행 필요시:
docker-compose up db-init kafka-init
```

#### 3단계: 초기 데이터 생성
```bash
# 초기 데이터 생성 (10,000 유저 + 20,000 상품)
docker-compose up initial-seeder
```

#### 4단계: 컨슈머 시작
```bash
# 9개 컨슈머 모두 시작
docker-compose up -d \
  user-consumer-1 user-consumer-2 user-consumer-3 \
  product-consumer-1 product-consumer-2 product-consumer-3 \
  order-consumer-1 order-consumer-2 order-consumer-3
```

#### 5단계: Producer 시작
```bash
# 실시간 데이터 생성 시작
docker-compose up -d producer
```

### 선택적 실행

#### Producer만 실행
```bash
docker-compose up -d postgres kafka1 kafka2 kafka3 producer
```

#### Consumer만 실행 (특정 그룹)
```bash
# Users 그룹만
docker-compose up -d user-consumer-1 user-consumer-2 user-consumer-3

# Products 그룹만
docker-compose up -d product-consumer-1 product-consumer-2 product-consumer-3

# Orders 그룹만
docker-compose up -d order-consumer-1 order-consumer-2 order-consumer-3
```

#### 단일 Consumer 실행 (테스트용)
```bash
docker-compose up -d user-consumer-1
```

### 환경변수 설정
```yaml
# cache-worker 환경변수
CACHE_REFRESH_INTERVAL: 50     # 캐시 갱신 주기 (초)
CACHE_BATCH_SIZE: 1000         # 캐시 배치 크기
CACHE_NEW_DATA_RATIO: 0.5      # 신규 데이터 비율 (50%)
```

### 성능 향상
| 지표 | Before | After | 개선율 |
|------|--------|-------|--------|
| DB 쿼리/분 | ~60회 | ~1.2회 | 98% 감소 |
| 조회 속도 | 10-100ms | 0.1-1ms | 100배 향상 |


## 로그 및 모니터링

### Redis 캐시 모니터링

```bash
# Redis Monitor 로그 확인 (실시간 캐시 상태)
docker logs -f redis_monitor

# 출력 예시:
# [11:45:35] [15/50s ######--------------] | MEM: 2.25M | OPS/s: 1 | HIT: 100.0% | CACHE: users=1000, products=1000 | 교체: 1회

# Cache Worker 로그 확인
docker logs -f cache_worker
```

### 일반 로그 확인

```bash
# 전체 로그
docker-compose logs -f

# 특정 서비스 로그
docker-compose logs -f producer
docker-compose logs -f order-consumer-1
docker-compose logs -f kafka1

# 최근 100줄만
docker-compose logs --tail=100 producer
```

### 컨테이너 상태 확인

```bash
# 모든 컨테이너 상태
docker-compose ps

# 리소스 사용량
docker stats

# 특정 컨테이너 상세 정보
docker inspect redis_monitor
```

### Kafka 모니터링

```bash
# Kafka UI
http://localhost:8080

# CLI로 컨슈머 그룹 확인
docker exec kafka1 kafka-consumer-groups \
  --bootstrap-server kafka1:29092 \
  --describe --group orders_group
```

### Grafana 대시보드

```bash
# Grafana 접속
http://localhost:3000

# 로그인: admin / admin

# 데이터소스 추가
# - Type: PostgreSQL
# - Host: postgres:5432
# - Database: sesac_db
# - User: postgres
# - Password: password
```

## 환경변수 설정

### Redis 캐시 설정
```yaml
# docker-compose.yml의 cache-worker
environment:
  REDIS_HOST: redis
  REDIS_PORT: 6379
  CACHE_REFRESH_INTERVAL: 50
  CACHE_BATCH_SIZE: 1000
  CACHE_NEW_DATA_RATIO: 0.5
```

### Kafka 설정
```yaml
environment:
  KAFKA_BOOTSTRAP_SERVERS: kafka1:29092,kafka2:29093,kafka3:29094
  KAFKA_ENABLED: "true"
```

### DB 설정
```yaml
environment:
  DB_TYPE: local
  POSTGRES_HOST: postgres
  POSTGRES_USER: postgres
  POSTGRES_PASSWORD: password
  POSTGRES_DB: sesac_db
```

## 데이터베이스 작업

### DB 접속
```bash
# PostgreSQL 컨테이너 접속
docker-compose exec postgres psql -U postgres -d sesac_db

# SQL 실행
docker exec local_postgres psql -U postgres -d sesac_db -c "SELECT COUNT(*) FROM users;"
```

### Redis 접속
```bash
# Redis CLI 접속
docker exec -it local_redis redis-cli

# 캐시 데이터 확인
docker exec local_redis redis-cli hlen cache:users
docker exec local_redis redis-cli hlen cache:products
```

### DB 초기화
```bash
# 데이터베이스 재생성
docker-compose exec postgres psql -U postgres -c "DROP DATABASE sesac_db;"
docker-compose exec postgres psql -U postgres -c "CREATE DATABASE sesac_db;"

# 스키마 재생성 (db-init 서비스 사용)
docker-compose up db-init
```

## 서비스 관리

### 중지 및 재시작

```bash
# 전체 중지
docker-compose stop

# 특정 서비스 중지
docker-compose stop producer
docker-compose stop cache-worker

# 재시작
docker-compose restart producer
docker-compose restart redis cache-worker

# 중지 후 제거
docker-compose down
```

### 업데이트 및 재배포

```bash
# 1. 코드 수정 후 이미지 재빌드
docker-compose build producer cache-worker

# 2. 서비스 재시작
docker-compose up -d producer cache-worker

# 3. 로그 확인
docker-compose logs -f producer cache-worker
```

## 문제 해결

### Redis 캐시 문제

```bash
# Redis 상태 확인
docker exec local_redis redis-cli ping

# 캐시 데이터 확인
docker exec local_redis redis-cli hlen cache:users
docker exec local_redis redis-cli hlen cache:products

# Redis 재시작
docker-compose restart redis cache-worker redis-monitor
```

### 컨테이너가 시작되지 않을 때

```bash
# 로그 확인
docker-compose logs producer
docker-compose logs cache-worker

# 에러 메시지 확인
docker-compose ps

# 컨테이너 재생성
docker-compose up -d --force-recreate producer cache-worker
```

### Kafka 연결 실패

```bash
# Kafka 브로커 상태 확인
docker-compose ps kafka1 kafka2 kafka3

# Kafka 재시작
docker-compose restart kafka1 kafka2 kafka3

# 네트워크 확인
docker network ls
```

### DB 연결 실패

```bash
# PostgreSQL 상태 확인
docker-compose exec postgres pg_isready

# 연결 테스트
docker-compose exec postgres psql -U postgres -c "SELECT 1;"

# PostgreSQL 재시작
docker-compose restart postgres
```

### 디스크 공간 부족

```bash
# 사용하지 않는 이미지/컨테이너 정리
docker system prune -a

# 볼륨 정리 (주의: 데이터 삭제됨)
docker-compose down -v

# 빌드 캐시 정리
docker builder prune
```

## 전체 플로우

```bash
cd deploy

# 1. 이미지 빌드
docker-compose build

# 2. 모든 서비스 시작
docker-compose up -d

# 3. 서비스 상태 확인
docker-compose ps

# 4. Redis 캐시 모니터링
docker logs -f redis_monitor

# 5. Producer 로그 확인
docker logs -f realtime_producer

# 6. Consumer 상태 확인
docker exec kafka1 kafka-consumer-groups \
  --bootstrap-server kafka1:29092 \
  --describe --group orders_group
```

## 볼륨

### depends_on의 한계
`depends_on`은 컨테이너 시작 순서만 보장하며, 서비스가 준비되었는지는 보장하지 않습니다.

해결 방법:
1. 헬스체크 사용
2. 애플리케이션에서 재시도 로직 구현
3. 초기화 서비스 분리 (db-init, kafka-init)

### 네트워크
모든 컨테이너는 같은 Docker 네트워크에 있어 서비스 이름으로 통신 가능:
- `postgres`: PostgreSQL
- `kafka1`: 카프카 브로커 1
- 등등

### 볼륨
데이터 영구 저장을 위한 볼륨:
- `postgres_data`: PostgreSQL 데이터
- `kafka1_data`, `kafka2_data`, `kafka3_data`: 카프카 데이터
- `grafana_data`: Grafana 대시보드 설정
- `redis_data`: Redis 데이터 (AOF 영속성)

## 추가 명령어

```bash
# 전체 종료 및 정리 (볼륨 포함)
docker-compose down -v

# 이미지 재빌드 (캐시 무시)
docker-compose build --no-cache

# 특정 서비스만 재빌드
docker-compose build producer cache-worker

# 서비스 로그를 파일로 저장
docker-compose logs producer > producer.log

# 실행 중인 컨테이너에서 명령 실행
docker-compose exec producer python --version
docker exec local_redis redis-cli info
```
