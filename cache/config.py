"""Redis configuration settings"""
import os
from dotenv import load_dotenv

load_dotenv()

# Redis 연결 설정
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', None)

# Redis 활성화 플래그
REDIS_ENABLED = os.getenv('REDIS_ENABLED', 'true').lower() == 'true'

# 캐시 설정
CACHE_CONFIG = {
    # 캐시 갱신 주기 (초)
    'refresh_interval': int(os.getenv('CACHE_REFRESH_INTERVAL', 50)),

    # 한 번에 가져올 데이터 개수
    'batch_size': int(os.getenv('CACHE_BATCH_SIZE', 1000)),

    # 캐시 키 이름
    'users_key': 'cache:users',
    'products_key': 'cache:products',

    # 캐시 메타데이터 키
    'users_meta_key': 'cache:users:meta',
    'products_meta_key': 'cache:products:meta',
}

# Redis 연결 URL (대체 방식)
def get_redis_url():
    """Redis 연결 URL 생성"""
    if REDIS_PASSWORD:
        return f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    return f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
