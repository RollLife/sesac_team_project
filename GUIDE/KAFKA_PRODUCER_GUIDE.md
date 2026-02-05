# Kafka Producer 가이드

## 개요

Kafka Producer는 **Redis 캐시에서 데이터를 조회**하여 주문 데이터를 생성하고, Kafka 토픽으로 이벤트를 발행합니다. (DB 저장은 Consumer가 담당)

### 아키텍처 (Redis 캐싱 + Aging)
```
[PostgreSQL] → [Cache-Worker] → [Redis] → [Producer] → [Kafka] → [Consumer] → [DB]
                 (50초마다)     (1000건)   (랜덤조회)
```

### 성능 향상
| 지표 | Before (DB 직접) | After (Redis 캐시) |
|------|------------------|-------------------|
| DB 쿼리/분 | ~60회 | ~1.2회 |
| 조회 속도 | 10-100ms | 0.1-1ms |

## Producer 구성

### 1. 초기 데이터 생성
**apps/seeders/initial_seeder.py**
- 고객 10,000명 생성
- 상품 20,000개 생성
- 일회성 실행

### 2. 실시간 데이터 생성 (Redis 캐시 모드)
**apps/seeders/realtime_generator.py**
- **Redis 캐시에서 유저/상품 랜덤 조회**
- 주문: 2~8초 간격으로 1~5건씩 생성
- 상품: 10~20초 간격으로 100건씩 생성
- Kafka에만 발행 (DB 저장 X)
- 무한 루프 (Ctrl+C로 중지)

### 3. Cache Worker (Aging 기법)
**cache/cache_worker.py**
- 50초마다 DB에서 1,000건씩 Redis로 캐싱
- Aging: 50% 신규 + 50% 기존 데이터 (기아 방지)
- `last_cached_at` 컬럼으로 조회 이력 관리

### 4. 데이터 생성기
- **collect/user_generator.py** - 유저 데이터 생성
- **collect/product_generator.py** - 상품 데이터 생성
- **collect/order_generator.py** - 주문 데이터 생성

## 실행 방법

### Docker 실행 (권장)

#### 1. 전체 시스템 시작
```bash
cd deploy
docker-compose build
docker-compose up -d
```

#### 2. Redis 캐시 모니터링
```bash
# 실시간 캐시 상태 확인
docker logs -f redis_monitor

# 출력 예시:
# [11:45:35] [15/50s ######--------------] | MEM: 2.25M | HIT: 100.0% | CACHE: users=1000, products=1000 | 교체: 1회
```

#### 3. Producer 로그 확인
```bash
docker logs -f realtime_producer

# 출력 예시:
# [14:30:05] 🛒 주문 발행: 3/3건 성공 | 누적: 42건 | TPS: 0.70
# [14:30:08] 📦 상품 발행: 100/100건 성공 | 누적: 500개 | TPS: 8.33
```

### 로컬 실행

#### 1. 초기 데이터 생성
```bash
python apps/seeders/initial_seeder.py
```

#### 2. Redis 캐시 워커 시작
```bash
python cache/cache_worker.py
```

#### 3. 실시간 데이터 생성
```bash
python apps/seeders/realtime_generator.py
```

## 데이터 생성 플로우

### 실시간 주문 생성 (Redis 캐시 모드)

```
1. Cache-Worker (50초마다)
   └─ DB에서 Aging 기법으로 조회
      ├─ 신규 500건 (last_cached_at IS NULL)
      └─ 기존 500건 (ORDER BY last_cached_at ASC)
   └─ Redis Hash에 저장 (cache:users, cache:products)

2. Producer (2~8초마다)
   └─ Redis에서 랜덤 조회 (HRANDFIELD)
   └─ 주문 데이터 생성
   └─ Kafka 'orders' 토픽에 발행 (DB 저장 X)

3. Consumer
   └─ Kafka에서 소비
   └─ PostgreSQL에 저장
```

### 상품 생성

```
ProductGenerator.generate_batch(100)
  ↓
  생성된 데이터 (dict)
  ↓
  Kafka 'products' 토픽에 발행
  ↓
  Consumer가 DB에 저장
```

## Producer 설정

### Redis 캐시 설정 (docker-compose.yml)

```yaml
# cache-worker 환경변수
environment:
  REDIS_HOST: redis
  REDIS_PORT: 6379
  CACHE_REFRESH_INTERVAL: 50     # 캐시 갱신 주기 (초)
  CACHE_BATCH_SIZE: 1000         # 캐시 배치 크기
  CACHE_NEW_DATA_RATIO: 0.5      # 신규 데이터 비율 (50%)
```

### Kafka 설정 (kafka/config.py)

```python
KAFKA_CONFIG = {
    'bootstrap.servers': 'localhost:9092,localhost:9093,localhost:9094',
    'client.id': 'sesac-producer',
    'acks': 'all',
    'enable.idempotence': True,
    'linger.ms': 10,
    'compression.type': 'gzip',
    'batch.size': 16384,
}
```

### 환경변수

```bash
# Kafka 설정
KAFKA_ENABLED=true
KAFKA_BOOTSTRAP_SERVERS=kafka1:29092,kafka2:29093,kafka3:29094

# Redis 설정
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_ENABLED=true

# DB 설정
DB_TYPE=local
POSTGRES_HOST=postgres
```

## Redis 캐시 클라이언트

### 사용법 (cache/client.py)

```python
from cache.client import get_redis_client

# 클라이언트 가져오기 (싱글톤)
redis_client = get_redis_client()

# 랜덤 유저 조회
user = redis_client.get_random_user()
print(user)  # {'user_id': 'u_123', 'name': '홍길동', ...}

# 랜덤 상품 조회
product = redis_client.get_random_product()
print(product)  # {'product_id': 'p_456', 'name': '무선 이어폰', ...}

# 연결 상태 확인
if redis_client.is_connected():
    print("Redis 연결됨")
```

### 캐시 데이터 구조

```bash
# Redis Hash 구조
cache:users     # {user_id: JSON 데이터}
cache:products  # {product_id: JSON 데이터}

# 데이터 확인
docker exec local_redis redis-cli hlen cache:users      # 1000
docker exec local_redis redis-cli hlen cache:products   # 1000

# 샘플 데이터 조회
docker exec local_redis redis-cli hrandfield cache:users 1 withvalues
```

## 메시지 포맷

### Orders 토픽 (Producer 발행)
```json
{
  "event_type": "order_created",
  "data": {
    "order_id": "550e8400-e29b-41d4-a716-446655440000",
    "created_at": "2026-02-03T14:30:00",
    "user_id": "u_12345",
    "product_id": "p_67890",
    "quantity": 2,
    "total_amount": 521500,
    "shipping_cost": 3000,
    "discount_amount": 500,
    "payment_method": "Card",
    "status": "Success",
    "category": "전자제품",
    "user_region": "서울시",
    "user_gender": "M",
    "user_age_group": "20대"
  }
}
```

### Products 토픽
```json
{
  "event_type": "product_created",
  "data": {
    "product_id": "p_67890",
    "name": "무선 이어폰",
    "category": "전자제품",
    "brand": "Apple",
    "price": 259000,
    "org_price": 299000,
    "discount_rate": 13.37,
    "stock": 150,
    "created_at": "2026-02-03T14:30:00"
  }
}
```

## 모니터링

### Redis 캐시 모니터링
```bash
# Redis Monitor 로그
docker logs -f redis_monitor

# 출력 형식:
# [시간] [진행/50s 프로그레스바] | MEM: 메모리 | HIT: 히트율 | CACHE: users=N, products=N | 교체: N회
```

### Producer 로그
```bash
docker logs -f realtime_producer

# 출력 예시:
# 🚀 주문 데이터 생성 스레드 시작 (Redis 캐시 + Kafka 발행 모드)...
# [14:30:05] 🛒 주문 발행: 3/3건 성공 | 누적: 42건 | TPS: 0.70
```

### Cache Worker 로그
```bash
docker logs -f cache_worker

# 출력 예시:
# 캐시 갱신 #7 완료 - 유저: 1000명, 상품: 1000개
```

### Kafka UI
```
http://localhost:8080
- Messages 탭: 발행된 메시지 확인
- Topics 탭: 토픽별 메시지 수 확인
```

## 트러블슈팅

### Redis 캐시에 데이터가 없을 때
```bash
# 1. Redis 연결 확인
docker exec local_redis redis-cli ping

# 2. 캐시 데이터 확인
docker exec local_redis redis-cli hlen cache:users
docker exec local_redis redis-cli hlen cache:products

# 3. Cache Worker 로그 확인
docker logs cache_worker

# 4. Cache Worker 재시작
docker-compose restart cache-worker
```

### Producer가 주문을 생성하지 않을 때

1. **Redis 연결 확인**
```bash
docker exec realtime_producer python -c "from cache.client import get_redis_client; print(get_redis_client().is_connected())"
```

2. **환경변수 확인**
```bash
docker exec realtime_producer env | grep REDIS
```

3. **Producer 재시작**
```bash
docker-compose restart producer
```

### Kafka 발행 실패 시
```bash
# Kafka 상태 확인
docker-compose ps kafka1 kafka2 kafka3

# Kafka 재시작
docker-compose restart kafka1 kafka2 kafka3

# Producer 재시작
docker-compose restart producer
```

## 성능 최적화

### Cache 설정 조정
```yaml
# docker-compose.yml
environment:
  CACHE_REFRESH_INTERVAL: 30   # 더 자주 갱신 (30초)
  CACHE_BATCH_SIZE: 2000       # 더 많이 캐싱 (2000건)
  CACHE_NEW_DATA_RATIO: 0.7    # 신규 데이터 비율 70%
```

### Kafka Producer 설정
```python
KAFKA_CONFIG = {
    'linger.ms': 5,           # 더 빠른 발행
    'batch.size': 32768,      # 더 큰 배치
    'compression.type': 'lz4', # 더 빠른 압축
}
```

## 참고 자료

- **[KAFKA_SETUP_GUIDE.md](KAFKA_SETUP_GUIDE.md)** - Kafka 클러스터 설정
- **[KAFKA_CONSUMER_GUIDE.md](KAFKA_CONSUMER_GUIDE.md)** - Consumer 가이드
- **[DOCKER_DEPLOYMENT_GUIDE.md](DOCKER_DEPLOYMENT_GUIDE.md)** - Docker 배포

## 요약

### Producer 역할 (Redis 캐시 모드)
- ✅ Redis 캐시에서 유저/상품 랜덤 조회
- ✅ 주문 데이터 생성
- ✅ Kafka 토픽에 이벤트 발행
- ❌ DB 직접 저장 (Consumer가 담당)

### 데이터 흐름
```
1. Cache-Worker (50초마다)
   → DB에서 Aging 기법으로 1,000건 조회
   → Redis에 캐싱

2. Producer (2~8초마다)
   → Redis에서 랜덤 조회
   → 주문 생성 → Kafka 발행

3. Consumer
   → Kafka에서 소비
   → PostgreSQL에 저장
```

**Redis 캐싱 + Aging 기법으로 대용량 환경에서도 효율적인 데이터 생성!**
