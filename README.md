# Kafka 데이터 파이프라인 프로젝트

새싹 팀 프로젝트 - 실시간 데이터 생성 및 Kafka 스트리밍 파이프라인

## 👥 팀 정보

- **팀원**: 안병호, 안서윤, 황이삭
- **기간**: 2024.01.30 ~ 2024.02.09

### 프로젝트 일정
- **Kick-off**: 1월 30일(금) - 팀별 주제 선정, 리서치 및 기획안 발표
- **MVP 개발**: 2월 2일(월) ~ 2월 4일(수) - 데이터 파이프라인 완성
- **중간 점검**: 2월 4일(수) 오후
- **고도화 및 마무리**: 2월 5일(목) ~ 2월 6일(금) - Kafka 분산 처리 적용
- **최종 발표**: 2월 9일(월)

## 🎯 프로젝트 개요

PostgreSQL + Kafka 클러스터를 활용한 실시간 데이터 파이프라인:
- **Producer**: 실시간 유저/상품/주문 데이터 생성
- **Kafka**: 3개 브로커 클러스터 (파티션 3개, 복제 팩터 3)
- **Consumer**: 9개 인스턴스 (3개 그룹)
- **Docker**: 모든 서비스 컨테이너화 (총 17개)

## 🚀 빠른 시작

### 방법 1: Makefile 사용 (권장)

```bash
# 한 번에 모두 실행 (빌드 + 시작 + 토픽 + 초기 데이터)
make start-all

# 또는 단계별 실행
make build          # 이미지 빌드
make up             # 서비스 시작
make topics         # 토픽 생성
make seed           # 초기 데이터 생성 (10,000 유저 + 20,000 상품)

# Kafka UI 확인
open http://localhost:8080
```

### 방법 2: 래퍼 스크립트 사용

```bash
# Unix/Mac/Git Bash
./dc.sh build
./dc.sh up -d
./dc.sh exec producer python kafka/admin/setup_topics.py
./dc.sh run --rm producer python apps/seeders/initial_seeder.py

# Windows (CMD/PowerShell)
dc.bat build
dc.bat up -d
dc.bat exec producer python kafka/admin/setup_topics.py
dc.bat run --rm producer python apps/seeders/initial_seeder.py
```

### 방법 3: Docker Compose 직접 사용

```bash
docker-compose -f deploy/docker-compose.yml build
docker-compose -f deploy/docker-compose.yml up -d
docker-compose -f deploy/docker-compose.yml exec producer python kafka/admin/setup_topics.py
docker-compose -f deploy/docker-compose.yml run --rm producer python apps/seeders/initial_seeder.py
```

## 📚 가이드 문서

모든 가이드는 **[GUIDE](GUIDE/)** 폴더에 있습니다.

### 주요 가이드
- **[GUIDE/README.md](GUIDE/README.md)** - 📖 가이드 문서 인덱스
- **[GUIDE/DOCKER_DEPLOYMENT_GUIDE.md](GUIDE/DOCKER_DEPLOYMENT_GUIDE.md)** - 🐳 Docker 배포
- **[GUIDE/KAFKA_SETUP_GUIDE.md](GUIDE/KAFKA_SETUP_GUIDE.md)** - ⚙️ Kafka 설정
- **[GUIDE/KAFKA_PRODUCER_GUIDE.md](GUIDE/KAFKA_PRODUCER_GUIDE.md)** - 📤 Producer 사용법
- **[GUIDE/KAFKA_CONSUMER_GUIDE.md](GUIDE/KAFKA_CONSUMER_GUIDE.md)** - 📥 Consumer 구성
- **[GUIDE/KAFKA_BENCHMARK_GUIDE.md](GUIDE/KAFKA_BENCHMARK_GUIDE.md)** - 📊 성능 벤치마크
- **[GUIDE/PYTHON_DEV_GUIDE.md](GUIDE/PYTHON_DEV_GUIDE.md)** - 🐍 개발 환경

## 📂 프로젝트 구조

```
.
├── apps/                       # 🚀 애플리케이션
│   ├── benchmarks/            # 성능 벤치마크
│   │   ├── kafka_comparison.py
│   │   └── realtime_comparison.py
│   ├── seeders/               # 데이터 생성
│   │   ├── initial_seeder.py
│   │   └── realtime_generator.py
│   └── runners/               # 실행기
│       └── consumer_runner.py
│
├── kafka/                      # ⚡ Kafka 모듈
│   ├── config.py              # Kafka 설정
│   ├── exceptions.py          # 예외 정의
│   ├── consumer.py            # Consumer 베이스 클래스
│   ├── admin/                 # 관리 도구
│   │   └── setup_topics.py   # 토픽 생성
│   ├── producer/              # Producer 관련
│   │   ├── producer.py       # Producer 클래스
│   │   └── serializers.py    # 직렬화
│   ├── consumers/             # Consumer 구현
│   │   ├── user_consumer.py
│   │   ├── product_consumer.py
│   │   └── order_consumer.py
│   └── utils/                 # 유틸리티
│       └── test_connection.py
│
├── database/                   # 💾 데이터베이스
│   ├── database.py            # DB 연결
│   ├── models.py              # ORM 모델
│   └── crud.py                # CRUD 연산
│
├── collect/                    # 📊 데이터 생성기
│   ├── user_generator.py      # 유저 생성
│   ├── product_generator.py   # 상품 생성
│   └── order_generator.py     # 주문 생성
│
├── tests/                      # 🧪 테스트
│   └── test_environment.py    # 환경 테스트
│
├── deploy/                     # 🐳 배포 관련
│   ├── docker-compose.yml     # Docker 서비스 정의
│   ├── Dockerfile             # Python 앱 이미지
│   ├── requirements.txt       # Python 의존성
│   └── README.md              # 배포 가이드
│
├── GUIDE/                      # 📚 가이드 문서
│   ├── README.md              # 가이드 인덱스
│   ├── DB_README.md           # 데이터베이스 가이드
│   ├── DOCKER_DEPLOYMENT_GUIDE.md
│   ├── KAFKA_SETUP_GUIDE.md
│   ├── KAFKA_PRODUCER_GUIDE.md
│   ├── KAFKA_CONSUMER_GUIDE.md
│   ├── KAFKA_BENCHMARK_GUIDE.md
│   └── PYTHON_DEV_GUIDE.md
│
├── Makefile                    # Make 명령어 정의
├── dc.sh                       # Docker Compose 래퍼 (Unix)
├── dc.bat                      # Docker Compose 래퍼 (Windows)
├── manage.py                   # 관리 스크립트
├── pyproject.toml             # Python 프로젝트 설정
└── README.md                   # 프로젝트 README
```

## 🏗️ 아키텍처

```
┌─────────────┐
│  Producer   │ (apps/seeders/realtime_generator.py)
│ 데이터 생성  │
└──────┬──────┘
       │
       ▼
┌──────────────────────────────────┐
│   Kafka Cluster (3 Brokers)     │
│  ┌────────┬──────────┬────────┐ │
│  │ users  │ products │ orders │ │
│  │ 3파티션 │ 3파티션   │ 3파티션 │ │
│  └────────┴──────────┴────────┘ │
└───────┬──────────────────────────┘
        │
        ├─────────┬─────────┬─────────┐
        │         │         │         │
   ┌────▼───┐┌───▼───┐┌───▼───┐  ... (총 9개)
   │user_c1 ││prod_c1││order_c1│
   └────┬───┘└───┬───┘└───┬───┘
        │        │        │
        └────────┴────────┴────────┐
                                   ▼
                          ┌──────────────┐
                          │ PostgreSQL   │
                          └──────────────┘
```

## 🛠️ 주요 기능

### ✅ 데이터 생성
- Faker를 활용한 실시간 데이터 생성
- 유저, 상품, 주문 데이터 자동 생성
- 커스터마이징 가능한 생성 규칙

### ✅ Kafka 스트리밍
- 3개 브로커 클러스터 (고가용성)
- 3개 파티션 (병렬 처리)
- 복제 팩터 3 (데이터 안정성)
- LZ4 압축 (성능 최적화)

### ✅ Consumer 클러스터
- 3개 컨슈머 그룹
- 각 그룹당 3개 인스턴스 (총 9개)
- 자동 파티션 할당
- 중복 방지 로직

### ✅ 성능 벤치마크
- Kafka ON/OFF 성능 비교
- TPS (초당 처리량) 측정
- CSV 리포트 생성

### ✅ Docker 통합
- 모든 서비스 컨테이너화
- docker-compose로 간편 관리
- 개발용 python-dev 컨테이너

## 🔧 기술 스택

### 백엔드
- **Python 3.11**
- **SQLAlchemy** - ORM
- **PostgreSQL 15** - 데이터베이스
- **Faker** - 더미 데이터 생성

### 메시지 큐
- **Apache Kafka** - 이벤트 스트리밍
- **Confluent Kafka Python** - Kafka 클라이언트
- **Kafka UI** - 모니터링

### 인프라
- **Docker & Docker Compose** - 컨테이너화
- **KRaft** - Kafka 메타데이터 관리 (Zookeeper 불필요)

## 📊 데이터 볼륨

- **초기 데이터**: 10,000 유저 + 20,000 상품
- **실시간 주문**: 2~8초마다 1~5건
- **실시간 상품**: 10~20초마다 100건
- **Retention**: 유저/상품 7일, 주문 30일

## 🖥️ 모니터링

### Kafka UI
```
http://localhost:8080
```
- 브로커 상태
- 토픽 및 메시지 확인
- 컨슈머 그룹 모니터링

### 로그
```bash
# Makefile 사용
make logs                    # 전체 로그
make logs-producer           # Producer 로그
make logs-consumers          # Consumer 로그
make logs-kafka              # Kafka 로그

# 래퍼 스크립트 사용
./dc.sh logs -f              # 전체 로그
./dc.sh logs -f producer     # Producer 로그

# 직접 사용
docker-compose -f deploy/docker-compose.yml logs -f producer
```

## 🧪 테스트

### 환경 테스트
```bash
# Makefile 사용
make test

# 래퍼 스크립트 사용
./dc.sh --profile dev up -d python-dev
./dc.sh exec python-dev python tests/test_environment.py
```

### 벤치마크
```bash
# Makefile 사용
make benchmark-kafka      # Kafka ON/OFF 비교
make benchmark-realtime   # 실시간 시나리오

# 직접 실행
python apps/benchmarks/kafka_comparison.py
python apps/benchmarks/realtime_comparison.py
```

## 🎯 Makefile 명령어

프로젝트는 편리한 Makefile 명령어를 제공합니다:

### 기본 명령어
```bash
make help           # 모든 명령어 보기
make build          # 이미지 빌드
make up             # 서비스 시작
make down           # 서비스 중지
make restart        # 서비스 재시작
make logs           # 전체 로그
make ps             # 실행 중인 서비스
```

### Kafka 관련
```bash
make topics         # 토픽 생성
make seed           # 초기 데이터 생성
```

### 통합 명령어
```bash
make start-all      # 전체 시작 (빌드 + 실행 + 토픽 + 데이터)
make clean          # 모든 컨테이너/볼륨 제거
```

### 개별 서비스
```bash
make start-producer     # Producer만 시작
make start-consumers    # Consumer들만 시작
make stop-producer      # Producer 중지
make stop-consumers     # Consumer들 중지
```

### 로그 확인
```bash
make logs-producer      # Producer 로그
make logs-consumers     # Consumer 로그
make logs-kafka         # Kafka 로그
```

## 📖 더 알아보기

자세한 내용은 **[GUIDE](GUIDE/)** 폴더의 가이드 문서를 참고하세요:
- 시작하기: [GUIDE/README.md](GUIDE/README.md)
- 배포: [GUIDE/DOCKER_DEPLOYMENT_GUIDE.md](GUIDE/DOCKER_DEPLOYMENT_GUIDE.md)
- 개발: [GUIDE/PYTHON_DEV_GUIDE.md](GUIDE/PYTHON_DEV_GUIDE.md)

---

**Kafka 데이터 파이프라인으로 실시간 스트리밍을 경험하세요!** 🚀
