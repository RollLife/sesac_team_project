"""Order Topic Consumer - orders_group"""

import sys
import os

# 프로젝트 루트를 sys.path에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.append(project_root)

import logging
from kafka.consumer import KafkaConsumerBase
from kafka.config import KAFKA_TOPIC_ORDERS
from database import crud, database, models

logger = logging.getLogger(__name__)


class OrderConsumer:
    """주문 토픽 컨슈머"""

    def __init__(self, consumer_id: str = "order_consumer_1"):
        """
        Args:
            consumer_id: 컨슈머 고유 ID (예: order_consumer_1, order_consumer_2, order_consumer_3)
        """
        self.consumer_id = consumer_id
        self.db = database.SessionLocal()

        # 메시지 핸들러 정의
        def handle_order_message(data: dict):
            """주문 메시지 처리 (PostgreSQL에 저장) - Producer가 역정규화 완료한 데이터"""
            try:
                # 중첩된 order 데이터 추출
                order_data = data.get('order', data)

                # 1. 이미 존재하는지 확인 (중복 방지)
                existing_order = crud.get_order(self.db, order_data['order_id'])

                if existing_order:
                    logger.debug(
                        f"[{self.consumer_id}] 이미 존재하는 주문: {order_data['order_id']}"
                    )
                    return

                # 2. DB에 직접 저장 (crud.create_order는 user/product 검증을 하므로 직접 저장)
                # Producer가 이미 역정규화 데이터를 포함해서 보내므로 검증 불필요
                db_order = models.Order(**order_data)
                self.db.add(db_order)
                self.db.commit()
                self.db.refresh(db_order)

                logger.info(
                    f"[{self.consumer_id}] 주문 저장 완료: {order_data['order_id']}"
                )

            except Exception as e:
                logger.error(
                    f"[{self.consumer_id}] 주문 저장 실패: {data.get('order', {}).get('order_id', 'unknown')} - {e}"
                )
                self.db.rollback()
                raise

        # 카프카 컨슈머 생성
        self.consumer = KafkaConsumerBase(
            group_id="orders_group",
            topics=[KAFKA_TOPIC_ORDERS],
            message_handler=handle_order_message,
            consumer_id=self.consumer_id
        )

    def start(self):
        """컨슈머 시작"""
        logger.info(f"[{self.consumer_id}] 주문 컨슈머 시작...")
        try:
            self.consumer.start()
        finally:
            self.db.close()

    def stop(self):
        """컨슈머 정지"""
        self.consumer.stop()


def main():
    """메인 실행 함수"""
    import argparse

    parser = argparse.ArgumentParser(description='주문 토픽 컨슈머')
    parser.add_argument(
        '--id',
        type=str,
        default='order_consumer_1',
        help='컨슈머 ID (예: order_consumer_1, order_consumer_2, order_consumer_3)'
    )
    args = parser.parse_args()

    consumer = OrderConsumer(consumer_id=args.id)
    consumer.start()


if __name__ == "__main__":
    main()
