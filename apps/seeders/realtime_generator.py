"""
실시간 데이터 생성 시뮬레이터

- 주문 데이터: 2~8초 간격으로 1~5건씩 생성 (무한 루프)
- 상품 데이터: 10~20초 간격으로 100건씩 생성 (무한 루프)
"""

import os
import sys
import time
import random
import threading
from datetime import datetime

# 프로젝트 루트를 sys.path에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from sqlalchemy.orm import Session
from database import crud, database, models
from collect.product_generator import ProductGenerator
from collect.order_generator import OrderGenerator


class RealtimeDataGenerator:
    """실시간 데이터 생성 시뮬레이터"""

    def __init__(self):
        self.running = True
        self.stats = {
            'orders_created': 0,
            'products_created': 0,
            'orders_failed': 0,
            'products_failed': 0,
            'start_time': None
        }
        self.lock = threading.Lock()

    def generate_orders_continuously(self):
        """주문 데이터를 지속적으로 생성 (2~8초 간격, 1~5건씩)"""
        db = database.SessionLocal()
        order_generator = OrderGenerator()

        print("🚀 주문 데이터 생성 스레드 시작...")

        try:
            while self.running:
                # 1. DB에서 유저와 상품 풀 가져오기
                try:
                    users = db.query(models.User).limit(1000).all()
                    products = db.query(models.Product).limit(1000).all()

                    if not users or not products:
                        print("⚠️ 유저 또는 상품 데이터가 없습니다. 먼저 initial_data_seeder.py를 실행하세요.")
                        time.sleep(5)
                        continue

                except Exception as e:
                    print(f"❌ DB 조회 실패: {e}")
                    time.sleep(5)
                    continue

                # 2. 랜덤 개수 결정 (1~5건)
                order_count = random.randint(1, 5)

                # 3. 주문 생성
                success_count = 0
                failed_count = 0

                for _ in range(order_count):
                    try:
                        user = random.choice(users)
                        product = random.choice(products)
                        order_data = order_generator.generate_order(user, product)

                        crud.create_order(db, order_data)
                        success_count += 1

                        with self.lock:
                            self.stats['orders_created'] += 1

                    except Exception as e:
                        failed_count += 1
                        with self.lock:
                            self.stats['orders_failed'] += 1
                        db.rollback()

                # 4. 로그 출력
                timestamp = datetime.now().strftime("%H:%M:%S")
                with self.lock:
                    total_orders = self.stats['orders_created']
                    elapsed = time.time() - self.stats['start_time'] if self.stats['start_time'] else 0
                    tps = total_orders / elapsed if elapsed > 0 else 0

                print(f"[{timestamp}] 🛒 주문 생성: {success_count}/{order_count}건 성공 | "
                      f"누적: {total_orders:,}건 | TPS: {tps:.2f}")

                # 5. 랜덤 대기 (2~8초)
                wait_time = random.uniform(2, 8)
                time.sleep(wait_time)

        except Exception as e:
            print(f"❌ 주문 생성 스레드 오류: {e}")
            import traceback
            traceback.print_exc()
        finally:
            db.close()
            print("🛑 주문 데이터 생성 스레드 종료")

    def generate_products_continuously(self):
        """상품 데이터를 지속적으로 생성 (10~20초 간격, 100건씩)"""
        db = database.SessionLocal()
        product_generator = ProductGenerator()

        print("🚀 상품 데이터 생성 스레드 시작...")

        try:
            while self.running:
                # 1. 100건 생성
                products_list = product_generator.generate_batch(100)

                success_count = 0
                failed_count = 0

                for product_data in products_list:
                    try:
                        # sleep 필드 제거
                        if 'sleep' in product_data:
                            del product_data['sleep']

                        crud.create_product(db, product_data)
                        success_count += 1

                        with self.lock:
                            self.stats['products_created'] += 1

                    except Exception as e:
                        failed_count += 1
                        with self.lock:
                            self.stats['products_failed'] += 1
                        db.rollback()

                # 2. 로그 출력
                timestamp = datetime.now().strftime("%H:%M:%S")
                with self.lock:
                    total_products = self.stats['products_created']
                    elapsed = time.time() - self.stats['start_time'] if self.stats['start_time'] else 0
                    tps = total_products / elapsed if elapsed > 0 else 0

                print(f"[{timestamp}] 📦 상품 생성: {success_count}/100건 성공 | "
                      f"누적: {total_products:,}개 | TPS: {tps:.2f}")

                # 3. 랜덤 대기 (10~20초)
                wait_time = random.uniform(10, 20)
                time.sleep(wait_time)

        except Exception as e:
            print(f"❌ 상품 생성 스레드 오류: {e}")
            import traceback
            traceback.print_exc()
        finally:
            db.close()
            print("🛑 상품 데이터 생성 스레드 종료")

    def print_stats_periodically(self):
        """통계를 주기적으로 출력 (10초마다)"""
        try:
            while self.running:
                time.sleep(10)

                if not self.running:
                    break

                with self.lock:
                    elapsed = time.time() - self.stats['start_time'] if self.stats['start_time'] else 0
                    orders_tps = self.stats['orders_created'] / elapsed if elapsed > 0 else 0
                    products_tps = self.stats['products_created'] / elapsed if elapsed > 0 else 0

                print(f"\n{'='*60}")
                print(f"📊 통계 (경과시간: {elapsed:.1f}초 / {elapsed/60:.1f}분)")
                print(f"{'='*60}")
                print(f"  🛒 주문:  성공 {self.stats['orders_created']:,}건 | "
                      f"실패 {self.stats['orders_failed']}건 | TPS: {orders_tps:.2f}")
                print(f"  📦 상품:  성공 {self.stats['products_created']:,}개 | "
                      f"실패 {self.stats['products_failed']}개 | TPS: {products_tps:.2f}")
                print(f"{'='*60}\n")

        except Exception as e:
            print(f"❌ 통계 출력 스레드 오류: {e}")

    def start(self):
        """실시간 데이터 생성 시작"""
        print("""
    ╔════════════════════════════════════════════════════════════╗
    ║            실시간 데이터 생성 시뮬레이터                    ║
    ╚════════════════════════════════════════════════════════════╝
        """)

        print("📋 생성 규칙:")
        print("  - 🛒 주문: 2~8초 간격으로 1~5건씩 생성")
        print("  - 📦 상품: 10~20초 간격으로 100건씩 생성")
        print("  - Ctrl+C로 중지\n")

        # 시작 시간 기록
        self.stats['start_time'] = time.time()

        # 스레드 생성 및 시작
        order_thread = threading.Thread(target=self.generate_orders_continuously, daemon=True)
        product_thread = threading.Thread(target=self.generate_products_continuously, daemon=True)
        stats_thread = threading.Thread(target=self.print_stats_periodically, daemon=True)

        order_thread.start()
        product_thread.start()
        stats_thread.start()

        print("✅ 실시간 데이터 생성 시작! (Ctrl+C로 중지)\n")

        try:
            # 메인 스레드는 대기 (Ctrl+C까지)
            while True:
                time.sleep(1)

        except KeyboardInterrupt:
            print("\n\n⚠️ 종료 신호 수신. 스레드를 정리하는 중...")
            self.running = False

            # 스레드 종료 대기 (최대 5초)
            order_thread.join(timeout=5)
            product_thread.join(timeout=5)
            stats_thread.join(timeout=5)

            # 최종 통계 출력
            elapsed = time.time() - self.stats['start_time']
            print(f"\n{'#'*60}")
            print("# 📊 최종 통계")
            print(f"{'#'*60}")
            print(f"  총 실행시간: {elapsed:.1f}초 ({elapsed/60:.1f}분)")
            print(f"  🛒 주문 생성: {self.stats['orders_created']:,}건 (실패: {self.stats['orders_failed']})")
            print(f"  📦 상품 생성: {self.stats['products_created']:,}개 (실패: {self.stats['products_failed']})")
            print(f"{'#'*60}\n")

            print("✅ 모든 스레드가 정상 종료되었습니다.")


def main():
    """메인 실행 함수"""
    generator = RealtimeDataGenerator()
    generator.start()


if __name__ == "__main__":
    main()
