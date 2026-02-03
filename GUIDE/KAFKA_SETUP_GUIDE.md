# 카프카 클러스터 설정 가이드

## 클러스터 구성

### 브로커 구성
- **총 3개 브로커**
  - kafka1 (리더): localhost:9092
  - kafka2 (레플리카): localhost:9093
  - kafka3 (레플리카): localhost:9094

### 토픽 구성
각 토픽은 다음과 같이 설정됩니다:
- **파티션**: 3개 (각 브로커에 분산)
- **복제 팩터**: 3 (모든 브로커에 복제)
- **최소 ISR**: 2 (최소 2개 브로커에 동기화 필요)

## 설치 및 실행

### 1. 카프카 클러스터 시작

```bash
# Docker Compose로 전체 서비스 시작
docker-compose up -d

# 카프카 브로커만 시작
docker-compose up -d kafka1 kafka2 kafka3

# 로그 확인
docker-compose logs -f kafka1 kafka2 kafka3
```

### 2. 브로커 상태 확인

```bash
# 모든 컨테이너 상태 확인
docker-compose ps

# 특정 브로커 로그 확인
docker-compose logs kafka1
docker-compose logs kafka2
docker-compose logs kafka3
```

### 3. 토픽 초기화

```bash
# 토픽 생성 (파티션 3개, 복제 팩터 3)
python kafka/admin/setup_topics.py

# 토픽 삭제 후 재생성 (필요 시)
python kafka/admin/setup_topics.py --delete
python kafka/admin/setup_topics.py
```

### 4. Kafka UI에서 확인

브라우저에서 접속:
```
http://localhost:8080
```

확인 사항:
- 3개 브로커가 모두 연결되어 있는지
- users, products, orders 토픽이 생성되었는지
- 각 토픽이 3개 파티션을 가지고 있는지

## 토픽 상세 설정

### users 토픽
```
토픽명: users
파티션: 3개
복제 팩터: 3
보관 기간: 7일
압축: gzip
최소 ISR: 2
```

### products 토픽
```
토픽명: products
파티션: 3개
복제 팩터: 3
보관 기간: 7일
압축: gzip
최소 ISR: 2
```

### orders 토픽
```
토픽명: orders
파티션: 3개
복제 팩터: 3
보관 기간: 30일 (주문은 더 오래 보관)
압축: gzip
최소 ISR: 2
```

## 파티션 분산 전략

### 파티션 키
- **users 토픽**: user_id를 키로 사용
- **products 토픽**: product_id를 키로 사용
- **orders 토픽**: user_id를 키로 사용

### 분산 방식
카프카는 파티션 키의 해시값을 기반으로 파티션을 선택:
```
partition = hash(key) % num_partitions
```

예시:
- user_id="user_001" → 파티션 0
- user_id="user_002" → 파티션 1
- user_id="user_003" → 파티션 2

## 복제 및 가용성

### 복제 팩터 3의 의미
- 각 파티션의 데이터가 3개 브로커에 모두 복제됨
- 리더 1개 + 팔로워 2개
- 최대 2개 브로커 장애 발생 시에도 데이터 유지

### ISR (In-Sync Replicas)
- 최소 ISR = 2: 리더 포함 최소 2개 브로커에 동기화되어야 쓰기 성공
- 데이터 안정성 보장

### 장애 복구
1개 브로커 다운 시:
- 자동으로 다른 브로커가 리더로 승격
- 서비스 중단 없이 계속 동작

## 성능 튜닝

### Producer 설정 (kafka/config.py)

```python
KAFKA_CONFIG = {
    'bootstrap.servers': 'localhost:9092,localhost:9093,localhost:9094',

    # 신뢰성 설정
    'acks': 'all',  # 모든 복제본 확인
    'enable.idempotence': True,  # 멱등성 보장

    # 성능 최적화
    'linger.ms': 10,  # 배치 대기 시간
    'compression.type': 'gzip',  # 압축
    'batch.size': 16384,  # 배치 크기
    'max.in.flight.requests.per.connection': 5,
}
```

### 파라미터 설명

| 파라미터 | 값 | 설명 |
|---------|-----|------|
| acks | all | 모든 ISR에 쓰기 완료 후 응답 (안정성 최대) |
| enable.idempotence | true | 중복 메시지 방지 |
| linger.ms | 10 | 10ms 동안 메시지를 모아서 배치 전송 |
| compression.type | gzip | gzip 압축으로 네트워크 효율 향상 |
| batch.size | 16KB | 한 번에 전송할 배치 크기 |
| max.in.flight | 5 | 동시에 전송 가능한 요청 수 |

## 모니터링

### Kafka UI 대시보드
- URL: http://localhost:8080
- 브로커 상태, 토픽 상세 정보, 메시지 확인 가능

### CLI 명령어

```bash
# 토픽 목록 확인
docker exec kafka1 kafka-topics --bootstrap-server localhost:9092 --list

# 토픽 상세 정보
docker exec kafka1 kafka-topics --bootstrap-server localhost:9092 --describe --topic users

# 컨슈머 그룹 확인
docker exec kafka1 kafka-consumer-groups --bootstrap-server localhost:9092 --list

# 메시지 수 확인 (간접적)
docker exec kafka1 kafka-run-class kafka.tools.GetOffsetShell \
  --broker-list localhost:9092 \
  --topic users
```

## 트러블슈팅

### 브로커가 시작되지 않을 때

```bash
# 로그 확인
docker-compose logs kafka1

# 볼륨 초기화 후 재시작
docker-compose down -v
docker-compose up -d
```

### 토픽 생성 실패 시

```bash
# 브로커 연결 확인
python kafka/test_connection.py

# 토픽 수동 생성
docker exec kafka1 kafka-topics \
  --bootstrap-server localhost:9092 \
  --create \
  --topic users \
  --partitions 3 \
  --replication-factor 3 \
  --config min.insync.replicas=2
```

### 메시지 발행 실패 시

확인 사항:
1. 모든 브로커가 정상 실행 중인지
2. ISR이 최소 2개인지 (1개면 쓰기 실패)
3. KAFKA_ENABLED=true로 설정되어 있는지

## 벤치마크 테스트 전 체크리스트

- [ ] Docker Compose로 3개 브로커 모두 실행
- [ ] `python kafka/admin/setup_topics.py`로 토픽 생성
- [ ] Kafka UI에서 3개 토픽 확인
- [ ] 각 토픽이 파티션 3개, 복제 팩터 3인지 확인
- [ ] `python kafka/test_connection.py`로 연결 테스트
- [ ] 초기 데이터 생성: `python apps/seeders/initial_seeder.py`
- [ ] 벤치마크 실행: `python apps/benchmarks/realtime_comparison.py`

## 참고 자료

### KRaft 모드
- Zookeeper 없이 동작하는 새로운 카프카 아키텍처
- 메타데이터를 카프카 자체 로그로 관리
- 더 간단한 운영, 더 빠른 시작

### 포트 정보
- 9092: kafka1 외부 접속 포트
- 9093: kafka2 외부 접속 포트
- 9094: kafka3 외부 접속 포트
- 29092, 29093, 29094: 내부 통신 포트
- 8080: Kafka UI
- 5432: PostgreSQL
