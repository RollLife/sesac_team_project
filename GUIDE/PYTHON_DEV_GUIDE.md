# Python 개발/테스트 컨테이너 가이드

## 개요

`python-dev` 컨테이너는 Docker 환경에서 Python 코드를 대화형으로 테스트하고 개발할 수 있는 환경을 제공합니다.

### 시스템 아키텍처 (Redis 캐싱 + Aging)

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

## 주요 기능

- ✅ PostgreSQL, Kafka, **Redis** 연결 테스트
- ✅ Python 대화형 쉘 (REPL)
- ✅ 스크립트 실행 및 디버깅
- ✅ 코드 변경 실시간 반영 (볼륨 마운트)
- ✅ 환경 확인 및 검증
- ✅ **Redis 캐시 클라이언트 테스트**

## 시작하기

### 1. 컨테이너 실행

```bash
# 프로파일을 사용하여 실행
docker-compose --profile dev up -d python-dev

# 또는 직접 실행
docker-compose up -d python-dev
```

### 2. 컨테이너 접속

```bash
# Bash 쉘 접속
docker-compose exec python-dev bash

# 또는
docker exec -it python_dev bash
```

## 환경 테스트

### 자동 테스트 실행

```bash
# 컨테이너 내부에서
python tests/test_environment.py
```

**출력 예시:**
```
╔════════════════════════════════════════════════════════════╗
║              환경 테스트 스크립트                           ║
╚════════════════════════════════════════════════════════════╝

============================================================
1. 환경변수 확인
============================================================

✅ DB_TYPE = local
✅ POSTGRES_HOST = postgres
✅ POSTGRES_PORT = 5432
✅ KAFKA_BOOTSTRAP_SERVERS = kafka1:29092,kafka2:29093,kafka3:29094
✅ REDIS_HOST = redis
✅ REDIS_PORT = 6379

...

============================================================
테스트 결과 요약
============================================================

✅ 환경변수: 성공
✅ Python 패키지: 성공
✅ PostgreSQL: 성공
✅ Kafka 연결: 성공
✅ Kafka Producer: 성공
✅ Redis 연결: 성공
✅ 데이터 생성기: 성공

✅ 모든 테스트 통과! (7/7)
✅ 환경이 정상적으로 구성되었습니다! 🎉
```

### 수동 테스트

#### PostgreSQL 연결 확인
```bash
docker-compose exec python-dev python -c "
from database.database import engine
from sqlalchemy import text
with engine.connect() as conn:
    result = conn.execute(text('SELECT version();'))
    print(result.fetchone()[0])
"
```

#### Kafka 연결 확인
```bash
docker-compose exec python-dev python -c "
from confluent_kafka.admin import AdminClient
from kafka.config import KAFKA_BOOTSTRAP_SERVERS
admin = AdminClient({'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS})
metadata = admin.list_topics(timeout=10)
print(f'브로커 수: {len(metadata.brokers)}')
print(f'토픽 수: {len(metadata.topics)}')
"
```

#### Redis 연결 확인
```bash
docker-compose exec python-dev python -c "
from cache.client import get_redis_client
client = get_redis_client()
if client.is_connected():
    print('Redis 연결 성공!')
    user = client.get_random_user()
    print(f'랜덤 유저: {user}')
"
```

## Redis 캐시 클라이언트 테스트

### 기본 사용법

```python
# Python 쉘에서
from cache.client import get_redis_client

# 클라이언트 가져오기 (싱글톤)
redis_client = get_redis_client()

# 연결 상태 확인
if redis_client.is_connected():
    print("Redis 연결됨")

# 랜덤 유저 조회
user = redis_client.get_random_user()
print(user)  # {'user_id': 'u_123', 'name': '홍길동', ...}

# 랜덤 상품 조회
product = redis_client.get_random_product()
print(product)  # {'product_id': 'p_456', 'name': '무선 이어폰', ...}
```

### 캐시 상태 확인

```bash
# Redis CLI로 캐시 확인
docker exec local_redis redis-cli hlen cache:users
docker exec local_redis redis-cli hlen cache:products

# 샘플 데이터 조회
docker exec local_redis redis-cli hrandfield cache:users 1 withvalues
```

## Python 대화형 쉘 (REPL)

### Python 쉘 실행

```bash
# 컨테이너 내부에서
python

# 또는 외부에서
docker-compose exec python-dev python
```

### 예제 사용법

```python
# PostgreSQL 테스트
>>> from database.database import SessionLocal
>>> from database import crud
>>> db = SessionLocal()
>>> users = crud.get_users(db, limit=5)
>>> for user in users:
...     print(user.name, user.email)
>>> db.close()

# Redis 캐시 테스트
>>> from cache.client import get_redis_client
>>> redis_client = get_redis_client()
>>> user = redis_client.get_random_user()
>>> print(f"랜덤 유저: {user['name']}, {user['region']}")
>>> product = redis_client.get_random_product()
>>> print(f"랜덤 상품: {product['name']}, {product['price']}원")

# Kafka Producer 테스트
>>> from kafka.producer import KafkaProducer
>>> from datetime import datetime
>>> producer = KafkaProducer()
>>> test_data = {
...     'user_id': 'test_001',
...     'name': '테스트',
...     'email': 'test@example.com',
...     'created_at': datetime.now()
... }
>>> producer.send_event('users', 'test_001', test_data, 'user_created')
>>> producer.close()

# 데이터 생성기 테스트
>>> from collect.user_generator import UserGenerator
>>> gen = UserGenerator()
>>> users = gen.generate_batch(10)
>>> print(f'{len(users)}명 생성됨')
>>> print(users[0])
```

### IPython 사용 (더 나은 REPL)

```bash
# IPython 설치 (필요시)
docker-compose exec python-dev pip install ipython

# IPython 실행
docker-compose exec python-dev ipython
```

## 스크립트 실행

### 기존 스크립트 실행

```bash
# 환경 테스트
docker-compose exec python-dev python tests/test_environment.py

# 데이터 생성기 테스트
docker-compose exec python-dev python collect/user_generator.py

# 토픽 생성
docker-compose exec python-dev python kafka/admin/setup_topics.py

# 초기 데이터 생성
docker-compose exec python-dev python apps/seeders/initial_seeder.py

# Redis 캐시 워커 테스트 (한 번만 실행)
docker-compose exec python-dev python cache/cache_worker.py --once
```

### 커스텀 스크립트 실행

```bash
# 1. 로컬에서 스크립트 작성
# test_script.py

# 2. 컨테이너에서 실행 (볼륨 마운트되어 있음)
docker-compose exec python-dev python test_script.py
```

## 데이터베이스 작업

### SQL 쿼리 실행

```bash
# Python으로 SQL 실행
docker-compose exec python-dev python -c "
from database.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    # 유저 수 확인
    result = conn.execute(text('SELECT COUNT(*) FROM users'))
    print(f'유저 수: {result.fetchone()[0]:,}')

    # 상품 수 확인
    result = conn.execute(text('SELECT COUNT(*) FROM products'))
    print(f'상품 수: {result.fetchone()[0]:,}')

    # 주문 수 확인
    result = conn.execute(text('SELECT COUNT(*) FROM orders'))
    print(f'주문 수: {result.fetchone()[0]:,}')

    # 캐시되지 않은 유저 수 확인
    result = conn.execute(text('SELECT COUNT(*) FROM users WHERE last_cached_at IS NULL'))
    print(f'캐시 안된 유저: {result.fetchone()[0]:,}')
"
```

### 테이블 스키마 확인

```bash
docker-compose exec python-dev python -c "
from database.database import engine, Base
from database import models

# 테이블 생성 (없으면)
Base.metadata.create_all(bind=engine)

# 스키마 정보
from sqlalchemy import inspect
inspector = inspect(engine)

for table_name in inspector.get_table_names():
    print(f'\n테이블: {table_name}')
    for column in inspector.get_columns(table_name):
        print(f'  {column[\"name\"]}: {column[\"type\"]}')
"
```

## Kafka 작업

### 토픽 목록 확인

```bash
docker-compose exec python-dev python -c "
from confluent_kafka.admin import AdminClient
from kafka.config import KAFKA_BOOTSTRAP_SERVERS

admin = AdminClient({'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS})
metadata = admin.list_topics(timeout=10)

print('토픽 목록:')
for topic_name, topic_metadata in metadata.topics.items():
    if not topic_name.startswith('_'):
        print(f'  - {topic_name}: {len(topic_metadata.partitions)}개 파티션')
"
```

### 메시지 발행 테스트

```bash
docker-compose exec python-dev python -c "
from kafka.producer import KafkaProducer
from datetime import datetime

producer = KafkaProducer()

# 테스트 메시지 발행
test_message = {
    'user_id': 'dev_test_001',
    'name': '개발 테스트',
    'email': 'dev@test.com',
    'created_at': datetime.now()
}

success = producer.send_event(
    topic='users',
    key='dev_test_001',
    data=test_message,
    event_type='user_created'
)

print(f'메시지 발행: {\"성공\" if success else \"실패\"}')
producer.flush()
producer.close()
"
```

## Redis 작업

### 캐시 상태 확인

```bash
docker-compose exec python-dev python -c "
from cache.client import get_redis_client

client = get_redis_client()
if client.is_connected():
    print('Redis 연결 성공!')

    # 캐시된 유저 수
    import redis
    r = redis.Redis(host='redis', port=6379, decode_responses=True)
    users_count = r.hlen('cache:users')
    products_count = r.hlen('cache:products')

    print(f'캐시된 유저: {users_count}')
    print(f'캐시된 상품: {products_count}')
"
```

### 랜덤 데이터 조회 테스트

```bash
docker-compose exec python-dev python -c "
from cache.client import get_redis_client

client = get_redis_client()

# 5명의 랜덤 유저 조회
for i in range(5):
    user = client.get_random_user()
    if user:
        print(f'{i+1}. {user[\"name\"]} ({user[\"region\"]})')
    else:
        print(f'{i+1}. 캐시에 데이터 없음')
"
```

## 디버깅

### 로그 레벨 조정

```python
# Python 스크립트에서
import logging
logging.basicConfig(level=logging.DEBUG)
```

### pdb 디버거 사용

```python
# 스크립트에 추가
import pdb; pdb.set_trace()

# 또는
breakpoint()  # Python 3.7+
```

```bash
# 디버거와 함께 실행
docker-compose exec python-dev python -m pdb your_script.py
```

## 개발 워크플로우

### 1. 코드 수정
```bash
# 로컬에서 코드 수정
# 예: collect/user_generator.py
```

### 2. 즉시 테스트
```bash
# 변경사항이 자동으로 반영됨 (볼륨 마운트)
docker-compose exec python-dev python collect/user_generator.py
```

### 3. 환경 검증
```bash
# 전체 환경 테스트
docker-compose exec python-dev python tests/test_environment.py
```

## 패키지 설치

### 임시 패키지 설치 (컨테이너 재시작 시 삭제됨)
```bash
docker-compose exec python-dev pip install ipython pandas matplotlib
```

### 영구 패키지 설치
```bash
# 1. requirements.txt에 추가
echo "ipython" >> requirements.txt

# 2. 이미지 재빌드
docker-compose build python-dev

# 3. 컨테이너 재시작
docker-compose up -d python-dev
```

## 유용한 명령어 모음

### 빠른 테스트

```bash
# 환경 전체 테스트
docker-compose exec python-dev python tests/test_environment.py

# DB 연결만 테스트
docker-compose exec python-dev python -c "from database.database import engine; print(engine.connect())"

# Kafka 연결만 테스트
docker-compose exec python-dev python kafka/test_connection.py

# Redis 연결만 테스트
docker-compose exec python-dev python -c "
from cache.client import get_redis_client
print(f'Redis 연결: {get_redis_client().is_connected()}')
"

# 데이터 생성기 테스트
docker-compose exec python-dev python -c "
from collect.user_generator import UserGenerator
users = UserGenerator().generate_batch(5)
print(f'{len(users)}명 생성')
"
```

### 데이터 확인

```bash
# 유저 수
docker-compose exec python-dev python -c "
from database.database import SessionLocal
from database import crud
db = SessionLocal()
users = crud.get_users(db, limit=0)
print(f'총 유저 수: {len(users)}')
db.close()
"

# 최근 주문 5건
docker-compose exec python-dev python -c "
from database.database import SessionLocal
from database import models
from sqlalchemy import desc
db = SessionLocal()
orders = db.query(models.Order).order_by(desc(models.Order.created_at)).limit(5).all()
for order in orders:
    print(f'{order.order_id}: {order.total_amount:,}원')
db.close()
"

# Redis 캐시 상태
docker-compose exec python-dev python -c "
import redis
r = redis.Redis(host='redis', port=6379, decode_responses=True)
print(f'캐시된 유저: {r.hlen(\"cache:users\")}')
print(f'캐시된 상품: {r.hlen(\"cache:products\")}')
"
```

## Jupyter Notebook (선택사항)

### Jupyter 설치 및 실행

```bash
# 1. Jupyter 설치
docker-compose exec python-dev pip install jupyter

# 2. Jupyter 실행
docker-compose exec python-dev jupyter notebook --ip=0.0.0.0 --port=8888 --no-browser --allow-root

# 3. docker-compose.yml에 포트 추가 필요
# ports:
#   - "8888:8888"
```

## 문제 해결

### 컨테이너가 시작되지 않을 때
```bash
# 로그 확인
docker-compose logs python-dev

# 컨테이너 재생성
docker-compose up -d --force-recreate python-dev
```

### 코드 변경이 반영되지 않을 때
```bash
# 볼륨 마운트 확인
docker-compose exec python-dev ls -la /app

# Python 모듈 캐시 삭제
docker-compose exec python-dev find . -type d -name __pycache__ -exec rm -rf {} +
docker-compose exec python-dev find . -type f -name "*.pyc" -delete
```

### 패키지 충돌 시
```bash
# 이미지 재빌드 (캐시 없이)
docker-compose build --no-cache python-dev

# 컨테이너 재시작
docker-compose up -d python-dev
```

### Redis 연결 실패 시
```bash
# Redis 서비스 상태 확인
docker-compose ps redis

# Redis 재시작
docker-compose restart redis

# 연결 테스트
docker exec local_redis redis-cli ping
```

## 정리

### 컨테이너 종료
```bash
docker-compose stop python-dev
```

### 컨테이너 삭제
```bash
docker-compose down python-dev
```

### 프로파일로 관리
```bash
# dev 프로파일 서비스만 시작
docker-compose --profile dev up -d

# dev 프로파일 서비스만 종료
docker-compose --profile dev down
```

## 요약

`python-dev` 컨테이너는:
- 🐍 Python 개발 환경 제공
- 🔍 환경 테스트 자동화
- 💻 대화형 쉘 (REPL)
- 🔧 스크립트 실행 및 디버깅
- 📝 코드 변경 실시간 반영
- ✅ PostgreSQL, Kafka, **Redis** 연결 검증
- 🚀 **Redis 캐시 클라이언트 테스트**

**개발, 테스트, 디버깅을 위한 완벽한 환경!**

## 참고 자료

- **[KAFKA_PRODUCER_GUIDE.md](KAFKA_PRODUCER_GUIDE.md)** - Producer 가이드 (Redis 캐시 모드)
- **[KAFKA_CONSUMER_GUIDE.md](KAFKA_CONSUMER_GUIDE.md)** - Consumer 가이드
- **[DB_README.md](DB_README.md)** - DB 구조 및 ORM 가이드
- **[DOCKER_DEPLOYMENT_GUIDE.md](DOCKER_DEPLOYMENT_GUIDE.md)** - Docker 배포
