"""
카프카 ON/OFF 성능 비교 벤치마크 스크립트

동일한 조건에서 카프카 활성화/비활성화 시 처리 속도를 비교합니다.
결과는 HTML 파일과 콘솔 리포트로 출력됩니다.
"""

import os
import sys
import time
from datetime import datetime
from typing import List, Dict
from tabulate import tabulate

# 프로젝트 루트를 sys.path에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.append(project_root)

from sqlalchemy.orm import Session
from database import crud, database, models
from collect.product_generator import ProductGenerator
from collect.user_generator import UserGenerator

# 리포트 저장 경로
REPORT_DIR = os.path.join(current_dir, "report")


class KafkaBenchmark:
    """카프카 성능 비교 벤치마크"""

    def __init__(self):
        self.results = []
        self.db = database.SessionLocal()

    def cleanup_database(self):
        """테스트 전 DB 초기화 (선택적)"""
        print("데이터베이스 정리 중...")
        try:
            self.db.query(models.Product).delete()
            self.db.query(models.User).delete()
            self.db.commit()
            print("데이터베이스 정리 완료")
        except Exception as e:
            print(f"데이터베이스 정리 실패: {e}")
            self.db.rollback()

    def set_kafka_enabled(self, enabled: bool):
        """카프카 활성화/비활성화 설정"""
        # 환경변수 설정
        os.environ['KAFKA_ENABLED'] = 'true' if enabled else 'false'

        # kafka.config 모듈 다시 로드하여 설정 반영
        import importlib
        import kafka.config as kafka_config
        importlib.reload(kafka_config)

        status = "활성화" if enabled else "비활성화"
        print(f"카프카 {status} 설정 완료")

    def benchmark_products(self, count: int, kafka_enabled: bool) -> Dict:
        """상품 생성 벤치마크"""
        self.set_kafka_enabled(kafka_enabled)

        generator = ProductGenerator()
        products_list = generator.generate_batch(count)

        kafka_status = "ON" if kafka_enabled else "OFF"
        print(f"\n{'='*60}")
        print(f"상품 생성 테스트 | 개수: {count}개 | 카프카: {kafka_status}")
        print(f"{'='*60}")

        success_count = 0
        failed_count = 0

        start_time = time.perf_counter()

        for product_data in products_list:
            try:
                crud.create_product(self.db, product_data)
                success_count += 1
            except Exception as e:
                failed_count += 1
                print(f"저장 실패: {e}")
                self.db.rollback()

        end_time = time.perf_counter()
        duration = end_time - start_time
        tps = success_count / duration if duration > 0 else 0

        result = {
            'entity': '상품',
            'count': count,
            'kafka_enabled': kafka_enabled,
            'kafka_status': kafka_status,
            'success': success_count,
            'failed': failed_count,
            'duration': duration,
            'tps': tps,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        print(f"성공: {success_count}개 | 실패: {failed_count}개")
        print(f"소요시간: {duration:.4f}초")
        print(f"TPS: {tps:.2f} records/sec")

        return result

    def benchmark_users(self, count: int, kafka_enabled: bool) -> Dict:
        """유저 생성 벤치마크"""
        self.set_kafka_enabled(kafka_enabled)

        generator = UserGenerator()
        users_list = generator.generate_batch(count)

        kafka_status = "ON" if kafka_enabled else "OFF"
        print(f"\n{'='*60}")
        print(f"유저 생성 테스트 | 개수: {count}명 | 카프카: {kafka_status}")
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
                print(f"저장 실패: {e}")
                self.db.rollback()

        end_time = time.perf_counter()
        duration = end_time - start_time
        tps = success_count / duration if duration > 0 else 0

        result = {
            'entity': '유저',
            'count': count,
            'kafka_enabled': kafka_enabled,
            'kafka_status': kafka_status,
            'success': success_count,
            'failed': failed_count,
            'duration': duration,
            'tps': tps,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        print(f"성공: {success_count}명 | 실패: {failed_count}명")
        print(f"소요시간: {duration:.4f}초")
        print(f"TPS: {tps:.2f} records/sec")

        return result

    def run_comparison(self, entity_type: str, test_counts: List[int]):
        """동일 조건에서 카프카 ON/OFF 비교"""
        entity_name = "상품" if entity_type == "Product" else "유저"
        print(f"\n{'#'*60}")
        print(f"# {entity_name} 카프카 성능 비교 테스트 시작")
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
        print("# 카프카 성능 비교 리포트")
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

        headers = ['유형', '개수', '카프카', '성공', '소요시간(초)', 'TPS']
        print(tabulate(table_data, headers=headers, tablefmt='grid'))

        # 개선율 계산 및 출력
        print(f"\n{'='*60}")
        print("성능 개선율 분석")
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
            '유형', '개수',
            '소요시간(OFF)', '소요시간(ON)', '개선율',
            'TPS(OFF)', 'TPS(ON)', 'TPS 개선율'
        ]
        print(tabulate(improvement_data, headers=improvement_headers, tablefmt='grid'))

        # 결론
        print(f"\n{'='*60}")
        print("결론")
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
            print(f"\n카프카 비활성화 시 평균 {avg_duration_improvement:.2f}% 더 빠름")
        elif avg_duration_improvement < 0:
            print(f"\n카프카 활성화 시 평균 {abs(avg_duration_improvement):.2f}% 더 빠름")
        else:
            print(f"\n카프카 ON/OFF 성능 차이 거의 없음")

        return improvement_data

    def generate_html_report(self, improvement_data: list):
        """HTML 형식의 리포트 생성"""
        # 리포트 디렉토리 확인/생성
        os.makedirs(REPORT_DIR, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(REPORT_DIR, f"kafka_comparison_{timestamp}.html")

        # HTML 내용 생성
        html_content = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>카프카 성능 비교 벤치마크 리포트</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 40px 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        .report-header {{
            background: white;
            border-radius: 16px;
            padding: 40px;
            margin-bottom: 30px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            text-align: center;
        }}
        .report-header h1 {{
            color: #333;
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        .report-header .subtitle {{
            color: #666;
            font-size: 1.1em;
        }}
        .report-header .timestamp {{
            color: #999;
            font-size: 0.9em;
            margin-top: 15px;
        }}
        .section {{
            background: white;
            border-radius: 16px;
            padding: 30px;
            margin-bottom: 25px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.15);
        }}
        .section h2 {{
            color: #333;
            font-size: 1.5em;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 3px solid #667eea;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }}
        th, td {{
            padding: 15px 12px;
            text-align: center;
            border-bottom: 1px solid #eee;
        }}
        th {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.9em;
            letter-spacing: 0.5px;
        }}
        tr:hover {{
            background-color: #f8f9ff;
        }}
        .kafka-on {{
            color: #28a745;
            font-weight: bold;
        }}
        .kafka-off {{
            color: #dc3545;
            font-weight: bold;
        }}
        .improvement-positive {{
            color: #28a745;
            font-weight: bold;
        }}
        .improvement-negative {{
            color: #dc3545;
            font-weight: bold;
        }}
        .summary-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}
        .summary-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 12px;
            padding: 25px;
            color: white;
            text-align: center;
        }}
        .summary-card .label {{
            font-size: 0.9em;
            opacity: 0.9;
            margin-bottom: 8px;
        }}
        .summary-card .value {{
            font-size: 2em;
            font-weight: bold;
        }}
        .conclusion {{
            background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
            color: white;
            padding: 25px;
            border-radius: 12px;
            text-align: center;
            font-size: 1.2em;
            margin-top: 20px;
        }}
        .footer {{
            text-align: center;
            color: white;
            margin-top: 30px;
            opacity: 0.8;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="report-header">
            <h1>카프카 성능 비교 벤치마크</h1>
            <p class="subtitle">카프카 활성화/비활성화 시 데이터 처리 성능 비교</p>
            <p class="timestamp">생성 시간: {datetime.now().strftime("%Y년 %m월 %d일 %H:%M:%S")}</p>
        </div>

        <div class="section">
            <h2>전체 결과</h2>
            <table>
                <thead>
                    <tr>
                        <th>유형</th>
                        <th>개수</th>
                        <th>카프카</th>
                        <th>성공</th>
                        <th>소요시간(초)</th>
                        <th>TPS</th>
                    </tr>
                </thead>
                <tbody>
"""

        for result in self.results:
            kafka_class = "kafka-on" if result['kafka_status'] == "ON" else "kafka-off"
            html_content += f"""                    <tr>
                        <td>{result['entity']}</td>
                        <td>{result['count']:,}</td>
                        <td class="{kafka_class}">{result['kafka_status']}</td>
                        <td>{result['success']:,}</td>
                        <td>{result['duration']:.4f}</td>
                        <td>{result['tps']:.2f}</td>
                    </tr>
"""

        html_content += """                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>성능 비교 분석</h2>
            <table>
                <thead>
                    <tr>
                        <th>유형</th>
                        <th>개수</th>
                        <th>소요시간(OFF)</th>
                        <th>소요시간(ON)</th>
                        <th>시간 개선율</th>
                        <th>TPS(OFF)</th>
                        <th>TPS(ON)</th>
                        <th>TPS 개선율</th>
                    </tr>
                </thead>
                <tbody>
"""

        for row in improvement_data:
            duration_class = "improvement-positive" if row[4].startswith('+') else "improvement-negative"
            tps_class = "improvement-positive" if row[7].startswith('+') else "improvement-negative"
            html_content += f"""                    <tr>
                        <td>{row[0]}</td>
                        <td>{row[1]:,}</td>
                        <td>{row[2]}</td>
                        <td>{row[3]}</td>
                        <td class="{duration_class}">{row[4]}</td>
                        <td>{row[5]}</td>
                        <td>{row[6]}</td>
                        <td class="{tps_class}">{row[7]}</td>
                    </tr>
"""

        # 평균 계산
        avg_duration_improvement = sum([
            float(row[4].rstrip('%')) for row in improvement_data
        ]) / len(improvement_data) if improvement_data else 0

        avg_tps_improvement = sum([
            float(row[7].rstrip('%')) for row in improvement_data
        ]) / len(improvement_data) if improvement_data else 0

        # 결론 메시지
        if avg_duration_improvement > 0:
            conclusion = f"카프카 비활성화 시 평균 {avg_duration_improvement:.2f}% 더 빠릅니다"
        elif avg_duration_improvement < 0:
            conclusion = f"카프카 활성화 시 평균 {abs(avg_duration_improvement):.2f}% 더 빠릅니다"
        else:
            conclusion = "카프카 ON/OFF 성능 차이가 거의 없습니다"

        html_content += f"""                </tbody>
            </table>

            <div class="summary-cards">
                <div class="summary-card">
                    <div class="label">평균 처리시간 개선율</div>
                    <div class="value">{avg_duration_improvement:+.2f}%</div>
                </div>
                <div class="summary-card">
                    <div class="label">평균 TPS 개선율</div>
                    <div class="value">{avg_tps_improvement:+.2f}%</div>
                </div>
                <div class="summary-card">
                    <div class="label">테스트 케이스 수</div>
                    <div class="value">{len(improvement_data)}</div>
                </div>
            </div>

            <div class="conclusion">
                {conclusion}
            </div>
        </div>

        <div class="section">
            <h2>참고 사항</h2>
            <ul style="list-style-position: inside; color: #666; line-height: 2;">
                <li>카프카의 가치는 단순 속도보다 확장성, 안정성, 이벤트 추적에 있습니다</li>
                <li>비동기 처리로 인한 응답 속도 개선 효과가 있을 수 있습니다</li>
                <li>대규모 분산 시스템에서 카프카의 장점이 더 크게 드러납니다</li>
                <li>테스트 환경과 실제 운영 환경은 다를 수 있습니다</li>
            </ul>
        </div>

        <div class="footer">
            <p>카프카 벤치마크 도구로 생성됨</p>
        </div>
    </div>
</body>
</html>
"""

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"\nHTML 리포트가 생성되었습니다: {filename}")
        return filename

    def close(self):
        """리소스 정리"""
        self.db.close()


def main():
    """메인 실행 함수"""
    print("""
    ========================================================
              카프카 ON/OFF 성능 비교 벤치마크 도구
    ========================================================
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
        improvement_data = benchmark.generate_comparison_report()

        # HTML 리포트 생성
        benchmark.generate_html_report(improvement_data)

        print("\n모든 벤치마크 테스트가 완료되었습니다!")

    except KeyboardInterrupt:
        print("\n\n사용자에 의해 테스트가 중단되었습니다.")
    except Exception as e:
        print(f"\n오류 발생: {e}")
        import traceback
        traceback.print_exc()
    finally:
        benchmark.close()


if __name__ == "__main__":
    main()
