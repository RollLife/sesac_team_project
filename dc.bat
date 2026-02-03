@echo off
REM Docker Compose 래퍼 스크립트 (Windows)
REM 기존 docker-compose 명령어를 그대로 사용 가능

docker-compose -f deploy/docker-compose.yml %*
