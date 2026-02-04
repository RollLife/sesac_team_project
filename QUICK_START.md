# 🚀 Quick Start Guide

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

**데이터 흐름:**
- **Producer** → Kafka에만 발행 (DB 저장 X)
- **Consumer** → Kafka에서 소비 → PostgreSQL에 저장
- **Consumer 그룹**: users_group(3), products_group(3), orders_group(3)

## 전체 시스템 시작

```bash
# 1. deploy 디렉토리로 이동
cd deploy

# 2. 모든 서비스 시작
make up
# 또는
docker-compose up -d

# 3. 토픽 생성 및 초기 데이터 seeding
make topics
make seed
```

## 개발 환경 (python-dev 포함)

```bash
# 개발 컨테이너 포함하여 시작
docker-compose --profile dev up -d

# 개발 컨테이너 접속
docker exec -it python_dev bash

# 컨테이너 내부에서 작업
python apps/seeders/initial_seeder.py
python apps/benchmarks/kafka_comparison.py
```

## 주요 명령어

### 서비스 관리
```bash
# 전체 시작
make up                 # docker-compose up -d

# 전체 중지
make down               # docker-compose down

# 로그 확인
make logs               # docker-compose logs -f

# 서비스 상태 확인
make ps                 # docker-compose ps
```

### Kafka
```bash
# 토픽 생성
make topics

# 토픽 목록 확인
docker-compose exec kafka1 kafka-topics --list --bootstrap-server localhost:9092

# 메시지 확인
docker-compose exec kafka1 kafka-console-consumer --bootstrap-server localhost:9092 --topic users --from-beginning --max-messages 5
```

### 데이터베이스
```bash
# Adminer 접속
http://localhost:8081
# 로그인: postgres / password / sesac_db

# PostgreSQL 직접 접속
docker-compose exec postgres psql -U postgres -d sesac_db

# 데이터 확인
SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM products;
SELECT COUNT(*) FROM orders;
```

### 개발 도구
```bash
# Python 개발 컨테이너 시작
docker-compose --profile dev up -d python-dev

# 컨테이너 접속
docker exec -it python_dev bash

# Python 대화형 모드
docker exec -it python_dev python
```

## 환경 설정

### 환경변수 변경
```bash
# deploy/.env 파일 수정
vi deploy/.env

# 변경사항 적용
docker-compose down
docker-compose up -d
```

### 운영 DB로 전환
```env
# deploy/.env
DB_TYPE=production
POSTGRES_HOST=prod-db.example.com
POSTGRES_PASSWORD=secure_password
```

## 모니터링

### Kafka UI
```
http://localhost:8080
```

### Adminer (DB 관리)
```
http://localhost:8081
```

### 컨테이너 상태
```bash
docker-compose ps
docker stats
```

### Consumer 실시간 처리 확인

**1. Consumer Lag 확인 (LAG=0이면 실시간 처리 중)**
```bash
# products_group Consumer Lag 확인
docker exec kafka1 kafka-consumer-groups \
  --bootstrap-server kafka1:29092 \
  --describe --group products_group

# orders_group Consumer Lag 확인
docker exec kafka1 kafka-consumer-groups \
  --bootstrap-server kafka1:29092 \
  --describe --group orders_group

# users_group Consumer Lag 확인
docker exec kafka1 kafka-consumer-groups \
  --bootstrap-server kafka1:29092 \
  --describe --group users_group
```

**2. DB 데이터 증가 확인**
```bash
# 테이블별 레코드 수 확인
docker exec local_postgres psql -U postgres -d sesac_db -c "
  SELECT 'users' as table_name, COUNT(*) FROM users
  UNION ALL SELECT 'products', COUNT(*) FROM products
  UNION ALL SELECT 'orders', COUNT(*) FROM orders;"

# 최근 주문 데이터 확인 (실시간 저장 확인)
docker exec local_postgres psql -U postgres -d sesac_db -c "
  SELECT order_id, created_at
  FROM orders
  ORDER BY created_at DESC
  LIMIT 5;"
```

**3. Consumer 로그 확인**
```bash
# 특정 Consumer 로그
docker logs --tail 50 product_consumer_1
docker logs --tail 50 order_consumer_1
docker logs --tail 50 user_consumer_1
```

## 문제 해결

### 컨테이너 재시작
```bash
# 특정 서비스만
docker-compose restart producer

# 전체 재시작
docker-compose restart
```

### 로그 확인
```bash
# 전체 로그
docker-compose logs -f

# 특정 서비스
docker-compose logs -f producer
docker-compose logs -f product-consumer-1
```

### 깨끗하게 재시작
```bash
# 모든 컨테이너 중지 및 삭제
make clean

# 볼륨까지 삭제 (데이터 초기화)
docker-compose down -v

# 다시 시작
make build
make up
make topics
make seed
```

## 디렉토리 구조

```
.
├── deploy/                 # Docker 관련 파일
│   ├── .env               # 환경변수 (수정 가능)
│   ├── .env.example       # 환경변수 템플릿
│   ├── docker-compose.yml # 서비스 정의
│   ├── Dockerfile         # Python 이미지
│   ├── ENV_GUIDE.md       # 환경변수 가이드
│   └── PYTHON_DEV_GUIDE.md # 개발 컨테이너 가이드
├── apps/                  # 애플리케이션
│   ├── benchmarks/        # 벤치마크 스크립트
│   └── seeders/           # 데이터 생성
├── kafka/                 # Kafka 관련 코드
│   ├── producer/          # Producer
│   ├── consumers/         # Consumers
│   └── admin/             # Admin 유틸리티
├── database/              # 데이터베이스
│   ├── models.py          # SQLAlchemy 모델
│   └── crud.py            # CRUD 함수
└── collect/               # 데이터 생성기
    ├── user_generator.py
    ├── product_generator.py
    └── order_generator.py
```

## 참고 문서

- [ENV_GUIDE.md](deploy/ENV_GUIDE.md) - 환경변수 설정 가이드
- [PYTHON_DEV_GUIDE.md](deploy/PYTHON_DEV_GUIDE.md) - 개발 컨테이너 사용법
- [DOCKER_DEPLOYMENT_GUIDE.md](GUIDE/DOCKER_DEPLOYMENT_GUIDE.md) - Docker 배포 가이드 (상세)
