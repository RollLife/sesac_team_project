# Docker 배포 가이드

## 개요

모든 애플리케이션이 Docker 컨테이너로 실행됩니다.

## 서비스 구성

### 인프라 (7개)
- `postgres`: PostgreSQL 데이터베이스
- `kafka1`, `kafka2`, `kafka3`: 카프카 클러스터 (3 브로커)
- `kafka-ui`: 카프카 모니터링 UI
- `grafana`: 데이터 시각화 대시보드
- `adminer`: PostgreSQL 관리 도구

### 초기화 서비스 (2개)
- `db-init`: 데이터베이스 테이블 초기화 (one-time job)
- `kafka-init`: 카프카 토픽 생성 (one-time job)

### 애플리케이션 (11개)
- `initial-seeder`: 초기 데이터 생성 (one-time job)
- `producer`: 실시간 데이터 생성
- `user-consumer-1/2/3`: 유저 토픽 컨슈머 (3개)
- `product-consumer-1/2/3`: 상품 토픽 컨슈머 (3개)
- `order-consumer-1/2/3`: 주문 토픽 컨슈머 (3개)

**총 20개 컨테이너**

## 빠른 시작

### 1. 전체 서비스 실행

```bash
# 1. 도커 이미지 빌드
docker-compose build

# 2. 인프라 + Producer + Consumers 시작
docker-compose up -d

# 3. 로그 확인
docker-compose logs -f
```

### 2. 서비스 확인

```bash
# 실행 중인 컨테이너 확인
docker-compose ps
```

**웹 UI 접속:**
| 서비스 | URL | 비고 |
|--------|-----|------|
| Kafka UI | http://localhost:8080 | 카프카 모니터링 |
| Grafana | http://localhost:3000 | admin / admin |
| Adminer | http://localhost:8081 | DB 관리 |

## 상세 실행 가이드

### 단계별 실행

#### 1단계: 인프라만 시작
```bash
# PostgreSQL + Kafka 클러스터 + 모니터링 시작
docker-compose up -d postgres kafka1 kafka2 kafka3 kafka-ui grafana adminer

# 상태 확인
docker-compose ps
```

#### 2단계: 초기화 (자동 실행)
```bash
# db-init과 kafka-init은 depends_on으로 자동 실행됨
# 수동 실행 필요시:
docker-compose up db-init kafka-init
```

#### 3단계: 초기 데이터 생성
```bash
# 초기 데이터 생성 (10,000 유저 + 20,000 상품)
docker-compose up initial-seeder
```

#### 4단계: 컨슈머 시작
```bash
# 9개 컨슈머 모두 시작
docker-compose up -d \
  user-consumer-1 user-consumer-2 user-consumer-3 \
  product-consumer-1 product-consumer-2 product-consumer-3 \
  order-consumer-1 order-consumer-2 order-consumer-3
```

#### 5단계: Producer 시작
```bash
# 실시간 데이터 생성 시작
docker-compose up -d producer
```

### 선택적 실행

#### Producer만 실행
```bash
docker-compose up -d postgres kafka1 kafka2 kafka3 producer
```

#### Consumer만 실행 (특정 그룹)
```bash
# Users 그룹만
docker-compose up -d user-consumer-1 user-consumer-2 user-consumer-3

# Products 그룹만
docker-compose up -d product-consumer-1 product-consumer-2 product-consumer-3

# Orders 그룹만
docker-compose up -d order-consumer-1 order-consumer-2 order-consumer-3
```

#### 단일 Consumer 실행 (테스트용)
```bash
docker-compose up -d user-consumer-1
```

## 로그 및 모니터링

### 로그 확인

```bash
# 전체 로그
docker-compose logs -f

# 특정 서비스 로그
docker-compose logs -f producer
docker-compose logs -f user-consumer-1
docker-compose logs -f kafka1

# 최근 100줄만
docker-compose logs --tail=100 producer
```

### 컨테이너 상태 확인

```bash
# 모든 컨테이너 상태
docker-compose ps

# 리소스 사용량
docker stats

# 특정 컨테이너 상세 정보
docker inspect user_consumer_1
```

### Kafka 모니터링

```bash
# Kafka UI
http://localhost:8080

# CLI로 컨슈머 그룹 확인
docker-compose exec kafka1 kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --describe --group users_group
```

### Grafana 대시보드

```bash
# Grafana 접속
http://localhost:3000

# 로그인: admin / admin

# 데이터소스 추가
# - Type: PostgreSQL
# - Host: postgres:5432
# - Database: sesac_db
# - User: postgres
# - Password: password
```

## 환경변수 설정

### 방법 1: docker-compose.yml 수정
```yaml
environment:
  DB_TYPE: local
  POSTGRES_HOST: postgres
  KAFKA_ENABLED: "true"
```

### 방법 2: .env.docker 파일 사용
```bash
# .env.docker 파일 생성 (이미 있음)
DB_TYPE=local
POSTGRES_USER=postgres
KAFKA_ENABLED=true

# docker-compose.yml에서 참조
env_file:
  - .env.docker
```

### 방법 3: 런타임 환경변수
```bash
# 카프카 비활성화로 실행
docker-compose run -e KAFKA_ENABLED=false producer
```

## 카프카 ON/OFF 제어

### 카프카 비활성화
```bash
# docker-compose.yml에서 환경변수 수정
environment:
  KAFKA_ENABLED: "false"

# 또는 런타임 설정
docker-compose run -e KAFKA_ENABLED=false producer python apps/seeders/realtime_generator.py
```

### 카프카 활성화
```bash
environment:
  KAFKA_ENABLED: "true"
```

## 데이터베이스 작업

### DB 접속
```bash
# PostgreSQL 컨테이너 접속
docker-compose exec postgres psql -U postgres -d sesac_db

# SQL 실행
docker-compose exec postgres psql -U postgres -d sesac_db -c "SELECT COUNT(*) FROM users;"
```

### DB 초기화
```bash
# 데이터베이스 재생성
docker-compose exec postgres psql -U postgres -c "DROP DATABASE sesac_db;"
docker-compose exec postgres psql -U postgres -c "CREATE DATABASE sesac_db;"

# 스키마 재생성 (db-init 서비스 사용)
docker-compose up db-init
```

## 서비스 관리

### 중지 및 재시작

```bash
# 전체 중지
docker-compose stop

# 특정 서비스 중지
docker-compose stop producer

# 재시작
docker-compose restart producer

# 중지 후 제거
docker-compose down
```

### 업데이트 및 재배포

```bash
# 1. 코드 수정 후 이미지 재빌드
docker-compose build producer

# 2. 서비스 재시작
docker-compose up -d producer

# 3. 로그 확인
docker-compose logs -f producer
```

### 스케일링

```bash
# 컨슈머 수 동적 조정 (docker-compose scale은 deprecated)
# 대신 docker-compose.yml에서 replicas 사용 (docker swarm mode)

# 또는 수동으로 추가 인스턴스 실행
docker-compose run -d --name user-consumer-4 \
  -e CONSUMER_ID=user_consumer_4 \
  user-consumer-1 python kafka/consumers/user_consumer.py --id user_consumer_4
```

## 문제 해결

### 컨테이너가 시작되지 않을 때

```bash
# 로그 확인
docker-compose logs producer

# 에러 메시지 확인
docker-compose ps

# 컨테이너 재생성
docker-compose up -d --force-recreate producer
```

### 카프카 연결 실패

```bash
# 카프카 브로커 상태 확인
docker-compose ps kafka1 kafka2 kafka3

# 카프카 재시작
docker-compose restart kafka1 kafka2 kafka3

# 네트워크 확인
docker network ls
docker network inspect deploy_default
```

### DB 연결 실패

```bash
# PostgreSQL 상태 확인
docker-compose exec postgres pg_isready

# 연결 테스트
docker-compose exec postgres psql -U postgres -c "SELECT 1;"

# PostgreSQL 재시작
docker-compose restart postgres
```

### 디스크 공간 부족

```bash
# 사용하지 않는 이미지/컨테이너 정리
docker system prune -a

# 볼륨 정리 (주의: 데이터 삭제됨)
docker-compose down -v

# 빌드 캐시 정리
docker builder prune
```

## 전체 플로우

```bash
# 1. 이미지 빌드
docker-compose build

# 2. 전체 서비스 시작 (인프라 + 초기화 + 앱)
docker-compose up -d

# 3. 초기 데이터 생성 (필요시)
docker-compose up initial-seeder

# 4. 모니터링
docker-compose logs -f

# 5. 웹 UI 접속
# - Kafka UI: http://localhost:8080
# - Grafana: http://localhost:3000
# - Adminer: http://localhost:8081
```

## 참고 사항

### depends_on의 한계
`depends_on`은 컨테이너 시작 순서만 보장하며, 서비스가 준비되었는지는 보장하지 않습니다.

해결 방법:
1. 헬스체크 사용
2. 애플리케이션에서 재시도 로직 구현
3. 초기화 서비스 분리 (db-init, kafka-init)

### 네트워크
모든 컨테이너는 같은 Docker 네트워크에 있어 서비스 이름으로 통신 가능:
- `postgres`: PostgreSQL
- `kafka1`: 카프카 브로커 1
- 등등

### 볼륨
데이터 영구 저장을 위한 볼륨:
- `postgres_data`: PostgreSQL 데이터
- `kafka1_data`, `kafka2_data`, `kafka3_data`: 카프카 데이터
- `grafana_data`: Grafana 대시보드 설정

## 추가 명령어

```bash
# 전체 종료 및 정리 (볼륨 포함)
docker-compose down -v

# 이미지 재빌드 (캐시 무시)
docker-compose build --no-cache

# 특정 서비스만 재빌드
docker-compose build producer

# 서비스 로그를 파일로 저장
docker-compose logs producer > producer.log

# 실행 중인 컨테이너에서 명령 실행
docker-compose exec producer python --version
docker-compose exec kafka1 kafka-topics --list --bootstrap-server localhost:9092
```
