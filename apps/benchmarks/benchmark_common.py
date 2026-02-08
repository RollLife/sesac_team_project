"""
벤치마크 공통 모듈

모든 벤치마크에서 사용하는 공통 기능:
- 시간 측정
- 결과 저장
- 리포트 생성
"""

import os
import sys
import json
import time
from datetime import datetime
from typing import Dict, List, Any
from dataclasses import dataclass, asdict

# 프로젝트 루트를 sys.path에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 결과 저장 디렉토리
RESULTS_DIR = os.path.join(project_root, "benchmark_results")
os.makedirs(RESULTS_DIR, exist_ok=True)


@dataclass
class BenchmarkResult:
    """벤치마크 결과 데이터 클래스"""
    test_name: str
    mode: str  # 'sequential' | 'kafka' | 'sql' | 'spark'
    total_records: int
    duration_seconds: float
    records_per_second: float  # TPS
    avg_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    success_count: int
    failure_count: int
    timestamp: str
    extra_info: Dict[str, Any] = None

    def to_dict(self) -> Dict:
        result = asdict(self)
        if result['extra_info'] is None:
            result['extra_info'] = {}
        return result


class BenchmarkTimer:
    """벤치마크 타이머"""

    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.latencies = []

    def start(self):
        self.start_time = time.perf_counter()

    def stop(self):
        self.end_time = time.perf_counter()

    def record_latency(self, latency_ms: float):
        self.latencies.append(latency_ms)

    @property
    def duration(self) -> float:
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0

    @property
    def avg_latency(self) -> float:
        return sum(self.latencies) / len(self.latencies) if self.latencies else 0

    @property
    def min_latency(self) -> float:
        return min(self.latencies) if self.latencies else 0

    @property
    def max_latency(self) -> float:
        return max(self.latencies) if self.latencies else 0


def save_result(result: BenchmarkResult, prefix: str = "benchmark"):
    """결과를 JSON 파일로 저장"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{result.mode}_{timestamp}.json"
    filepath = os.path.join(RESULTS_DIR, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)

    print(f"✅ 결과 저장: {filepath}")
    return filepath


def load_results(pattern: str = None) -> List[Dict]:
    """저장된 결과 파일들을 로드"""
    results = []
    for filename in os.listdir(RESULTS_DIR):
        if filename.endswith('.json'):
            if pattern is None or pattern in filename:
                filepath = os.path.join(RESULTS_DIR, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    results.append(json.load(f))
    return results


def generate_comparison_html(results: List[Dict], output_name: str) -> str:
    """비교 리포트 HTML 생성"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{output_name}_{timestamp}.html"
    filepath = os.path.join(RESULTS_DIR, filename)

    # 결과 정렬 (모드별)
    sorted_results = sorted(results, key=lambda x: x.get('mode', ''))

    html_content = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>벤치마크 성능 비교 리포트</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            padding: 40px 20px;
            color: #fff;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{
            text-align: center;
            margin-bottom: 40px;
        }}
        .header h1 {{
            font-size: 2.5em;
            background: linear-gradient(90deg, #00d4ff, #7b2cbf);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }}
        .header .timestamp {{ color: #888; font-size: 0.9em; }}
        .card {{
            background: rgba(255,255,255,0.05);
            border-radius: 16px;
            padding: 30px;
            margin-bottom: 25px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.1);
        }}
        .card h2 {{
            color: #00d4ff;
            margin-bottom: 20px;
            font-size: 1.5em;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th, td {{
            padding: 15px 12px;
            text-align: center;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }}
        th {{
            background: rgba(0,212,255,0.2);
            color: #00d4ff;
            font-weight: 600;
        }}
        tr:hover {{ background: rgba(255,255,255,0.05); }}
        .metric-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-top: 30px;
        }}
        .metric-card {{
            background: linear-gradient(135deg, #7b2cbf 0%, #00d4ff 100%);
            border-radius: 12px;
            padding: 25px;
            text-align: center;
        }}
        .metric-card .label {{ font-size: 0.9em; opacity: 0.9; }}
        .metric-card .value {{ font-size: 2.5em; font-weight: bold; }}
        .metric-card .unit {{ font-size: 0.8em; opacity: 0.8; }}
        .improvement {{ color: #00ff88; font-weight: bold; }}
        .slower {{ color: #ff6b6b; font-weight: bold; }}
        .chart-container {{
            margin-top: 30px;
            height: 300px;
            background: rgba(0,0,0,0.3);
            border-radius: 8px;
            display: flex;
            align-items: flex-end;
            justify-content: space-around;
            padding: 20px;
        }}
        .bar {{
            width: 100px;
            background: linear-gradient(180deg, #00d4ff, #7b2cbf);
            border-radius: 8px 8px 0 0;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: flex-end;
            padding: 10px;
            transition: all 0.3s;
        }}
        .bar:hover {{ transform: scale(1.05); }}
        .bar .value {{ font-weight: bold; font-size: 1.2em; }}
        .bar .label {{ margin-top: 10px; font-size: 0.8em; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 벤치마크 성능 비교 리포트</h1>
            <p class="timestamp">생성 시간: {datetime.now().strftime("%Y년 %m월 %d일 %H:%M:%S")}</p>
        </div>

        <div class="card">
            <h2>📊 상세 결과</h2>
            <table>
                <thead>
                    <tr>
                        <th>테스트</th>
                        <th>모드</th>
                        <th>레코드 수</th>
                        <th>소요시간(초)</th>
                        <th>TPS</th>
                        <th>평균 지연(ms)</th>
                        <th>성공/실패</th>
                    </tr>
                </thead>
                <tbody>
"""

    for r in sorted_results:
        html_content += f"""                    <tr>
                        <td>{r.get('test_name', 'N/A')}</td>
                        <td><strong>{r.get('mode', 'N/A').upper()}</strong></td>
                        <td>{r.get('total_records', 0):,}</td>
                        <td>{r.get('duration_seconds', 0):.2f}</td>
                        <td><strong>{r.get('records_per_second', 0):.1f}</strong></td>
                        <td>{r.get('avg_latency_ms', 0):.2f}</td>
                        <td>{r.get('success_count', 0):,} / {r.get('failure_count', 0)}</td>
                    </tr>
"""

    # 성능 비교 계산
    if len(sorted_results) >= 2:
        modes = [r.get('mode', '') for r in sorted_results]
        tps_values = [r.get('records_per_second', 0) for r in sorted_results]

        if tps_values[0] > 0 and tps_values[1] > 0:
            improvement = ((tps_values[1] - tps_values[0]) / tps_values[0]) * 100
            faster_mode = modes[1] if improvement > 0 else modes[0]
            improvement_class = "improvement" if improvement > 0 else "slower"

            html_content += f"""
                </tbody>
            </table>

            <div class="metric-cards">
                <div class="metric-card">
                    <div class="label">{modes[0].upper()} TPS</div>
                    <div class="value">{tps_values[0]:.1f}</div>
                    <div class="unit">records/sec</div>
                </div>
                <div class="metric-card">
                    <div class="label">{modes[1].upper()} TPS</div>
                    <div class="value">{tps_values[1]:.1f}</div>
                    <div class="unit">records/sec</div>
                </div>
                <div class="metric-card">
                    <div class="label">성능 차이</div>
                    <div class="value {improvement_class}">{abs(improvement):.1f}%</div>
                    <div class="unit">{faster_mode.upper()} 우세</div>
                </div>
            </div>

            <div class="chart-container">
                <div class="bar" style="height: {min(tps_values[0] / max(tps_values) * 250, 250)}px;">
                    <div class="value">{tps_values[0]:.0f}</div>
                    <div class="label">{modes[0].upper()}</div>
                </div>
                <div class="bar" style="height: {min(tps_values[1] / max(tps_values) * 250, 250)}px;">
                    <div class="value">{tps_values[1]:.0f}</div>
                    <div class="label">{modes[1].upper()}</div>
                </div>
            </div>
"""
    else:
        html_content += """
                </tbody>
            </table>
"""

    html_content += """
        </div>

        <div class="card">
            <h2>💡 해석 가이드</h2>
            <ul style="line-height: 2; padding-left: 20px; color: #ccc;">
                <li><strong>TPS (Throughput)</strong>: 초당 처리 레코드 수. 높을수록 좋음</li>
                <li><strong>평균 지연</strong>: 단일 레코드 처리에 걸리는 시간. 낮을수록 좋음</li>
                <li><strong>Kafka의 장점</strong>: 비동기 처리로 Producer가 빠르게 반환, 장애 복구 가능</li>
                <li><strong>Spark의 장점</strong>: 대용량 데이터 분산 병렬 처리</li>
            </ul>
        </div>
    </div>
</body>
</html>
"""

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"✅ HTML 리포트 생성: {filepath}")
    return filepath


def print_result_summary(result: BenchmarkResult):
    """결과 요약 출력"""
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                    벤치마크 결과 요약                         ║
╠══════════════════════════════════════════════════════════════╣
║  테스트: {result.test_name:<48} ║
║  모드: {result.mode.upper():<50} ║
╠══════════════════════════════════════════════════════════════╣
║  총 레코드: {result.total_records:>10,}개                              ║
║  소요 시간: {result.duration_seconds:>10.2f}초                             ║
║  TPS:       {result.records_per_second:>10.2f} records/sec                  ║
╠══════════════════════════════════════════════════════════════╣
║  평균 지연: {result.avg_latency_ms:>10.2f}ms                               ║
║  최소 지연: {result.min_latency_ms:>10.2f}ms                               ║
║  최대 지연: {result.max_latency_ms:>10.2f}ms                               ║
╠══════════════════════════════════════════════════════════════╣
║  성공: {result.success_count:>10,}개 | 실패: {result.failure_count:>10,}개               ║
╚══════════════════════════════════════════════════════════════╝
""")
