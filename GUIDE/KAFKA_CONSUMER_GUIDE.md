# 카프카 컨슈머 가이드

## 개요

3개 컨슈머 그룹, 총 9개 컨슈머 인스턴스로 구성된 카프카 컨슈머 클러스터입니다.

**Consumer는 Kafka 토픽에서 메시지를 소비하여 PostgreSQL에 저장하는 역할을 담당합니다.**

### 시스템 아키텍처 (Redis 캐싱 + 분리적재)

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

### Consumer의 역할
- ✅ Kafka 토픽에서 메시지 소비
- ✅ 메시지 역직렬화 (JSON → dict)
- ✅ 중복 체크 후 PostgreSQL 저장
- ✅ 오프셋 수동 커밋 (At-least-once 보장)

## 컨슈머 구성

### 컨슈머 그룹

| 그룹 ID | 토픽 | 컨슈머 수 | 역직렬화 | 저장소 |
|---------|------|-----------|----------|--------|
| users_group | users | 3개 | JSON | PostgreSQL |
| products_group | products | 3개 | JSON | PostgreSQL |
| orders_group | orders | 3개 | JSON | PostgreSQL |

### 컨슈머 인스턴스

```
👥 users_group:
   - user_consumer_1    → 파티션 0
   - user_consumer_2    → 파티션 1
   - user_consumer_3    → 파티션 2

📦 products_group:
   - product_consumer_1 → 파티션 0
   - product_consumer_2 → 파티션 1
   - product_consumer_3 → 파티션 2

🛒 orders_group:
   - order_consumer_1   → 파티션 0
   - order_consumer_2   → 파티션 1
   - order_consumer_3   → 파티션 2
```

## 파티션 할당 전략

### 1:1 매핑
- 각 토픽: 3개 파티션
- 각 그룹: 3개 컨슈머
- **결과**: 각 컨슈머가 1개 파티션 전담

### 자동 리밸런싱
컨슈머가 추가/제거되면 자동으로 파티션 재할당:
```
2개 컨슈머만 실행 시:
- consumer_1: 파티션 0, 1
- consumer_2: 파티션 2

4개 컨슈머 실행 시:
- consumer_1: 파티션 0
- consumer_2: 파티션 1
- consumer_3: 파티션 2
- consumer_4: (대기 - 파티션 없음)
```

## 실행 방법

### Docker 실행 (권장)

```bash
cd deploy

# 전체 시스템 시작 (Consumer 포함)
docker-compose up -d

# Consumer 로그 확인
docker logs -f order_consumer_1
docker logs -f user_consumer_1
docker logs -f product_consumer_1
```

### 로컬 실행

#### 1. 전체 컨슈머 실행 (9개)

```bash
python apps/runners/consumer_runner.py
```

출력 예시:
```
🚀 컨슈머 시작 중...

   ✅ user_consumer_1 시작
   ✅ user_consumer_2 시작
   ✅ user_consumer_3 시작
   ✅ product_consumer_1 시작
   ✅ product_consumer_2 시작
   ✅ product_consumer_3 시작
   ✅ order_consumer_1 시작
   ✅ order_consumer_2 시작
   ✅ order_consumer_3 시작

✅ 총 9개 컨슈머가 시작되었습니다!
   Ctrl+C로 종료
```

#### 2. 단일 컨슈머 실행 (테스트용)

```bash
# 유저 컨슈머 1개만 실행
python apps/runners/consumer_runner.py --single --type user --id user_consumer_1

# 상품 컨슈머 1개만 실행
python apps/runners/consumer_runner.py --single --type product --id product_consumer_1

# 주문 컨슈머 1개만 실행
python apps/runners/consumer_runner.py --single --type order --id order_consumer_1
```

#### 3. 개별 컨슈머 실행

```bash
# 유저 컨슈머
python kafka/consumers/user_consumer.py --id user_consumer_1

# 상품 컨슈머
python kafka/consumers/product_consumer.py --id product_consumer_2

# 주문 컨슈머
python kafka/consumers/order_consumer.py --id order_consumer_3
```

## 메시지 처리 흐름

### 전체 데이터 흐름

```
1. Cache-Worker (50초마다)
   └─ DB에서 분리 적재로 1,000건 조회
      ├─ 고객: 구매이력 600명 (last_ordered_at ASC) + 미구매 400명 (created_at DESC)
      └─ 상품: 인기 700개 (order_count DESC) + 신상품 300개 (created_at DESC)
   └─ Redis에 캐싱 (cache:users, cache:products)

2. Producer (3~5초마다)
   └─ Redis에서 구매 성향 상위 200명 선택
   └─ 주문 데이터 생성
   └─ Kafka 토픽에 발행 (DB 저장 X)

3. Consumer (이 문서의 주제)
   └─ Kafka에서 메시지 소비
   └─ 중복 체크
   └─ PostgreSQL에 저장
   └─ 오프셋 커밋
```

### Consumer 상세 처리 흐름

#### 1. 메시지 수신
```
Kafka Topic (users)
  └─> user_consumer_1 (파티션 0)
      └─> 메시지 폴링 (poll)
```

#### 2. 역직렬화 (JSON)
```python
# Kafka 메시지 (bytes)
b'{"user_id": "u123", "name": "홍길동", ...}'

# 역직렬화 후 (dict)
{
    "user_id": "u123",
    "name": "홍길동",
    "age": 25,
    ...
}
```

#### 3. 중복 체크
```python
# DB에 이미 존재하는지 확인
existing_user = crud.get_user(db, data['user_id'])

if existing_user:
    # 이미 존재 → 스킵
    return
```

#### 4. PostgreSQL 저장
```python
# 카프카 재발행 방지 (무한 루프 방지)
crud_module.KAFKA_ENABLED = False

# DB에 저장
crud.create_user(db, data)

# 설정 복원
crud_module.KAFKA_ENABLED = True
```

#### 5. 오프셋 커밋
```python
# 성공 시 오프셋 커밋
consumer.commit(message=message)
```

## 컨슈머 설정

### 주요 설정 (kafka/consumer.py)

```python
config = {
    'bootstrap.servers': 'localhost:9092,localhost:9093,localhost:9094',
    'group.id': 'users_group',  # 컨슈머 그룹
    'client.id': 'user_consumer_1',  # 컨슈머 ID

    # 오프셋 관리
    'enable.auto.commit': False,  # 수동 커밋
    'auto.offset.reset': 'earliest',  # 처음부터 읽기

    # 성능 설정
    'fetch.min.bytes': 1024,  # 최소 1KB 대기
    'fetch.wait.max.ms': 500,  # 최대 500ms 대기
    'max.poll.records': 500,  # 한 번에 최대 500개

    # 세션 관리
    'session.timeout.ms': 30000,  # 30초
    'heartbeat.interval.ms': 10000,  # 10초
}
```

### 파라미터 설명

| 파라미터 | 값 | 설명 |
|---------|-----|------|
| enable.auto.commit | false | 수동 오프셋 커밋 (정확성 보장) |
| auto.offset.reset | earliest | 처음부터 읽기 (신규 그룹) |
| fetch.min.bytes | 1024 | 최소 1KB 데이터가 있을 때 반환 |
| fetch.wait.max.ms | 500 | 최대 500ms 대기 |
| max.poll.records | 500 | 한 번에 최대 500개 처리 |
| session.timeout.ms | 30000 | 30초 동안 heartbeat 없으면 제외 |

## 데이터 흐름 전체 구조

```
┌─────────────┐
│  Producer   │ (apps/seeders/realtime_generator.py)
│ Redis 캐시  │ ← 주문 생성 시 Redis에서 유저/상품 조회
│   조회      │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────┐
│      Kafka Cluster (3 Brokers)  │
│  ┌─────────┬──────────┬────────┐│
│  │ users   │products  │orders  ││
│  │ (3 파티션)│(3 파티션) │(3 파티션)││
│  └─────────┴──────────┴────────┘│
└───────┬─────────────────────────┘
        │
        ├─────────────┬─────────────┬─────────────┐
        │             │             │             │
   ┌────▼────┐  ┌────▼────┐  ┌────▼────┐  ...   │
   │ user_   │  │product_ │  │ order_  │         │
   │consumer1│  │consumer1│  │consumer1│         │
   └────┬────┘  └────┬────┘  └────┬────┘         │
        │            │            │              │
        └────────────┴────────────┴──────────────┘
                     │
                     ▼
              ┌──────────────┐
              │  PostgreSQL  │
              │   Database   │
              └──────────────┘
```

## 모니터링

### Consumer 로그 확인 (Docker)

```bash
# 주문 컨슈머 로그
docker logs -f order_consumer_1
docker logs -f order_consumer_2
docker logs -f order_consumer_3

# 유저 컨슈머 로그
docker logs -f user_consumer_1

# 상품 컨슈머 로그
docker logs -f product_consumer_1
```

### 컨슈머 그룹 상태 확인

```bash
# 컨슈머 그룹 목록
docker exec kafka1 kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --list

# orders_group 상세 정보
docker exec kafka1 kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --describe \
  --group orders_group
```

출력 예시:
```
GROUP           TOPIC      PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG
orders_group    orders     0          1000            1000            0
orders_group    orders     1          1050            1050            0
orders_group    orders     2          980             980             0
```

### LAG 확인
- **LAG = 0**: 모든 메시지 처리 완료
- **LAG > 0**: 처리되지 않은 메시지 존재

### Kafka UI에서 확인
```
http://localhost:8080
```
- Consumer Groups 탭
- 각 그룹의 LAG, 오프셋 확인

## 트러블슈팅

### 컨슈머가 메시지를 받지 못할 때

1. **토픽이 생성되었는지 확인**
```bash
python kafka/admin/setup_topics.py
```

2. **컨슈머 그룹 리셋 (테스트 시)**
```bash
docker exec kafka1 kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --group orders_group \
  --reset-offsets \
  --to-earliest \
  --topic orders \
  --execute
```

3. **DB 연결 확인**
```bash
# PostgreSQL 연결 테스트
docker-compose ps postgres
```

4. **컨슈머 재시작**
```bash
docker-compose restart order-consumer-1 order-consumer-2 order-consumer-3
```

### 중복 데이터가 저장될 때

컨슈머 코드에 중복 체크 로직이 있습니다:
```python
existing_user = crud.get_user(db, data['user_id'])
if existing_user:
    return  # 이미 존재하면 스킵
```

### 무한 루프 방지

Producer가 DB에 저장 시 카프카에 다시 발행하는 것을 방지:
```python
# 컨슈머에서 저장 시 카프카 비활성화
crud_module.KAFKA_ENABLED = False
crud.create_user(db, data)
crud_module.KAFKA_ENABLED = True
```

### Consumer LAG이 계속 증가할 때

1. **Consumer 성능 확인**
```bash
docker stats order_consumer_1 order_consumer_2 order_consumer_3
```

2. **DB 병목 확인**
```bash
docker exec local_postgres psql -U postgres -d sesac_db -c "SELECT count(*) FROM orders;"
```

3. **Consumer 스케일 업** (docker-compose.yml에서 인스턴스 추가)

## 성능 최적화

### 배치 처리
```python
'max.poll.records': 500  # 한 번에 500개 처리
```

### 병렬 처리
- 3개 파티션 = 3개 컨슈머 병렬 처리
- 처리량 3배 증가

### 오프셋 커밋 전략
- 수동 커밋: 메시지 처리 성공 후에만 커밋
- At-least-once 보장

## 전체 실행 순서

### Docker 실행 (권장)
```bash
cd deploy
docker-compose up -d
```

### 로컬 실행

#### 1. 카프카 클러스터 시작
```bash
docker-compose up -d kafka1 kafka2 kafka3
```

#### 2. 토픽 생성
```bash
python kafka/admin/setup_topics.py
```

#### 3. 초기 데이터 생성
```bash
python apps/seeders/initial_seeder.py
```

#### 4. Cache Worker 시작
```bash
python cache/cache_worker.py
```

#### 5. 컨슈머 시작
```bash
python apps/runners/consumer_runner.py
```

#### 6. 실시간 데이터 생성 (별도 터미널)
```bash
python apps/seeders/realtime_generator.py
```

#### 7. 모니터링
- Kafka UI: http://localhost:8080
- Redis Monitor: `docker logs -f redis_monitor`
- 컨슈머 로그: 각 컨슈머 출력

## 참고 사항

### 오프셋 관리
- **earliest**: 처음부터 읽기 (신규 컨슈머 그룹)
- **latest**: 새 메시지만 읽기
- **수동 커밋**: 처리 성공 후에만 커밋

### 리밸런싱
- 컨슈머 추가/제거 시 자동 파티션 재할당
- 잠깐 처리 중단 발생 가능 (보통 수 초)

### At-least-once vs Exactly-once
- 현재 구현: **At-least-once** (중복 가능, 손실 없음)
- Exactly-once 필요 시: Kafka Transactions 사용

## 참고 자료

- **[KAFKA_PRODUCER_GUIDE.md](KAFKA_PRODUCER_GUIDE.md)** - Producer 가이드 (Redis 캐시 모드)
- **[KAFKA_SETUP_GUIDE.md](KAFKA_SETUP_GUIDE.md)** - Kafka 클러스터 설정
- **[DOCKER_DEPLOYMENT_GUIDE.md](DOCKER_DEPLOYMENT_GUIDE.md)** - Docker 배포
