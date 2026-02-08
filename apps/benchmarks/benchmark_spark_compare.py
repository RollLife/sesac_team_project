"""
Spark 벤치마크 결과 비교 및 리포트 생성

PostgreSQL과 Spark의 집계 성능을 비교하고 HTML 리포트를 생성합니다.
"""

import os
import sys
import json
import glob
from datetime import datetime

# 프로젝트 루트를 sys.path에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from benchmark_common import generate_comparison_html, RESULTS_DIR


def find_latest_results():
    """가장 최근 벤치마크 결과 파일 찾기"""
    sql_files = glob.glob(os.path.join(RESULTS_DIR, "spark_benchmark_sql_*.json"))
    spark_files = glob.glob(os.path.join(RESULTS_DIR, "spark_benchmark_spark_*.json"))
    
    latest_sql = max(sql_files, key=os.path.getctime) if sql_files else None
    latest_spark = max(spark_files, key=os.path.getctime) if spark_files else None
    
    return latest_sql, latest_spark


def compare_results():
    """결과 비교 및 리포트 생성"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║           Spark vs PostgreSQL 집계 성능 비교                 ║
╚══════════════════════════════════════════════════════════════╝
""")

    sql_file, spark_file = find_latest_results()
    
    if not sql_file or not spark_file:
        print("❌ 벤치마크 결과 파일을 찾을 수 없습니다.")
        print(f"   PostgreSQL 결과: {'있음' if sql_file else '없음'}")
        print(f"   Spark 결과: {'있음' if spark_file else '없음'}")
        return None
    
    # 결과 로드
    with open(sql_file, 'r', encoding='utf-8') as f:
        sql_result = json.load(f)
    
    with open(spark_file, 'r', encoding='utf-8') as f:
        spark_result = json.load(f)
    
    # 비교 출력
    print(f"📊 PostgreSQL 결과: {os.path.basename(sql_file)}")
    print(f"📊 Spark 결과: {os.path.basename(spark_file)}")
    print()
    
    # 성능 비교
    sql_qps = sql_result.get('records_per_second', 0)
    spark_qps = spark_result.get('records_per_second', 0)
    
    sql_duration = sql_result.get('duration_seconds', 0)
    spark_duration = spark_result.get('duration_seconds', 0)
    
    sql_latency = sql_result.get('avg_latency_ms', 0)
    spark_latency = spark_result.get('avg_latency_ms', 0)
    
    print("┌────────────────────┬──────────────┬──────────────┬─────────────┐")
    print("│       지표         │  PostgreSQL  │    Spark     │    차이     │")
    print("├────────────────────┼──────────────┼──────────────┼─────────────┤")
    
    # QPS 비교
    qps_diff = ((spark_qps - sql_qps) / sql_qps * 100) if sql_qps > 0 else 0
    qps_indicator = "↑" if qps_diff > 0 else "↓"
    print(f"│ QPS (queries/sec)  │ {sql_qps:>10.1f}   │ {spark_qps:>10.1f}   │ {qps_indicator}{abs(qps_diff):>6.1f}%    │")
    
    # 소요시간 비교
    duration_diff = ((sql_duration - spark_duration) / sql_duration * 100) if sql_duration > 0 else 0
    duration_indicator = "↑" if duration_diff > 0 else "↓"
    print(f"│ 소요시간 (초)       │ {sql_duration:>10.2f}   │ {spark_duration:>10.2f}   │ {duration_indicator}{abs(duration_diff):>6.1f}%    │")
    
    # 평균 지연 비교
    latency_diff = ((sql_latency - spark_latency) / sql_latency * 100) if sql_latency > 0 else 0
    latency_indicator = "↑" if latency_diff > 0 else "↓"
    print(f"│ 평균 지연 (ms)      │ {sql_latency:>10.2f}   │ {spark_latency:>10.2f}   │ {latency_indicator}{abs(latency_diff):>6.1f}%    │")
    
    print("└────────────────────┴──────────────┴──────────────┴─────────────┘")
    
    # 쿼리별 상세 비교
    sql_stats = sql_result.get('extra_info', {}).get('query_stats', {})
    spark_stats = spark_result.get('extra_info', {}).get('query_stats', {})
    
    if sql_stats and spark_stats:
        print(f"\n{'='*60}")
        print("쿼리별 상세 비교")
        print(f"{'='*60}")
        print(f"{'쿼리명':<20} {'PostgreSQL':<12} {'Spark':<12} {'차이':<10}")
        print("-" * 60)
        
        for query_name in sql_stats:
            if query_name in spark_stats:
                sql_avg = sql_stats[query_name].get('avg_ms', 0)
                spark_avg = spark_stats[query_name].get('avg_ms', 0)
                diff = ((sql_avg - spark_avg) / sql_avg * 100) if sql_avg > 0 else 0
                indicator = "↑" if diff > 0 else "↓"
                print(f"{query_name:<20} {sql_avg:>10.2f}ms {spark_avg:>10.2f}ms {indicator}{abs(diff):>6.1f}%")
    
    # 결론
    print()
    if spark_qps > sql_qps:
        improvement = (spark_qps / sql_qps - 1) * 100
        print(f"✅ 결론: Spark가 PostgreSQL보다 {improvement:.1f}% 더 빠름")
        print("   → 분산 처리와 인메모리 연산의 효과")
        print("   → 대용량 데이터에서 더 큰 성능 향상 기대")
    else:
        slowdown = (sql_qps / spark_qps - 1) * 100
        print(f"⚠️ 결론: PostgreSQL이 Spark보다 {slowdown:.1f}% 더 빠름")
        print("   → 소규모 데이터에서는 Spark 오버헤드가 있을 수 있음")
        print("   → 데이터 규모가 클수록 Spark의 장점이 드러남")
    
    # HTML 리포트 생성
    print()
    results = [sql_result, spark_result]
    html_path = generate_comparison_html(results, "spark_comparison_report")
    print(f"\n📄 HTML 리포트: {html_path}")
    
    return results


if __name__ == "__main__":
    compare_results()
