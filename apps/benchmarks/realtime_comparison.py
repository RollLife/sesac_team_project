"""
실시간 데이터 생성 시나리오에서 카프카 ON/OFF 성능 비교

- 일정 시간 동안 실시간 데이터 생성 (주문 + 상품)
- 카프카 OFF vs ON 성능 비교
- 결과 리포트 생성
"""

import os
import sys
import time
import random
import threading
from datetime import datetime
from typing import Dict
from tabulate import tabulate

# 프로젝트 루트를 sys.path에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from sqlalchemy.orm import Session
from database import crud, database, models
from collect.product_generator import ProductGenerator
from collect.order_generator import OrderGenerator


class RealtimeBenchmark:
    """실시간 데이터 생성 벤치마크"""

    def __init__(self, duration_seconds: int = 60):
        """
        Args:
            duration_seconds: 테스트 지속 시간 (초)
        """
        self.duration = duration_seconds
        self.running = True
        self.stats = {
            'orders_created': 0,
            'products_created': 0,
            'orders_failed': 0,
            'products_failed': 0,
            'start_time': None,
            'end_time': None
        }
        self.lock = threading.Lock()

    def set_kafka_enabled(self, enabled: bool):
        """카프카 활성화/비활성화 설정"""
        os.environ['KAFKA_ENABLED'] = 'true' if enabled else 'false'

        # crud 모듈 다시 로드하여 설정 반영
        import importlib
        import kafka.config
        importlib.reload(kafka.config)

        import database.crud as crud_module
        crud_module.KAFKA_ENABLED = enabled

        status = "활성화" if enabled else "비활성화"
        print(f"⚙️  카프카 {status} 설정 완료")

    def generate_orders_thread(self):
        """주문 데이터 생성 스레드 (2~8초 간격, 1~5건씩)"""
        db = database.SessionLocal()
        order_generator = OrderGenerator()

        try:
            while self.running:
                # 유저와 상품 풀 가져오기
                try:
                    users = db.query(models.User).limit(1000).all()
                    products = db.query(models.Product).limit(1000).all()

                    if not users or not products:
                        time.sleep(5)
                        continue

                except Exception as e:
                    time.sleep(5)
                    continue

                # 랜덤 개수 결정 (1~5건)
                order_count = random.randint(1, 5)

                # 주문 생성
                success_count = 0
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
                        with self.lock:
                            self.stats['orders_failed'] += 1
                        db.rollback()

                # 랜덤 대기 (2~8초)
                wait_time = random.uniform(2, 8)
                time.sleep(wait_time)

        finally:
            db.close()

    def generate_products_thread(self):
        """상품 데이터 생성 스레드 (10~20초 간격, 100건씩)"""
        db = database.SessionLocal()
        product_generator = ProductGenerator()

        try:
            while self.running:
                # 100건 생성
                products_list = product_generator.generate_batch(100)

                success_count = 0
                for product_data in products_list:
                    try:
                        if 'sleep' in product_data:
                            del product_data['sleep']
                        crud.create_product(db, product_data)
                        success_count += 1
                        with self.lock:
                            self.stats['products_created'] += 1
                    except Exception as e:
                        with self.lock:
                            self.stats['products_failed'] += 1
                        db.rollback()

                # 랜덤 대기 (10~20초)
                wait_time = random.uniform(10, 20)
                time.sleep(wait_time)

        finally:
            db.close()

    def run_test(self, kafka_enabled: bool) -> Dict:
        """
        지정된 시간 동안 실시간 데이터 생성 테스트 실행

        Args:
            kafka_enabled: 카프카 활성화 여부

        Returns:
            테스트 결과 딕셔너리
        """
        kafka_status = "ON" if kafka_enabled else "OFF"
        print(f"\n{'='*60}")
        print(f"🚀 실시간 데이터 생성 테스트 시작")
        print(f"   카프카: {kafka_status} | 지속시간: {self.duration}초 ({self.duration/60:.1f}분)")
        print(f"{'='*60}\n")

        # 카프카 설정
        self.set_kafka_enabled(kafka_enabled)

        # 통계 초기화
        self.running = True
        self.stats = {
            'orders_created': 0,
            'products_created': 0,
            'orders_failed': 0,
            'products_failed': 0,
            'start_time': time.time(),
            'end_time': None
        }

        # 스레드 시작
        order_thread = threading.Thread(target=self.generate_orders_thread, daemon=True)
        product_thread = threading.Thread(target=self.generate_products_thread, daemon=True)

        order_thread.start()
        product_thread.start()

        # 지정된 시간만큼 대기
        try:
            for remaining in range(self.duration, 0, -10):
                if remaining % 10 == 0:
                    with self.lock:
                        elapsed = time.time() - self.stats['start_time']
                        orders_tps = self.stats['orders_created'] / elapsed if elapsed > 0 else 0
                        products_tps = self.stats['products_created'] / elapsed if elapsed > 0 else 0

                    print(f"⏱️  남은시간: {remaining}초 | "
                          f"주문: {self.stats['orders_created']:,}건 (TPS: {orders_tps:.2f}) | "
                          f"상품: {self.stats['products_created']:,}개 (TPS: {products_tps:.2f})")

                time.sleep(10)

        except KeyboardInterrupt:
            print("\n⚠️ 사용자에 의해 테스트가 중단되었습니다.")

        # 스레드 종료
        self.running = False
        order_thread.join(timeout=5)
        product_thread.join(timeout=5)

        # 최종 통계
        self.stats['end_time'] = time.time()
        actual_duration = self.stats['end_time'] - self.stats['start_time']

        orders_tps = self.stats['orders_created'] / actual_duration if actual_duration > 0 else 0
        products_tps = self.stats['products_created'] / actual_duration if actual_duration > 0 else 0
        total_tps = (self.stats['orders_created'] + self.stats['products_created']) / actual_duration if actual_duration > 0 else 0

        result = {
            'kafka_enabled': kafka_enabled,
            'kafka_status': kafka_status,
            'duration': actual_duration,
            'orders_created': self.stats['orders_created'],
            'orders_failed': self.stats['orders_failed'],
            'orders_tps': orders_tps,
            'products_created': self.stats['products_created'],
            'products_failed': self.stats['products_failed'],
            'products_tps': products_tps,
            'total_records': self.stats['orders_created'] + self.stats['products_created'],
            'total_tps': total_tps
        }

        print(f"\n✅ 테스트 완료 (카프카 {kafka_status})")
        print(f"   주문: {result['orders_created']:,}건 (TPS: {result['orders_tps']:.2f})")
        print(f"   상품: {result['products_created']:,}개 (TPS: {result['products_tps']:.2f})")
        print(f"   총계: {result['total_records']:,}건 (TPS: {result['total_tps']:.2f})")

        return result


class BenchmarkRunner:
    """벤치마크 실행 및 비교"""

    def __init__(self, test_duration: int = 60):
        self.test_duration = test_duration
        self.results = []

    def run_comparison(self):
        """카프카 ON/OFF 비교 테스트 실행"""
        print("""
    ╔════════════════════════════════════════════════════════════╗
    ║      실시간 데이터 생성 - 카프카 성능 비교 벤치마크         ║
    ╚════════════════════════════════════════════════════════════╝
        """)

        print(f"📋 테스트 조건:")
        print(f"   - 테스트 시간: {self.test_duration}초 ({self.test_duration/60:.1f}분)")
        print(f"   - 주문 생성: 2~8초 간격으로 1~5건씩")
        print(f"   - 상품 생성: 10~20초 간격으로 100건씩\n")

        input("준비되셨으면 Enter를 눌러주세요...")

        # 카프카 OFF 테스트
        print(f"\n{'#'*60}")
        print("# 1단계: 카프카 비활성화 테스트")
        print(f"{'#'*60}")
        benchmark_off = RealtimeBenchmark(self.test_duration)
        result_off = benchmark_off.run_test(kafka_enabled=False)
        self.results.append(result_off)

        print("\n⏸️  5초 대기 후 다음 테스트를 시작합니다...")
        time.sleep(5)

        # 카프카 ON 테스트
        print(f"\n{'#'*60}")
        print("# 2단계: 카프카 활성화 테스트")
        print(f"{'#'*60}")
        benchmark_on = RealtimeBenchmark(self.test_duration)
        result_on = benchmark_on.run_test(kafka_enabled=True)
        self.results.append(result_on)

    def generate_report(self):
        """비교 리포트 생성"""
        print(f"\n{'#'*60}")
        print("# 📊 카프카 성능 비교 리포트")
        print(f"{'#'*60}\n")

        # 전체 결과 테이블
        table_data = []
        for result in self.results:
            table_data.append([
                result['kafka_status'],
                f"{result['duration']:.1f}",
                f"{result['orders_created']:,}",
                f"{result['orders_tps']:.2f}",
                f"{result['products_created']:,}",
                f"{result['products_tps']:.2f}",
                f"{result['total_records']:,}",
                f"{result['total_tps']:.2f}"
            ])

        headers = [
            'Kafka', 'Duration(s)',
            'Orders', 'Orders TPS',
            'Products', 'Products TPS',
            'Total', 'Total TPS'
        ]
        print(tabulate(table_data, headers=headers, tablefmt='grid'))

        # 상세 비교 분석
        if len(self.results) >= 2:
            off_result = self.results[0]
            on_result = self.results[1]

            print(f"\n{'='*60}")
            print("📈 성능 비교 분석")
            print(f"{'='*60}\n")

            # 주문 TPS 비교
            orders_tps_diff = on_result['orders_tps'] - off_result['orders_tps']
            orders_tps_improvement = (orders_tps_diff / off_result['orders_tps'] * 100) if off_result['orders_tps'] > 0 else 0

            print(f"🛒 주문 데이터:")
            print(f"   OFF TPS: {off_result['orders_tps']:.2f}")
            print(f"   ON TPS:  {on_result['orders_tps']:.2f}")
            print(f"   차이:    {orders_tps_improvement:+.2f}%")

            # 상품 TPS 비교
            products_tps_diff = on_result['products_tps'] - off_result['products_tps']
            products_tps_improvement = (products_tps_diff / off_result['products_tps'] * 100) if off_result['products_tps'] > 0 else 0

            print(f"\n📦 상품 데이터:")
            print(f"   OFF TPS: {off_result['products_tps']:.2f}")
            print(f"   ON TPS:  {on_result['products_tps']:.2f}")
            print(f"   차이:    {products_tps_improvement:+.2f}%")

            # 전체 TPS 비교
            total_tps_diff = on_result['total_tps'] - off_result['total_tps']
            total_tps_improvement = (total_tps_diff / off_result['total_tps'] * 100) if off_result['total_tps'] > 0 else 0

            print(f"\n📊 전체 처리량:")
            print(f"   OFF TPS: {off_result['total_tps']:.2f}")
            print(f"   ON TPS:  {on_result['total_tps']:.2f}")
            print(f"   차이:    {total_tps_improvement:+.2f}%")

            # 결론
            print(f"\n{'='*60}")
            print("💡 결론")
            print(f"{'='*60}")

            if total_tps_improvement > 5:
                print(f"✅ 카프카 활성화 시 약 {total_tps_improvement:.1f}% 더 빠름")
            elif total_tps_improvement < -5:
                print(f"⚠️ 카프카 비활성화 시 약 {abs(total_tps_improvement):.1f}% 더 빠름")
            else:
                print(f"⚖️ 카프카 ON/OFF 성능 차이 미미 ({abs(total_tps_improvement):.1f}%)")

            print(f"\n📝 참고:")
            print(f"   - 실시간 처리 환경에서는 카프카의 비동기 처리가 효과적일 수 있습니다")
            print(f"   - 카프카의 진정한 가치는 속도보다 확장성, 안정성, 이벤트 추적에 있습니다")


def main():
    """메인 실행 함수"""
    # 테스트 시간 설정 (초)
    test_duration = int(input("테스트 지속 시간 (초) [기본값: 60]: ").strip() or "60")

    runner = BenchmarkRunner(test_duration=test_duration)

    try:
        # 비교 테스트 실행
        runner.run_comparison()

        # 리포트 생성
        runner.generate_report()

        print("\n✅ 모든 벤치마크 테스트가 완료되었습니다!")

    except KeyboardInterrupt:
        print("\n\n⚠️ 사용자에 의해 테스트가 중단되었습니다.")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
