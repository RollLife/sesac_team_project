# DB Structure & ORM Implementation Guide

This project uses **SQLAlchemy** with a modular structure to support **Local PostgreSQL**, **Supabase**, and **AWS RDS**.

## 시스템 아키텍처 (Redis 캐싱 + 구매이력/미구매 분리 적재)

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
| gender | VARCHAR(10) | 성별 (M/F) |
| age | INTEGER | 나이 |
| birth_year | INTEGER | 출생년도 |
| address | VARCHAR(255) | 전체 주소 |
| address_district | VARCHAR(100) | 주소 (구 단위, 인덱스) |
| email | VARCHAR(100) | 이메일 |
| grade | VARCHAR(20) | 멤버십 등급 (기본: BRONZE, 배치 갱신) |
| status | VARCHAR(20) | 활동/휴면 상태 (ACTIVE/DORMANT) |
| last_login_at | TIMESTAMP | 마지막 로그인 일시 |
| marketing_agree | VARCHAR(5) | 마케팅 동의 여부 ("true"/"false") |
| created_at | TIMESTAMP | 가입일 |
| **last_ordered_at** | TIMESTAMP | **마지막 주문 시간 (캐시 분리 적재 기준)** |
| **random_seed** | FLOAT | **캐시 랜덤 선택용 시드 (0.0~1.0, 인덱스)** |
| created_datetime | TIMESTAMP | 실제 추가되는 시각 |
| updated_datetime | TIMESTAMP | 실제 수정되는 시각 |

### Products Table

| Column | Type | Description |
|--------|------|-------------|
| product_id | VARCHAR(50) | Primary Key |
| name | VARCHAR(200) | 상품명 |
| category | VARCHAR(50) | 카테고리 (인덱스) |
| brand | VARCHAR(100) | 브랜드 (인덱스) |
| org_price | INTEGER | 정가 |
| price | INTEGER | 판매가 |
| discount_rate | FLOAT | 할인율 |
| stock | INTEGER | 재고 |
| rating | FLOAT | 평점 |
| review_count | INTEGER | 리뷰 수 |
| is_best | VARCHAR(1) | 베스트 상품 여부 |
| created_at | TIMESTAMP | 등록일 |
| **order_count** | INTEGER | **누적 판매 수 (인덱스, 캐시 분리 적재 기준)** |
| created_datetime | TIMESTAMP | 실제 추가되는 시각 |
| updated_datetime | TIMESTAMP | 실제 수정되는 시각 |

### Orders Table

| Column | Type | Description |
|--------|------|-------------|
| order_id | VARCHAR(100) | Primary Key |
| user_id | VARCHAR(50) | Foreign Key (Users) |
| product_id | VARCHAR(50) | Foreign Key (Products) |
| quantity | INTEGER | 주문 수량 |
| total_amount | INTEGER | 총 금액 |
| shipping_cost | INTEGER | 배송비 |
| discount_amount | INTEGER | 할인 금액 |
| payment_method | VARCHAR(50) | 결제 방식 |
| status | VARCHAR(20) | 주문 상태 (인덱스) |
| category | VARCHAR(50) | 상품 카테고리 (비정규화) |
| user_name | VARCHAR(100) | 유저 이름 (비정규화) |
| user_region | VARCHAR(100) | 유저 지역 (비정규화) |
| user_gender | VARCHAR(10) | 유저 성별 (비정규화) |
| user_age_group | VARCHAR(20) | 연령대 (비정규화) |
| created_at | TIMESTAMP | 주문 발생 시간 (인덱스) |
| created_datetime | TIMESTAMP | 실제 추가되는 시각 |
| updated_datetime | TIMESTAMP | 실제 수정되는 시각 |

## 4. Redis 캐싱 - 구매이력/미구매 분리 적재

### 목적
- **구매이력 분리**: 구매 고객과 미구매 고객을 분리하여 현실적 캐시 풀 구성
- **재구매 기회**: 오래 전 구매한 고객에게 재구매 기회 제공
- **신규 고객 노출**: 최근 가입한 미구매 고객에게 첫 구매 기회 부여

### 고객 적재 방식 (1000명)
```
구매이력 고객 600명 (last_ordered_at ASC - 구매한 지 가장 오래된 순)
+ 미구매 고객 400명 (created_at DESC - 최근 가입 순)
= 총 1000명 (미구매 부족 시 구매이력 풀 확대)
```

### 상품 적재 방식 (1000개)
```
인기 상품 700개 (order_count DESC - 판매량 높은 순)
+ 신상품 300개 (order_count == 0, created_at DESC - 최신 등록순)
= 총 1000개 (신상품 부족 시 인기상품 풀 확대)
```

### 구매 성향 기반 선택
캐싱된 1000명 전체에서 **성향 점수 가중치**로 고객을 선택하고, **장바구니(1~10개)**를 한번에 구매합니다:
```python
최종 점수 = 기본 점수(인구통계) x 시간대 변동 x 마케팅 부스트 x 생활 이벤트
```

### 성능 향상
| 지표 | Before (DB 직접) | After (Redis 캐시) |
|------|------------------|-------------------|
| DB 쿼리/분 | ~60회 | ~1.2회 |
| 조회 속도 | 10-100ms | 0.1-1ms |
| 개선율 | - | 98% 감소, 100배 향상 |

## 5. 고객 등급 시스템

### 등급 기준 (6개월 누적)
| 등급 | 누적 금액 | 주문 횟수 |
|------|----------|----------|
| VIP | 500만원 이상 | 30회 이상 |
| GOLD | 200만원 이상 | 15회 이상 |
| SILVER | 50만원 이상 | 5회 이상 |
| BRONZE | 기본 (조건 미달) | - |

### 갱신 주기
- **실시간 시스템**: 10분마다 배치 갱신 (`apps/batch/grade_updater.py`)
- **1년치 스크립트**: 7일마다 갱신
- **느슨한 강등**: 한 번에 1단계씩만 (VIP→GOLD→SILVER→BRONZE)

## 6. Operations

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

## 7. Redis Cache Client

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

## 8. Database Connection Testing

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

## 9. Troubleshooting

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

### 캐시 적재 관련 확인
```sql
-- 구매이력 고객 수 확인
SELECT COUNT(*) FROM users WHERE last_ordered_at IS NOT NULL;

-- 미구매 고객 수 확인
SELECT COUNT(*) FROM users WHERE last_ordered_at IS NULL;

-- 인기 상품 수 확인
SELECT COUNT(*) FROM products WHERE order_count > 0;

-- 등급별 고객 분포
SELECT grade, COUNT(*) FROM users GROUP BY grade ORDER BY COUNT(*) DESC;
```

## 10. 참고 자료

- **[KAFKA_PRODUCER_GUIDE.md](KAFKA_PRODUCER_GUIDE.md)** - Producer 가이드 (Redis 캐시 모드)
- **[KAFKA_CONSUMER_GUIDE.md](KAFKA_CONSUMER_GUIDE.md)** - Consumer 가이드
- **[DOCKER_DEPLOYMENT_GUIDE.md](DOCKER_DEPLOYMENT_GUIDE.md)** - Docker 배포
