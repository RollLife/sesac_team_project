# 벤치마크 시스템 구현 계획

Kafka vs 순차처리, Spark vs 기본 집계의 성능 차이를 Docker Compose 기반으로 측정하는 벤치마크 시스템을 구현합니다.

## 목표

1. **Kafka 벤치마크**: 순차처리(DB 직접 저장) vs Kafka 파이프라인 처리 속도 비교
2. **Spark 벤치마크**: PostgreSQL 기본 집계 vs Spark Streaming 집계 성능 비교
3. **동일 조건**: 두 벤치마크 모두 동일한 데이터 양, 동일한 환경에서 실행
4. **결과 파일**: JSON + HTML 리포트 자동 생성

---

## 핵심 설계

### 성능 차이를 보이게 하는 방법

현재 로컬 DB라 속도가 너무 빨라 차이가 안 보이므로:

| 요소 | 기존 | 벤치마크용 |
|------|------|-----------|
| 배치 크기 | 1~10개씩 | **5,000개씩** 대량 처리 |
| 처리 시뮬레이션 | 없음 | **10~50ms sleep** (네트워크 지연 시뮬레이션) |
| Consumer 수 | 3개 | **1개 vs 3개** 비교 |
| 측정 지표 | TPS만 | **TPS + 지연시간 + 처리율** |

---

## Proposed Changes

### 벤치마크 공통 인프라

---

#### [NEW] [benchmark_runner.py](file:///c:/Workspace/sesac_team_project/apps/benchmarks/benchmark_runner.py)

Docker 컨테이너에서 실행되는 벤치마크 메인 스크립트:
- 데이터 생성 → 처리 시작 → 시간 측정 → 결과 저장
- 환경변수로 벤치마크 모드 제어 (`BENCHMARK_MODE=kafka|spark`)
- 결과를 `/app/benchmark_results/` 에 JSON + HTML로 저장

---

### Kafka 벤치마크

---

#### [NEW] [docker-compose.benchmark-kafka.yml](file:///c:/Workspace/sesac_team_project/deploy/docker-compose.benchmark-kafka.yml)

Kafka 성능 비교를 위한 Docker Compose 파일:

**구성:**
- PostgreSQL (공통)
- Redis (공통)
- **Mode A (순차처리)**: Producer가 직접 DB에 저장
- **Mode B (Kafka)**: Producer → Kafka → Consumer → DB

**실행 흐름:**
```
1. 인프라 시작 (postgres, redis, kafka 클러스터)
2. DB/토픽 초기화
3. benchmark-sequential 실행 (5000건 직접 DB 저장, 시간 측정)
4. benchmark-kafka 실행 (5000건 Kafka 통해 저장, 시간 측정)
5. 결과 비교 리포트 생성
```

---

#### [NEW] [benchmark_sequential_producer.py](file:///c:/Workspace/sesac_team_project/apps/benchmarks/benchmark_sequential_producer.py)

순차처리 벤치마크 프로듀서:
- Kafka 없이 직접 DB에 저장
- 각 저장마다 20ms sleep (네트워크 지연 시뮬레이션)
- 처리 시간, TPS 측정

---

#### [NEW] [benchmark_kafka_producer.py](file:///c:/Workspace/sesac_team_project/apps/benchmarks/benchmark_kafka_producer.py)

Kafka 벤치마크 프로듀서:
- Kafka 토픽에 발행
- Producer ACK 시점까지 시간 측정
- 비동기 발행의 장점 측정

---

#### [NEW] [benchmark_kafka_consumer.py](file:///c:/Workspace/sesac_team_project/apps/benchmarks/benchmark_kafka_consumer.py)

Kafka 벤치마크 컨슈머:
- 5000건 모두 소비 완료까지 시간 측정
- 병렬 처리 (3개 인스턴스) 효과 측정

---

### Spark 벤치마크

---

#### [NEW] [docker-compose.benchmark-spark.yml](file:///c:/Workspace/sesac_team_project/deploy/docker-compose.benchmark-spark.yml)

Spark 성능 비교를 위한 Docker Compose 파일:

**구성:**
- PostgreSQL (공통)
- Kafka (데이터 소스)
- **Mode A (SQL 집계)**: PostgreSQL GROUP BY로 집계
- **Mode B (Spark)**: Spark Streaming으로 집계

**실행 흐름:**
```
1. 인프라 시작
2. 10,000건 주문 데이터 생성 (orders 테이블에 저장)
3. benchmark-sql 실행 (PostgreSQL로 카테고리별/결제수단별 집계, 시간 측정)
4. benchmark-spark 실행 (Spark로 동일 집계, 시간 측정)
5. 결과 비교 리포트 생성
```

---

#### [NEW] [benchmark_sql_aggregation.py](file:///c:/Workspace/sesac_team_project/apps/benchmarks/benchmark_sql_aggregation.py)

PostgreSQL 기본 집계 벤치마크:
- 카테고리별 매출 집계
- 결제수단별 통계
- 연령대별 분석
- 각 쿼리 실행 시간 측정

---

#### [NEW] [benchmark_spark_aggregation.py](file:///c:/Workspace/sesac_team_project/apps/benchmarks/benchmark_spark_aggregation.py)

Spark 집계 벤치마크:
- 동일한 집계를 Spark DataFrame API로 수행
- 처리 시간 측정
- 분산 처리의 이점 표시

---

#### [NEW] [benchmark_report_generator.py](file:///c:/Workspace/sesac_team_project/apps/benchmarks/benchmark_report_generator.py)

결과 리포트 생성기:
- JSON 결과 파일을 읽어 HTML 리포트 생성
- 그래프 (막대 차트) 포함
- 성능 개선율 자동 계산

---

## 결과 파일 구조

```
benchmark_results/
├── kafka_benchmark_20250209_004600.json
├── kafka_benchmark_20250209_004600.html
├── spark_benchmark_20250209_004700.json
└── spark_benchmark_20250209_004700.html
```

---

## Verification Plan

### 자동화된 검증

#### 1. Kafka 벤치마크 실행 테스트

```bash
cd deploy
docker-compose -f docker-compose.benchmark-kafka.yml up --build
```

**예상 결과:**
- 컨테이너가 정상 시작됨
- 벤치마크 완료 후 `benchmark_results/` 폴더에 결과 파일 생성
- 콘솔에 결과 요약 출력

#### 2. Spark 벤치마크 실행 테스트

```bash
cd deploy
docker-compose -f docker-compose.benchmark-spark.yml up --build
```

**예상 결과:**
- Spark 컨테이너 정상 시작
- 집계 완료 후 결과 파일 생성

### 수동 검증

벤치마크 실행 후 사용자가 확인해야 할 사항:

1. **결과 파일 확인**: `benchmark_results/` 폴더에 JSON, HTML 파일 존재
2. **HTML 리포트 확인**: 브라우저에서 열어 그래프 및 수치 확인
3. **성능 차이 확인**: 
   - Kafka: 순차처리 대비 처리량 증가 확인 (병렬 처리 효과)
   - Spark: 대용량 집계 시 SQL 대비 속도 향상 확인

---

## 실행 방법 (최종)

### Kafka 벤치마크

```bash
cd deploy
docker-compose -f docker-compose.benchmark-kafka.yml up --build
# 완료 후 결과 확인
cat ../benchmark_results/kafka_*.json
# 또는 HTML 파일을 브라우저로 열기
```

### Spark 벤치마크

```bash
cd deploy
docker-compose -f docker-compose.benchmark-spark.yml up --build
# 완료 후 결과 확인
cat ../benchmark_results/spark_*.json
```

### 정리

```bash
docker-compose -f docker-compose.benchmark-kafka.yml down -v
docker-compose -f docker-compose.benchmark-spark.yml down -v
```
