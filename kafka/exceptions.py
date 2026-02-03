"""Kafka custom exceptions"""


class KafkaConnectionError(Exception):
    """Kafka 연결 실패"""
    pass


class KafkaPublishError(Exception):
    """메시지 발행 실패"""
    pass
