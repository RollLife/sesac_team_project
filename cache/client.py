"""Redis Client with connection management and error handling"""
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

import redis
from redis.exceptions import ConnectionError, TimeoutError, RedisError

from .config import (
    REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD,
    REDIS_ENABLED, CACHE_CONFIG
)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RedisClient:
    """Redis 클라이언트 (싱글톤 패턴)"""

    _instance: Optional['RedisClient'] = None
    _client: Optional[redis.Redis] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._client is None:
            self._connect()

    def _connect(self):
        """Redis 연결"""
        if not REDIS_ENABLED:
            logger.warning("Redis가 비활성화되어 있습니다 (REDIS_ENABLED=false)")
            return

        try:
            self._client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                password=REDIS_PASSWORD,
                decode_responses=True,  # 문자열로 디코딩
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True,
            )
            # 연결 테스트
            self._client.ping()
            logger.info(f"Redis 연결 성공: {REDIS_HOST}:{REDIS_PORT}")
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Redis 연결 실패: {e}")
            self._client = None

    @property
    def client(self) -> Optional[redis.Redis]:
        """Redis 클라이언트 반환 (연결 확인 후)"""
        if self._client is None:
            self._connect()
        return self._client

    def is_connected(self) -> bool:
        """연결 상태 확인"""
        if self._client is None:
            return False
        try:
            self._client.ping()
            return True
        except (ConnectionError, TimeoutError, RedisError):
            return False

    def reconnect(self):
        """재연결"""
        logger.info("Redis 재연결 시도...")
        self._client = None
        self._connect()

    # ========================================
    # 캐시 데이터 저장/조회 메서드
    # ========================================

    def set_users_cache(self, users: List[Dict[str, Any]]) -> bool:
        """유저 캐시 저장 (기존 데이터 교체)"""
        if not self.is_connected():
            logger.error("Redis 연결 안됨 - 유저 캐시 저장 실패")
            return False

        try:
            key = CACHE_CONFIG['users_key']
            pipe = self._client.pipeline()

            # 기존 캐시 삭제 후 새로 저장
            pipe.delete(key)
            for user in users:
                # user_id를 키로, 전체 데이터를 JSON으로 저장
                pipe.hset(key, user['user_id'], json.dumps(user, default=str))

            # 메타데이터 업데이트
            meta_key = CACHE_CONFIG['users_meta_key']
            pipe.hset(meta_key, mapping={
                'count': len(users),
                'updated_at': datetime.now().isoformat(),
            })

            pipe.execute()
            logger.info(f"유저 캐시 저장 완료: {len(users)}건")
            return True

        except RedisError as e:
            logger.error(f"유저 캐시 저장 실패: {e}")
            return False

    def set_products_cache(self, products: List[Dict[str, Any]]) -> bool:
        """상품 캐시 저장 (기존 데이터 교체)"""
        if not self.is_connected():
            logger.error("Redis 연결 안됨 - 상품 캐시 저장 실패")
            return False

        try:
            key = CACHE_CONFIG['products_key']
            pipe = self._client.pipeline()

            # 기존 캐시 삭제 후 새로 저장
            pipe.delete(key)
            for product in products:
                pipe.hset(key, product['product_id'], json.dumps(product, default=str))

            # 메타데이터 업데이트
            meta_key = CACHE_CONFIG['products_meta_key']
            pipe.hset(meta_key, mapping={
                'count': len(products),
                'updated_at': datetime.now().isoformat(),
            })

            pipe.execute()
            logger.info(f"상품 캐시 저장 완료: {len(products)}건")
            return True

        except RedisError as e:
            logger.error(f"상품 캐시 저장 실패: {e}")
            return False

    def add_user_to_cache(self, user: Dict[str, Any]) -> bool:
        """단일 유저를 캐시에 추가 (신규 데이터 즉시 반영)"""
        if not self.is_connected():
            return False

        try:
            key = CACHE_CONFIG['users_key']
            self._client.hset(key, user['user_id'], json.dumps(user, default=str))
            return True
        except RedisError as e:
            logger.error(f"유저 캐시 추가 실패: {e}")
            return False

    def add_product_to_cache(self, product: Dict[str, Any]) -> bool:
        """단일 상품을 캐시에 추가 (신규 데이터 즉시 반영)"""
        if not self.is_connected():
            return False

        try:
            key = CACHE_CONFIG['products_key']
            self._client.hset(key, product['product_id'], json.dumps(product, default=str))
            return True
        except RedisError as e:
            logger.error(f"상품 캐시 추가 실패: {e}")
            return False

    def get_random_user(self) -> Optional[Dict[str, Any]]:
        """캐시에서 랜덤 유저 1명 조회"""
        if not self.is_connected():
            return None

        try:
            key = CACHE_CONFIG['users_key']
            # HRANDFIELD로 랜덤 키 조회 (Redis 6.2+)
            random_key = self._client.hrandfield(key, 1)
            if random_key:
                data = self._client.hget(key, random_key[0])
                if data:
                    return json.loads(data)
            return None
        except RedisError as e:
            logger.error(f"랜덤 유저 조회 실패: {e}")
            return None

    def get_random_product(self) -> Optional[Dict[str, Any]]:
        """캐시에서 랜덤 상품 1개 조회"""
        if not self.is_connected():
            return None

        try:
            key = CACHE_CONFIG['products_key']
            random_key = self._client.hrandfield(key, 1)
            if random_key:
                data = self._client.hget(key, random_key[0])
                if data:
                    return json.loads(data)
            return None
        except RedisError as e:
            logger.error(f"랜덤 상품 조회 실패: {e}")
            return None

    def get_random_users(self, count: int = 10) -> List[Dict[str, Any]]:
        """캐시에서 랜덤 유저 여러 명 조회"""
        if not self.is_connected():
            return []

        try:
            key = CACHE_CONFIG['users_key']
            random_keys = self._client.hrandfield(key, count)
            if not random_keys:
                return []

            users = []
            for k in random_keys:
                data = self._client.hget(key, k)
                if data:
                    users.append(json.loads(data))
            return users
        except RedisError as e:
            logger.error(f"랜덤 유저 조회 실패: {e}")
            return []

    def get_random_products(self, count: int = 10) -> List[Dict[str, Any]]:
        """캐시에서 랜덤 상품 여러 개 조회"""
        if not self.is_connected():
            return []

        try:
            key = CACHE_CONFIG['products_key']
            random_keys = self._client.hrandfield(key, count)
            if not random_keys:
                return []

            products = []
            for k in random_keys:
                data = self._client.hget(key, k)
                if data:
                    products.append(json.loads(data))
            return products
        except RedisError as e:
            logger.error(f"랜덤 상품 조회 실패: {e}")
            return []

    def get_cache_stats(self) -> Dict[str, Any]:
        """캐시 통계 조회"""
        if not self.is_connected():
            return {'connected': False}

        try:
            users_meta = self._client.hgetall(CACHE_CONFIG['users_meta_key'])
            products_meta = self._client.hgetall(CACHE_CONFIG['products_meta_key'])

            return {
                'connected': True,
                'users': {
                    'count': int(users_meta.get('count', 0)),
                    'updated_at': users_meta.get('updated_at', 'N/A'),
                },
                'products': {
                    'count': int(products_meta.get('count', 0)),
                    'updated_at': products_meta.get('updated_at', 'N/A'),
                },
            }
        except RedisError as e:
            logger.error(f"캐시 통계 조회 실패: {e}")
            return {'connected': False, 'error': str(e)}


# 전역 인스턴스 (편의용)
def get_redis_client() -> RedisClient:
    """Redis 클라이언트 인스턴스 반환"""
    return RedisClient()
