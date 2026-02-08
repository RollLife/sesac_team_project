# Kafka + Redis 실시간 데이터 파이프라인

## 프로젝트 개요

Kafka 기반 실시간 데이터 스트리밍 파이프라인으로, **Redis 캐싱 (구매이력/미구매 분리 적재)** + **구매 성향 기반 주문 생성** + **등급 자동 갱신**을 통해 현실적인 이커머스 데이터를 생성합니다.

## 시스템 아키텍처

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   PostgreSQL    │────▶│  Cache-Worker   │────▶│     Redis       │
│  (원본 데이터)   │     │(분리적재 50초)  │     │  (1000건 캐시)  │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                                                         ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    Producer     │◀────│  구매 성향 기반  │     │   Kafka         │
│ (realtime_gen)  │     │  가중치 선택    │────▶│  (3 brokers)    │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
┌─────────────────┐                                      ▼
│  Grade Updater  │                             ┌─────────────────┐
│  (10분 배치)    │                             │    Consumers    │
└─────────────────┘                             │  (9 instances)  │
                                                └────────┬────────┘
                                                         │
                                                         ▼
                                                ┌─────────────────┐
                                                │   PostgreSQL    │
                                                │    (저장)       │
                                                └─────────────────┘
```

## 주요 특징

### Redis 캐싱 - 구매이력/미구매 분리 적재
- **50초마다** DB에서 1,000건의 유저/상품 데이터를 Redis로 캐싱
- **고객 분리 적재**: 구매이력 600명 (last_ordered_at ASC) + 미구매 400명 (created_at DESC)
- **상품 분리 적재**: 인기상품 700개 (order_count DESC) + 신상품 300개 (created_at DESC)
- **성능 향상**: DB 쿼리 98% 감소, 조회 속도 100배 향상

### 구매 성향 기반 주문 생성 (장바구니)
캐싱된 1,000명 전체에서 **성향 점수 가중치**로 고객을 선택하고, **장바구니(1~10개 상품)**를 한번에 구매합니다:
```
최종 점수 = 기본 점수(나이+성별+상태+마케팅+등급) × 시간대 변동 × 마케팅 부스트 × 생활 이벤트
```

### 고객 등급 자동 갱신
| 등급 | 6개월 누적 금액 | 주문 횟수 |
|------|----------------|----------|
| VIP | 500만원 이상 | 30회 이상 |
| GOLD | 200만원 이상 | 15회 이상 |
| SILVER | 50만원 이상 | 5회 이상 |
| BRONZE | 기본 (조건 미달) | - |

- **실시간 시스템**: 10분마다 배치 갱신
- **1년치 스크립트**: 7일마다 갱신
- **느슨한 강등**: 한 번에 1단계씩만 (VIP→GOLD→SILVER→BRONZE)

### 데이터 생성 주기
| 데이터 | 간격 | 수량 |
|--------|------|------|
| 주문 | 3~5초 | 장바구니 1~10건 |
| 상품 | 6~8초 | 1개 |
| 고객 | S커브 감쇄 (초기 10명/10초 → 점진적 감소) | 가변 |

### 데이터 흐름
1. **Cache-Worker**: DB → Redis (50초마다 구매이력/미구매 분리 적재)
2. **Producer**: Redis 1000명에서 성향 가중치로 선택 → 장바구니 구매 → Kafka 발행
3. **Consumer**: Kafka 소비 → PostgreSQL 저장
4. **Grade Updater**: 10분마다 6개월 누적 기준 등급 갱신

## 서비스 구성 (21개 컨테이너)

### 인프라 (7개)
- `postgres`: PostgreSQL 데이터베이스
- `kafka1`, `kafka2`, `kafka3`: Kafka 클러스터
- `kafka-ui`: Kafka 모니터링 UI
- `redis`: Redis 캐시 서버
- `adminer`: DB 관리 UI

### 애플리케이션 (14개)
- `cache-worker`: Redis 캐시 갱신 (구매이력/미구매 분리 적재)
- `redis-monitor`: Redis 실시간 모니터링
- `producer`: 실시간 주문/상품 생성 (구매 성향 기반)
- `user-seeder`: 실시간 고객 생성 (S커브 감쇄)
- `initial-seeder`: 초기 데이터 생성
- `grade-updater`: 고객 등급 배치 갱신 (10분 주기)
- `user-consumer-1/2/3`: 유저 컨슈머
- `product-consumer-1/2/3`: 상품 컨슈머
- `order-consumer-1/2/3`: 주문 컨슈머

## 빠른 시작

```bash
# 1. deploy 디렉토리로 이동
cd deploy

# 2. 빌드 및 실행
docker-compose build
docker-compose up -d

# 3. 로그 확인
docker-compose logs -f
```

## 모니터링

| 서비스 | URL | 설명 |
|--------|-----|------|
| Kafka UI | http://localhost:8080 | Kafka 토픽/메시지 모니터링 |
| Adminer | http://localhost:8081 | PostgreSQL 관리 |
| Redis Monitor | `docker logs redis_monitor` | Redis 캐시 상태 |

## 문서

- [QUICK_START.md](QUICK_START.md) - 빠른 시작 가이드
- [GUIDE/DB_README.md](GUIDE/DB_README.md) - DB 구조 및 ORM 가이드
- [GUIDE/DOCKER_DEPLOYMENT_GUIDE.md](GUIDE/DOCKER_DEPLOYMENT_GUIDE.md) - Docker 배포 상세 가이드
- [GUIDE/KAFKA_SETUP_GUIDE.md](GUIDE/KAFKA_SETUP_GUIDE.md) - Kafka 설정 가이드
- [GUIDE/HISTORICAL_DATA_GUIDE.md](GUIDE/HISTORICAL_DATA_GUIDE.md) - 과거 데이터 생성 가이드

## 디렉토리 구조

```
.
├── deploy/                 # Docker 배포 파일
├── apps/                   # 애플리케이션
│   ├── batch/              # 배치 작업
│   │   └── grade_updater.py  # 등급 갱신 (10분 배치)
│   ├── benchmarks/         # 벤치마크 스크립트
│   └── seeders/            # 데이터 생성
│       ├── realtime_generator.py      # 주문/상품 생성 (성향 기반)
│       └── realtime_generator_user.py # 고객 생성 (S커브 감쇄)
├── kafka/                  # Kafka Producer/Consumer
├── cache/                  # Redis 캐시 모듈
│   ├── client.py           # Redis 클라이언트
│   ├── config.py           # Redis 설정
│   ├── cache_worker.py     # 분리 적재 캐시 워커
│   └── redis_monitor.py    # 실시간 모니터링
├── database/               # SQLAlchemy 모델
├── collect/                # 데이터 생성기
│   ├── user_generator.py        # 고객 생성 (전원 BRONZE)
│   ├── product_generator.py     # 상품 생성 (베타분포 가격)
│   ├── order_generator.py       # 주문 생성 (장바구니 1~10개)
│   ├── purchase_propensity.py   # 구매 성향 점수 시스템
│   └── scenario_engine.py       # 20가지 시나리오 정의
└── scripts/                # 유틸리티 스크립트
    └── generate_historical_data.py  # 과거 1년치 데이터 생성
```

## Grafana 분석용 과거 데이터 생성

1년치 과거 주문 데이터를 생성하여 분석 대시보드용 데이터를 준비합니다.

### 실행 방법

```bash
# 프로젝트 루트에서 실행
python scripts/generate_historical_data.py
```

### 생성 내용
| 항목 | 내용 |
|------|------|
| 기간 | 2025년 1월 ~ 12월 |
| 주문 수 | 약 50,000건 |
| 성장 패턴 | 월 3,000건 → 6,000건 |
| 시나리오 | 20가지 이벤트 (설날, 블프, 여름 등) |
| 캐시 풀 | 첫 7일 random_seed, 이후 600+400 분리 |
| 등급 갱신 | 7일마다 6개월 누적 기준 갱신 |

### 전제 조건
- `initial_seeder.py` 실행 완료 (유저 1만명, 상품 2만개)
- PostgreSQL 컨테이너 실행 중

자세한 내용: [GUIDE/HISTORICAL_DATA_GUIDE.md](GUIDE/HISTORICAL_DATA_GUIDE.md)

## 참고 문서

- [GUIDE/DB_README.md](GUIDE/DB_README.md) - DB 구조 및 캐시 적재 가이드
- [GUIDE/DOCKER_DEPLOYMENT_GUIDE.md](GUIDE/DOCKER_DEPLOYMENT_GUIDE.md) - Docker 배포 가이드 (상세)
- [GUIDE/KAFKA_SETUP_GUIDE.md](GUIDE/KAFKA_SETUP_GUIDE.md) - Kafka 설정 가이드
- [GUIDE/HISTORICAL_DATA_GUIDE.md](GUIDE/HISTORICAL_DATA_GUIDE.md) - 과거 데이터 생성 가이드
- [GUIDE/PYTHON_DEV_GUIDE.md](GUIDE/PYTHON_DEV_GUIDE.md) - 개발 컨테이너 사용법
