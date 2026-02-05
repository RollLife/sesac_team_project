# DB Structure & ORM Implementation Guide

This project uses **SQLAlchemy** with a modular structure to support **Local PostgreSQL**, **Supabase**, and **AWS RDS**.

## 시스템 아키텍처 (Redis 캐싱 + Aging)

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

## 1. Setup Environment

Ensure your `.env` file contains the database connection details.

### Local PostgreSQL
To use the local database via Docker Compose:
```bash
# Start the local database
cd deploy
docker-compose up -d postgres
```

Add to `.env`:
```ini
DB_TYPE=local
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
POSTGRES_DB=sesac_db
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

### Supabase
To use Supabase:
Add to `.env`:
```ini
DB_TYPE=supabase
SUPABASE_DIRECT_URL=postgresql://postgres:[YOUR-PASSWORD]@db.xxxx.supabase.co:5432/postgres
SUPABASE_PASSWORD=your_actual_password
```
*(The code automatically replaces `[YOUR-PASSWORD]` with `SUPABASE_PASSWORD` if present)*

### AWS RDS
To use RDS:
Add to `.env`:
```ini
DB_TYPE=rds
RDS_USER=admin
RDS_PASSWORD=your_rds_password
RDS_HOST=your-rds-endpoint.amazonaws.com
RDS_DB=sesac_db
```

## 2. Install Dependencies
You need to install the following packages:
```bash
pip install sqlalchemy psycopg2-binary python-dotenv
```

## 3. Database Schema

### Users Table

| Column | Type | Description |
|--------|------|-------------|
| user_id | VARCHAR(50) | Primary Key |
| name | VARCHAR(100) | 사용자 이름 |
| gender | CHAR(1) | 성별 (M/F) |
| age | INTEGER | 나이 |
| age_group | VARCHAR(10) | 연령대 (20대, 30대 등) |
| region | VARCHAR(50) | 지역 |
| join_date | DATE | 가입일 |
| **last_cached_at** | TIMESTAMP | **Redis 캐싱 시점 (Aging 기법용)** |
| created_at | TIMESTAMP | 생성일시 |

### Products Table

| Column | Type | Description |
|--------|------|-------------|
| product_id | VARCHAR(50) | Primary Key |
| name | VARCHAR(200) | 상품명 |
| category | VARCHAR(50) | 카테고리 |
| brand | VARCHAR(100) | 브랜드 |
| price | INTEGER | 판매가 |
| org_price | INTEGER | 원가 |
| discount_rate | FLOAT | 할인율 |
| stock | INTEGER | 재고 |
| **last_cached_at** | TIMESTAMP | **Redis 캐싱 시점 (Aging 기법용)** |
| created_at | TIMESTAMP | 생성일시 |

### Orders Table

| Column | Type | Description |
|--------|------|-------------|
| order_id | VARCHAR(50) | Primary Key |
| user_id | VARCHAR(50) | Foreign Key (Users) |
| product_id | VARCHAR(50) | Foreign Key (Products) |
| quantity | INTEGER | 주문 수량 |
| total_amount | INTEGER | 총 금액 |
| shipping_cost | INTEGER | 배송비 |
| discount_amount | INTEGER | 할인 금액 |
| payment_method | VARCHAR(20) | 결제 방식 |
| status | VARCHAR(20) | 주문 상태 |
| category | VARCHAR(50) | 상품 카테고리 (비정규화) |
| user_region | VARCHAR(50) | 사용자 지역 (비정규화) |
| user_gender | CHAR(1) | 사용자 성별 (비정규화) |
| user_age_group | VARCHAR(10) | 사용자 연령대 (비정규화) |
| created_at | TIMESTAMP | 생성일시 |

## 4. Redis 캐싱을 위한 last_cached_at 컬럼

### 목적
- **Aging 기법**: 캐시 교체 시 신규 데이터와 기존 데이터를 균형있게 선택
- **기아(Starvation) 방지**: 특정 데이터가 계속 캐시되지 않는 문제 해결

### 동작 방식
```python
# Cache Worker가 50초마다 실행
# 1. 신규 데이터 500건 (last_cached_at IS NULL)
# 2. 기존 데이터 500건 (ORDER BY last_cached_at ASC - 가장 오래된 것 우선)
# 3. 캐싱 후 last_cached_at = NOW() 업데이트
```

### 쿼리 예시
```sql
-- 아직 캐시되지 않은 신규 데이터
SELECT * FROM users
WHERE last_cached_at IS NULL
LIMIT 500;

-- 가장 오래전에 캐시된 데이터
SELECT * FROM users
WHERE last_cached_at IS NOT NULL
ORDER BY last_cached_at ASC
LIMIT 500;

-- 캐싱 후 업데이트
UPDATE users
SET last_cached_at = NOW()
WHERE user_id IN (...);
```

### 성능 향상
| 지표 | Before (DB 직접) | After (Redis 캐시) |
|------|------------------|-------------------|
| DB 쿼리/분 | ~60회 | ~1.2회 |
| 조회 속도 | 10-100ms | 0.1-1ms |
| 개선율 | - | 98% 감소, 100배 향상 |

## 5. Operations

### Initialize Database (Create Tables)
Run the following command to create tables for the configured `DB_TYPE`:
```bash
python -m database.init_db
```

### Using CRUD Operations
Import the `crud` module to interact with the database.

```python
from database import database, crud, models

# Start a session
db = database.SessionLocal()

# Create a User
new_user = crud.create_user(db, {
    "user_id": "U_001",
    "name": "Hong Gil Dong",
    "gender": "M",
    "age": 30,
    "address": "Seoul Gangnam-gu ..."
})

# Create a Product
new_product = crud.create_product(db, {
    "product_id": "P1001",
    "name": "MacBook Pro",
    "category": "Electronics",
    "price": 3000000
})

# Create an Order (Denormalized fields are auto-filled)
new_order = crud.create_order(db, {
    "user_id": "U_001",
    "product_id": "P1001",
    "quantity": 1,
    "total_amount": 3000000
})

# Commit and close
db.close()
```

## 6. Redis Cache Client

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

### Redis 캐시 데이터 구조

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

## 7. Database Connection Testing

### PostgreSQL 연결 테스트
```bash
# Docker에서
docker exec local_postgres psql -U postgres -d sesac_db -c "SELECT COUNT(*) FROM users;"

# Python에서
docker exec python_dev python -c "
from database.database import engine
from sqlalchemy import text
with engine.connect() as conn:
    result = conn.execute(text('SELECT COUNT(*) FROM users'))
    print(f'유저 수: {result.fetchone()[0]:,}')
"
```

### Redis 연결 테스트
```bash
# Redis ping 테스트
docker exec local_redis redis-cli ping

# 캐시 데이터 확인
docker exec local_redis redis-cli hlen cache:users
docker exec local_redis redis-cli hlen cache:products
```

## 8. Troubleshooting

### DB 연결 실패
```bash
# PostgreSQL 상태 확인
docker-compose exec postgres pg_isready

# 연결 테스트
docker-compose exec postgres psql -U postgres -c "SELECT 1;"

# PostgreSQL 재시작
docker-compose restart postgres
```

### Redis 캐시 문제
```bash
# Redis 상태 확인
docker exec local_redis redis-cli ping

# 캐시 데이터 확인
docker exec local_redis redis-cli hlen cache:users

# Redis 재시작
docker-compose restart redis cache-worker
```

### last_cached_at 관련 문제
```sql
-- 캐시되지 않은 데이터 수 확인
SELECT COUNT(*) FROM users WHERE last_cached_at IS NULL;
SELECT COUNT(*) FROM products WHERE last_cached_at IS NULL;

-- last_cached_at 초기화 (전체 재캐싱 필요 시)
UPDATE users SET last_cached_at = NULL;
UPDATE products SET last_cached_at = NULL;
```

## 9. 참고 자료

- **[KAFKA_PRODUCER_GUIDE.md](KAFKA_PRODUCER_GUIDE.md)** - Producer 가이드 (Redis 캐시 모드)
- **[KAFKA_CONSUMER_GUIDE.md](KAFKA_CONSUMER_GUIDE.md)** - Consumer 가이드
- **[DOCKER_DEPLOYMENT_GUIDE.md](DOCKER_DEPLOYMENT_GUIDE.md)** - Docker 배포
