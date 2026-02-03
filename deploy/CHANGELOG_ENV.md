# 환경변수 리팩토링 변경사항

## 📅 변경 일자
2026-02-03

## 🎯 목적
데이터베이스 및 Kafka 설정을 하드코딩에서 환경변수 기반으로 변경하여:
- 개발/스테이징/운영 환경 전환 용이
- 민감한 정보(비밀번호) 관리 개선
- 코드 중복 제거 및 유지보수성 향상

## 📝 변경 내용

### 1. 파일 구조
```
deploy/
├── .env                    # 실제 환경변수 값 (Git 제외)
├── .env.example            # 환경변수 템플릿 (Git 포함)
├── docker-compose.yml      # 환경변수 참조로 변경
├── ENV_GUIDE.md            # 환경변수 사용 가이드
└── CHANGELOG_ENV.md        # 이 파일
```

### 2. docker-compose.yml 변경사항

#### Before (하드코딩)
```yaml
services:
  producer:
    environment:
      DB_TYPE: local
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
      POSTGRES_DB: sesac_db
      POSTGRES_HOST: postgres
      POSTGRES_PORT: 5432
      KAFKA_BOOTSTRAP_SERVERS: kafka1:29092,kafka2:29093,kafka3:29094
      KAFKA_ENABLED: "true"

  user-consumer-1:
    environment:
      DB_TYPE: local              # 모든 서비스에 중복
      POSTGRES_USER: postgres      # 12번 반복됨
      POSTGRES_PASSWORD: password  # 12번 반복됨
      # ...
```

#### After (환경변수 + YAML Anchors)
```yaml
# 공통 설정 정의 (1번만)
x-app-environment: &app-environment
  DB_TYPE: ${DB_TYPE:-local}
  POSTGRES_USER: ${POSTGRES_USER:-postgres}
  POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-password}
  POSTGRES_DB: ${POSTGRES_DB:-sesac_db}
  POSTGRES_HOST: ${POSTGRES_HOST:-postgres}
  POSTGRES_PORT: ${POSTGRES_PORT:-5432}
  KAFKA_BOOTSTRAP_SERVERS: ${KAFKA_BOOTSTRAP_SERVERS:-kafka1:29092,...}
  KAFKA_ENABLED: ${KAFKA_ENABLED:-true}

services:
  producer:
    environment: *app-environment  # 참조만

  user-consumer-1:
    environment: *app-environment  # 참조만
```

### 3. .env 파일 구조
```env
# 데이터베이스 설정
DB_TYPE=local
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
POSTGRES_DB=sesac_db
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

# Kafka 설정
KAFKA_BOOTSTRAP_SERVERS=kafka1:29092,kafka2:29093,kafka3:29094
KAFKA_ENABLED=true
KAFKA_CLUSTER_ID=MkU3OEVBNTcwNTJENDM2Qk
```

### 4. .gitignore 업데이트
```gitignore
# .env 파일은 제외 (민감한 정보 포함)
deploy/.env
deploy/.env.local
deploy/.env.*.local

# .env.example은 포함 (템플릿)
!deploy/.env.example
```

## 📊 개선 효과

### 코드 라인 수 감소
- **Before**: 453 lines
- **After**: 314 lines
- **감소**: 139 lines (-30.7%)

### 중복 제거
- **Before**: 12개 서비스에서 8개 환경변수 × 12 = 96번 반복
- **After**: 1번 정의 + 12번 참조 = 13번
- **감소**: 83번 (-86.5%)

### 유지보수성
- **Before**: 설정 변경 시 12개 서비스를 모두 수정해야 함
- **After**: .env 파일 1개만 수정하면 됨

## 🔧 사용 방법

### 환경 전환
```bash
# 개발 환경
cp .env.dev .env
docker-compose up -d

# 운영 환경
cp .env.prod .env
docker-compose up -d
```

### 설정 확인
```bash
# 환경변수가 제대로 적용되었는지 확인
docker-compose config

# 특정 서비스만 확인
docker-compose config producer
```

## ⚠️ 주의사항

1. **.env 파일 보안**
   - `.env` 파일은 절대 Git에 커밋하지 말 것
   - 운영 환경 비밀번호는 시크릿 관리 도구 사용 권장

2. **환경변수 우선순위**
   - Shell 환경변수 > .env 파일 > 기본값 (docker-compose.yml)

3. **컨테이너 재시작**
   - .env 파일 수정 후 반드시 컨테이너 재시작 필요

## 📚 참고 문서
- [ENV_GUIDE.md](./ENV_GUIDE.md) - 상세 사용 가이드
- [.env.example](./.env.example) - 환경변수 템플릿

## 🔄 롤백 방법
만약 이전 버전으로 돌아가야 한다면:
```bash
git checkout <이전-커밋> -- deploy/docker-compose.yml
```

## ✅ 테스트 완료
- [x] docker-compose.yml 문법 검증
- [x] 환경변수 로드 확인
- [x] 모든 서비스 정상 작동 확인
- [x] .gitignore 규칙 검증
