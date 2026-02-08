"""
순차처리 벤치마크 프로듀서

Kafka 없이 직접 DB에 저장하는 방식의 성능을 측정합니다.
네트워크 지연을 시뮬레이션하여 실제 분산환경에서의 성능 차이를 보여줍니다.
"""

import os
import sys
import time
import random
from datetime import datetime

# 프로젝트 루트를 sys.path에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from benchmark_common import BenchmarkResult, BenchmarkTimer, save_result, print_result_summary

from database import database, crud, models
from collect.order_generator import OrderGenerator
from collect.user_generator import UserGenerator
from collect.product_generator import ProductGenerator


# 벤치마크 설정 (환경변수로 오버라이드 가능)
TOTAL_RECORDS = int(os.environ.get('BENCHMARK_RECORDS', 5000))
SIMULATE_NETWORK_DELAY = os.environ.get('SIMULATE_NETWORK_DELAY', 'true').lower() == 'true'
NETWORK_DELAY_MS = int(os.environ.get('NETWORK_DELAY_MS', 20))  # 20ms 기본 지연
BATCH_SIZE = int(os.environ.get('BATCH_SIZE', 100))


def simulate_network_delay():
    """네트워크 지연 시뮬레이션 (원격 DB 접속 시뮬레이션)"""
    if SIMULATE_NETWORK_DELAY:
        # 20ms 기본 + 0~10ms 랜덤 지터
        delay = (NETWORK_DELAY_MS + random.uniform(0, 10)) / 1000
        time.sleep(delay)


def run_sequential_benchmark():
    """순차처리 벤치마크 실행"""
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║           순차처리 벤치마크 (Kafka 미사용)                    ║
╠══════════════════════════════════════════════════════════════╣
║  레코드 수: {TOTAL_RECORDS:>10,}개                                    ║
║  네트워크 지연 시뮬레이션: {'ON' if SIMULATE_NETWORK_DELAY else 'OFF':<10}                    ║
║  지연 시간: {NETWORK_DELAY_MS:>10}ms                                   ║
║  배치 크기: {BATCH_SIZE:>10}개                                    ║
╚══════════════════════════════════════════════════════════════╝
""")

    # DB 세션
    db = database.SessionLocal()
    timer = BenchmarkTimer()
    
    success_count = 0
    failure_count = 0

    # 먼저 기존 유저/상품 ID 조회
    try:
        existing_users = db.query(models.User.id).limit(1000).all()
        existing_products = db.query(models.Product.id).limit(1000).all()
        
        if not existing_users or not existing_products:
            print("❌ 오류: 기존 유저/상품 데이터가 없습니다. initial_seeder를 먼저 실행하세요.")
            return None
            
        user_ids = [u[0] for u in existing_users]
        product_ids = [p[0] for p in existing_products]
        
    except Exception as e:
        print(f"❌ 데이터 조회 오류: {e}")
        return None

    # 주문 생성기
    order_gen = OrderGenerator()

    print(f"\n🚀 순차처리 벤치마크 시작... ({TOTAL_RECORDS}건)")
    print("-" * 60)

    timer.start()

    for i in range(TOTAL_RECORDS):
        record_start = time.perf_counter()
        
        try:
            # 랜덤 유저/상품 선택
            user_id = random.choice(user_ids)
            product_id = random.choice(product_ids)
            
            # 주문 데이터 생성
            order_data = order_gen.generate_single(user_id, product_id)
            
            # 네트워크 지연 시뮬레이션
            simulate_network_delay()
            
            # DB에 직접 저장 (순차처리)
            crud.create_order(db, order_data)
            
            success_count += 1
            
        except Exception as e:
            failure_count += 1
            db.rollback()
            
        record_end = time.perf_counter()
        latency_ms = (record_end - record_start) * 1000
        timer.record_latency(latency_ms)
        
        # 진행률 출력 (10% 단위)
        if (i + 1) % (TOTAL_RECORDS // 10) == 0:
            progress = (i + 1) / TOTAL_RECORDS * 100
            current_tps = (i + 1) / (time.perf_counter() - timer.start_time)
            print(f"  ⏳ {progress:.0f}% 완료 | {i + 1:,}건 | TPS: {current_tps:.1f}")

    timer.stop()

    # 결과 생성
    result = BenchmarkResult(
        test_name="주문 데이터 생성",
        mode="sequential",
        total_records=TOTAL_RECORDS,
        duration_seconds=timer.duration,
        records_per_second=success_count / timer.duration if timer.duration > 0 else 0,
        avg_latency_ms=timer.avg_latency,
        min_latency_ms=timer.min_latency,
        max_latency_ms=timer.max_latency,
        success_count=success_count,
        failure_count=failure_count,
        timestamp=datetime.now().isoformat(),
        extra_info={
            "network_delay_simulated": SIMULATE_NETWORK_DELAY,
            "network_delay_ms": NETWORK_DELAY_MS,
            "batch_size": BATCH_SIZE
        }
    )

    # 결과 출력 및 저장
    print_result_summary(result)
    save_result(result, "kafka_benchmark")
    
    db.close()
    return result


if __name__ == "__main__":
    result = run_sequential_benchmark()
    if result:
        print("\n✅ 순차처리 벤치마크 완료!")
    else:
        print("\n❌ 벤치마크 실패")
        sys.exit(1)
