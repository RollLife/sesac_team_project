# Deploy 폴더

이 폴더에는 Docker 배포 관련 파일들이 포함되어 있습니다.

## 파일 구성

- **docker-compose.yml** - 전체 서비스 정의 (20개 컨테이너)
- **Dockerfile** - Python 애플리케이션 이미지
- **requirements.txt** - Python 의존성 패키지

## 사용 방법

### 방법 1: docker-compose 직접 사용 (권장)

```bash
cd deploy

# 빌드
docker-compose build

# 전체 시작
docker-compose up -d

# 로그 확인
docker-compose logs -f
```

### 방법 2: Makefile 사용

루트 디렉토리에서 Makefile 명령어 사용:

```bash
# 도움말
make help

# 전체 시작
make build
make up

# 한 번에 모두 실행
make start-all
```

## 서비스 구성 (21개 컨테이너)

### 인프라 (7개)
- `postgres`: PostgreSQL 데이터베이스
- `kafka1`, `kafka2`, `kafka3`: Kafka 클러스터 (3 브로커)
- `kafka-ui`: Kafka 모니터링 UI
- `redis`: Redis 캐시 서버
- `adminer`: DB 관리 UI

### 캐시 및 배치 서비스 (3개)
- `cache-worker`: Redis 캐시 갱신 (구매이력/미구매 분리 적재, 50초마다)
- `redis-monitor`: Redis 실시간 모니터링
- `grade-updater`: 고객 등급 배치 갱신 (10분 주기)

### 데이터 생성 (3개)
- `initial-seeder`: 초기 데이터 생성 (one-time)
- `producer`: 실시간 주문/상품 생성 (구매 성향 기반)
- `user-seeder`: 실시간 고객 생성 (S커브 감쇄)

### Consumer (9개)
- `user-consumer-1/2/3`: 유저 토픽 컨슈머
- `product-consumer-1/2/3`: 상품 토픽 컨슈머
- `order-consumer-1/2/3`: 주문 토픽 컨슈머

### 개발 (1개, 선택적)
- `python-dev`: 개발 컨테이너 (dev 프로파일)

## Redis 캐싱 + 구매이력/미구매 분리 적재

### 아키텍처
```
[PostgreSQL] → [Cache-Worker] → [Redis] → [Producer] → [Kafka]
                 (50초마다)     (1000건)  (성향기반선택)
```

### 분리 적재 방식
- **고객**: 구매이력 600명 (last_ordered_at ASC) + 미구매 400명 (created_at DESC)
- **상품**: 인기상품 700개 (order_count DESC) + 신상품 300개 (created_at DESC)

### 환경변수 (cache-worker)
```yaml
CACHE_REFRESH_INTERVAL: 50     # 캐시 갱신 주기 (초)
CACHE_BATCH_SIZE: 1000         # 캐시 배치 크기
```

### 성능 향상
- **DB 쿼리 98% 감소**: 매 주문마다 → 50초마다 1회
- **조회 속도 100배 향상**: 10-100ms → 0.1-1ms

## 모니터링

### Redis 모니터링
```bash
# 실시간 캐시 상태
docker logs -f redis_monitor

# 출력 예시:
# [11:45:35] [15/50s ######--------------] | MEM: 2.25M | HIT: 100.0% | CACHE: users=1000, products=1000 | 교체: 1회
```

### 웹 UI
- **Kafka UI**: http://localhost:8080
- **Adminer**: http://localhost:8081

## 참고

자세한 사용법은 [GUIDE/DOCKER_DEPLOYMENT_GUIDE.md](../GUIDE/DOCKER_DEPLOYMENT_GUIDE.md)를 참고하세요.
