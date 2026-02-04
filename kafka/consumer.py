"""Kafka Consumer Base Class with JSON Deserializer"""

import json
import logging
from typing import Callable, Optional
from confluent_kafka import Consumer, KafkaException, KafkaError
from kafka.config import KAFKA_BOOTSTRAP_SERVERS

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class KafkaConsumerBase:
    """카프카 컨슈머 베이스 클래스"""

    def __init__(
        self,
        group_id: str,
        topics: list,
        message_handler: Callable,
        consumer_id: Optional[str] = None
    ):
        """
        Args:
            group_id: 컨슈머 그룹 ID (예: users_group)
            topics: 구독할 토픽 리스트 (예: ['users'])
            message_handler: 메시지 처리 함수 (dict를 받아서 처리)
            consumer_id: 컨슈머 고유 ID (로깅용)
        """
        self.group_id = group_id
        self.topics = topics
        self.message_handler = message_handler
        self.consumer_id = consumer_id or group_id
        self.running = True

        # 컨슈머 설정
        self.config = {
            'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
            'group.id': group_id,
            'client.id': self.consumer_id,

            # 자동 오프셋 커밋 비활성화 (수동 관리)
            'enable.auto.commit': False,
            'auto.offset.reset': 'earliest',  # 처음부터 읽기

            # 세션 타임아웃
            'session.timeout.ms': 30000,  # 30초
            'heartbeat.interval.ms': 10000,  # 10초
        }

        # 컨슈머 생성
        self.consumer = Consumer(self.config)
        self.consumer.subscribe(topics)

        logger.info(f"[{self.consumer_id}] 컨슈머 초기화 완료")
        logger.info(f"[{self.consumer_id}] 그룹 ID: {group_id}")
        logger.info(f"[{self.consumer_id}] 구독 토픽: {topics}")

    def deserialize_message(self, message) -> dict:
        """메시지를 JSON으로 역직렬화"""
        try:
            value = message.value().decode('utf-8')
            return json.loads(value)
        except json.JSONDecodeError as e:
            logger.error(f"[{self.consumer_id}] JSON 역직렬화 실패: {e}")
            logger.error(f"[{self.consumer_id}] 원본 메시지: {message.value()}")
            raise
        except Exception as e:
            logger.error(f"[{self.consumer_id}] 메시지 디코딩 실패: {e}")
            raise

    def process_message(self, message):
        """메시지 처리 (역직렬화 + 핸들러 호출)"""
        try:
            # 1. 역직렬화
            data = self.deserialize_message(message)

            # 2. 메시지 핸들러 호출 (DB 저장 등)
            self.message_handler(data)

            # 3. 오프셋 커밋 (성공 시에만)
            self.consumer.commit(message=message)

            # 4. 로깅 (간략하게)
            logger.debug(
                f"[{self.consumer_id}] 메시지 처리 완료 - "
                f"토픽: {message.topic()}, "
                f"파티션: {message.partition()}, "
                f"오프셋: {message.offset()}"
            )

        except Exception as e:
            logger.error(
                f"[{self.consumer_id}] 메시지 처리 실패 - "
                f"토픽: {message.topic()}, "
                f"파티션: {message.partition()}, "
                f"오프셋: {message.offset()}, "
                f"에러: {e}"
            )
            # 에러 발생 시에도 오프셋 커밋 (무한 재처리 방지)
            # 실제 운영에서는 DLQ(Dead Letter Queue)로 전송
            self.consumer.commit(message=message)

    def start(self):
        """컨슈머 시작 (무한 루프)"""
        logger.info(f"[{self.consumer_id}] 컨슈머 시작...")

        try:
            while self.running:
                # 메시지 폴링 (타임아웃 1초)
                message = self.consumer.poll(timeout=1.0)

                if message is None:
                    # 메시지 없음
                    continue

                if message.error():
                    # 에러 처리
                    if message.error().code() == KafkaError._PARTITION_EOF:
                        # 파티션 끝에 도달 (정상)
                        logger.debug(
                            f"[{self.consumer_id}] 파티션 끝 도달 - "
                            f"토픽: {message.topic()}, "
                            f"파티션: {message.partition()}"
                        )
                    else:
                        # 실제 에러
                        logger.error(
                            f"[{self.consumer_id}] 카프카 에러: {message.error()}"
                        )
                    continue

                # 정상 메시지 처리
                self.process_message(message)

        except KeyboardInterrupt:
            logger.info(f"[{self.consumer_id}] 종료 신호 수신")

        except Exception as e:
            logger.error(f"[{self.consumer_id}] 예상치 못한 오류: {e}")
            import traceback
            traceback.print_exc()

        finally:
            # 컨슈머 종료
            self.close()

    def stop(self):
        """컨슈머 정지"""
        logger.info(f"[{self.consumer_id}] 컨슈머 정지 중...")
        self.running = False

    def close(self):
        """컨슈머 종료 및 리소스 정리"""
        logger.info(f"[{self.consumer_id}] 컨슈머 종료 중...")
        self.consumer.close()
        logger.info(f"[{self.consumer_id}] 컨슈머 종료 완료")
