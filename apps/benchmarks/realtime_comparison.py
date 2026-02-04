"""
실시간 데이터 생성 시나리오에서 카프카 ON/OFF 성능 비교

- 일정 시간 동안 실시간 데이터 생성 (주문 + 상품)
- 카프카 OFF vs ON 성능 비교
- HTML 리포트 생성
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
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.append(project_root)

from sqlalchemy.orm import Session
from database import crud, database, models
from collect.product_generator import ProductGenerator
from collect.order_generator import OrderGenerator

# 리포트 저장 경로
REPORT_DIR = os.path.join(current_dir, "report")


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

        # kafka.config 모듈 다시 로드하여 설정 반영
        import importlib
        import kafka.config as kafka_config
        importlib.reload(kafka_config)

        status = "활성화" if enabled else "비활성화"
        print(f"카프카 {status} 설정 완료")

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
        print(f"실시간 데이터 생성 테스트 시작")
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

                    print(f"남은시간: {remaining}초 | "
                          f"주문: {self.stats['orders_created']:,}건 (TPS: {orders_tps:.2f}) | "
                          f"상품: {self.stats['products_created']:,}개 (TPS: {products_tps:.2f})")

                time.sleep(10)

        except KeyboardInterrupt:
            print("\n사용자에 의해 테스트가 중단되었습니다.")

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

        print(f"\n테스트 완료 (카프카 {kafka_status})")
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
    ========================================================
          실시간 데이터 생성 - 카프카 성능 비교 벤치마크
    ========================================================
        """)

        print(f"테스트 조건:")
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

        print("\n5초 대기 후 다음 테스트를 시작합니다...")
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
        print("# 카프카 성능 비교 리포트")
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
            '카프카', '소요시간(초)',
            '주문', '주문 TPS',
            '상품', '상품 TPS',
            '총계', '총 TPS'
        ]
        print(tabulate(table_data, headers=headers, tablefmt='grid'))

        # 상세 비교 분석
        comparison_data = {}
        if len(self.results) >= 2:
            off_result = self.results[0]
            on_result = self.results[1]

            print(f"\n{'='*60}")
            print("성능 비교 분석")
            print(f"{'='*60}\n")

            # 주문 TPS 비교
            orders_tps_diff = on_result['orders_tps'] - off_result['orders_tps']
            orders_tps_improvement = (orders_tps_diff / off_result['orders_tps'] * 100) if off_result['orders_tps'] > 0 else 0

            print(f"주문 데이터:")
            print(f"   OFF TPS: {off_result['orders_tps']:.2f}")
            print(f"   ON TPS:  {on_result['orders_tps']:.2f}")
            print(f"   차이:    {orders_tps_improvement:+.2f}%")

            # 상품 TPS 비교
            products_tps_diff = on_result['products_tps'] - off_result['products_tps']
            products_tps_improvement = (products_tps_diff / off_result['products_tps'] * 100) if off_result['products_tps'] > 0 else 0

            print(f"\n상품 데이터:")
            print(f"   OFF TPS: {off_result['products_tps']:.2f}")
            print(f"   ON TPS:  {on_result['products_tps']:.2f}")
            print(f"   차이:    {products_tps_improvement:+.2f}%")

            # 전체 TPS 비교
            total_tps_diff = on_result['total_tps'] - off_result['total_tps']
            total_tps_improvement = (total_tps_diff / off_result['total_tps'] * 100) if off_result['total_tps'] > 0 else 0

            print(f"\n전체 처리량:")
            print(f"   OFF TPS: {off_result['total_tps']:.2f}")
            print(f"   ON TPS:  {on_result['total_tps']:.2f}")
            print(f"   차이:    {total_tps_improvement:+.2f}%")

            # 결론
            print(f"\n{'='*60}")
            print("결론")
            print(f"{'='*60}")

            if total_tps_improvement > 5:
                print(f"카프카 활성화 시 약 {total_tps_improvement:.1f}% 더 빠름")
            elif total_tps_improvement < -5:
                print(f"카프카 비활성화 시 약 {abs(total_tps_improvement):.1f}% 더 빠름")
            else:
                print(f"카프카 ON/OFF 성능 차이 미미 ({abs(total_tps_improvement):.1f}%)")

            print(f"\n참고:")
            print(f"   - 실시간 처리 환경에서는 카프카의 비동기 처리가 효과적일 수 있습니다")
            print(f"   - 카프카의 진정한 가치는 속도보다 확장성, 안정성, 이벤트 추적에 있습니다")

            # 비교 데이터 저장
            comparison_data = {
                'orders_tps_improvement': orders_tps_improvement,
                'products_tps_improvement': products_tps_improvement,
                'total_tps_improvement': total_tps_improvement
            }

        return comparison_data

    def generate_html_report(self, comparison_data: dict):
        """HTML 형식의 리포트 생성"""
        # 리포트 디렉토리 확인/생성
        os.makedirs(REPORT_DIR, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(REPORT_DIR, f"realtime_comparison_{timestamp}.html")

        if len(self.results) < 2:
            print("결과가 충분하지 않아 HTML 리포트를 생성할 수 없습니다.")
            return None

        off_result = self.results[0]
        on_result = self.results[1]

        orders_improvement = comparison_data.get('orders_tps_improvement', 0)
        products_improvement = comparison_data.get('products_tps_improvement', 0)
        total_improvement = comparison_data.get('total_tps_improvement', 0)

        # 결론 메시지
        if total_improvement > 5:
            conclusion = f"카프카 활성화 시 약 {total_improvement:.1f}% 더 빠릅니다"
            conclusion_color = "#28a745"
        elif total_improvement < -5:
            conclusion = f"카프카 비활성화 시 약 {abs(total_improvement):.1f}% 더 빠릅니다"
            conclusion_color = "#dc3545"
        else:
            conclusion = f"카프카 ON/OFF 성능 차이가 미미합니다 ({abs(total_improvement):.1f}%)"
            conclusion_color = "#6c757d"

        # HTML 내용 생성
        html_content = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>실시간 데이터 생성 벤치마크 리포트</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            min-height: 100vh;
            padding: 40px 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        .report-header {{
            background: rgba(255, 255, 255, 0.95);
            border-radius: 16px;
            padding: 40px;
            margin-bottom: 30px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
            text-align: center;
        }}
        .report-header h1 {{
            color: #1a1a2e;
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
        .test-info {{
            background: rgba(255, 255, 255, 0.95);
            border-radius: 16px;
            padding: 25px;
            margin-bottom: 25px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }}
        .test-info h3 {{
            color: #1a1a2e;
            margin-bottom: 15px;
        }}
        .test-info ul {{
            list-style-position: inside;
            color: #666;
            line-height: 1.8;
        }}
        .section {{
            background: rgba(255, 255, 255, 0.95);
            border-radius: 16px;
            padding: 30px;
            margin-bottom: 25px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }}
        .section h2 {{
            color: #1a1a2e;
            font-size: 1.5em;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 3px solid #0f3460;
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
            background: linear-gradient(135deg, #1a1a2e 0%, #0f3460 100%);
            color: white;
            font-weight: 600;
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
        .comparison-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}
        .comparison-card {{
            background: linear-gradient(135deg, #1a1a2e 0%, #0f3460 100%);
            border-radius: 12px;
            padding: 25px;
            color: white;
        }}
        .comparison-card h4 {{
            font-size: 1.1em;
            margin-bottom: 15px;
            opacity: 0.9;
        }}
        .comparison-card .values {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
        }}
        .comparison-card .values span {{
            font-size: 0.9em;
        }}
        .comparison-card .improvement {{
            font-size: 1.5em;
            font-weight: bold;
            text-align: center;
            padding: 15px;
            border-radius: 8px;
            margin-top: 10px;
        }}
        .improvement.positive {{
            background: rgba(40, 167, 69, 0.3);
        }}
        .improvement.negative {{
            background: rgba(220, 53, 69, 0.3);
        }}
        .summary-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}
        .summary-card {{
            background: linear-gradient(135deg, #0f3460 0%, #16213e 100%);
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
            background: linear-gradient(135deg, {conclusion_color} 0%, {conclusion_color}cc 100%);
            color: white;
            padding: 30px;
            border-radius: 12px;
            text-align: center;
            font-size: 1.3em;
            margin-top: 20px;
        }}
        .notes {{
            background: #f8f9fa;
            border-left: 4px solid #0f3460;
            padding: 20px;
            margin-top: 20px;
            border-radius: 0 8px 8px 0;
        }}
        .notes h4 {{
            color: #1a1a2e;
            margin-bottom: 10px;
        }}
        .notes ul {{
            list-style-position: inside;
            color: #666;
            line-height: 1.8;
        }}
        .footer {{
            text-align: center;
            color: white;
            margin-top: 30px;
            opacity: 0.7;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="report-header">
            <h1>실시간 데이터 생성 벤치마크</h1>
            <p class="subtitle">카프카 활성화/비활성화 시 실시간 처리 성능 비교</p>
            <p class="timestamp">생성 시간: {datetime.now().strftime("%Y년 %m월 %d일 %H:%M:%S")}</p>
        </div>

        <div class="test-info">
            <h3>테스트 조건</h3>
            <ul>
                <li>테스트 시간: {self.test_duration}초 ({self.test_duration/60:.1f}분)</li>
                <li>주문 생성: 2~8초 간격으로 1~5건씩 랜덤 생성</li>
                <li>상품 생성: 10~20초 간격으로 100건씩 배치 생성</li>
                <li>멀티스레드 환경에서 동시 처리</li>
            </ul>
        </div>

        <div class="section">
            <h2>전체 결과</h2>
            <table>
                <thead>
                    <tr>
                        <th>카프카</th>
                        <th>소요시간(초)</th>
                        <th>주문</th>
                        <th>주문 TPS</th>
                        <th>상품</th>
                        <th>상품 TPS</th>
                        <th>총계</th>
                        <th>총 TPS</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td class="kafka-off">OFF</td>
                        <td>{off_result['duration']:.1f}</td>
                        <td>{off_result['orders_created']:,}</td>
                        <td>{off_result['orders_tps']:.2f}</td>
                        <td>{off_result['products_created']:,}</td>
                        <td>{off_result['products_tps']:.2f}</td>
                        <td>{off_result['total_records']:,}</td>
                        <td>{off_result['total_tps']:.2f}</td>
                    </tr>
                    <tr>
                        <td class="kafka-on">ON</td>
                        <td>{on_result['duration']:.1f}</td>
                        <td>{on_result['orders_created']:,}</td>
                        <td>{on_result['orders_tps']:.2f}</td>
                        <td>{on_result['products_created']:,}</td>
                        <td>{on_result['products_tps']:.2f}</td>
                        <td>{on_result['total_records']:,}</td>
                        <td>{on_result['total_tps']:.2f}</td>
                    </tr>
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>성능 비교 분석</h2>
            <div class="comparison-grid">
                <div class="comparison-card">
                    <h4>주문 데이터</h4>
                    <div class="values">
                        <span>OFF TPS: {off_result['orders_tps']:.2f}</span>
                        <span>ON TPS: {on_result['orders_tps']:.2f}</span>
                    </div>
                    <div class="improvement {'positive' if orders_improvement >= 0 else 'negative'}">
                        {orders_improvement:+.2f}%
                    </div>
                </div>
                <div class="comparison-card">
                    <h4>상품 데이터</h4>
                    <div class="values">
                        <span>OFF TPS: {off_result['products_tps']:.2f}</span>
                        <span>ON TPS: {on_result['products_tps']:.2f}</span>
                    </div>
                    <div class="improvement {'positive' if products_improvement >= 0 else 'negative'}">
                        {products_improvement:+.2f}%
                    </div>
                </div>
                <div class="comparison-card">
                    <h4>전체 처리량</h4>
                    <div class="values">
                        <span>OFF TPS: {off_result['total_tps']:.2f}</span>
                        <span>ON TPS: {on_result['total_tps']:.2f}</span>
                    </div>
                    <div class="improvement {'positive' if total_improvement >= 0 else 'negative'}">
                        {total_improvement:+.2f}%
                    </div>
                </div>
            </div>

            <div class="summary-cards">
                <div class="summary-card">
                    <div class="label">카프카 OFF 총 처리</div>
                    <div class="value">{off_result['total_records']:,}</div>
                </div>
                <div class="summary-card">
                    <div class="label">카프카 ON 총 처리</div>
                    <div class="value">{on_result['total_records']:,}</div>
                </div>
                <div class="summary-card">
                    <div class="label">처리량 차이</div>
                    <div class="value">{on_result['total_records'] - off_result['total_records']:+,}</div>
                </div>
            </div>

            <div class="conclusion">
                {conclusion}
            </div>
        </div>

        <div class="section">
            <h2>참고 사항</h2>
            <div class="notes">
                <ul>
                    <li>실시간 처리 환경에서는 카프카의 비동기 처리가 효과적일 수 있습니다</li>
                    <li>카프카의 진정한 가치는 속도보다 확장성, 안정성, 이벤트 추적에 있습니다</li>
                    <li>대규모 분산 시스템에서 카프카의 장점이 더 크게 드러납니다</li>
                    <li>테스트 환경과 실제 운영 환경은 다를 수 있습니다</li>
                    <li>네트워크 지연, 디스크 I/O, 브로커 상태에 따라 결과가 달라질 수 있습니다</li>
                </ul>
            </div>
        </div>

        <div class="footer">
            <p>실시간 벤치마크 도구로 생성됨</p>
        </div>
    </div>
</body>
</html>
"""

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"\nHTML 리포트가 생성되었습니다: {filename}")
        return filename


def main():
    """메인 실행 함수"""
    # 테스트 시간 설정 (초)
    test_duration = int(input("테스트 지속 시간 (초) [기본값: 60]: ").strip() or "60")

    runner = BenchmarkRunner(test_duration=test_duration)

    try:
        # 비교 테스트 실행
        runner.run_comparison()

        # 리포트 생성
        comparison_data = runner.generate_report()

        # HTML 리포트 생성
        runner.generate_html_report(comparison_data)

        print("\n모든 벤치마크 테스트가 완료되었습니다!")

    except KeyboardInterrupt:
        print("\n\n사용자에 의해 테스트가 중단되었습니다.")
    except Exception as e:
        print(f"\n오류 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
