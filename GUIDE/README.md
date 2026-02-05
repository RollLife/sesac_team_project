# 가이드 문서 모음

Kafka + Redis 데이터 파이프라인 프로젝트의 모든 가이드 문서입니다.

## 시스템 아키텍처

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ PostgreSQL  │────▶│Cache-Worker │────▶│    Redis    │
│  (원본 DB)  │     │(Aging 50초) │     │ (1000건)    │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
      ┌────────────────────────────────────────┘
      ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Producer   │────▶│   Kafka     │────▶│  Consumers  │
│(Redis조회)  │     │ (3 brokers) │     │(9 instances)│
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                                               ▼
                                        ┌─────────────┐
                                        │ PostgreSQL  │
                                        │   (저장)    │
                                        └─────────────┘
```

## 빠른 시작

### 1. Docker 환경 구축
**[DOCKER_DEPLOYMENT_GUIDE.md](DOCKER_DEPLOYMENT_GUIDE.md)**
- 전체 시스템을 Docker로 실행
- 총 20개 컨테이너 구성 (Redis + Cache-Worker 포함)
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
# Producer 로그 (Redis → Kafka)
docker logs -f realtime_producer

# Consumer 로그 (Kafka → DB)
docker logs -f order_consumer_1
```

## Redis 캐싱 + Aging 기법

### 개념
- **Cache-Worker**: 50초마다 DB에서 1,000건씩 Redis로 캐싱
- **Aging 기법**: 50% 신규 + 50% 기존 데이터 (기아 방지)
- **Producer**: Redis 캐시에서 랜덤 조회 → Kafka 발행

### 성능 향상
| 지표 | Before | After | 개선율 |
|------|--------|-------|--------|
| DB 쿼리/분 | ~60회 | ~1.2회 | 98% 감소 |
| 조회 속도 | 10-100ms | 0.1-1ms | 100배 향상 |

## 가이드 목록

### 인프라 및 설정
| 가이드 | 설명 | 주요 내용 |
|-------|------|----------|
| [DOCKER_DEPLOYMENT_GUIDE.md](DOCKER_DEPLOYMENT_GUIDE.md) | Docker 배포 가이드 | 20개 컨테이너, Redis 캐시, 모니터링 |
| [KAFKA_SETUP_GUIDE.md](KAFKA_SETUP_GUIDE.md) | Kafka 클러스터 설정 | 브로커, 토픽, 파티션, 복제 |

### 애플리케이션
| 가이드 | 설명 | 주요 내용 |
|-------|------|----------|
| [KAFKA_PRODUCER_GUIDE.md](KAFKA_PRODUCER_GUIDE.md) | Producer 사용법 | Redis 캐시 조회, Kafka 발행 |
| [KAFKA_CONSUMER_GUIDE.md](KAFKA_CONSUMER_GUIDE.md) | Consumer 구성 | 컨슈머 그룹, 역직렬화, 저장 |

### 성능 및 테스트
| 가이드 | 설명 | 주요 내용 |
|-------|------|----------|
| [KAFKA_BENCHMARK_GUIDE.md](KAFKA_BENCHMARK_GUIDE.md) | 성능 벤치마크 | Kafka ON/OFF 비교, TPS |
| [PYTHON_DEV_GUIDE.md](PYTHON_DEV_GUIDE.md) | 개발 환경 | 환경 테스트, REPL, 디버깅 |

## 서비스 구성 (20개 컨테이너)

### 인프라 (7개)
- `postgres`, `kafka1/2/3`, `kafka-ui`, `redis`, `adminer`

### 캐시 서비스 (2개)
- `cache-worker`: Redis 캐시 갱신 (Aging 기법)
- `redis-monitor`: 실시간 모니터링

### 데이터 생성 (3개)
- `initial-seeder`, `producer`, `user-seeder`

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
2. cache/ 모듈 분석 (Redis 캐싱 구현)
   ↓
3. KAFKA_PRODUCER_GUIDE.md (Producer 커스터마이징)
   ↓
4. KAFKA_BENCHMARK_GUIDE.md (성능 최적화)
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
- `cache/cache_worker.py` - Aging 기법 캐시 워커
- `cache/redis_monitor.py` - 실시간 모니터링

### 데이터 생성
- `apps/seeders/initial_seeder.py` - 초기 데이터 생성
- `apps/seeders/realtime_generator.py` - 실시간 데이터 생성 (Redis 연동)

### 설정
- `deploy/docker-compose.yml` - 전체 서비스 정의 (20개 컨테이너)

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

### 전체 재시작
```bash
docker-compose down && docker-compose up -d
```

---

**Redis 캐싱 + Aging 기법으로 대용량 데이터 환경에서도 효율적인 Kafka 파이프라인을 구축하세요!**
