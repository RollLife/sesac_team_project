"""
백그라운드 캐시 워커

- 50초 주기로 DB에서 데이터를 가져와 Redis 캐시 갱신
- 고객: 구매이력 고객 600명 + 미구매 고객 400명
- 상품: 판매율 높은 상품 700개 + 신상품 300개
"""

import os
import sys
import time
import logging
from datetime import datetime
from typing import List, Dict, Any

# 프로젝트 루트를 sys.path에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from sqlalchemy.orm import Session

from database.database import SessionLocal
from database.models import User, Product
from cache.client import get_redis_client
from cache.config import CACHE_CONFIG, REDIS_ENABLED

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CacheWorker:
    """Redis 캐시 갱신 워커 (구매이력/미구매 분리 적재)"""

    # 고객 캐시 비율
    USER_PURCHASED_LIMIT = 600
    USER_NEW_LIMIT = 400

    # 상품 캐시 비율
    PRODUCT_POPULAR_LIMIT = 700
    PRODUCT_NEW_LIMIT = 300

    def __init__(self):
        self.redis_client = get_redis_client()
        self.refresh_interval = CACHE_CONFIG['refresh_interval']  # 50초
        self.batch_size = CACHE_CONFIG['batch_size']  # 1000개
        self.running = True

        # 통계
        self.stats = {
            'users_cached': 0,
            'products_cached': 0,
            'refresh_count': 0,
            'start_time': None,
        }

    def fetch_users(self, db: Session) -> List[Dict[str, Any]]:
        """
        구매이력/미구매 분리 적재로 유저 데이터 조회
        - 구매이력 고객: last_ordered_at 오래된 순 (기본 600명)
        - 미구매 고객: created_at 최신순 (최대 400명)
        - 미구매 부족 시 구매이력 풀 확대, 합계 항상 1000명
        """
        # 1. 미구매 고객 (최대 400명, created_at 최신순)
        new_users = db.query(User).filter(
            User.last_ordered_at.is_(None)
        ).order_by(
            User.created_at.desc()
        ).limit(self.USER_NEW_LIMIT).all()

        # 2. 미구매 부족분만큼 구매이력 풀 확대
        purchased_limit = self.batch_size - len(new_users)

        # 3. 구매이력 고객 (last_ordered_at 오래된 순)
        purchased_users = db.query(User).filter(
            User.last_ordered_at.isnot(None)
        ).order_by(
            User.last_ordered_at.asc()
        ).limit(purchased_limit).all()

        # 4. 합치기
        all_users = purchased_users + new_users
        users = [self._user_to_dict(user) for user in all_users]

        logger.info(
            f"유저 조회 완료: 구매이력 {len(purchased_users)}명 + "
            f"미구매 {len(new_users)}명 = 총 {len(users)}명"
        )
        return users

    def fetch_products(self, db: Session) -> List[Dict[str, Any]]:
        """
        판매율/신상품 분리 적재로 상품 데이터 조회
        - 판매율 높은 상품: order_count 높은 순 (기본 700개)
        - 신상품: order_count == 0, created_at 최신순 (최대 300개)
        - 신상품 부족 시 판매 상품 풀 확대, 합계 항상 1000개
        """
        # 1. 신상품 (최대 300개, created_at 최신순)
        new_products = db.query(Product).filter(
            Product.order_count == 0
        ).order_by(
            Product.created_at.desc()
        ).limit(self.PRODUCT_NEW_LIMIT).all()

        # 2. 신상품 부족분만큼 판매 상품 풀 확대
        popular_limit = self.batch_size - len(new_products)

        # 3. 판매율 높은 상품 (order_count 높은 순)
        popular_products = db.query(Product).filter(
            Product.order_count > 0
        ).order_by(
            Product.order_count.desc()
        ).limit(popular_limit).all()

        # 4. 합치기
        all_products = popular_products + new_products
        products = [self._product_to_dict(product) for product in all_products]

        logger.info(
            f"상품 조회 완료: 인기 {len(popular_products)}개 + "
            f"신상품 {len(new_products)}개 = 총 {len(products)}개"
        )
        return products

    def _user_to_dict(self, user: User) -> Dict[str, Any]:
        """User 객체를 딕셔너리로 변환 (구매 성향 계산에 필요한 필드 포함)"""
        return {
            'user_id': user.user_id,
            'name': user.name,
            'gender': user.gender,
            'age': user.age,
            'birth_year': user.birth_year,
            'address': user.address,
            'address_district': user.address_district,
            'email': user.email,
            'grade': user.grade,
            'status': user.status,
            'marketing_agree': user.marketing_agree,
            'last_ordered_at': user.last_ordered_at.isoformat() if user.last_ordered_at else None,
            'random_seed': user.random_seed,
            'created_at': user.created_at.isoformat() if user.created_at else None,
        }

    def _product_to_dict(self, product: Product) -> Dict[str, Any]:
        """Product 객체를 딕셔너리로 변환"""
        return {
            'product_id': product.product_id,
            'category': product.category,
            'name': product.name,
            'org_price': product.org_price,
            'price': product.price,
            'discount_rate': product.discount_rate,
            'description': product.description,
            'brand': product.brand,
            'stock': product.stock,
            'order_count': product.order_count,
            'created_at': product.created_at.isoformat() if product.created_at else None,
        }

    def refresh_cache(self):
        """캐시 갱신 (1회 실행)"""
        db = SessionLocal()
        try:
            # 1. DB에서 구매이력/미구매 분리 적재로 데이터 조회
            users = self.fetch_users(db)
            products = self.fetch_products(db)

            # 2. Redis에 캐시 저장
            if users:
                self.redis_client.set_users_cache(users)
                self.stats['users_cached'] = len(users)

            if products:
                self.redis_client.set_products_cache(products)
                self.stats['products_cached'] = len(products)

            self.stats['refresh_count'] += 1

            # 3. 통계 로그
            logger.info(
                f"캐시 갱신 #{self.stats['refresh_count']} 완료 - "
                f"유저: {len(users)}명, 상품: {len(products)}개"
            )

        except Exception as e:
            logger.error(f"캐시 갱신 실패: {e}")
            import traceback
            traceback.print_exc()
        finally:
            db.close()

    def start(self):
        """워커 시작 (무한 루프)"""
        if not REDIS_ENABLED:
            logger.error("Redis가 비활성화되어 있습니다 (REDIS_ENABLED=false)")
            return

        if not self.redis_client.is_connected():
            logger.error("Redis 연결 실패. 워커를 시작할 수 없습니다.")
            return

        print("""
╔════════════════════════════════════════════════════════════╗
║     Redis 캐시 워커 (구매이력/미구매 분리 적재)              ║
╚════════════════════════════════════════════════════════════╝
        """)
        print(f"📋 설정:")
        print(f"  - 갱신 주기: {self.refresh_interval}초")
        print(f"  - 배치 크기: {self.batch_size}개")
        print(f"  - Ctrl+C로 중지\n")

        self.stats['start_time'] = time.time()

        # 최초 1회 즉시 실행
        logger.info("최초 캐시 로드 시작...")
        self.refresh_cache()

        try:
            while self.running:
                # 갱신 주기만큼 대기
                time.sleep(self.refresh_interval)

                if not self.running:
                    break

                # 캐시 갱신
                self.refresh_cache()

        except KeyboardInterrupt:
            logger.info("종료 신호 수신...")
            self.running = False

        # 최종 통계
        elapsed = time.time() - self.stats['start_time']
        print(f"\n{'='*60}")
        print(f"📊 최종 통계")
        print(f"{'='*60}")
        print(f"  총 실행 시간: {elapsed:.1f}초 ({elapsed/60:.1f}분)")
        print(f"  갱신 횟수: {self.stats['refresh_count']}회")
        print(f"  마지막 캐시: 유저 {self.stats['users_cached']}명, 상품 {self.stats['products_cached']}개")
        print(f"{'='*60}\n")


def main():
    """메인 실행 함수"""
    worker = CacheWorker()
    worker.start()


if __name__ == "__main__":
    main()
