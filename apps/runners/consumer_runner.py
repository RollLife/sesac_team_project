"""
모든 카프카 컨슈머 실행 스크립트

총 9개 컨슈머 실행:
- users_group: 3개 (user_consumer_1, 2, 3)
- products_group: 3개 (product_consumer_1, 2, 3)
- orders_group: 3개 (order_consumer_1, 2, 3)
"""

import os
import sys
import multiprocessing
import signal
import time

# 프로젝트 루트를 sys.path에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from kafka.consumers.user_consumer import UserConsumer
from kafka.consumers.product_consumer import ProductConsumer
from kafka.consumers.order_consumer import OrderConsumer


# 전역 프로세스 리스트
processes = []


def run_user_consumer(consumer_id: str):
    """유저 컨슈머 실행"""
    consumer = UserConsumer(consumer_id=consumer_id)
    consumer.start()


def run_product_consumer(consumer_id: str):
    """상품 컨슈머 실행"""
    consumer = ProductConsumer(consumer_id=consumer_id)
    consumer.start()


def run_order_consumer(consumer_id: str):
    """주문 컨슈머 실행"""
    consumer = OrderConsumer(consumer_id=consumer_id)
    consumer.start()


def signal_handler(sig, frame):
    """종료 시그널 핸들러 (Ctrl+C)"""
    print("\n\n⚠️ 종료 신호 수신. 모든 컨슈머를 정리하는 중...")

    # 모든 프로세스 종료
    for process in processes:
        if process.is_alive():
            print(f"   {process.name} 종료 중...")
            process.terminate()

    # 모든 프로세스가 종료될 때까지 대기 (최대 5초)
    for process in processes:
        process.join(timeout=5)
        if process.is_alive():
            print(f"   {process.name} 강제 종료...")
            process.kill()

    print("\n✅ 모든 컨슈머가 정상 종료되었습니다.")
    sys.exit(0)


def main():
    """메인 실행 함수"""
    print("""
    ╔════════════════════════════════════════════════════════════╗
    ║              카프카 컨슈머 클러스터 실행                    ║
    ║                    총 9개 인스턴스                          ║
    ╚════════════════════════════════════════════════════════════╝
    """)

    print("📋 컨슈머 그룹 구성:")
    print("   👥 users_group:    user_consumer_1, user_consumer_2, user_consumer_3")
    print("   📦 products_group: product_consumer_1, product_consumer_2, product_consumer_3")
    print("   🛒 orders_group:   order_consumer_1, order_consumer_2, order_consumer_3")
    print()

    # Ctrl+C 시그널 핸들러 등록
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 컨슈머 프로세스 생성
    consumer_configs = [
        # Users Group (3개)
        ('user_consumer_1', run_user_consumer),
        ('user_consumer_2', run_user_consumer),
        ('user_consumer_3', run_user_consumer),

        # Products Group (3개)
        ('product_consumer_1', run_product_consumer),
        ('product_consumer_2', run_product_consumer),
        ('product_consumer_3', run_product_consumer),

        # Orders Group (3개)
        ('order_consumer_1', run_order_consumer),
        ('order_consumer_2', run_order_consumer),
        ('order_consumer_3', run_order_consumer),
    ]

    print("🚀 컨슈머 시작 중...\n")

    # 프로세스 생성 및 시작
    for consumer_id, consumer_func in consumer_configs:
        process = multiprocessing.Process(
            target=consumer_func,
            args=(consumer_id,),
            name=consumer_id
        )
        process.start()
        processes.append(process)
        print(f"   ✅ {consumer_id} 시작")
        time.sleep(0.5)  # 순차적 시작 (약간의 지연)

    print(f"\n✅ 총 {len(processes)}개 컨슈머가 시작되었습니다!")
    print("   Ctrl+C로 종료\n")

    # 모든 프로세스 모니터링
    try:
        while True:
            # 프로세스 상태 확인
            alive_count = sum(1 for p in processes if p.is_alive())

            if alive_count < len(processes):
                print(f"\n⚠️ 일부 컨슈머가 종료되었습니다 ({alive_count}/{len(processes)} 실행 중)")

                # 종료된 프로세스 확인
                for process in processes:
                    if not process.is_alive():
                        print(f"   ❌ {process.name} 종료됨 (Exit Code: {process.exitcode})")

            time.sleep(10)  # 10초마다 체크

    except KeyboardInterrupt:
        signal_handler(None, None)


def run_single_consumer(consumer_type: str, consumer_id: str):
    """단일 컨슈머만 실행 (테스트용)"""
    print(f"🚀 {consumer_id} 시작...\n")

    if consumer_type == 'user':
        consumer = UserConsumer(consumer_id=consumer_id)
    elif consumer_type == 'product':
        consumer = ProductConsumer(consumer_id=consumer_id)
    elif consumer_type == 'order':
        consumer = OrderConsumer(consumer_id=consumer_id)
    else:
        print(f"❌ 알 수 없는 컨슈머 타입: {consumer_type}")
        return

    try:
        consumer.start()
    except KeyboardInterrupt:
        print(f"\n⚠️ {consumer_id} 종료")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='카프카 컨슈머 실행')
    parser.add_argument(
        '--single',
        action='store_true',
        help='단일 컨슈머만 실행 (테스트용)'
    )
    parser.add_argument(
        '--type',
        type=str,
        choices=['user', 'product', 'order'],
        help='컨슈머 타입 (--single과 함께 사용)'
    )
    parser.add_argument(
        '--id',
        type=str,
        help='컨슈머 ID (--single과 함께 사용)'
    )

    args = parser.parse_args()

    if args.single:
        if not args.type or not args.id:
            print("❌ --single 모드에서는 --type과 --id가 필요합니다.")
            print("   예: python run_consumers.py --single --type user --id user_consumer_1")
            sys.exit(1)

        run_single_consumer(args.type, args.id)
    else:
        main()
