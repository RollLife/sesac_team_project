# 🚀 Spark Streaming 실행 가이드

## 자동 실행 (권장)

`docker-compose up` 명령어를 실행하면 **Spark Streaming Job이 자동으로 시작**됩니다!

```bash
cd deploy
docker-compose up -d
```

### 구조 설명:

```
┌─────────────────┐     ┌─────────────────────┐
│  spark-master   │     │   spark-streaming   │
│  (Web UI 제공)  │     │   (Local 모드 실행)  │
│  Port: 8082     │     │   실제 Job 실행      │
└─────────────────┘     └─────────────────────┘
```

- **spark-master**: Spark Web UI 및 모니터링용 (선택적)
- **spark-streaming**: Local 모드로 Spark Streaming Job 실행 (핵심)

### 로그 확인:

```bash
# Spark Streaming 로그 확인
docker logs -f spark_streaming

# Spark Master Web UI (선택적)
# 브라우저에서 http://localhost:8082 접속
```

---

## 수동 실행 (테스트/디버깅용)

필요한 경우 수동으로도 실행할 수 있습니다:

```bash
docker exec -it spark_streaming /opt/spark/bin/spark-submit \
  --master local[*] \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,org.postgresql:postgresql:42.6.0 \
  /app/apps/spark/streaming_analysis.py
```

---

## Jupyter Notebook 테스트

Jupyter 환경에서 Spark 코드를 테스트하려면:

```bash
docker-compose up -d jupyter
```

- 브라우저로 `localhost:8888` 접속
- 토큰 확인: `docker-compose logs jupyter`
- `work/apps/spark/spark_streaming_test.ipynb` 파일에서 테스트

---

## 생성되는 테이블

Spark Streaming이 정상 작동하면 PostgreSQL에 다음 테이블이 자동 생성됩니다:

| 테이블명 | 설명 |
|---------|------|
| `realtime_category_stats` | 카테고리별 매출 통계 |
| `realtime_payment_stats` | 결제 수단별 점유율 |
| `realtime_age_payment_stats` | 연령대 x 결제수단 분석 |
| `realtime_user_stats` | 유저별 누적 통계 |

---

## 문제 해결

### CRLF 오류 발생 시 (`$'\r': command not found`):

Windows에서 만든 Python 파일의 줄바꿈 문제입니다:

```bash
# Linux/Mac에서 수정
sed -i 's/\r$//' apps/spark/streaming_analysis.py

# 또는 전체 파일 수정
find apps/spark -name "*.py" -exec sed -i 's/\r$//' {} \;
```

### Spark Job이 시작되지 않는 경우:

```bash
# 컨테이너 상태 확인
docker ps -a | grep spark

# 로그 확인
docker logs spark_streaming

# 재시작
docker-compose restart spark-streaming
```

### 로그에서 Kafka 연결 오류가 나는 경우:

```bash
# Kafka 상태 확인
docker-compose logs kafka1 | tail -20

# Kafka 토픽 확인
docker exec kafka1 kafka-topics --bootstrap-server localhost:9092 --list
```