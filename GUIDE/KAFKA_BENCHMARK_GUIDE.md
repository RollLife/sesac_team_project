# 카프카 성능 비교 벤치마크 가이드

## 개요

이 도구는 **동일한 조건**에서 카프카 활성화/비활성화 시 데이터 처리 성능을 비교합니다.

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

## 주요 기능

- ✅ 카프카 ON/OFF 자동 전환
- ✅ 동일한 데이터 양으로 공정한 비교
- ✅ 상품(Product) 및 유저(User) 데이터 테스트
- ✅ TPS(초당 처리량) 자동 계산
- ✅ 성능 개선율 분석
- ✅ 결과를 CSV 파일로 저장
- ✅ 콘솔에 표 형태로 리포트 출력

## Redis 캐싱 성능 향상

벤치마크 도입 전, Redis 캐싱 기법 적용으로 다음과 같은 성능 향상을 달성했습니다:

| 지표 | Before (DB 직접) | After (Redis 캐시) | 개선율 |
|------|------------------|-------------------|--------|
| DB 쿼리/분 | ~60회 | ~1.2회 | 98% 감소 |
| 조회 속도 | 10-100ms | 0.1-1ms | 100배 향상 |

**Redis 캐싱 + 구매이력/미구매 분리 적재**를 통해 대용량 데이터 환경에서도 효율적인 데이터 조회가 가능합니다.

## 설치

### 1. 필수 패키지 설치

```bash
pip install tabulate
```

또는 전체 의존성 설치:

```bash
pip install -r requirements.txt
```

### 2. 전체 시스템 시작 (권장)

```bash
cd deploy
docker-compose build
docker-compose up -d
```

### 3. 카프카 서버 확인

```bash
# 브로커 상태 확인
docker-compose ps kafka1 kafka2 kafka3

# Redis 캐시 상태 확인
docker logs -f redis_monitor
```

## 사용 방법

### 기본 실행

```bash
python apps/benchmarks/kafka_comparison.py
```

### 실행 흐름

1. DB 정리 여부 선택 (y/n)
2. 다양한 데이터 양으로 자동 테스트 진행:
   - 100개 (카프카 OFF → ON)
   - 500개 (카프카 OFF → ON)
   - 1000개 (카프카 OFF → ON)
3. 상품(Product) 데이터 테스트
4. 유저(User) 데이터 테스트
5. 결과 리포트 출력 및 CSV 저장

## 테스트 시나리오 커스터마이징

스크립트 내부의 `test_counts` 변수를 수정하여 테스트 데이터 양을 변경할 수 있습니다:

```python
# apps/benchmarks/kafka_comparison.py의 main() 함수 내부
test_counts = [100, 500, 1000]  # 원하는 값으로 변경
```

예시:
```python
test_counts = [50, 200, 500, 1000, 2000]  # 더 다양한 시나리오
```

## 출력 결과

### 1. 콘솔 출력

#### 실시간 진행 상황
```
====================================================================
📦 상품 생성 테스트 | 개수: 100개 | 카프카: OFF
====================================================================
✅ 성공: 100개 | ❌ 실패: 0개
⏱️  소요시간: 2.3456초
🚀 TPS: 42.63 records/sec
```

#### 전체 결과 테이블
```
+--------+-------+--------+---------+--------------+---------+
| Entity | Count | Kafka  | Success | Duration(s)  | TPS     |
+========+=======+========+=========+==============+=========+
| Product|  100  | OFF    |   100   |   2.3456     |  42.63  |
| Product|  100  | ON     |   100   |   2.5123     |  39.81  |
| Product|  500  | OFF    |   500   |  11.2345     |  44.51  |
| Product|  500  | ON     |   500   |  12.1234     |  41.23  |
+--------+-------+--------+---------+--------------+---------+
```

#### 성능 개선율 분석
```
+--------+-------+--------------+-------------+-------------+---------+---------+------------------+
| Entity | Count | Duration OFF | Duration ON | Improvement | TPS OFF | TPS ON  | TPS Improvement  |
+========+=======+==============+=============+=============+=========+=========+==================+
| Product|  100  |   2.3456     |   2.5123    |   -7.11%    |  42.63  |  39.81  |     -6.62%       |
| Product|  500  |  11.2345     |  12.1234    |   -7.92%    |  44.51  |  41.23  |     -7.37%       |
+--------+-------+--------------+-------------+-------------+---------+---------+------------------+
```

### 2. CSV 파일 저장

`kafka_comparison_results.csv` 파일에 모든 결과가 저장됩니다:

```csv
timestamp,entity,count,kafka_status,success,failed,duration,tps
2026-02-03 14:30:00,Product,100,OFF,100,0,2.3456,42.63
2026-02-03 14:30:05,Product,100,ON,100,0,2.5123,39.81
...
```

## 결과 해석

### 성능 개선율

- **양수(+)**: 카프카 OFF일 때 더 빠름 (카프카 오버헤드 존재)
- **음수(-)**: 카프카 ON일 때 더 빠름 (카프카 최적화 효과)
- **0에 가까움**: 성능 차이 거의 없음

### 주의사항

1. **카프카 오버헤드**: 소량 데이터 처리 시 카프카의 직렬화/네트워크 오버헤드로 인해 약간 느려질 수 있습니다.
2. **카프카 장점**: 대량 데이터 처리 시 배치 처리, 압축, 비동기 처리의 이점이 나타날 수 있습니다.
3. **실제 이점**: 카프카의 진정한 가치는 속도보다 **데이터 스트리밍**, **이벤트 소싱**, **마이크로서비스 간 통신** 등에 있습니다.

### Redis 캐싱 효과

벤치마크 결과와 별개로, Redis 캐싱 도입으로 다음과 같은 이점이 있습니다:
- **DB 부하 98% 감소**: 50초마다 1회만 DB 쿼리
- **조회 속도 100배 향상**: Redis 캐시에서 구매 성향 기반 조회
- **스케일링 용이**: 데이터 양이 증가해도 일정한 조회 성능

## 트러블슈팅

### 카프카 연결 실패

카프카 ON 테스트에서 연결 오류 발생 시:

1. 카프카 서버가 실행 중인지 확인
```bash
docker-compose ps kafka1 kafka2 kafka3
```

2. `.env` 파일의 `KAFKA_BOOTSTRAP_SERVERS` 확인

3. 네트워크 연결 확인
```bash
python kafka/test_connection.py
```

### DB 연결 실패

```bash
# PostgreSQL이 실행 중인지 확인
docker-compose ps postgres

# 연결 테스트
docker exec local_postgres psql -U postgres -d sesac_db -c "SELECT 1;"
```

### Redis 캐시 문제

```bash
# Redis 상태 확인
docker exec local_redis redis-cli ping

# 캐시 데이터 확인
docker exec local_redis redis-cli hlen cache:users
docker exec local_redis redis-cli hlen cache:products

# Cache Worker 로그 확인
docker logs cache_worker
```

### 메모리 부족

대량 데이터 테스트 시 메모리 부족 발생 가능:

```python
# test_counts를 줄여서 테스트
test_counts = [100, 200]  # 작은 값으로 시작
```

## 코드 구조

```
apps/benchmarks/kafka_comparison.py
├── KafkaBenchmark 클래스
│   ├── set_kafka_enabled()      # 카프카 ON/OFF 전환
│   ├── benchmark_products()     # 상품 생성 벤치마크
│   ├── benchmark_users()        # 유저 생성 벤치마크
│   ├── run_comparison()         # 비교 테스트 실행
│   ├── generate_comparison_report()  # 리포트 생성
│   └── save_results_to_csv()    # CSV 저장
└── main()                        # 메인 실행 함수
```

## 커스터마이징

### 다른 Entity 추가

Order 데이터 등 다른 엔티티를 테스트하려면:

```python
def benchmark_orders(self, count: int, kafka_enabled: bool) -> Dict:
    # benchmark_products()를 참고하여 구현
    pass
```

### 결과 포맷 변경

리포트 생성 부분을 수정하여 원하는 형태로 출력 가능:

```python
# generate_comparison_report() 함수 내부
print(tabulate(table_data, headers=headers, tablefmt='fancy_grid'))  # 다른 스타일
```

## 예상 결과 분석

일반적으로 다음과 같은 패턴이 관찰됩니다:

1. **소량 데이터 (100~500개)**
   - 카프카 OFF가 약간 더 빠름 (~5-10%)
   - 카프카 초기화 및 직렬화 오버헤드

2. **대량 데이터 (1000개 이상)**
   - 성능 차이가 줄어듦
   - 카프카 배치 처리 효과 발생

3. **실제 운영 환경**
   - 카프카는 처리 속도보다 **확장성**, **안정성**, **이벤트 추적**에서 가치 제공

4. **Redis 캐싱 도입 후**
   - DB 조회 병목 해소
   - 대용량 데이터에서도 일정한 조회 성능
   - Producer가 Redis에서 빠르게 랜덤 데이터 조회

## 벤치마크 실행 전 체크리스트

- [ ] Docker Compose로 전체 서비스 실행
- [ ] `docker-compose ps`로 모든 컨테이너 상태 확인
- [ ] Redis Monitor 로그 확인 (`docker logs -f redis_monitor`)
- [ ] 캐시 데이터 확인 (`docker exec local_redis redis-cli hlen cache:users`)
- [ ] 초기 데이터 생성 완료 확인
- [ ] 벤치마크 실행: `python apps/benchmarks/kafka_comparison.py`

## 참고 자료

- **[KAFKA_PRODUCER_GUIDE.md](KAFKA_PRODUCER_GUIDE.md)** - Producer 가이드 (Redis 캐시 모드)
- **[KAFKA_CONSUMER_GUIDE.md](KAFKA_CONSUMER_GUIDE.md)** - Consumer 가이드
- **[KAFKA_SETUP_GUIDE.md](KAFKA_SETUP_GUIDE.md)** - Kafka 클러스터 설정
- **[DOCKER_DEPLOYMENT_GUIDE.md](DOCKER_DEPLOYMENT_GUIDE.md)** - Docker 배포
