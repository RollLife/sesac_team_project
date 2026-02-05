"""Kafka 연결 테스트 스크립트"""
from kafka.producer import KafkaProducer
from kafka.config import KAFKA_BOOTSTRAP_SERVERS


def test_connection():
    """Kafka 연결 테스트"""
    try:
        print(f"Kafka 연결 시도: {KAFKA_BOOTSTRAP_SERVERS}")
        producer = KafkaProducer()
        print("✅ Kafka 연결 성공!")

        # 연결 종료
        producer.close()
        return True

    except Exception as e:
        print(f"❌ Kafka 연결 실패: {e}")
        return False


if __name__ == "__main__":
    test_connection()
