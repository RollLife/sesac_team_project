# 🚀 벤치마크 시스템 사용 가이드

이 문서는 Kafka와 Spark의 성능을 테스트하는 벤치마크 시스템 사용법을 설명합니다.

## 📁 파일 구조

```
apps/benchmarks/
├── benchmark_common.py              # 공통 모듈 (타이머, 결과 저장, HTML 리포트)
├── benchmark_sequential_producer.py # 순차처리 벤치마크 (Kafka 미사용)
├── benchmark_kafka_producer.py      # Kafka Producer 벤치마크
├── benchmark_kafka_consumer.py      # Kafka Consumer 벤치마크
├── benchmark_kafka_compare.py       # Kafka 결과 비교 리포트
├── benchmark_sql_aggregation.py     # PostgreSQL 집계 벤치마크
├── benchmark_spark_aggregation.py   # Spark 집계 벤치마크
└── benchmark_spark_compare.py       # Spark 결과 비교 리포트

deploy/
├── docker-compose.benchmark-kafka.yml  # Kafka 벤치마크용
└── docker-compose.benchmark-spark.yml  # Spark 벤치마크용

benchmark_results/                   # 결과 파일 저장 폴더
├── kafka_benchmark_*.json           # Kafka 벤치마크 결과
├── kafka_comparison_report_*.html   # Kafka 비교 리포트
├── spark_benchmark_*.json           # Spark 벤치마크 결과
└── spark_comparison_report_*.html   # Spark 비교 리포트
```

---

## 🔧 Kafka 벤치마크 실행

### 테스트 내용
- **순차처리**: Kafka 없이 DB에 직접 저장 (20ms 네트워크 지연 시뮬레이션)
- **Kafka**: Producer → Kafka → Consumer (3개) → DB

### 실행 방법

```bash
# deploy 폴더로 이동
cd deploy

# 벤치마크 실행 (빌드 + 실행)
docker-compose -f docker-compose.benchmark-kafka.yml up --build

# 완료 후 정리
docker-compose -f docker-compose.benchmark-kafka.yml down -v
```

### 설정 변경

환경변수로 벤치마크 설정을 변경할 수 있습니다:

| 환경변수 | 기본값 | 설명 |
|----------|--------|------|
| `BENCHMARK_RECORDS` | 5000 | 생성할 주문 레코드 수 |
| `NETWORK_DELAY_MS` | 20 | 순차처리 시 네트워크 지연 (ms) |
| `SIMULATE_NETWORK_DELAY` | true | 지연 시뮬레이션 활성화 |

---

## ⚡ Spark 벤치마크 실행

### 테스트 내용
- **PostgreSQL**: GROUP BY 쿼리로 집계 (6가지 분석 쿼리)
- **Spark**: DataFrame API로 동일 집계

### 실행 방법

```bash
# deploy 폴더로 이동
cd deploy

# 벤치마크 실행 (빌드 + 실행)
docker-compose -f docker-compose.benchmark-spark.yml up --build

# 완료 후 정리
docker-compose -f docker-compose.benchmark-spark.yml down -v
```

### 설정 변경

| 환경변수 | 기본값 | 설명 |
|----------|--------|------|
| `BENCHMARK_ITERATIONS` | 10 | 집계 쿼리 반복 횟수 |

---

## 📊 결과 확인

### JSON 결과 파일

```bash
# Kafka 벤치마크 결과
cat benchmark_results/kafka_benchmark_*.json

# Spark 벤치마크 결과
cat benchmark_results/spark_benchmark_*.json
```

### HTML 리포트

`benchmark_results/` 폴더의 `.html` 파일을 브라우저에서 열어 시각화된 결과를 확인하세요:

- `kafka_comparison_report_*.html` - Kafka 성능 비교
- `spark_comparison_report_*.html` - Spark 성능 비교

---

## 📈 예상 결과

### Kafka 벤치마크
- **순차처리**: 네트워크 지연으로 인해 낮은 TPS
- **Kafka**: 비동기 발행 + 병렬 Consumer로 높은 TPS
- **예상 개선율**: 2~5배 TPS 향상

### Spark 벤치마크
- **소규모 데이터**: PostgreSQL이 Spark 오버헤드로 인해 더 빠를 수 있음
- **대규모 데이터**: Spark의 분산 처리가 유리
- **50,000건 기준**: 비슷하거나 Spark가 약간 빠름

---

## 💡 발표용 해석

### Kafka를 쓰는 이유
1. **비동기 처리**: Producer가 ACK를 기다리지 않고 빠르게 다음 작업
2. **병렬 Consumer**: 메시지를 여러 인스턴스가 동시에 처리
3. **장애 복구**: 메시지가 디스크에 저장되어 장애 시 재처리 가능
4. **확장성**: Consumer만 추가하면 처리량 증가

### Spark를 쓰는 이유
1. **분산 처리**: 대용량 데이터를 여러 노드에서 병렬 처리
2. **인메모리 연산**: 디스크 I/O 최소화로 빠른 처리
3. **실시간 스트리밍**: Kafka와 연동하여 실시간 분석
4. **풍부한 API**: DataFrame, SQL, ML 등 다양한 분석 도구
