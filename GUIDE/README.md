# 가이드 문서 모음

Kafka + Redis 데이터 파이프라인 프로젝트의 모든 가이드 문서입니다.

## 시스템 아키텍처

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

## 빠른 시작

### 1. Docker 환경 구축
**[DOCKER_DEPLOYMENT_GUIDE.md](DOCKER_DEPLOYMENT_GUIDE.md)**
- 전체 시스템을 Docker로 실행
- 총 21개 컨테이너 구성 (Redis + Cache-Worker + Grade Updater 포함)
- 한 명령어로 시작

```bash
cd deploy
docker-compose build
docker-compose up -d
```

### 2. Redis 캐시 모니터링
```bash
# 실시간 캐시 상태 확인
docker logs -f redis_monitor

# 출력 예시:
# [11:45:35] [15/50s ######--------------] | MEM: 2.25M | HIT: 100.0% | CACHE: users=1000, products=1000 | 교체: 1회
```

### 3. Kafka 클러스터 설정
**[KAFKA_SETUP_GUIDE.md](KAFKA_SETUP_GUIDE.md)**
- 3개 브로커 클러스터
- 토픽 생성 (파티션 3개, 복제 팩터 3)
- 모니터링 설정

### 4. 데이터 흐름 확인
```bash
# Producer 로그 (구매 성향 기반 주문 생성)
docker logs -f realtime_producer

# Consumer 로그 (Kafka → DB)
docker logs -f order_consumer_1

# 등급 갱신 로그
docker logs -f grade_updater
```

## Redis 캐싱 - 구매이력/미구매 분리 적재

### 개념
- **Cache-Worker**: 50초마다 DB에서 1,000건씩 Redis로 캐싱
- **고객 분리 적재**: 구매이력 600명 (last_ordered_at ASC) + 미구매 400명 (created_at DESC)
- **상품 분리 적재**: 인기상품 700개 (order_count DESC) + 신상품 300개 (created_at DESC)
- **Producer**: Redis 캐시에서 구매 성향 상위 200명 선택 → Kafka 발행

### 구매 성향 기반 선택
캐싱된 1,000명 중 **구매 성향 상위 200명**이 실제 주문 후보로 선택됩니다:
```
최종 점수 = 기본 점수(나이+성별+상태+마케팅+등급) × 시간대 변동 × 마케팅 부스트 × 생활 이벤트
```

### 성능 향상
| 지표 | Before | After | 개선율 |
|------|--------|-------|--------|
| DB 쿼리/분 | ~60회 | ~1.2회 | 98% 감소 |
| 조회 속도 | 10-100ms | 0.1-1ms | 100배 향상 |

## 고객 등급 시스템

### 등급 기준 (6개월 누적)
| 등급 | 누적 금액 | 주문 횟수 |
|------|----------|----------|
| VIP | 300만원 이상 | 15회 이상 |
| GOLD | 100만원 이상 | 8회 이상 |
| SILVER | 30만원 이상 | 3회 이상 |
| BRONZE | 기본 (조건 미달) | - |

### 갱신 주기
- **실시간 시스템**: 10분마다 배치 갱신 (`apps/batch/grade_updater.py`)
- **1년치 스크립트**: 7일마다 갱신

## 가이드 목록

### 인프라 및 설정
| 가이드 | 설명 | 주요 내용 |
|-------|------|----------|
| [DOCKER_DEPLOYMENT_GUIDE.md](DOCKER_DEPLOYMENT_GUIDE.md) | Docker 배포 가이드 | 21개 컨테이너, Redis 캐시, 모니터링 |
| [KAFKA_SETUP_GUIDE.md](KAFKA_SETUP_GUIDE.md) | Kafka 클러스터 설정 | 브로커, 토픽, 파티션, 복제 |

### 데이터베이스
| 가이드 | 설명 | 주요 내용 |
|-------|------|----------|
| [DB_README.md](DB_README.md) | DB 구조 및 ORM | 스키마, 캐시 적재, 등급 시스템 |

### 애플리케이션
| 가이드 | 설명 | 주요 내용 |
|-------|------|----------|
| [KAFKA_PRODUCER_GUIDE.md](KAFKA_PRODUCER_GUIDE.md) | Producer 사용법 | Redis 캐시 조회, 성향 기반 선택, Kafka 발행 |
| [KAFKA_CONSUMER_GUIDE.md](KAFKA_CONSUMER_GUIDE.md) | Consumer 구성 | 컨슈머 그룹, 역직렬화, 저장 |

### 성능 및 테스트
| 가이드 | 설명 | 주요 내용 |
|-------|------|----------|
| [KAFKA_BENCHMARK_GUIDE.md](KAFKA_BENCHMARK_GUIDE.md) | 성능 벤치마크 | Kafka ON/OFF 비교, TPS |
| [PYTHON_DEV_GUIDE.md](PYTHON_DEV_GUIDE.md) | 개발 환경 | 환경 테스트, REPL, 디버깅 |

### 핵심 시스템
| 가이드 | 설명 | 주요 내용 |
|-------|------|----------|
| [PROPENSITY_GRADE_GUIDE.md](PROPENSITY_GRADE_GUIDE.md) | 구매 성향 & 등급 갱신 | 성향 점수, 시간대 변동, 등급 기준, API 레퍼런스 |
| [ORDER_RULES_GUIDE.md](ORDER_RULES_GUIDE.md) | 주문 생성 규칙 | 카테고리별 주문 빈도, 수량 옵션 |

### 데이터 분석
| 가이드 | 설명 | 주요 내용 |
|-------|------|----------|
| [HISTORICAL_DATA_GUIDE.md](HISTORICAL_DATA_GUIDE.md) | 과거 데이터 생성 | 1년치 주문 데이터, 성향 기반 선택, 등급 갱신, Grafana 분석용 |

## 서비스 구성 (21개 컨테이너)

### 인프라 (7개)
- `postgres`, `kafka1/2/3`, `kafka-ui`, `redis`, `adminer`

### 캐시 및 배치 서비스 (3개)
- `cache-worker`: Redis 캐시 갱신 (구매이력/미구매 분리 적재)
- `redis-monitor`: 실시간 모니터링
- `grade-updater`: 고객 등급 배치 갱신 (10분 주기)

### 데이터 생성 (3개)
- `initial-seeder`: 초기 유저/상품 생성
- `producer`: 실시간 주문/상품 생성 (구매 성향 기반, 3~5초/6~8초 간격)
- `user-seeder`: 실시간 고객 생성 (S커브 감쇄)

### Consumer (9개)
- `user-consumer-1/2/3`, `product-consumer-1/2/3`, `order-consumer-1/2/3`

## 학습 경로

### 초보자
```
1. DOCKER_DEPLOYMENT_GUIDE.md (환경 구축)
   ↓
2. Redis 캐시 모니터링 (docker logs -f redis_monitor)
   ↓
3. KAFKA_SETUP_GUIDE.md (Kafka 기본)
   ↓
4. KAFKA_PRODUCER_GUIDE.md (데이터 생성)
```

### 개발자
```
1. PYTHON_DEV_GUIDE.md (개발 환경)
   ↓
2. DB_README.md (DB 구조 + 캐시 적재 + 등급 시스템)
   ↓
3. cache/ 모듈 분석 (분리 적재 구현)
   ↓
4. collect/purchase_propensity.py (구매 성향 시스템)
   ↓
5. KAFKA_BENCHMARK_GUIDE.md (성능 최적화)
```

## 모니터링 URL

| 서비스 | URL | 설명 |
|--------|-----|------|
| Kafka UI | http://localhost:8080 | 토픽/메시지 모니터링 |
| Adminer | http://localhost:8081 | PostgreSQL 관리 |
| Redis Monitor | `docker logs redis_monitor` | 캐시 상태 |

## 관련 파일

### 캐시 모듈
- `cache/client.py` - Redis 클라이언트
- `cache/config.py` - 캐시 설정
- `cache/cache_worker.py` - 구매이력/미구매 분리 적재 캐시 워커
- `cache/redis_monitor.py` - 실시간 모니터링

### 배치 작업
- `apps/batch/grade_updater.py` - 고객 등급 배치 갱신 (10분 주기)

### 데이터 생성
- `apps/seeders/initial_seeder.py` - 초기 데이터 생성 (유저 1만명, 상품 2만개)
- `apps/seeders/realtime_generator.py` - 실시간 주문/상품 생성 (구매 성향 기반)
- `apps/seeders/realtime_generator_user.py` - 실시간 고객 생성 (S커브 감쇄)
- `collect/purchase_propensity.py` - 구매 성향 점수 시스템
- `scripts/generate_historical_data.py` - 과거 1년치 주문 데이터 생성

### 설정
- `deploy/docker-compose.yml` - 전체 서비스 정의 (21개 컨테이너)

## 문제 해결

### Redis 캐시 문제
```bash
# Redis 상태 확인
docker exec local_redis redis-cli ping

# 캐시 데이터 확인
docker exec local_redis redis-cli hlen cache:users

# 재시작
docker-compose restart redis cache-worker
```

### 등급 갱신 문제
```bash
# Grade Updater 로그 확인
docker logs -f grade_updater

# DB에서 등급 분포 확인
docker exec local_postgres psql -U postgres -d sesac_db -c "
  SELECT grade, COUNT(*) FROM users GROUP BY grade ORDER BY COUNT(*) DESC;"
```

### 전체 재시작
```bash
docker-compose down && docker-compose up -d
```

---

**Redis 캐싱 (구매이력/미구매 분리 적재) + 구매 성향 기반 선택 + 등급 자동 갱신으로 현실적인 이커머스 데이터 파이프라인을 구축하세요!**
