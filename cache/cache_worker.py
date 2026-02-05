"""
백그라운드 캐시 워커 (Aging 기법)

- 50초 주기로 DB에서 데이터를 가져와 Redis 캐시 갱신
- Aging 기법: 신규 50% + 오래된 것 50% 비율로 가져옴
- 기아현상 방지: 모든 데이터가 순환될 기회 제공
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
    """Redis 캐시 갱신 워커 (Aging 기법 적용)"""

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

    def fetch_users_with_aging(self, db: Session) -> List[Dict[str, Any]]:
        """
        Aging 기법으로 유저 데이터 조회
        - last_cached_at IS NULL (미캐싱) 우선, 그 다음 last_cached_at 오래된 순
        - 항상 batch_size(1000)개를 가져와서 테이블 전체를 순환
        """
        fetched_users = db.query(User).order_by(
            User.last_cached_at.asc().nullsfirst()
        ).limit(self.batch_size).all()

        users = []
        user_ids = []
        for user in fetched_users:
            users.append(self._user_to_dict(user))
            user_ids.append(user.user_id)

        if user_ids:
            now = datetime.now()
            db.query(User).filter(
                User.user_id.in_(user_ids)
            ).update(
                {User.last_cached_at: now},
                synchronize_session=False
            )
            db.commit()

        logger.info(f"유저 조회 완료: 총 {len(users)}명")
        return users

    def fetch_products_with_aging(self, db: Session) -> List[Dict[str, Any]]:
        """
        Aging 기법으로 상품 데이터 조회
        - last_cached_at IS NULL (미캐싱) 우선, 그 다음 last_cached_at 오래된 순
        - 항상 batch_size(1000)개를 가져와서 테이블 전체를 순환
        """
        fetched_products = db.query(Product).order_by(
            Product.last_cached_at.asc().nullsfirst()
        ).limit(self.batch_size).all()

        products = []
        product_ids = []
        for product in fetched_products:
            products.append(self._product_to_dict(product))
            product_ids.append(product.product_id)

        if product_ids:
            now = datetime.now()
            db.query(Product).filter(
                Product.product_id.in_(product_ids)
            ).update(
                {Product.last_cached_at: now},
                synchronize_session=False
            )
            db.commit()

        logger.info(f"상품 조회 완료: 총 {len(products)}개")
        return products

    def _user_to_dict(self, user: User) -> Dict[str, Any]:
        """User 객체를 딕셔너리로 변환"""
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
            'created_at': product.created_at.isoformat() if product.created_at else None,
        }

    def refresh_cache(self):
        """캐시 갱신 (1회 실행)"""
        db = SessionLocal()
        try:
            # 1. DB에서 Aging 기법으로 데이터 조회
            users = self.fetch_users_with_aging(db)
            products = self.fetch_products_with_aging(db)

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
║            Redis 캐시 워커 (Aging 기법)                     ║
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
