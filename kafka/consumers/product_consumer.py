"""Product Topic Consumer - products_group"""

import sys
import os

# 프로젝트 루트를 sys.path에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.append(project_root)

import logging
from kafka.consumer import KafkaConsumerBase
from kafka.config import KAFKA_TOPIC_PRODUCTS
from database import crud, database, models

logger = logging.getLogger(__name__)


class ProductConsumer:
    """상품 토픽 컨슈머"""

    def __init__(self, consumer_id: str = "product_consumer_1"):
        """
        Args:
            consumer_id: 컨슈머 고유 ID (예: product_consumer_1, product_consumer_2, product_consumer_3)
        """
        self.consumer_id = consumer_id
        self.db = database.SessionLocal()

        # 메시지 핸들러 정의
        def handle_product_message(data: dict):
            """상품 메시지 처리 (PostgreSQL에 저장) - Producer가 보낸 데이터"""
            try:
                # 중첩된 product 데이터 추출
                product_data = data.get('product', data)

                # 1. 이미 존재하는지 확인 (중복 방지)
                existing_product = crud.get_product(self.db, product_data['product_id'])

                if existing_product:
                    logger.debug(
                        f"[{self.consumer_id}] 이미 존재하는 상품: {product_data['product_id']}"
                    )
                    return

                # 2. DB에 직접 저장 (Kafka 재발행 방지)
                db_product = models.Product(**product_data)
                self.db.add(db_product)
                self.db.commit()
                self.db.refresh(db_product)

                logger.info(
                    f"[{self.consumer_id}] 상품 저장 완료: {product_data['product_id']}"
                )

            except Exception as e:
                logger.error(
                    f"[{self.consumer_id}] 상품 저장 실패: {data.get('product', {}).get('product_id', 'unknown')} - {e}"
                )
                self.db.rollback()
                raise

        # 카프카 컨슈머 생성
        self.consumer = KafkaConsumerBase(
            group_id="products_group",
            topics=[KAFKA_TOPIC_PRODUCTS],
            message_handler=handle_product_message,
            consumer_id=self.consumer_id
        )

    def start(self):
        """컨슈머 시작"""
        logger.info(f"[{self.consumer_id}] 상품 컨슈머 시작...")
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

    parser = argparse.ArgumentParser(description='상품 토픽 컨슈머')
    parser.add_argument(
        '--id',
        type=str,
        default='product_consumer_1',
        help='컨슈머 ID (예: product_consumer_1, product_consumer_2, product_consumer_3)'
    )
    args = parser.parse_args()

    consumer = ProductConsumer(consumer_id=args.id)
    consumer.start()


if __name__ == "__main__":
    main()
