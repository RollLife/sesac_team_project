"""
Kafka 벤치마크 결과 비교 및 리포트 생성

순차처리와 Kafka 처리의 결과를 비교하고 HTML 리포트를 생성합니다.
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

from benchmark_common import load_results, generate_comparison_html, RESULTS_DIR


def find_latest_results():
    """가장 최근 벤치마크 결과 파일 찾기"""
    sequential_files = glob.glob(os.path.join(RESULTS_DIR, "kafka_benchmark_sequential_*.json"))
    kafka_files = glob.glob(os.path.join(RESULTS_DIR, "kafka_benchmark_kafka_*.json"))
    
    latest_sequential = max(sequential_files, key=os.path.getctime) if sequential_files else None
    latest_kafka = max(kafka_files, key=os.path.getctime) if kafka_files else None
    
    return latest_sequential, latest_kafka


def compare_results():
    """결과 비교 및 리포트 생성"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║           Kafka 벤치마크 결과 비교                           ║
╚══════════════════════════════════════════════════════════════╝
""")

    sequential_file, kafka_file = find_latest_results()
    
    if not sequential_file or not kafka_file:
        print("❌ 벤치마크 결과 파일을 찾을 수 없습니다.")
        print(f"   순차처리 결과: {'있음' if sequential_file else '없음'}")
        print(f"   Kafka 결과: {'있음' if kafka_file else '없음'}")
        return None
    
    # 결과 로드
    with open(sequential_file, 'r', encoding='utf-8') as f:
        sequential_result = json.load(f)
    
    with open(kafka_file, 'r', encoding='utf-8') as f:
        kafka_result = json.load(f)
    
    # 비교 출력
    print(f"📊 순차처리 결과: {os.path.basename(sequential_file)}")
    print(f"📊 Kafka 결과: {os.path.basename(kafka_file)}")
    print()
    
    # 성능 비교
    seq_tps = sequential_result.get('records_per_second', 0)
    kafka_tps = kafka_result.get('records_per_second', 0)
    
    seq_duration = sequential_result.get('duration_seconds', 0)
    kafka_duration = kafka_result.get('duration_seconds', 0)
    
    seq_latency = sequential_result.get('avg_latency_ms', 0)
    kafka_latency = kafka_result.get('avg_latency_ms', 0)
    
    print("┌────────────────────┬──────────────┬──────────────┬─────────────┐")
    print("│       지표         │   순차처리   │    Kafka     │    차이     │")
    print("├────────────────────┼──────────────┼──────────────┼─────────────┤")
    
    # TPS 비교
    tps_diff = ((kafka_tps - seq_tps) / seq_tps * 100) if seq_tps > 0 else 0
    tps_indicator = "↑" if tps_diff > 0 else "↓"
    print(f"│ TPS (records/sec)  │ {seq_tps:>10.1f}   │ {kafka_tps:>10.1f}   │ {tps_indicator}{abs(tps_diff):>6.1f}%    │")
    
    # 소요시간 비교
    duration_diff = ((seq_duration - kafka_duration) / seq_duration * 100) if seq_duration > 0 else 0
    duration_indicator = "↑" if duration_diff > 0 else "↓"
    print(f"│ 소요시간 (초)       │ {seq_duration:>10.2f}   │ {kafka_duration:>10.2f}   │ {duration_indicator}{abs(duration_diff):>6.1f}%    │")
    
    # 평균 지연 비교
    latency_diff = ((seq_latency - kafka_latency) / seq_latency * 100) if seq_latency > 0 else 0
    latency_indicator = "↑" if latency_diff > 0 else "↓"
    print(f"│ 평균 지연 (ms)      │ {seq_latency:>10.2f}   │ {kafka_latency:>10.2f}   │ {latency_indicator}{abs(latency_diff):>6.1f}%    │")
    
    print("└────────────────────┴──────────────┴──────────────┴─────────────┘")
    
    # 결론
    print()
    if kafka_tps > seq_tps:
        improvement = (kafka_tps / seq_tps - 1) * 100
        print(f"✅ 결론: Kafka가 순차처리보다 {improvement:.1f}% 더 빠름")
        print("   → 비동기 처리로 인한 Producer 응답 속도 향상")
        print("   → 병렬 Consumer 사용 시 추가 성능 향상 가능")
    else:
        slowdown = (seq_tps / kafka_tps - 1) * 100
        print(f"⚠️ 결론: 순차처리가 Kafka보다 {slowdown:.1f}% 더 빠름")
        print("   → 소규모 데이터에서는 Kafka 오버헤드가 있을 수 있음")
        print("   → 대규모/분산 환경에서 Kafka의 장점이 더 드러남")
    
    # HTML 리포트 생성
    print()
    results = [sequential_result, kafka_result]
    html_path = generate_comparison_html(results, "kafka_comparison_report")
    print(f"\n📄 HTML 리포트: {html_path}")
    
    return results


if __name__ == "__main__":
    compare_results()
