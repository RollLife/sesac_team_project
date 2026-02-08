"""
Kafka 벤치마크 프로듀서

Kafka를 통해 데이터를 발행하는 방식의 성능을 측정합니다.
비동기 발행의 장점을 보여주기 위한 벤치마크입니다.
"""

import os
import sys
import time
import random
import json
from datetime import datetime

# 프로젝트 루트를 sys.path에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from benchmark_common import BenchmarkResult, BenchmarkTimer, save_result, print_result_summary

from database import database, models
from collect.order_generator import OrderGenerator
from confluent_kafka import Producer


# 벤치마크 설정 (환경변수로 오버라이드 가능)
TOTAL_RECORDS = int(os.environ.get('BENCHMARK_RECORDS', 5000))
KAFKA_BOOTSTRAP_SERVERS = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'kafka1:29092,kafka2:29093,kafka3:29094')
KAFKA_TOPIC = os.environ.get('KAFKA_TOPIC_ORDERS', 'orders')


class KafkaBenchmarkProducer:
    """Kafka 벤치마크 프로듀서"""

    def __init__(self):
        self.producer = Producer({
            'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
            'client.id': 'benchmark-producer',
            'acks': 'all',  # 모든 replica에 쓰기 완료 확인
            'linger.ms': 5,  # 배치 전송 대기 시간
            'batch.size': 16384,  # 배치 크기
        })
        self.delivered_count = 0
        self.failed_count = 0
        self.latencies = []

    def delivery_callback(self, err, msg):
        """메시지 전송 완료 콜백"""
        if err:
            self.failed_count += 1
        else:
            self.delivered_count += 1

    def produce_message(self, topic: str, data: dict) -> float:
        """메시지 발행 및 지연시간 측정"""
        start = time.perf_counter()
        
        message = json.dumps(data, ensure_ascii=False, default=str)
        self.producer.produce(
            topic,
            value=message.encode('utf-8'),
            callback=self.delivery_callback
        )
        
        end = time.perf_counter()
        latency = (end - start) * 1000
        self.latencies.append(latency)
        return latency

    def flush(self):
        """남은 메시지 모두 전송"""
        self.producer.flush()


def run_kafka_benchmark():
    """Kafka 벤치마크 실행"""
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║             Kafka 벤치마크 (비동기 발행)                      ║
╠══════════════════════════════════════════════════════════════╣
║  레코드 수: {TOTAL_RECORDS:>10,}개                                    ║
║  Kafka Servers: {KAFKA_BOOTSTRAP_SERVERS[:30]:<30}     ║
║  Topic: {KAFKA_TOPIC:<48} ║
╚══════════════════════════════════════════════════════════════╝
""")

    # DB 세션 (유저/상품 ID 조회용)
    db = database.SessionLocal()
    timer = BenchmarkTimer()
    
    # Kafka 프로듀서
    kafka_producer = KafkaBenchmarkProducer()

    # 기존 유저/상품 ID 조회
    try:
        existing_users = db.query(models.User.user_id).limit(1000).all()
        existing_products = db.query(models.Product.product_id).limit(1000).all()
        
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

    print(f"\n🚀 Kafka 벤치마크 시작... ({TOTAL_RECORDS}건)")
    print("-" * 60)

    timer.start()
    produce_start = time.perf_counter()

    for i in range(TOTAL_RECORDS):
        # 랜덤 유저/상품 선택
        user_id = random.choice(user_ids)
        product_id = random.choice(product_ids)
        
        # 주문 데이터 생성
        order_data = order_gen.generate_single(user_id, product_id)
        
        # Kafka 메시지 구성
        kafka_message = {
            "event_type": "order_created",
            "timestamp": datetime.now().isoformat(),
            "order": order_data
        }
        
        # Kafka에 발행
        kafka_producer.produce_message(KAFKA_TOPIC, kafka_message)
        
        # 진행률 출력 (10% 단위)
        if (i + 1) % (TOTAL_RECORDS // 10) == 0:
            progress = (i + 1) / TOTAL_RECORDS * 100
            current_tps = (i + 1) / (time.perf_counter() - produce_start)
            print(f"  ⏳ {progress:.0f}% 발행 | {i + 1:,}건 | TPS: {current_tps:.1f}")
        
        # 주기적으로 poll (내부 이벤트 처리)
        if (i + 1) % 100 == 0:
            kafka_producer.producer.poll(0)

    produce_end = time.perf_counter()
    produce_duration = produce_end - produce_start
    
    print(f"\n  ⏳ 메시지 플러시 중...")
    flush_start = time.perf_counter()
    kafka_producer.flush()
    flush_end = time.perf_counter()
    flush_duration = flush_end - flush_start
    
    timer.stop()

    # 결과 생성
    latencies = kafka_producer.latencies
    result = BenchmarkResult(
        test_name="주문 데이터 생성",
        mode="kafka",
        total_records=TOTAL_RECORDS,
        duration_seconds=timer.duration,
        records_per_second=kafka_producer.delivered_count / timer.duration if timer.duration > 0 else 0,
        avg_latency_ms=sum(latencies) / len(latencies) if latencies else 0,
        min_latency_ms=min(latencies) if latencies else 0,
        max_latency_ms=max(latencies) if latencies else 0,
        success_count=kafka_producer.delivered_count,
        failure_count=kafka_producer.failed_count,
        timestamp=datetime.now().isoformat(),
        extra_info={
            "produce_duration": produce_duration,
            "flush_duration": flush_duration,
            "kafka_servers": KAFKA_BOOTSTRAP_SERVERS,
            "topic": KAFKA_TOPIC
        }
    )

    # 결과 출력 및 저장
    print_result_summary(result)
    print(f"  ℹ️  발행 시간: {produce_duration:.2f}초")
    print(f"  ℹ️  플러시 시간: {flush_duration:.2f}초")
    save_result(result, "kafka_benchmark")
    
    db.close()
    return result


if __name__ == "__main__":
    result = run_kafka_benchmark()
    if result:
        print("\n✅ Kafka 벤치마크 완료!")
    else:
        print("\n❌ 벤치마크 실패")
        sys.exit(1)
