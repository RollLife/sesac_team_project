## Redis 캐싱 + Aging 기법 추가 

### 개념
- **Cache-Worker**: 50초마다 DB에서 1,000건씩 Redis로 캐싱
- **Aging 기법**: 50% 신규 + 50% 기존 데이터 (기아 방지)
- **Producer**: Redis 캐시에서 랜덤 조회 → Kafka 발행


# Kafka + Redis 실시간 데이터 파이프라인

## 프로젝트 개요

Kafka 기반 실시간 데이터 스트리밍 파이프라인으로, Redis 캐싱 + Aging 기법을 통해 대용량 데이터 환경에서도 효율적인 성능을 제공합니다.

## 시스템 아키텍처

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   PostgreSQL    │────▶│  Cache-Worker   │────▶│     Redis       │
│  (원본 데이터)   │     │  (Aging 기법)   │     │  (1000건 캐시)  │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                                                         ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    Producer     │◀────│  Redis 캐시에서  │     │   Kafka         │
│ (realtime_gen)  │     │   랜덤 조회      │────▶│  (3 brokers)    │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                                                         ▼
                                                ┌─────────────────┐
                                                │    Consumers    │
                                                │  (9 instances)  │
                                                └────────┬────────┘
                                                         │
                                                         ▼
                                                ┌─────────────────┐
                                                │   PostgreSQL    │
                                                │    (저장)       │
                                                └─────────────────┘
```

## 주요 특징

### Redis 캐싱 + Aging 기법
- **50초마다** DB에서 1,000건의 유저/상품 데이터를 Redis로 캐싱
- **Aging 기법**: 50% 신규 데이터 + 50% 기존 데이터로 기아(Starvation) 방지
- **성능 향상**: DB 쿼리 98% 감소, 조회 속도 100배 향상

### 데이터 흐름
1. **Cache-Worker**: DB → Redis (50초마다 Aging 기법으로 갱신)
2. **Producer**: Redis에서 랜덤 조회 → Kafka 발행
3. **Consumer**: Kafka 소비 → PostgreSQL 저장

## 서비스 구성 (20개 컨테이너)

### 인프라 (7개)
- `postgres`: PostgreSQL 데이터베이스
- `kafka1`, `kafka2`, `kafka3`: Kafka 클러스터
- `kafka-ui`: Kafka 모니터링 UI
- `redis`: Redis 캐시 서버
- `adminer`: DB 관리 UI

### 애플리케이션 (13개)
- `cache-worker`: Redis 캐시 갱신 (Aging 기법)
- `redis-monitor`: Redis 실시간 모니터링
- `producer`: 실시간 주문/상품 생성
- `user-seeder`: 실시간 고객 생성
- `initial-seeder`: 초기 데이터 생성
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
- [GUIDE/DOCKER_DEPLOYMENT_GUIDE.md](GUIDE/DOCKER_DEPLOYMENT_GUIDE.md) - Docker 배포 상세 가이드
- [GUIDE/KAFKA_SETUP_GUIDE.md](GUIDE/KAFKA_SETUP_GUIDE.md) - Kafka 설정 가이드

## 디렉토리 구조

```
.
├── deploy/                 # Docker 배포 파일
├── apps/                   # 애플리케이션
│   ├── benchmarks/         # 벤치마크 스크립트
│   └── seeders/            # 데이터 생성
├── kafka/                  # Kafka Producer/Consumer
├── cache/                  # Redis 캐시 모듈
│   ├── client.py           # Redis 클라이언트
│   ├── config.py           # Redis 설정
│   ├── cache_worker.py     # Aging 기법 캐시 워커
│   └── redis_monitor.py    # 실시간 모니터링
├── database/               # SQLAlchemy 모델
└── collect/                # 데이터 생성기
```
>>>>>>> Stashed changes
