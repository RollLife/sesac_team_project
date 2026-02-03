"""
카프카 ON/OFF 성능 비교 벤치마크 스크립트

동일한 조건에서 카프카 활성화/비활성화 시 처리 속도를 비교합니다.
결과는 CSV 파일과 콘솔 리포트로 출력됩니다.
"""

import os
import sys
import time
import csv
from datetime import datetime
from typing import List, Dict
from tabulate import tabulate

# 프로젝트 루트를 sys.path에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from sqlalchemy.orm import Session
from database import crud, database, models
from collect.product_generator import ProductGenerator
from collect.user_generator import UserGenerator


class KafkaBenchmark:
    """카프카 성능 비교 벤치마크"""

    def __init__(self):
        self.results = []
        self.db = database.SessionLocal()

    def cleanup_database(self):
        """테스트 전 DB 초기화 (선택적)"""
        print("🧹 데이터베이스 정리 중...")
        try:
            self.db.query(models.Product).delete()
            self.db.query(models.User).delete()
            self.db.commit()
            print("✅ 데이터베이스 정리 완료")
        except Exception as e:
            print(f"⚠️ 데이터베이스 정리 실패: {e}")
            self.db.rollback()

    def set_kafka_enabled(self, enabled: bool):
        """카프카 활성화/비활성화 설정"""
        # 환경변수 설정
        os.environ['KAFKA_ENABLED'] = 'true' if enabled else 'false'

        # crud 모듈 다시 로드하여 설정 반영
        import importlib
        import kafka.config
        importlib.reload(kafka.config)

        # crud 모듈의 KAFKA_ENABLED 변수 업데이트
        import database.crud as crud_module
        crud_module.KAFKA_ENABLED = enabled

        status = "활성화" if enabled else "비활성화"
        print(f"⚙️  카프카 {status} 설정 완료")

    def benchmark_products(self, count: int, kafka_enabled: bool) -> Dict:
        """상품 생성 벤치마크"""
        self.set_kafka_enabled(kafka_enabled)

        generator = ProductGenerator()
        products_list = generator.generate_batch(count)

        kafka_status = "ON" if kafka_enabled else "OFF"
        print(f"\n{'='*60}")
        print(f"📦 상품 생성 테스트 | 개수: {count}개 | 카프카: {kafka_status}")
        print(f"{'='*60}")

        success_count = 0
        failed_count = 0

        start_time = time.perf_counter()

        for product_data in products_list:
            try:
                # sleep 필드 제거 (DB 모델에 없음)
                if 'sleep' in product_data:
                    del product_data['sleep']

                crud.create_product(self.db, product_data)
                success_count += 1
            except Exception as e:
                failed_count += 1
                print(f"⚠️ 저장 실패: {e}")
                self.db.rollback()

        end_time = time.perf_counter()
        duration = end_time - start_time
        tps = success_count / duration if duration > 0 else 0

        result = {
            'entity': 'Product',
            'count': count,
            'kafka_enabled': kafka_enabled,
            'kafka_status': kafka_status,
            'success': success_count,
            'failed': failed_count,
            'duration': duration,
            'tps': tps,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        print(f"✅ 성공: {success_count}개 | ❌ 실패: {failed_count}개")
        print(f"⏱️  소요시간: {duration:.4f}초")
        print(f"🚀 TPS: {tps:.2f} records/sec")

        return result

    def benchmark_users(self, count: int, kafka_enabled: bool) -> Dict:
        """유저 생성 벤치마크"""
        self.set_kafka_enabled(kafka_enabled)

        generator = UserGenerator()
        users_list = generator.generate_batch(count)

        kafka_status = "ON" if kafka_enabled else "OFF"
        print(f"\n{'='*60}")
        print(f"👥 유저 생성 테스트 | 개수: {count}명 | 카프카: {kafka_status}")
        print(f"{'='*60}")

        success_count = 0
        failed_count = 0

        start_time = time.perf_counter()

        for user_data in users_list:
            try:
                crud.create_user(self.db, user_data)
                success_count += 1
            except Exception as e:
                failed_count += 1
                print(f"⚠️ 저장 실패: {e}")
                self.db.rollback()

        end_time = time.perf_counter()
        duration = end_time - start_time
        tps = success_count / duration if duration > 0 else 0

        result = {
            'entity': 'User',
            'count': count,
            'kafka_enabled': kafka_enabled,
            'kafka_status': kafka_status,
            'success': success_count,
            'failed': failed_count,
            'duration': duration,
            'tps': tps,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        print(f"✅ 성공: {success_count}명 | ❌ 실패: {failed_count}명")
        print(f"⏱️  소요시간: {duration:.4f}초")
        print(f"🚀 TPS: {tps:.2f} records/sec")

        return result

    def run_comparison(self, entity_type: str, test_counts: List[int]):
        """동일 조건에서 카프카 ON/OFF 비교"""
        print(f"\n{'#'*60}")
        print(f"# {entity_type} 카프카 성능 비교 테스트 시작")
        print(f"# 테스트 케이스: {test_counts}")
        print(f"{'#'*60}")

        for count in test_counts:
            # 카프카 OFF 테스트
            if entity_type == 'Product':
                result_off = self.benchmark_products(count, kafka_enabled=False)
            else:
                result_off = self.benchmark_users(count, kafka_enabled=False)
            self.results.append(result_off)

            # 잠깐 대기 (DB 안정화)
            time.sleep(1)

            # 카프카 ON 테스트
            if entity_type == 'Product':
                result_on = self.benchmark_products(count, kafka_enabled=True)
            else:
                result_on = self.benchmark_users(count, kafka_enabled=True)
            self.results.append(result_on)

            # 잠깐 대기
            time.sleep(1)

    def generate_comparison_report(self):
        """비교 리포트 생성"""
        print(f"\n{'#'*60}")
        print("# 📊 카프카 성능 비교 리포트")
        print(f"{'#'*60}\n")

        # 테이블 형태로 출력
        table_data = []
        for result in self.results:
            table_data.append([
                result['entity'],
                result['count'],
                result['kafka_status'],
                result['success'],
                f"{result['duration']:.4f}",
                f"{result['tps']:.2f}"
            ])

        headers = ['Entity', 'Count', 'Kafka', 'Success', 'Duration(s)', 'TPS']
        print(tabulate(table_data, headers=headers, tablefmt='grid'))

        # 개선율 계산 및 출력
        print(f"\n{'='*60}")
        print("📈 성능 개선율 분석")
        print(f"{'='*60}\n")

        # Entity별, Count별로 그룹화하여 비교
        grouped = {}
        for result in self.results:
            key = (result['entity'], result['count'])
            if key not in grouped:
                grouped[key] = {}
            grouped[key][result['kafka_status']] = result

        improvement_data = []
        for (entity, count), statuses in grouped.items():
            if 'OFF' in statuses and 'ON' in statuses:
                off_result = statuses['OFF']
                on_result = statuses['ON']

                duration_diff = off_result['duration'] - on_result['duration']
                duration_improvement = (duration_diff / off_result['duration'] * 100) if off_result['duration'] > 0 else 0

                tps_diff = on_result['tps'] - off_result['tps']
                tps_improvement = (tps_diff / off_result['tps'] * 100) if off_result['tps'] > 0 else 0

                improvement_data.append([
                    entity,
                    count,
                    f"{off_result['duration']:.4f}",
                    f"{on_result['duration']:.4f}",
                    f"{duration_improvement:+.2f}%",
                    f"{off_result['tps']:.2f}",
                    f"{on_result['tps']:.2f}",
                    f"{tps_improvement:+.2f}%"
                ])

        improvement_headers = [
            'Entity', 'Count',
            'Duration OFF', 'Duration ON', 'Improvement',
            'TPS OFF', 'TPS ON', 'TPS Improvement'
        ]
        print(tabulate(improvement_data, headers=improvement_headers, tablefmt='grid'))

        # 결론
        print(f"\n{'='*60}")
        print("💡 결론")
        print(f"{'='*60}")

        avg_duration_improvement = sum([
            float(row[4].rstrip('%')) for row in improvement_data
        ]) / len(improvement_data) if improvement_data else 0

        avg_tps_improvement = sum([
            float(row[7].rstrip('%')) for row in improvement_data
        ]) / len(improvement_data) if improvement_data else 0

        print(f"평균 처리시간 개선율: {avg_duration_improvement:+.2f}%")
        print(f"평균 TPS 개선율: {avg_tps_improvement:+.2f}%")

        if avg_duration_improvement > 0:
            print(f"\n✅ 카프카 비활성화 시 평균 {avg_duration_improvement:.2f}% 더 빠름")
        elif avg_duration_improvement < 0:
            print(f"\n✅ 카프카 활성화 시 평균 {abs(avg_duration_improvement):.2f}% 더 빠름")
        else:
            print(f"\n⚖️ 카프카 ON/OFF 성능 차이 거의 없음")

    def save_results_to_csv(self, filename: str = "kafka_comparison_results.csv"):
        """결과를 CSV 파일로 저장"""
        file_exists = os.path.isfile(filename)

        with open(filename, mode='a', newline='', encoding='utf-8') as f:
            fieldnames = ['timestamp', 'entity', 'count', 'kafka_status',
                         'success', 'failed', 'duration', 'tps']
            writer = csv.DictWriter(f, fieldnames=fieldnames)

            if not file_exists:
                writer.writeheader()

            for result in self.results:
                writer.writerow({
                    'timestamp': result['timestamp'],
                    'entity': result['entity'],
                    'count': result['count'],
                    'kafka_status': result['kafka_status'],
                    'success': result['success'],
                    'failed': result['failed'],
                    'duration': f"{result['duration']:.4f}",
                    'tps': f"{result['tps']:.2f}"
                })

        print(f"\n💾 결과가 '{filename}' 파일에 저장되었습니다.")

    def close(self):
        """리소스 정리"""
        self.db.close()


def main():
    """메인 실행 함수"""
    print("""
    ╔════════════════════════════════════════════════════════════╗
    ║         카프카 ON/OFF 성능 비교 벤치마크 도구               ║
    ╚════════════════════════════════════════════════════════════╝
    """)

    benchmark = KafkaBenchmark()

    try:
        # 테스트 시나리오 정의
        # 다양한 데이터 양으로 테스트 (작은 양, 중간, 많은 양)
        test_counts = [100, 500, 1000]

        # DB 정리 여부 선택
        cleanup = input("테스트 전 DB를 정리하시겠습니까? (y/n, 기본값: n): ").strip().lower()
        if cleanup == 'y':
            benchmark.cleanup_database()

        # 상품 데이터 비교 테스트
        benchmark.run_comparison('Product', test_counts)

        # 유저 데이터 비교 테스트
        benchmark.run_comparison('User', test_counts)

        # 결과 리포트 생성
        benchmark.generate_comparison_report()

        # CSV로 저장
        benchmark.save_results_to_csv()

        print("\n✅ 모든 벤치마크 테스트가 완료되었습니다!")

    except KeyboardInterrupt:
        print("\n\n⚠️ 사용자에 의해 테스트가 중단되었습니다.")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    finally:
        benchmark.close()


if __name__ == "__main__":
    main()
