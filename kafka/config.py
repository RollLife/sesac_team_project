"""Kafka configuration settings"""
import os
from dotenv import load_dotenv

load_dotenv()

# Kafka 연결 설정 (3개 브로커 클러스터)
KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092,localhost:9093,localhost:9094')

# Kafka 토픽 설정
KAFKA_TOPIC_USERS = os.getenv('KAFKA_TOPIC_USERS', 'users')
KAFKA_TOPIC_PRODUCTS = os.getenv('KAFKA_TOPIC_PRODUCTS', 'products')
KAFKA_TOPIC_ORDERS = os.getenv('KAFKA_TOPIC_ORDERS', 'orders')

# Kafka 활성화 플래그
KAFKA_ENABLED = os.getenv('KAFKA_ENABLED', 'true').lower() == 'true'

# Kafka Producer 설정 (confluent-kafka 형식)
KAFKA_CONFIG = {
    'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
    'client.id': 'sesac-producer',

    # 신뢰성 설정
    'acks': 'all',  # 모든 복제본 확인 (데이터 안전성 최대)
    'enable.idempotence': True,  # 멱등성 보장 (중복 방지)

    # 성능 최적화
    'linger.ms': 10,  # 10ms 배치 대기 (효율성 향상)
    'compression.type': 'gzip',  # 압축 (네트워크 효율)
    'batch.size': 16384,  # 배치 크기 16KB
    'max.in.flight.requests.per.connection': 5,  # 파이프라이닝

    # 재시도 설정
    'retries': 2147483647,  # 무한 재시도
    'retry.backoff.ms': 100,  # 재시도 간격 100ms
    'request.timeout.ms': 30000,  # 요청 타임아웃 30초
}
