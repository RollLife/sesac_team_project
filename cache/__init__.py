"""Redis module for caching with Aging strategy"""
from .config import REDIS_ENABLED, CACHE_CONFIG
from .client import RedisClient, get_redis_client

__all__ = [
    'REDIS_ENABLED',
    'CACHE_CONFIG',
    'RedisClient',
    'get_redis_client',
]
