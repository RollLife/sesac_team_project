# 환경변수 설정 가이드

## 개요

이 프로젝트는 `.env` 파일을 사용하여 데이터베이스 및 Kafka 설정을 관리합니다.
환경에 따라 `.env` 파일만 수정하면 모든 서비스의 설정이 자동으로 변경됩니다.

## 초기 설정

### 1. .env 파일 생성

```bash
# deploy 디렉토리로 이동
cd deploy

# .env.example 파일을 복사하여 .env 파일 생성
cp .env.example .env
```

### 2. 환경에 맞게 .env 파일 수정

`.env` 파일을 열어서 값을 수정합니다:

```bash
# 개발 환경 (로컬 Docker)
DB_TYPE=local
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
POSTGRES_DB=sesac_db
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

# 운영 환경 예시
# DB_TYPE=production
# POSTGRES_USER=prod_user
# POSTGRES_PASSWORD=secure_password_here
# POSTGRES_DB=sesac_prod_db
# POSTGRES_HOST=production-db.example.com
# POSTGRES_PORT=5432
```

## 환경별 설정 예시

### 개발 환경 (Local Docker)

```env
DB_TYPE=local
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
POSTGRES_DB=sesac_db
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

KAFKA_BOOTSTRAP_SERVERS=kafka1:29092,kafka2:29093,kafka3:29094
KAFKA_ENABLED=true
```

### 스테이징 환경

```env
DB_TYPE=staging
POSTGRES_USER=staging_user
POSTGRES_PASSWORD=staging_password
POSTGRES_DB=sesac_staging_db
POSTGRES_HOST=staging-db.internal
POSTGRES_PORT=5432

KAFKA_BOOTSTRAP_SERVERS=staging-kafka-1:9092,staging-kafka-2:9092
KAFKA_ENABLED=true
```

### 운영 환경

```env
DB_TYPE=production
POSTGRES_USER=prod_user
POSTGRES_PASSWORD=${SECRET_PASSWORD}  # 시크릿 관리 시스템에서 주입
POSTGRES_DB=sesac_prod_db
POSTGRES_HOST=prod-db.example.com
POSTGRES_PORT=5432

KAFKA_BOOTSTRAP_SERVERS=prod-kafka-1.example.com:9092,prod-kafka-2.example.com:9092,prod-kafka-3.example.com:9092
KAFKA_ENABLED=true
```

## 환경 전환 방법

### 방법 1: .env 파일 교체

환경별로 `.env.dev`, `.env.staging`, `.env.prod` 파일을 만들어두고 필요에 따라 복사합니다:

```bash
# 개발 환경으로 전환
cp .env.dev .env

# 스테이징 환경으로 전환
cp .env.staging .env

# 운영 환경으로 전환
cp .env.prod .env
```

### 방법 2: 환경변수 직접 설정

`.env` 파일 없이 환경변수를 직접 설정할 수도 있습니다:

```bash
# Linux/Mac
export POSTGRES_HOST=production-db.example.com
export POSTGRES_PASSWORD=secure_password
docker-compose up -d

# Windows PowerShell
$env:POSTGRES_HOST="production-db.example.com"
$env:POSTGRES_PASSWORD="secure_password"
docker-compose up -d
```

## docker-compose.yml 구조

### YAML Anchors 사용

중복을 제거하기 위해 YAML Anchors를 사용합니다:

```yaml
# 공통 설정 정의 (파일 최상단)
x-database-config: &database-config
  DB_TYPE: ${DB_TYPE:-local}
  POSTGRES_USER: ${POSTGRES_USER:-postgres}
  # ... 나머지 DB 설정

x-kafka-config: &kafka-config
  KAFKA_BOOTSTRAP_SERVERS: ${KAFKA_BOOTSTRAP_SERVERS:-kafka1:29092,...}
  KAFKA_ENABLED: ${KAFKA_ENABLED:-true}

# 전체 앱 환경변수 (DB + Kafka)
x-app-environment: &app-environment
  <<: *database-config  # DB 설정 merge
  <<: *kafka-config     # Kafka 설정 merge

# 서비스에서 사용
services:
  producer:
    environment: *app-environment  # 모든 설정이 자동으로 적용됨
```

### 장점

1. **중복 제거**: 453줄 → 314줄로 감소
2. **유지보수 용이**: `.env` 파일 하나만 수정하면 모든 서비스에 적용
3. **환경 전환 간편**: 파일 하나만 교체하면 전체 환경 전환
4. **실수 방지**: 하나의 값만 관리하므로 불일치 발생 방지

## 보안 주의사항

### .gitignore 설정

`.env` 파일은 민감한 정보를 포함하므로 **절대** Git에 커밋하지 마세요:

```gitignore
# .gitignore
deploy/.env
*.env

# 단, .env.example은 커밋
!deploy/.env.example
```

### 운영 환경 비밀번호 관리

운영 환경에서는 다음과 같은 시크릿 관리 도구를 사용하세요:

- **Docker Secrets**
- **Kubernetes Secrets**
- **AWS Secrets Manager**
- **HashiCorp Vault**
- **Azure Key Vault**

예시 (Docker Secrets):
```yaml
services:
  producer:
    environment:
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
    secrets:
      - db_password

secrets:
  db_password:
    external: true
```

## 검증

설정이 제대로 적용되었는지 확인:

```bash
# 환경변수 확인
docker-compose config

# 특정 서비스의 환경변수만 확인
docker-compose config producer | grep -A 10 "environment:"

# 실행 중인 컨테이너에서 확인
docker-compose exec producer env | grep POSTGRES
```

## 문제 해결

### Q: .env 파일을 수정했는데 적용이 안 됩니다

A: 컨테이너를 재시작해야 합니다:

```bash
docker-compose down
docker-compose up -d
```

### Q: 환경변수가 비어있습니다

A: `.env` 파일이 `deploy/` 디렉토리에 있는지 확인하고, `docker-compose` 명령어를 `deploy/` 디렉토리에서 실행하세요:

```bash
cd deploy
docker-compose up -d
```

또는 루트에서 실행할 경우:

```bash
docker-compose -f deploy/docker-compose.yml --env-file deploy/.env up -d
```

### Q: 기본값을 변경하고 싶습니다

A: docker-compose.yml의 `${VAR:-default}` 부분에서 `default` 값을 수정하세요.

## 참고

- [Docker Compose Environment Variables](https://docs.docker.com/compose/environment-variables/)
- [YAML Anchors](https://yaml.org/spec/1.2/spec.html#id2765878)
