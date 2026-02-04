# Deploy 폴더

이 폴더에는 Docker 배포 관련 파일들이 포함되어 있습니다.

## 파일 구성

- **docker-compose.yml** - 전체 서비스 정의 (17개 컨테이너)
- **Dockerfile** - Python 애플리케이션 이미지
- **requirements.txt** - Python 의존성 패키지

## 사용 방법

### 방법 1: Makefile 사용 (권장)

루트 디렉토리에서 Makefile 명령어 사용:

```bash
# 도움말
make help

# 전체 시작
make build
make up

# 토픽 생성 및 초기 데이터
make topics
make seed

# 한 번에 모두 실행
make start-all
```

### 방법 2: 래퍼 스크립트 사용

루트 디렉토리에서 래퍼 스크립트 사용:

#### Unix/Mac/Git Bash
```bash
./dc.sh build
./dc.sh up -d
./dc.sh logs -f
```

#### Windows (CMD/PowerShell)
```cmd
dc.bat build
dc.bat up -d
dc.bat logs -f
```

### 방법 3: 직접 docker-compose 사용

```bash
docker-compose -f deploy/docker-compose.yml build
docker-compose -f deploy/docker-compose.yml up -d
```

## 서비스 구성

### 인프라 (5개)
- postgres
- kafka1, kafka2, kafka3
- kafka-ui

### 애플리케이션 (12개)
- initial-seeder (초기 데이터)
- producer (실시간 주문/상품 생성)
- user-seeder (실시간 고객 생성)
- user-consumer-1/2/3 (유저 컨슈머)
- product-consumer-1/2/3 (상품 컨슈머)
- order-consumer-1/2/3 (주문 컨슈머)

### 개발 (1개)
- python-dev (dev 프로파일)

## 참고

자세한 사용법은 [GUIDE/DOCKER_DEPLOYMENT_GUIDE.md](../GUIDE/DOCKER_DEPLOYMENT_GUIDE.md)를 참고하세요.
