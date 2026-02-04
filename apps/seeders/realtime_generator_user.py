"""
실시간 고객 데이터 생성 시뮬레이터

- 고객 데이터: 10초 간격으로 10명씩 생성 (무한 루프)
- Producer → Broker → Consumer → DB 파이프라인
"""

import os
import sys
import time
import threading
from datetime import datetime

# 프로젝트 루트를 sys.path에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.append(project_root)

from collect.user_generator import UserGenerator
from kafka.producer import KafkaProducer
from kafka.config import KAFKA_TOPIC_USERS


class RealtimeUserGenerator:
    """실시간 고객 데이터 생성 시뮬레이터"""

    def __init__(self, batch_size: int = 10, interval: int = 10):
        """
        Args:
            batch_size: 한 번에 생성할 고객 수 (기본값: 10명)
            interval: 생성 간격 (초) (기본값: 10초)
        """
        self.batch_size = batch_size
        self.interval = interval
        self.running = True
        self.stats = {
            'users_created': 0,
            'users_failed': 0,
            'start_time': None
        }
        self.lock = threading.Lock()

    def generate_users_continuously(self):
        """고객 데이터를 지속적으로 생성 - Kafka에만 발행"""
        user_generator = UserGenerator()
        kafka_producer = KafkaProducer()

        print(f"🚀 고객 데이터 생성 스레드 시작 (Kafka 발행 모드)...")
        print(f"   - 배치 크기: {self.batch_size}명")
        print(f"   - 생성 간격: {self.interval}초")

        try:
            while self.running:
                # 1. 고객 데이터 생성
                users_list = user_generator.generate_batch(self.batch_size)

                success_count = 0
                failed_count = 0

                for user_data in users_list:
                    try:
                        # Kafka에만 발행 (DB 저장은 Consumer가 담당)
                        kafka_producer.send_event(
                            topic=KAFKA_TOPIC_USERS,
                            key=user_data['user_id'],
                            data=user_data,
                            event_type='user_created'
                        )
                        success_count += 1

                        with self.lock:
                            self.stats['users_created'] += 1

                    except Exception as e:
                        failed_count += 1
                        with self.lock:
                            self.stats['users_failed'] += 1

                # 2. 로그 출력
                timestamp = datetime.now().strftime("%H:%M:%S")
                with self.lock:
                    total_users = self.stats['users_created']
                    elapsed = time.time() - self.stats['start_time'] if self.stats['start_time'] else 0
                    tps = total_users / elapsed if elapsed > 0 else 0

                print(f"[{timestamp}] 👥 고객 발행: {success_count}/{self.batch_size}명 성공 | "
                      f"누적: {total_users:,}명 | TPS: {tps:.2f}")

                # 3. 대기
                time.sleep(self.interval)

        except Exception as e:
            print(f"❌ 고객 생성 스레드 오류: {e}")
            import traceback
            traceback.print_exc()
        finally:
            kafka_producer.flush()
            print("🛑 고객 데이터 생성 스레드 종료")

    def print_stats_periodically(self):
        """통계를 주기적으로 출력 (30초마다)"""
        try:
            while self.running:
                time.sleep(30)

                if not self.running:
                    break

                with self.lock:
                    elapsed = time.time() - self.stats['start_time'] if self.stats['start_time'] else 0
                    users_tps = self.stats['users_created'] / elapsed if elapsed > 0 else 0

                print(f"\n{'='*60}")
                print(f"📊 통계 (경과시간: {elapsed:.1f}초 / {elapsed/60:.1f}분)")
                print(f"{'='*60}")
                print(f"  👥 고객:  성공 {self.stats['users_created']:,}명 | "
                      f"실패 {self.stats['users_failed']}명 | TPS: {users_tps:.2f}")
                print(f"{'='*60}\n")

        except Exception as e:
            print(f"❌ 통계 출력 스레드 오류: {e}")

    def start(self):
        """실시간 고객 데이터 생성 시작"""
        print(f"""
    ╔════════════════════════════════════════════════════════════╗
    ║            실시간 고객 데이터 생성 시뮬레이터                 ║
    ║        Producer → Broker → Consumer → DB                   ║
    ╚════════════════════════════════════════════════════════════╝
        """)

        print("📋 생성 규칙:")
        print(f"  - 👥 고객: {self.interval}초 간격으로 {self.batch_size}명씩 생성")
        print(f"  - 📡 토픽: {KAFKA_TOPIC_USERS}")
        print("  - Ctrl+C로 중지\n")

        # 시작 시간 기록
        self.stats['start_time'] = time.time()

        # 스레드 생성 및 시작
        user_thread = threading.Thread(target=self.generate_users_continuously, daemon=True)
        stats_thread = threading.Thread(target=self.print_stats_periodically, daemon=True)

        user_thread.start()
        stats_thread.start()

        print("✅ 실시간 고객 데이터 생성 시작! (Ctrl+C로 중지)\n")

        try:
            # 메인 스레드는 대기 (Ctrl+C까지)
            while True:
                time.sleep(1)

        except KeyboardInterrupt:
            print("\n\n⚠️ 종료 신호 수신. 스레드를 정리하는 중...")
            self.running = False

            # 스레드 종료 대기 (최대 5초)
            user_thread.join(timeout=5)
            stats_thread.join(timeout=5)

            # 최종 통계 출력
            elapsed = time.time() - self.stats['start_time']
            print(f"\n{'#'*60}")
            print("# 📊 최종 통계")
            print(f"{'#'*60}")
            print(f"  총 실행시간: {elapsed:.1f}초 ({elapsed/60:.1f}분)")
            print(f"  👥 고객 생성: {self.stats['users_created']:,}명 (실패: {self.stats['users_failed']})")
            print(f"{'#'*60}\n")

            print("✅ 모든 스레드가 정상 종료되었습니다.")


def main():
    """메인 실행 함수"""
    import argparse

    parser = argparse.ArgumentParser(description='실시간 고객 데이터 생성')
    parser.add_argument(
        '--batch-size',
        type=int,
        default=10,
        help='한 번에 생성할 고객 수 (기본값: 10)'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=10,
        help='생성 간격 (초) (기본값: 10)'
    )
    args = parser.parse_args()

    generator = RealtimeUserGenerator(
        batch_size=args.batch_size,
        interval=args.interval
    )
    generator.start()


if __name__ == "__main__":
    main()
