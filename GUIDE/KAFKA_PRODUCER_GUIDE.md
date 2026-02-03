# Kafka Producer 가이드

## 개요

Kafka Producer는 데이터를 생성하여 PostgreSQL에 저장하고, 동시에 Kafka 토픽으로 이벤트를 발행합니다.

## Producer 구성

### 1. 초기 데이터 생성
**[apps/seeders/initial_seeder.py](apps/seeders/initial_seeder.py)**
- 고객 10,000명 생성
- 상품 20,000개 생성
- 일회성 실행

### 2. 실시간 데이터 생성
**[apps/seeders/realtime_generator.py](apps/seeders/realtime_generator.py)**
- 주문: 2~8초 간격으로 1~5건씩 생성
- 상품: 10~20초 간격으로 100건씩 생성
- 무한 루프 (Ctrl+C로 중지)

### 3. 데이터 생성기
- **[collect/user_generator.py](collect/user_generator.py)** - 유저 데이터 생성
- **[collect/product_generator.py](collect/product_generator.py)** - 상품 데이터 생성
- **[collect/order_generator.py](collect/order_generator.py)** - 주문 데이터 생성

## 실행 방법

### 로컬 실행

#### 1. 초기 데이터 생성
```bash
# 10,000명 유저 + 20,000개 상품
python apps/seeders/initial_seeder.py
```

**출력 예시:**
```
============================================================
👥 고객 데이터 생성 시작 (목표: 10,000명)
============================================================

  📊 배치 1: 1000/1000건 성공 | 누적: 1,000명 | 경과: 5.2초 | TPS: 192.3
  📊 배치 2: 1000/1000건 성공 | 누적: 2,000명 | 경과: 10.1초 | TPS: 198.0
  ...

✅ 고객 데이터 생성 완료!
   성공: 10,000명 | 실패: 0명
   소요시간: 52.34초 | 평균 TPS: 191.06

============================================================
📦 상품 데이터 생성 시작 (목표: 20,000개)
============================================================

✅ 상품 데이터 생성 완료!
   성공: 20,000개 | 실패: 0개
   소요시간: 105.67초 | 평균 TPS: 189.25
```

#### 2. 실시간 데이터 생성
```bash
# Ctrl+C로 중지할 때까지 계속 실행
python apps/seeders/realtime_generator.py
```

**출력 예시:**
```
🚀 주문 데이터 생성 스레드 시작...
🚀 상품 데이터 생성 스레드 시작...

[14:30:05] 🛒 주문 생성: 3/3건 성공 | 누적: 3건 | TPS: 0.60
[14:30:08] 📦 상품 생성: 100/100건 성공 | 누적: 100개 | TPS: 10.25
[14:30:12] 🛒 주문 생성: 2/2건 성공 | 누적: 5건 | TPS: 0.71

============================================================
📊 통계 (경과시간: 60.0초 / 1.0분)
============================================================
  🛒 주문:  성공 42건 | 실패 0건 | TPS: 0.70
  📦 상품:  성공 500개 | 실패 0개 | TPS: 8.33
============================================================
```

### Docker 실행

#### 1. 초기 데이터 생성
```bash
# 방법 1: run 명령
docker-compose run --rm producer python apps/seeders/initial_seeder.py

# 방법 2: 전용 서비스 (프로파일)
docker-compose --profile seeder up initial-seeder
```

#### 2. 실시간 데이터 생성
```bash
# Producer 서비스 시작
docker-compose up -d producer

# 로그 확인
docker-compose logs -f producer

# 중지
docker-compose stop producer
```

## Producer 설정

### Kafka 설정 ([kafka/config.py](kafka/config.py))

```python
# Kafka Producer 설정
KAFKA_CONFIG = {
    'bootstrap.servers': 'localhost:9092,localhost:9093,localhost:9094',
    'client.id': 'sesac-producer',

    # 신뢰성 설정
    'acks': 'all',  # 모든 복제본 확인
    'enable.idempotence': True,  # 멱등성 보장 (중복 방지)

    # 성능 최적화
    'linger.ms': 10,  # 10ms 배치 대기
    'compression.type': 'gzip',  # 압축
    'batch.size': 16384,  # 배치 크기 16KB
    'max.in.flight.requests.per.connection': 5,

    # 재시도 설정
    'retries': 2147483647,  # 무한 재시도
    'retry.backoff.ms': 100,
    'request.timeout.ms': 30000,
}
```

### 환경변수

```bash
# Kafka 활성화/비활성화
KAFKA_ENABLED=true   # 카프카 발행
KAFKA_ENABLED=false  # DB만 저장

# Kafka 브로커 주소
KAFKA_BOOTSTRAP_SERVERS=localhost:9092,localhost:9093,localhost:9094

# 토픽 이름
KAFKA_TOPIC_USERS=users
KAFKA_TOPIC_PRODUCTS=products
KAFKA_TOPIC_ORDERS=orders

# DB 설정
DB_TYPE=local
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
POSTGRES_DB=sesac_db
```

## 데이터 생성 플로우

### 1. 유저 생성
```
UserGenerator.generate_batch(count)
  ↓
  생성된 데이터 (dict)
  ↓
crud.create_user(db, data)
  ↓
  ├─ PostgreSQL에 저장
  └─ Kafka 'users' 토픽에 발행 (KAFKA_ENABLED=true 시)
```

### 2. 상품 생성
```
ProductGenerator.generate_batch(count)
  ↓
  생성된 데이터 (dict)
  ↓
crud.create_product(db, data)
  ↓
  ├─ PostgreSQL에 저장
  └─ Kafka 'products' 토픽에 발행
```

### 3. 주문 생성
```
OrderGenerator.generate_order(user, product)
  ↓
  생성된 주문 데이터 (dict)
  ↓
crud.create_order(db, data)
  ↓
  ├─ PostgreSQL에 저장
  │  └─ 역정규화 (user, product 정보 포함)
  └─ Kafka 'orders' 토픽에 발행
```

## Kafka 발행 상세

### Producer 클래스 ([kafka/producer.py](kafka/producer.py))

```python
from kafka.producer import KafkaProducer

# Producer 생성 (싱글톤)
producer = KafkaProducer()

# 메시지 발행
producer.send_event(
    topic='users',           # 토픽
    key='user_123',          # 파티션 키
    data=user_dict,          # 데이터 (dict)
    event_type='user_created' # 이벤트 타입
)

# 버퍼 플러시 (즉시 전송)
producer.flush()

# 종료
producer.close()
```

### 메시지 포맷

#### Users 토픽
```json
{
  "event_type": "user_created",
  "data": {
    "user_id": "u_12345",
    "name": "홍길동",
    "gender": "M",
    "age": 25,
    "birth_year": 1999,
    "address": "서울시 강남구",
    "address_district": "강남구",
    "email": "hong@example.com",
    "grade": "VIP",
    "created_at": "2026-02-03T14:30:00"
  }
}
```

#### Products 토픽
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
    "description": "최신 무선 이어폰...",
    "stock": 150,
    "created_at": "2026-02-03T14:30:00"
  }
}
```

#### Orders 토픽
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

## 데이터 생성기 커스터마이징

### UserGenerator 예제

```python
from collect.user_generator import UserGenerator

# 생성기 생성
gen = UserGenerator()

# 단일 유저 생성
user = gen.generate_user()
print(user)

# 배치 생성
users = gen.generate_batch(100)
print(f'{len(users)}명 생성')

# 특정 지역만
# (코드 수정 필요)
```

### ProductGenerator 예제

```python
from collect.product_generator import ProductGenerator

gen = ProductGenerator()

# 100개 상품 생성
products = gen.generate_batch(100)

# 카테고리별 개수 확인
from collections import Counter
categories = [p['category'] for p in products]
print(Counter(categories))
```

### OrderGenerator 예제

```python
from collect.order_generator import OrderGenerator
from database.database import SessionLocal
from database import crud

db = SessionLocal()
gen = OrderGenerator()

# DB에서 유저/상품 가져오기
users = crud.get_users(db, limit=100)
products = crud.get_products(db, limit=100)

# 주문 생성
orders = gen.generate_batch(users, products, count=50)

print(f'{len(orders)}건 생성')
db.close()
```

## Kafka ON/OFF 제어

### 카프카 비활성화 (DB만 저장)
```bash
# 환경변수 설정
export KAFKA_ENABLED=false

# 실행
python apps/seeders/initial_seeder.py

# 결과: DB에만 저장, 카프카 발행 안 함
```

### 카프카 활성화 (DB + Kafka)
```bash
# 환경변수 설정
export KAFKA_ENABLED=true

# 실행
python apps/seeders/realtime_generator.py

# 결과: DB 저장 + 카프카 발행
```

### Docker에서 제어
```yaml
# docker-compose.yml
environment:
  KAFKA_ENABLED: "false"  # 비활성화
  # KAFKA_ENABLED: "true"   # 활성화
```

## 성능 최적화

### 1. 배치 크기 조정
```python
# apps/seeders/initial_seeder.py
seeder.seed_users(count=10000, batch_size=1000)  # 배치 크기 조정
```

### 2. Kafka Producer 설정
```python
# kafka/config.py
KAFKA_CONFIG = {
    'linger.ms': 10,      # 배치 대기 시간 (ms)
    'batch.size': 16384,  # 배치 크기 (bytes)
    'compression.type': 'lz4',  # 압축 (gzip, lz4, snappy)
}
```

### 3. DB 연결 풀 설정
```python
# database/database.py
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=10,        # 연결 풀 크기
    max_overflow=20,     # 추가 연결 수
    pool_pre_ping=True
)
```

## 모니터링

### Producer 로그
```bash
# 로컬
python apps/seeders/realtime_generator.py

# Docker
docker-compose logs -f producer
```

### Kafka UI
```
http://localhost:8080

- Messages 탭: 발행된 메시지 확인
- Topics 탭: 토픽별 메시지 수 확인
```

### DB 데이터 확인
```bash
# 유저 수
docker-compose exec postgres psql -U postgres -d sesac_db -c "SELECT COUNT(*) FROM users;"

# 상품 수
docker-compose exec postgres psql -U postgres -d sesac_db -c "SELECT COUNT(*) FROM products;"

# 주문 수
docker-compose exec postgres psql -U postgres -d sesac_db -c "SELECT COUNT(*) FROM orders;"
```

## 트러블슈팅

### Producer가 데이터를 생성하지 않을 때

1. **DB 연결 확인**
```bash
docker-compose exec postgres pg_isready
```

2. **Kafka 연결 확인** (KAFKA_ENABLED=true 시)
```bash
python kafka/test_connection.py
```

3. **환경변수 확인**
```bash
docker-compose exec producer env | grep KAFKA
docker-compose exec producer env | grep POSTGRES
```

### 중복 데이터 발생 시

**원인**: Producer와 Consumer가 동시에 DB에 저장

**해결**:
- Producer: DB 저장 + Kafka 발행
- Consumer: Kafka 메시지만 소비 (중복 체크 로직 있음)

```python
# Consumer에서 중복 체크
existing = crud.get_user(db, data['user_id'])
if existing:
    return  # 이미 존재하면 스킵
```

### Kafka 발행 실패 시

```bash
# Circuit Breaker 확인
# 연속 5번 실패 시 자동으로 차단됨

# 재시작
docker-compose restart producer
```

## 벤치마크

### 처리량 측정
```bash
# Kafka OFF
KAFKA_ENABLED=false python apps/seeders/initial_seeder.py

# Kafka ON
KAFKA_ENABLED=true python apps/seeders/initial_seeder.py

# 비교
python apps/benchmarks/kafka_comparison.py
```

### 실시간 시나리오 벤치마크
```bash
# 60초 동안 실시간 생성 후 비교
python apps/benchmarks/realtime_comparison.py
```

## 참고 자료

- **[KAFKA_SETUP_GUIDE.md](KAFKA_SETUP_GUIDE.md)** - Kafka 클러스터 설정
- **[KAFKA_CONSUMER_GUIDE.md](KAFKA_CONSUMER_GUIDE.md)** - Consumer 가이드
- **[DOCKER_DEPLOYMENT_GUIDE.md](DOCKER_DEPLOYMENT_GUIDE.md)** - Docker 배포
- **[PYTHON_DEV_GUIDE.md](PYTHON_DEV_GUIDE.md)** - 개발 환경

## 요약

### Producer 역할
- ✅ 데이터 생성 (Faker 사용)
- ✅ PostgreSQL에 저장
- ✅ Kafka 토픽에 이벤트 발행
- ✅ 실시간 데이터 스트림 시뮬레이션

### 실행 흐름
```
1. apps/seeders/initial_seeder.py (초기 데이터)
   → 10,000 유저 + 20,000 상품

2. apps/seeders/realtime_generator.py (실시간)
   → 주문: 2~8초마다 1~5건
   → 상품: 10~20초마다 100건

3. Kafka Producer
   → 메시지 직렬화 (JSON)
   → 토픽별 발행
   → 파티션 분산

4. PostgreSQL
   → 동기 저장
   → 트랜잭션 커밋
```

**데이터 생성부터 Kafka 발행까지 완벽하게!** 🚀
