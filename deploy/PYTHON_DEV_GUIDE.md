# Python 개발 컨테이너 사용 가이드

## 개요

`python-dev` 컨테이너는 코드를 수정하면서 바로 테스트할 수 있는 개발용 환경입니다.
프로젝트 전체가 마운트되어 로컬에서 코드를 수정하면 컨테이너 내부에 즉시 반영됩니다.

## 시스템 아키텍처

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    Producer     │────▶│     Kafka       │────▶│    Consumer     │
│ (realtime_gen)  │     │   (3 brokers)   │     │  (9 instances)  │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                                                         ▼
                                                ┌─────────────────┐
                                                │   PostgreSQL    │
                                                └─────────────────┘
```

**핵심 데이터 흐름:**
| 구성요소 | 역할 | 비고 |
|---------|------|------|
| Producer (realtime_generator.py) | Kafka에만 발행 | DB 저장 X |
| Consumer (user/product/order_consumer.py) | Kafka 소비 → DB 저장 | 각 그룹 3개 인스턴스 |
| Kafka | 메시지 브로커 | 3개 브로커 클러스터 |
| PostgreSQL | 데이터 영구 저장 | Consumer가 저장 담당 |

## 시작하기

### 1. python-dev 컨테이너 시작

```bash
# deploy 디렉토리에서
cd deploy

# dev 프로파일로 실행
docker-compose --profile dev up -d python-dev

# 또는 모든 서비스와 함께 실행
docker-compose --profile dev up -d
```

### 2. 컨테이너 접속

```bash
# 컨테이너 내부 접속
docker-compose exec python-dev bash

# 또는 직접 docker 명령어 사용
docker exec -it python_dev bash
```

### 3. 컨테이너 내부에서 작업

```bash
# 컨테이너 내부 프롬프트에서
root@python_dev:/app#

# Python 파일 실행
python apps/seeders/initial_seeder.py

# 벤치마크 실행
python apps/benchmarks/kafka_comparison.py

# 대화형 Python 실행
python
>>> from database import crud, database
>>> db = database.SessionLocal()
>>> users = crud.get_users(db, limit=10)
>>> print(users)
```

## 주요 기능

### 1. 코드 즉시 반영

로컬에서 코드를 수정하면 컨테이너 내부에 바로 반영됩니다:

```bash
# 로컬에서 (호스트)
cd c:\Users\USER\20260203_
vi database/crud.py  # 코드 수정

# 컨테이너에서 바로 실행 가능
docker-compose exec python-dev python -c "from database import crud; print('Updated!')"
```

### 2. 데이터베이스 직접 접근

```python
# Python 대화형 모드
>>> from database import crud, database, models
>>> db = database.SessionLocal()

# 데이터 조회
>>> products = db.query(models.Product).limit(5).all()
>>> for p in products:
...     print(f"{p.product_id}: {p.name}")

# 데이터 생성
>>> from collect.user_generator import UserGenerator
>>> gen = UserGenerator()
>>> user_data = gen.generate_single()
>>> crud.create_user(db, user_data)
```

### 3. Kafka 테스트

**Producer → Kafka 발행 테스트:**
```python
>>> from kafka.producer import KafkaProducer
>>> from kafka.config import KAFKA_TOPIC_PRODUCTS
>>> from datetime import datetime

>>> producer = KafkaProducer()

# 테스트 상품 발행 (Consumer가 DB에 저장함)
>>> test_product = {
...     "product_id": "TEST_001",
...     "name": "테스트 상품",
...     "category": "테스트",
...     "price": 10000,
...     "brand": "테스트브랜드",
...     "stock": 100,
...     "created_at": datetime.now()
... }
>>> producer.send_event(KAFKA_TOPIC_PRODUCTS, "TEST_001", test_product, "product_created")
>>> producer.flush()

# DB에서 확인 (Consumer가 저장했는지)
>>> from database import database, models
>>> db = database.SessionLocal()
>>> db.query(models.Product).filter(models.Product.product_id == "TEST_001").first()
```

**Consumer 동작 테스트:**
```python
>>> from kafka.consumer import KafkaConsumerBase

>>> def handler(data):
...     print(f"Received: {data}")

# 주의: 이 consumer는 test_group으로 생성되어 기존 consumer와 별도로 동작
>>> consumer = KafkaConsumerBase("test_group", ["products"], handler, "test_consumer")
>>> consumer.start()  # Ctrl+C로 중지
```

### 4. 스크립트 실행 및 디버깅

```bash
# 초기 데이터 생성 (DB + Kafka 발행)
python apps/seeders/initial_seeder.py

# 실시간 데이터 생성 (Kafka에만 발행 - Consumer가 DB 저장)
# 주의: 이 스크립트는 Kafka에만 발행하고, Consumer가 DB에 저장합니다
python apps/seeders/realtime_generator.py

# 벤치마크 실행
python apps/benchmarks/kafka_comparison.py

# 컨슈머 테스트 (특정 ID로 실행)
python kafka/consumers/product_consumer.py --id test_consumer
python kafka/consumers/order_consumer.py --id test_order_consumer
python kafka/consumers/user_consumer.py --id test_user_consumer

# 디버깅 모드로 실행
python -m pdb apps/seeders/realtime_generator.py
```

### 5. Consumer 실시간 처리 확인

```bash
# Consumer Lag 확인 (LAG=0이면 실시간 처리 중)
docker exec kafka1 kafka-consumer-groups \
  --bootstrap-server kafka1:29092 \
  --describe --group products_group

# 출력 예시:
# GROUP           TOPIC     PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG
# products_group  products  0          9287            9287            0   ← LAG=0 정상
# products_group  products  1          9349            9349            0
# products_group  products  2          9361            9361            0
```

```python
# Python에서 DB 데이터 증가 확인
from database import database, models
from sqlalchemy import func
import time

db = database.SessionLocal()

# 5초 간격으로 레코드 수 변화 확인
for i in range(3):
    count = db.query(func.count(models.Order.order_id)).scalar()
    print(f"[{i}] Orders: {count:,}")
    time.sleep(5)
```

## 환경변수

python-dev 컨테이너는 `.env` 파일의 모든 설정을 사용합니다:

```bash
# 컨테이너 내부에서 환경변수 확인
env | grep POSTGRES
env | grep KAFKA

# Python에서 확인
python -c "import os; print(os.getenv('POSTGRES_HOST'))"
```

## 패키지 설치

컨테이너 내부에서 추가 패키지 설치 가능:

```bash
# 컨테이너 내부에서
pip install ipython jupyter pandas

# IPython 실행
ipython

# Jupyter 노트북 실행 (선택사항)
jupyter notebook --ip=0.0.0.0 --port=8888 --no-browser --allow-root
```

## 유용한 작업 예시

### 1. 데이터베이스 상태 확인

```python
from database import database, models
from sqlalchemy import func

db = database.SessionLocal()

# 테이블별 레코드 수
user_count = db.query(func.count(models.User.user_id)).scalar()
product_count = db.query(func.count(models.Product.product_id)).scalar()
order_count = db.query(func.count(models.Order.order_id)).scalar()

print(f"Users: {user_count:,}")
print(f"Products: {product_count:,}")
print(f"Orders: {order_count:,}")
```

### 2. Kafka 토픽 메시지 수 확인

```bash
# 컨테이너 내부에서
apt-get update && apt-get install -y kafkacat

# 토픽 메시지 수 확인
kafkacat -b kafka1:29092 -t users -C -e -q | wc -l
kafkacat -b kafka1:29092 -t products -C -e -q | wc -l
kafkacat -b kafka1:29092 -t orders -C -e -q | wc -l
```

### 3. 성능 테스트

```bash
# 대량 데이터 생성 테스트
python -c "
from database import crud, database
from collect.user_generator import UserGenerator
import time

db = database.SessionLocal()
gen = UserGenerator()

start = time.time()
for i in range(1000):
    user_data = gen.generate_single()
    crud.create_user(db, user_data)

duration = time.time() - start
print(f'Created 1000 users in {duration:.2f}s')
print(f'TPS: {1000/duration:.2f}')
"
```

## 컨테이너 관리

### 시작/중지

```bash
# 시작
docker-compose --profile dev up -d python-dev

# 중지
docker-compose --profile dev stop python-dev

# 삭제
docker-compose --profile dev down python-dev

# 재시작
docker-compose --profile dev restart python-dev
```

### 로그 확인

```bash
# 실시간 로그 보기
docker-compose --profile dev logs -f python-dev

# 최근 로그 100줄
docker-compose logs --tail=100 python-dev
```

### 리소스 사용량 확인

```bash
# CPU/메모리 사용량
docker stats python_dev

# 디스크 사용량
docker exec python_dev df -h
```

## 주의사항

### 1. 프로파일 설정

`python-dev`는 `dev` 프로파일로 설정되어 있어 **기본적으로 실행되지 않습니다**.
반드시 `--profile dev` 옵션을 사용해야 합니다:

```bash
# ❌ 이렇게 하면 python-dev는 시작되지 않음
docker-compose up -d

# ✅ 이렇게 해야 python-dev가 시작됨
docker-compose --profile dev up -d
```

### 2. 볼륨 마운트

프로젝트 루트가 `/app`에 마운트되므로:
- 로컬 파일 수정 시 컨테이너에 즉시 반영
- 컨테이너에서 파일 생성 시 로컬에도 생성됨
- `.pyc` 파일 등이 호스트에 생성될 수 있음

### 3. 종속성 추가

`requirements.txt`를 수정한 경우 이미지 재빌드 필요:

```bash
# requirements.txt 수정 후
docker-compose build python-dev
docker-compose --profile dev up -d python-dev
```

## 문제 해결

### Q: 컨테이너가 시작되지 않습니다

A: 프로파일 옵션을 확인하세요:
```bash
docker-compose --profile dev up -d python-dev
```

### Q: 코드 수정이 반영되지 않습니다

A: Python 모듈 캐시를 삭제하고 재시작:
```bash
docker-compose exec python-dev find /app -type d -name __pycache__ -exec rm -rf {} +
docker-compose --profile dev restart python-dev
```

### Q: 패키지 import 오류가 발생합니다

A: PYTHONPATH 확인:
```bash
docker-compose exec python-dev python -c "import sys; print('\n'.join(sys.path))"
```

PYTHONPATH가 올바르게 설정되어 있는지 확인하고, 필요시 `.env`에 추가:
```env
PYTHONPATH=/app
```

## 참고

- 운영 환경에서는 이 컨테이너를 사용하지 마세요 (개발용)
- 민감한 데이터 작업 시 주의하세요
- 코드 변경 사항은 반드시 Git으로 커밋하세요

## 관련 문서
- [ENV_GUIDE.md](./ENV_GUIDE.md) - 환경변수 설정 가이드
- [docker-compose.yml](./docker-compose.yml) - 전체 서비스 구성
