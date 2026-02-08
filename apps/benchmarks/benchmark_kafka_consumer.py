"""
Kafka 벤치마크 컨슈머

Kafka에서 메시지를 소비하고 DB에 저장하는 시간을 측정합니다.
병렬 처리의 효과를 보여주기 위한 벤치마크입니다.
"""

import os
import sys
import time
import json
from datetime import datetime
from threading import Thread, Event

# 프로젝트 루트를 sys.path에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from benchmark_common import BenchmarkResult, BenchmarkTimer, save_result, print_result_summary

from database import database, crud
from confluent_kafka import Consumer, KafkaError


# 벤치마크 설정
EXPECTED_RECORDS = int(os.environ.get('BENCHMARK_RECORDS', 5000))
KAFKA_BOOTSTRAP_SERVERS = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'kafka1:29092,kafka2:29093,kafka3:29094')
KAFKA_TOPIC = os.environ.get('KAFKA_TOPIC_ORDERS', 'orders')
CONSUMER_GROUP = os.environ.get('CONSUMER_GROUP', 'benchmark-consumer-group')
CONSUMER_ID = os.environ.get('CONSUMER_ID', 'benchmark-consumer-1')
TIMEOUT_SECONDS = int(os.environ.get('BENCHMARK_TIMEOUT', 300))  # 5분 타임아웃


class KafkaBenchmarkConsumer:
    """Kafka 벤치마크 컨슈머"""

    def __init__(self, consumer_id: str):
        self.consumer_id = consumer_id
        self.consumer = Consumer({
            'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
            'group.id': CONSUMER_GROUP,
            'client.id': consumer_id,
            'auto.offset.reset': 'earliest',
            'enable.auto.commit': False,
        })
        self.consumer.subscribe([KAFKA_TOPIC])
        
        self.consumed_count = 0
        self.saved_count = 0
        self.failed_count = 0
        self.latencies = []
        self.running = True
        self.db = database.SessionLocal()

    def process_message(self, message) -> float:
        """메시지 처리 및 DB 저장"""
        start = time.perf_counter()
        
        try:
            # 메시지 파싱
            value = message.value().decode('utf-8')
            data = json.loads(value)
            
            # 주문 데이터 추출
            if 'order' in data:
                order_data = data['order']
                crud.create_order(self.db, order_data)
                self.saved_count += 1
            
            # 커밋
            self.consumer.commit(message=message)
            
        except Exception as e:
            self.failed_count += 1
            self.db.rollback()
        
        end = time.perf_counter()
        latency = (end - start) * 1000
        self.latencies.append(latency)
        return latency

    def consume_batch(self, expected_count: int, timeout: int = 300):
        """지정된 개수의 메시지를 소비"""
        print(f"\n[{self.consumer_id}] 메시지 소비 시작... (목표: {expected_count}건)")
        
        start_time = time.perf_counter()
        last_report_time = start_time
        
        while self.consumed_count < expected_count and self.running:
            # 타임아웃 체크
            elapsed = time.perf_counter() - start_time
            if elapsed > timeout:
                print(f"\n[{self.consumer_id}] ⚠️ 타임아웃 ({timeout}초)")
                break
            
            # 메시지 폴링
            message = self.consumer.poll(timeout=1.0)
            
            if message is None:
                continue
                
            if message.error():
                if message.error().code() == KafkaError._PARTITION_EOF:
                    continue
                else:
                    print(f"[{self.consumer_id}] 오류: {message.error()}")
                    continue
            
            # 메시지 처리
            self.process_message(message)
            self.consumed_count += 1
            
            # 진행률 출력 (5초마다)
            current_time = time.perf_counter()
            if current_time - last_report_time >= 5:
                progress = self.consumed_count / expected_count * 100
                tps = self.consumed_count / (current_time - start_time)
                print(f"  [{self.consumer_id}] {progress:.1f}% | {self.consumed_count:,}건 | TPS: {tps:.1f}")
                last_report_time = current_time
        
        return time.perf_counter() - start_time

    def close(self):
        """리소스 정리"""
        self.running = False
        self.consumer.close()
        self.db.close()


def run_consumer_benchmark():
    """컨슈머 벤치마크 실행"""
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║             Kafka 컨슈머 벤치마크                             ║
╠══════════════════════════════════════════════════════════════╣
║  예상 레코드: {EXPECTED_RECORDS:>10,}개                                ║
║  Consumer ID: {CONSUMER_ID:<42} ║
║  Group ID: {CONSUMER_GROUP:<45} ║
║  타임아웃: {TIMEOUT_SECONDS:>10}초                                   ║
╚══════════════════════════════════════════════════════════════╝
""")

    timer = BenchmarkTimer()
    consumer = KafkaBenchmarkConsumer(CONSUMER_ID)

    print(f"\n🚀 컨슈머 벤치마크 시작...")
    print("-" * 60)

    timer.start()
    duration = consumer.consume_batch(EXPECTED_RECORDS, TIMEOUT_SECONDS)
    timer.stop()

    # 결과 생성
    latencies = consumer.latencies
    result = BenchmarkResult(
        test_name="Kafka 메시지 소비 및 DB 저장",
        mode="kafka_consumer",
        total_records=EXPECTED_RECORDS,
        duration_seconds=timer.duration,
        records_per_second=consumer.saved_count / timer.duration if timer.duration > 0 else 0,
        avg_latency_ms=sum(latencies) / len(latencies) if latencies else 0,
        min_latency_ms=min(latencies) if latencies else 0,
        max_latency_ms=max(latencies) if latencies else 0,
        success_count=consumer.saved_count,
        failure_count=consumer.failed_count,
        timestamp=datetime.now().isoformat(),
        extra_info={
            "consumer_id": CONSUMER_ID,
            "consumer_group": CONSUMER_GROUP,
            "consumed_count": consumer.consumed_count
        }
    )

    # 결과 출력 및 저장
    print_result_summary(result)
    save_result(result, "kafka_consumer_benchmark")
    
    consumer.close()
    return result


if __name__ == "__main__":
    result = run_consumer_benchmark()
    if result:
        print("\n✅ 컨슈머 벤치마크 완료!")
    else:
        print("\n❌ 벤치마크 실패")
        sys.exit(1)
