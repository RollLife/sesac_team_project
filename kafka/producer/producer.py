"""Kafka Producer with Singleton and Circuit Breaker pattern"""
import logging
import threading
from typing import Dict, Any
from confluent_kafka import Producer
from kafka.config import KAFKA_CONFIG
from .serializers import serialize_event
from kafka.exceptions import KafkaConnectionError, KafkaPublishError

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KafkaProducer:
    """Kafka Producer 싱글톤 클래스"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """싱글톤 패턴 구현"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Producer 초기화"""
        if self._initialized:
            return

        try:
            self.producer = Producer(KAFKA_CONFIG)
            self._initialized = True

            # Circuit Breaker 설정
            self._consecutive_failures = 0
            self._circuit_open = False
            self._max_failures = 5

            logger.info("Kafka Producer initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Kafka Producer: {e}")
            raise KafkaConnectionError(f"Kafka connection failed: {e}")

    def send_event(self, topic: str, key: str, data: Dict[str, Any], event_type: str) -> bool:
        """
        Kafka에 이벤트 발행

        Args:
            topic: Kafka 토픽명 (users, products, orders)
            key: 파티션 키 (user_id, product_id 등)
            data: 이벤트 데이터
            event_type: 이벤트 타입 (user_created, product_created, order_created)

        Returns:
            bool: 발행 성공 여부
        """
        # Circuit Breaker 체크
        if self._circuit_open:
            logger.warning("Kafka circuit breaker is OPEN, skipping message")
            return False

        try:
            # 메시지 직렬화
            value = serialize_event(event_type, data)

            # Kafka에 발행 (비동기)
            self.producer.produce(
                topic=topic,
                key=key.encode('utf-8') if isinstance(key, str) else key,
                value=value,
                callback=self._delivery_callback
            )

            # 주기적으로 poll하여 콜백 처리
            self.producer.poll(0)

            # 성공 시 실패 카운트 리셋
            self._consecutive_failures = 0

            return True

        except Exception as e:
            self._consecutive_failures += 1

            # Circuit Breaker 열기
            if self._consecutive_failures >= self._max_failures:
                self._circuit_open = True
                logger.error(f"Kafka circuit breaker OPENED after {self._max_failures} failures")

            logger.error(f"Failed to publish to Kafka: {e}")
            raise KafkaPublishError(f"Message publish failed: {e}")

    def _delivery_callback(self, err, msg):
        """메시지 전송 콜백 (confluent-kafka 형식)"""
        if err:
            logger.error(f'Message delivery failed: {err}')
        else:
            logger.debug(
                f'Message delivered to {msg.topic()} '
                f'[partition {msg.partition()}] at offset {msg.offset()}'
            )

    def flush(self):
        """대기 중인 모든 메시지 전송"""
        try:
            self.producer.flush()
            logger.info("Kafka producer flushed")
        except Exception as e:
            logger.error(f"Failed to flush Kafka producer: {e}")

    def close(self):
        """Producer 종료"""
        try:
            self.producer.flush()
            logger.info("Kafka Producer closed successfully")
        except Exception as e:
            logger.error(f"Failed to close Kafka producer: {e}")
