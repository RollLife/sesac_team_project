"""
Redis 실시간 모니터링 스크립트
- Redis 상태 및 활동을 실시간으로 로깅
- 캐시 히트/미스, 메모리 사용량, 연결 수 등 모니터링
- 50초 주기 카운트 및 교체 횟수 표시
"""

import os
import sys
import time
import logging
from datetime import datetime

# 프로젝트 루트를 sys.path에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import redis

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - REDIS_MONITOR - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Redis 설정
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
MONITOR_INTERVAL = int(os.getenv('REDIS_MONITOR_INTERVAL', 1))  # 1초마다 (카운트용)
CACHE_REFRESH_INTERVAL = int(os.getenv('CACHE_REFRESH_INTERVAL', 50))  # 캐시 갱신 주기


class RedisMonitor:
    """Redis 실시간 모니터"""

    def __init__(self):
        self.client = None
        self.prev_stats = {}
        self.replacement_count = -1  # 교체 횟수 (-1부터 시작, 첫 로드시 0)
        self.second_count = 0  # 1~50초 카운트
        self.initial_load_done = False  # 초기 로드 완료 여부
        self.connect()

    def connect(self):
        """Redis 연결"""
        try:
            self.client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                decode_responses=True
            )
            self.client.ping()
            logger.info(f"Redis 연결 성공 ({REDIS_HOST}:{REDIS_PORT})")
            return True
        except Exception as e:
            logger.error(f"Redis 연결 실패: {e}")
            return False

    def get_stats(self):
        """Redis 통계 조회"""
        try:
            info = self.client.info()

            # 주요 통계 추출
            stats = {
                # 메모리
                'used_memory_human': info.get('used_memory_human', 'N/A'),
                'used_memory_peak_human': info.get('used_memory_peak_human', 'N/A'),

                # 연결
                'connected_clients': info.get('connected_clients', 0),

                # 명령어 통계
                'total_commands_processed': info.get('total_commands_processed', 0),
                'instantaneous_ops_per_sec': info.get('instantaneous_ops_per_sec', 0),

                # 키스페이스 히트/미스
                'keyspace_hits': info.get('keyspace_hits', 0),
                'keyspace_misses': info.get('keyspace_misses', 0),

                # DB 키 수
                'db0_keys': 0,
            }

            # DB0 키 수 조회
            if 'db0' in info:
                stats['db0_keys'] = info['db0'].get('keys', 0)

            return stats
        except Exception as e:
            logger.error(f"통계 조회 실패: {e}")
            return None

    def get_cache_keys_info(self):
        """캐시 키 정보 조회"""
        try:
            users_count = self.client.hlen('cache:users')
            products_count = self.client.hlen('cache:products')
            return users_count, products_count
        except Exception as e:
            return 0, 0

    def calculate_rates(self, current_stats):
        """초당 변화율 계산"""
        rates = {}

        if self.prev_stats:
            time_diff = MONITOR_INTERVAL

            # 명령어 처리율
            cmd_diff = current_stats['total_commands_processed'] - self.prev_stats.get('total_commands_processed', 0)
            rates['commands_per_sec'] = cmd_diff / time_diff if time_diff > 0 else 0

            # 히트율 변화
            hits_diff = current_stats['keyspace_hits'] - self.prev_stats.get('keyspace_hits', 0)
            misses_diff = current_stats['keyspace_misses'] - self.prev_stats.get('keyspace_misses', 0)
            total_requests = hits_diff + misses_diff

            rates['hit_rate'] = (hits_diff / total_requests * 100) if total_requests > 0 else 100.0
            rates['requests_per_sec'] = total_requests / time_diff if time_diff > 0 else 0
        else:
            rates['commands_per_sec'] = current_stats['instantaneous_ops_per_sec']
            total = current_stats['keyspace_hits'] + current_stats['keyspace_misses']
            rates['hit_rate'] = (current_stats['keyspace_hits'] / total * 100) if total > 0 else 100.0
            rates['requests_per_sec'] = 0

        self.prev_stats = current_stats.copy()
        return rates

    def check_data_replacement(self, users_count, products_count):
        """데이터 교체 감지"""
        # 캐시에 데이터가 있는지 확인
        has_data = users_count > 0 and products_count > 0

        # 초기 로드 감지 (처음으로 데이터가 채워진 경우)
        if not self.initial_load_done and has_data:
            self.initial_load_done = True
            self.replacement_count = 0
            self.second_count = 0
            return True

        # 이후에는 50초마다 교체 감지
        if self.initial_load_done and self.second_count >= CACHE_REFRESH_INTERVAL:
            self.replacement_count += 1
            self.second_count = 0
            return True

        return False

    def print_status(self):
        """상태 출력"""
        stats = self.get_stats()
        if not stats:
            return

        rates = self.calculate_rates(stats)
        users_count, products_count = self.get_cache_keys_info()

        # 데이터 교체 감지
        was_replaced = self.check_data_replacement(users_count, products_count)

        timestamp = datetime.now().strftime("%H:%M:%S")

        # 교체가 발생한 경우 특별 메시지 출력
        if was_replaced:
            logger.info("=" * 70)
            logger.info(f"🔄 {self.replacement_count}번째 교체 완료! (users={users_count}, products={products_count})")
            logger.info("=" * 70)

        # 카운트 증가
        self.second_count += MONITOR_INTERVAL

        # 진행률 바 생성 (ASCII 문자 사용)
        progress = min(self.second_count, CACHE_REFRESH_INTERVAL)
        bar_length = 20
        filled = int(bar_length * progress / CACHE_REFRESH_INTERVAL)
        bar = "#" * filled + "-" * (bar_length - filled)

        # 상태 로그 출력
        logger.info(
            f"[{timestamp}] "
            f"[{progress:2d}/{CACHE_REFRESH_INTERVAL}s {bar}] | "
            f"MEM: {stats['used_memory_human']} | "
            f"OPS/s: {stats['instantaneous_ops_per_sec']:3d} | "
            f"HIT: {rates['hit_rate']:.1f}% | "
            f"CACHE: users={users_count}, products={products_count} | "
            f"교체: {self.replacement_count}회"
        )

    def run(self):
        """모니터링 실행"""
        logger.info("=" * 70)
        logger.info("Redis 실시간 모니터링 시작")
        logger.info(f"모니터링 간격: {MONITOR_INTERVAL}초 | 캐시 갱신 주기: {CACHE_REFRESH_INTERVAL}초")
        logger.info("=" * 70)

        try:
            while True:
                self.print_status()
                time.sleep(MONITOR_INTERVAL)
        except KeyboardInterrupt:
            logger.info("모니터링 종료")
        except Exception as e:
            logger.error(f"모니터링 오류: {e}")
            import traceback
            traceback.print_exc()


def main():
    """메인 함수"""
    # Redis 연결 대기
    retry_count = 0
    max_retries = 30

    while retry_count < max_retries:
        try:
            test_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)
            test_client.ping()
            break
        except:
            retry_count += 1
            logger.info(f"Redis 연결 대기 중... ({retry_count}/{max_retries})")
            time.sleep(2)

    if retry_count >= max_retries:
        logger.error("Redis 연결 실패. 종료합니다.")
        return

    monitor = RedisMonitor()
    monitor.run()


if __name__ == "__main__":
    main()
