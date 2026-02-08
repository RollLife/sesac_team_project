"""
PostgreSQL 집계 벤치마크

PostgreSQL의 GROUP BY를 사용한 기본 집계 성능을 측정합니다.
Spark Streaming과 비교하기 위한 기준선입니다.
"""

import os
import sys
import time
from datetime import datetime

# 프로젝트 루트를 sys.path에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from benchmark_common import BenchmarkResult, BenchmarkTimer, save_result, print_result_summary

from sqlalchemy import text
from database import database


# 벤치마크 설정
NUM_ITERATIONS = int(os.environ.get('BENCHMARK_ITERATIONS', 10))  # 반복 횟수


# 집계 쿼리 정의
AGGREGATION_QUERIES = {
    "category_revenue": """
        SELECT 
            p.category,
            COUNT(o.id) as order_count,
            SUM(o.total_amount) as total_revenue,
            AVG(o.total_amount) as avg_order_value
        FROM orders o
        JOIN products p ON o.product_id = p.id
        GROUP BY p.category
        ORDER BY total_revenue DESC
    """,
    
    "payment_stats": """
        SELECT 
            payment_method,
            COUNT(*) as count,
            SUM(total_amount) as total_revenue,
            AVG(total_amount) as avg_amount
        FROM orders
        GROUP BY payment_method
        ORDER BY count DESC
    """,
    
    "hourly_orders": """
        SELECT 
            DATE_TRUNC('hour', created_at) as hour,
            COUNT(*) as order_count,
            SUM(total_amount) as revenue
        FROM orders
        WHERE created_at >= NOW() - INTERVAL '24 hours'
        GROUP BY DATE_TRUNC('hour', created_at)
        ORDER BY hour DESC
    """,
    
    "user_stats": """
        SELECT 
            u.grade,
            COUNT(DISTINCT o.user_id) as unique_users,
            COUNT(o.id) as total_orders,
            SUM(o.total_amount) as total_spent,
            AVG(o.total_amount) as avg_order
        FROM orders o
        JOIN users u ON o.user_id = u.id
        GROUP BY u.grade
        ORDER BY total_spent DESC
    """,
    
    "top_products": """
        SELECT 
            p.name as product_name,
            p.category,
            COUNT(o.id) as order_count,
            SUM(o.total_amount) as total_revenue
        FROM orders o
        JOIN products p ON o.product_id = p.id
        GROUP BY p.id, p.name, p.category
        ORDER BY order_count DESC
        LIMIT 20
    """,
    
    "daily_trend": """
        SELECT 
            DATE(created_at) as date,
            COUNT(*) as order_count,
            SUM(total_amount) as daily_revenue,
            COUNT(DISTINCT user_id) as unique_buyers
        FROM orders
        WHERE created_at >= NOW() - INTERVAL '30 days'
        GROUP BY DATE(created_at)
        ORDER BY date DESC
    """
}


def run_sql_benchmark():
    """PostgreSQL 집계 벤치마크 실행"""
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║           PostgreSQL 집계 벤치마크                           ║
╠══════════════════════════════════════════════════════════════╣
║  집계 쿼리 수: {len(AGGREGATION_QUERIES):>10}개                                ║
║  반복 횟수: {NUM_ITERATIONS:>10}회                                   ║
╚══════════════════════════════════════════════════════════════╝
""")

    db = database.SessionLocal()
    timer = BenchmarkTimer()
    
    query_results = {}
    total_rows = 0

    # 먼저 orders 테이블 레코드 수 확인
    try:
        count_result = db.execute(text("SELECT COUNT(*) FROM orders")).scalar()
        print(f"📊 orders 테이블 레코드 수: {count_result:,}건")
        total_rows = count_result
    except Exception as e:
        print(f"❌ 테이블 조회 오류: {e}")
        return None

    print(f"\n🚀 PostgreSQL 집계 벤치마크 시작...")
    print("-" * 60)

    timer.start()
    all_latencies = []

    for iteration in range(NUM_ITERATIONS):
        iteration_start = time.perf_counter()
        
        for query_name, query in AGGREGATION_QUERIES.items():
            query_start = time.perf_counter()
            
            try:
                result = db.execute(text(query))
                rows = result.fetchall()
                
                if query_name not in query_results:
                    query_results[query_name] = {
                        'row_count': len(rows),
                        'latencies': []
                    }
                
            except Exception as e:
                print(f"❌ 쿼리 오류 ({query_name}): {e}")
                continue
            
            query_end = time.perf_counter()
            latency = (query_end - query_start) * 1000
            query_results[query_name]['latencies'].append(latency)
            all_latencies.append(latency)
        
        iteration_end = time.perf_counter()
        iteration_time = (iteration_end - iteration_start) * 1000
        
        # 진행률 출력
        if (iteration + 1) % max(1, NUM_ITERATIONS // 5) == 0:
            progress = (iteration + 1) / NUM_ITERATIONS * 100
            print(f"  ⏳ {progress:.0f}% 완료 | 반복 {iteration + 1}/{NUM_ITERATIONS} | {iteration_time:.1f}ms")

    timer.stop()

    # 쿼리별 결과 요약
    print(f"\n{'='*60}")
    print("쿼리별 성능 분석")
    print(f"{'='*60}")
    print(f"{'쿼리명':<20} {'결과행':<8} {'평균(ms)':<10} {'최소(ms)':<10} {'최대(ms)':<10}")
    print("-" * 60)
    
    for query_name, data in query_results.items():
        latencies = data['latencies']
        if latencies:
            avg_lat = sum(latencies) / len(latencies)
            min_lat = min(latencies)
            max_lat = max(latencies)
            print(f"{query_name:<20} {data['row_count']:<8} {avg_lat:<10.2f} {min_lat:<10.2f} {max_lat:<10.2f}")

    # 결과 생성
    total_queries = len(AGGREGATION_QUERIES) * NUM_ITERATIONS
    result = BenchmarkResult(
        test_name="PostgreSQL 집계 쿼리",
        mode="sql",
        total_records=total_queries,
        duration_seconds=timer.duration,
        records_per_second=total_queries / timer.duration if timer.duration > 0 else 0,
        avg_latency_ms=sum(all_latencies) / len(all_latencies) if all_latencies else 0,
        min_latency_ms=min(all_latencies) if all_latencies else 0,
        max_latency_ms=max(all_latencies) if all_latencies else 0,
        success_count=total_queries,
        failure_count=0,
        timestamp=datetime.now().isoformat(),
        extra_info={
            "query_count": len(AGGREGATION_QUERIES),
            "iterations": NUM_ITERATIONS,
            "total_orders": total_rows,
            "query_stats": {
                name: {
                    'avg_ms': sum(data['latencies']) / len(data['latencies']) if data['latencies'] else 0,
                    'row_count': data['row_count']
                }
                for name, data in query_results.items()
            }
        }
    )

    # 결과 출력 및 저장
    print_result_summary(result)
    save_result(result, "spark_benchmark")
    
    db.close()
    return result


if __name__ == "__main__":
    result = run_sql_benchmark()
    if result:
        print("\n✅ PostgreSQL 집계 벤치마크 완료!")
    else:
        print("\n❌ 벤치마크 실패")
        sys.exit(1)
