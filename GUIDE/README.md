# 📚 가이드 문서 모음

Kafka 데이터 파이프라인 프로젝트의 모든 가이드 문서입니다.

## 🚀 빠른 시작

### 1. Docker 환경 구축
**[DOCKER_DEPLOYMENT_GUIDE.md](DOCKER_DEPLOYMENT_GUIDE.md)**
- 전체 시스템을 Docker로 실행
- 총 17개 컨테이너 구성
- 한 명령어로 시작

```bash
# Makefile 사용 (권장)
make build
make up

# 또는 래퍼 스크립트
./dc.sh build && ./dc.sh up -d

# 또는 직접 사용
docker-compose -f deploy/docker-compose.yml build
docker-compose -f deploy/docker-compose.yml up -d
```

### 2. Kafka 클러스터 설정
**[KAFKA_SETUP_GUIDE.md](KAFKA_SETUP_GUIDE.md)**
- 3개 브로커 클러스터
- 토픽 생성 (파티션 3개, 복제 팩터 3)
- 모니터링 설정

```bash
docker-compose exec producer python kafka/admin/setup_topics.py
```

### 3. 데이터 생성 (Producer)
**[KAFKA_PRODUCER_GUIDE.md](KAFKA_PRODUCER_GUIDE.md)**
- 초기 데이터: 10,000 유저 + 20,000 상품
- 실시간 데이터: 주문 + 상품 (무한 루프)
- Kafka 발행 제어

```bash
# 초기 데이터
docker-compose run --rm producer python apps/seeders/initial_seeder.py

# 실시간 데이터
docker-compose up -d producer
```

### 4. 데이터 소비 (Consumer)
**[KAFKA_CONSUMER_GUIDE.md](KAFKA_CONSUMER_GUIDE.md)**
- 3개 컨슈머 그룹 (총 9개 인스턴스)
- JSON 역직렬화
- PostgreSQL 저장

```bash
docker-compose up -d \
  user-consumer-1 user-consumer-2 user-consumer-3 \
  product-consumer-1 product-consumer-2 product-consumer-3 \
  order-consumer-1 order-consumer-2 order-consumer-3
```

## 📊 성능 측정

### 벤치마크 비교
**[KAFKA_BENCHMARK_GUIDE.md](KAFKA_BENCHMARK_GUIDE.md)**
- Kafka ON/OFF 성능 비교
- 배치 처리 벤치마크
- TPS 측정 및 분석

```bash
python apps/benchmarks/kafka_comparison.py
```

## 🛠️ 개발 및 테스트

### Python 개발 컨테이너
**[PYTHON_DEV_GUIDE.md](PYTHON_DEV_GUIDE.md)**
- 환경 테스트 자동화
- Python REPL (대화형 쉘)
- 스크립트 실행 및 디버깅
- 코드 변경 실시간 반영

```bash
# 컨테이너 실행
docker-compose --profile dev up -d python-dev

# 환경 테스트
docker-compose exec python-dev python tests/test_environment.py

# 쉘 접속
docker-compose exec python-dev bash
```

## 📖 가이드 목록

### 인프라 및 설정
| 가이드 | 설명 | 주요 내용 |
|-------|------|----------|
| [DOCKER_DEPLOYMENT_GUIDE.md](DOCKER_DEPLOYMENT_GUIDE.md) | Docker 배포 가이드 | 컨테이너 구성, 실행, 모니터링 |
| [KAFKA_SETUP_GUIDE.md](KAFKA_SETUP_GUIDE.md) | Kafka 클러스터 설정 | 브로커, 토픽, 파티션, 복제 |

### 애플리케이션
| 가이드 | 설명 | 주요 내용 |
|-------|------|----------|
| [KAFKA_PRODUCER_GUIDE.md](KAFKA_PRODUCER_GUIDE.md) | Producer 사용법 | 데이터 생성, Kafka 발행 |
| [KAFKA_CONSUMER_GUIDE.md](KAFKA_CONSUMER_GUIDE.md) | Consumer 구성 | 컨슈머 그룹, 역직렬화, 저장 |

### 성능 및 테스트
| 가이드 | 설명 | 주요 내용 |
|-------|------|----------|
| [KAFKA_BENCHMARK_GUIDE.md](KAFKA_BENCHMARK_GUIDE.md) | 성능 벤치마크 | Kafka ON/OFF 비교, TPS |
| [PYTHON_DEV_GUIDE.md](PYTHON_DEV_GUIDE.md) | 개발 환경 | 환경 테스트, REPL, 디버깅 |

## 🗺️ 학습 경로

### 초보자
```
1. DOCKER_DEPLOYMENT_GUIDE.md (환경 구축)
   ↓
2. KAFKA_SETUP_GUIDE.md (Kafka 기본)
   ↓
3. KAFKA_PRODUCER_GUIDE.md (데이터 생성)
   ↓
4. KAFKA_CONSUMER_GUIDE.md (데이터 소비)
```

### 개발자
```
1. PYTHON_DEV_GUIDE.md (개발 환경 설정)
   ↓
2. KAFKA_PRODUCER_GUIDE.md (Producer 커스터마이징)
   ↓
3. KAFKA_CONSUMER_GUIDE.md (Consumer 커스터마이징)
   ↓
4. KAFKA_BENCHMARK_GUIDE.md (성능 최적화)
```

### 운영자
```
1. DOCKER_DEPLOYMENT_GUIDE.md (배포)
   ↓
2. KAFKA_SETUP_GUIDE.md (클러스터 관리)
   ↓
3. KAFKA_BENCHMARK_GUIDE.md (성능 모니터링)
```

## 🔗 외부 링크

### Kafka UI
```
http://localhost:8080
```
- 브로커 상태 확인
- 토픽 및 메시지 모니터링
- 컨슈머 그룹 관리

### PostgreSQL
```
Host: localhost:5432
User: postgres
Password: password
Database: sesac_db
```

## 📝 추가 자료

### 공식 문서
- [Kafka Documentation](https://kafka.apache.org/documentation/)
- [Confluent Kafka Python](https://docs.confluent.io/kafka-clients/python/current/overview.html)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)

### 관련 파일
- `tests/test_environment.py` - 환경 테스트 스크립트
- `apps/seeders/initial_seeder.py` - 초기 데이터 생성
- `apps/seeders/realtime_generator.py` - 실시간 데이터 생성
- `apps/runners/consumer_runner.py` - 컨슈머 실행
- `docker-compose.yml` - 전체 서비스 정의

## 💡 팁

### 빠른 시작 (All-in-One)
```bash
# 1. 전체 빌드 및 시작
docker-compose build && docker-compose up -d

# 2. 토픽 생성
docker-compose exec producer python kafka/admin/setup_topics.py

# 3. 초기 데이터
docker-compose run --rm producer python apps/seeders/initial_seeder.py

# 4. 환경 테스트
docker-compose --profile dev up -d python-dev
docker-compose exec python-dev python tests/test_environment.py

# 5. 모니터링
open http://localhost:8080
```

### 문제 해결
```bash
# 로그 확인
docker-compose logs -f

# 특정 서비스 재시작
docker-compose restart producer

# 전체 재시작
docker-compose down && docker-compose up -d
```

## 📞 지원

문제가 발생하거나 질문이 있으시면:
1. 해당 가이드의 "트러블슈팅" 섹션 참고
2. `PYTHON_DEV_GUIDE.md`로 환경 테스트
3. 로그 확인 및 분석

---

**모든 가이드를 통해 완벽한 Kafka 데이터 파이프라인을 구축하세요!** 🚀
