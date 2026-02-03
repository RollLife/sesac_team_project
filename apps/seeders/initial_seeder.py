"""
초기 데이터 생성 스크립트

- 고객 10,000명 생성
- 상품 20,000개 생성
"""

import os
import sys
import time
from datetime import datetime

# 프로젝트 루트를 sys.path에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from sqlalchemy.orm import Session
from database import crud, database
from collect.user_generator import UserGenerator
from collect.product_generator import ProductGenerator


class InitialDataSeeder:
    """초기 데이터 생성"""

    def __init__(self):
        self.db = database.SessionLocal()

    def seed_users(self, count: int = 10000, batch_size: int = 1000):
        """고객 데이터 대량 생성"""
        print(f"\n{'='*60}")
        print(f"👥 고객 데이터 생성 시작 (목표: {count:,}명)")
        print(f"{'='*60}")

        generator = UserGenerator()
        total_success = 0
        total_failed = 0

        start_time = time.perf_counter()

        # 배치 단위로 생성 (메모리 효율)
        for batch_num in range(0, count, batch_size):
            current_batch_size = min(batch_size, count - batch_num)
            users_list = generator.generate_batch(current_batch_size)

            batch_success = 0
            for user_data in users_list:
                try:
                    crud.create_user(self.db, user_data)
                    batch_success += 1
                    total_success += 1
                except Exception as e:
                    total_failed += 1
                    self.db.rollback()

            elapsed = time.perf_counter() - start_time
            tps = total_success / elapsed if elapsed > 0 else 0

            print(f"  📊 배치 {batch_num//batch_size + 1}: "
                  f"{batch_success}/{current_batch_size}건 성공 | "
                  f"누적: {total_success:,}명 | "
                  f"경과: {elapsed:.1f}초 | "
                  f"TPS: {tps:.1f}")

        end_time = time.perf_counter()
        duration = end_time - start_time
        final_tps = total_success / duration if duration > 0 else 0

        print(f"\n✅ 고객 데이터 생성 완료!")
        print(f"   성공: {total_success:,}명 | 실패: {total_failed}명")
        print(f"   소요시간: {duration:.2f}초 | 평균 TPS: {final_tps:.2f}")

        return {
            'entity': 'User',
            'count': count,
            'success': total_success,
            'failed': total_failed,
            'duration': duration,
            'tps': final_tps
        }

    def seed_products(self, count: int = 20000, batch_size: int = 1000):
        """상품 데이터 대량 생성"""
        print(f"\n{'='*60}")
        print(f"📦 상품 데이터 생성 시작 (목표: {count:,}개)")
        print(f"{'='*60}")

        generator = ProductGenerator()
        total_success = 0
        total_failed = 0

        start_time = time.perf_counter()

        # 배치 단위로 생성
        for batch_num in range(0, count, batch_size):
            current_batch_size = min(batch_size, count - batch_num)
            products_list = generator.generate_batch(current_batch_size)

            batch_success = 0
            for product_data in products_list:
                try:
                    # sleep 필드 제거 (DB 모델에 없음)
                    if 'sleep' in product_data:
                        del product_data['sleep']

                    crud.create_product(self.db, product_data)
                    batch_success += 1
                    total_success += 1
                except Exception as e:
                    total_failed += 1
                    self.db.rollback()

            elapsed = time.perf_counter() - start_time
            tps = total_success / elapsed if elapsed > 0 else 0

            print(f"  📊 배치 {batch_num//batch_size + 1}: "
                  f"{batch_success}/{current_batch_size}건 성공 | "
                  f"누적: {total_success:,}개 | "
                  f"경과: {elapsed:.1f}초 | "
                  f"TPS: {tps:.1f}")

        end_time = time.perf_counter()
        duration = end_time - start_time
        final_tps = total_success / duration if duration > 0 else 0

        print(f"\n✅ 상품 데이터 생성 완료!")
        print(f"   성공: {total_success:,}개 | 실패: {total_failed}개")
        print(f"   소요시간: {duration:.2f}초 | 평균 TPS: {final_tps:.2f}")

        return {
            'entity': 'Product',
            'count': count,
            'success': total_success,
            'failed': total_failed,
            'duration': duration,
            'tps': final_tps
        }

    def generate_summary_report(self, user_result, product_result):
        """요약 리포트 출력"""
        print(f"\n{'#'*60}")
        print("# 📊 초기 데이터 생성 완료 리포트")
        print(f"{'#'*60}\n")

        print(f"👥 고객 데이터:")
        print(f"   목표: {user_result['count']:,}명")
        print(f"   성공: {user_result['success']:,}명")
        print(f"   실패: {user_result['failed']}명")
        print(f"   소요시간: {user_result['duration']:.2f}초")
        print(f"   평균 TPS: {user_result['tps']:.2f}")

        print(f"\n📦 상품 데이터:")
        print(f"   목표: {product_result['count']:,}개")
        print(f"   성공: {product_result['success']:,}개")
        print(f"   실패: {product_result['failed']}개")
        print(f"   소요시간: {product_result['duration']:.2f}초")
        print(f"   평균 TPS: {product_result['tps']:.2f}")

        total_duration = user_result['duration'] + product_result['duration']
        total_records = user_result['success'] + product_result['success']

        print(f"\n📈 전체 요약:")
        print(f"   총 레코드: {total_records:,}건")
        print(f"   총 소요시간: {total_duration:.2f}초 ({total_duration/60:.1f}분)")
        print(f"   전체 평균 TPS: {total_records/total_duration:.2f}")

    def close(self):
        """리소스 정리"""
        self.db.close()


def main():
    """메인 실행 함수"""
    print("""
    ╔════════════════════════════════════════════════════════════╗
    ║              초기 데이터 대량 생성 도구                     ║
    ║        고객 10,000명 + 상품 20,000개 생성                  ║
    ╚════════════════════════════════════════════════════════════╝
    """)

    seeder = InitialDataSeeder()

    try:
        # 1. 고객 데이터 생성 (10,000명)
        user_result = seeder.seed_users(count=10000, batch_size=1000)

        # 2. 상품 데이터 생성 (20,000개)
        product_result = seeder.seed_products(count=20000, batch_size=1000)

        # 3. 요약 리포트
        seeder.generate_summary_report(user_result, product_result)

        print("\n✅ 모든 초기 데이터 생성이 완료되었습니다!")
        print("   이제 realtime_data_generator.py를 실행하여 실시간 데이터를 생성할 수 있습니다.")

    except KeyboardInterrupt:
        print("\n\n⚠️ 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    finally:
        seeder.close()


if __name__ == "__main__":
    main()
