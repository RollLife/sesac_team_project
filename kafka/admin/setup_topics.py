"""
카프카 토픽 초기화 스크립트

- users, products, orders 토픽 생성
- 각 토픽: 파티션 3개, 복제 팩터 3
"""

import sys
import os

# 프로젝트 루트를 sys.path에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

from confluent_kafka.admin import AdminClient, NewTopic
from kafka.config import KAFKA_BOOTSTRAP_SERVERS, KAFKA_TOPIC_USERS, KAFKA_TOPIC_PRODUCTS, KAFKA_TOPIC_ORDERS
import time


def create_topics():
    """토픽 생성"""
    print("""
    ╔════════════════════════════════════════════════════════════╗
    ║              카프카 토픽 초기화 스크립트                    ║
    ╚════════════════════════════════════════════════════════════╝
    """)

    print(f"📡 카프카 클러스터 연결 중...")
    print(f"   Bootstrap Servers: {KAFKA_BOOTSTRAP_SERVERS}\n")

    # AdminClient 생성
    admin_client = AdminClient({
        'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS
    })

    # 토픽 정의 (파티션 3개, 복제 팩터 3)
    topics = [
        NewTopic(
            topic=KAFKA_TOPIC_USERS,
            num_partitions=3,
            replication_factor=3,
            config={
                'min.insync.replicas': '2',  # 최소 동기화 복제본 2개
                'retention.ms': '604800000',  # 7일 보관
                'compression.type': 'lz4'  # 압축
            }
        ),
        NewTopic(
            topic=KAFKA_TOPIC_PRODUCTS,
            num_partitions=3,
            replication_factor=3,
            config={
                'min.insync.replicas': '2',
                'retention.ms': '604800000',
                'compression.type': 'lz4'
            }
        ),
        NewTopic(
            topic=KAFKA_TOPIC_ORDERS,
            num_partitions=3,
            replication_factor=3,
            config={
                'min.insync.replicas': '2',
                'retention.ms': '2592000000',  # 30일 보관 (주문은 더 오래)
                'compression.type': 'lz4'
            }
        )
    ]

    print("📋 생성할 토픽 목록:")
    for topic in topics:
        print(f"   - {topic.topic}: 파티션 {topic.num_partitions}개, 복제 팩터 {topic.replication_factor}")

    # 기존 토픽 확인
    print(f"\n🔍 기존 토픽 확인 중...")
    metadata = admin_client.list_topics(timeout=10)
    existing_topics = set(metadata.topics.keys())

    topics_to_create = [topic for topic in topics if topic.topic not in existing_topics]
    topics_already_exist = [topic for topic in topics if topic.topic in existing_topics]

    if topics_already_exist:
        print(f"\n⚠️  이미 존재하는 토픽:")
        for topic in topics_already_exist:
            print(f"   - {topic.topic}")

    if not topics_to_create:
        print(f"\n✅ 모든 토픽이 이미 생성되어 있습니다.")
        return

    # 토픽 생성
    print(f"\n🚀 토픽 생성 중...")
    futures = admin_client.create_topics(topics_to_create)

    # 결과 확인
    success_count = 0
    failed_count = 0

    for topic_name, future in futures.items():
        try:
            future.result()  # 결과 대기
            print(f"   ✅ {topic_name} 생성 완료")
            success_count += 1
        except Exception as e:
            print(f"   ❌ {topic_name} 생성 실패: {e}")
            failed_count += 1

    # 최종 결과
    print(f"\n{'='*60}")
    print(f"📊 토픽 생성 결과")
    print(f"{'='*60}")
    print(f"   성공: {success_count}개")
    print(f"   실패: {failed_count}개")
    print(f"   기존: {len(topics_already_exist)}개")
    print(f"{'='*60}\n")

    # 토픽 정보 확인
    if success_count > 0:
        print("⏳ 토픽 메타데이터 동기화 대기 중 (3초)...")
        time.sleep(3)

        print(f"\n📋 토픽 상세 정보:")
        metadata = admin_client.list_topics(timeout=10)

        for topic in topics:
            if topic.topic in metadata.topics:
                topic_metadata = metadata.topics[topic.topic]
                partitions = topic_metadata.partitions

                print(f"\n🔹 {topic.topic}")
                print(f"   파티션 개수: {len(partitions)}개")

                for partition_id, partition_info in partitions.items():
                    leader = partition_info.leader
                    replicas = partition_info.replicas
                    isrs = partition_info.isrs

                    print(f"   - 파티션 {partition_id}: "
                          f"리더={leader}, "
                          f"레플리카={replicas}, "
                          f"ISR={isrs}")

    print(f"\n✅ 토픽 초기화가 완료되었습니다!")
    print(f"   Kafka UI에서 확인: http://localhost:8080")


def delete_all_topics():
    """모든 토픽 삭제 (재설정 시 사용)"""
    print("⚠️  모든 토픽을 삭제합니다...")

    admin_client = AdminClient({
        'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS
    })

    # 기존 토픽 목록
    metadata = admin_client.list_topics(timeout=10)
    topics_to_delete = [KAFKA_TOPIC_USERS, KAFKA_TOPIC_PRODUCTS, KAFKA_TOPIC_ORDERS]
    existing_topics = [topic for topic in topics_to_delete if topic in metadata.topics.keys()]

    if not existing_topics:
        print("   삭제할 토픽이 없습니다.")
        return

    # 토픽 삭제
    futures = admin_client.delete_topics(existing_topics, operation_timeout=30)

    for topic_name, future in futures.items():
        try:
            future.result()
            print(f"   ✅ {topic_name} 삭제 완료")
        except Exception as e:
            print(f"   ❌ {topic_name} 삭제 실패: {e}")


def main():
    """메인 실행 함수"""
    import argparse

    parser = argparse.ArgumentParser(description='카프카 토픽 관리')
    parser.add_argument('--delete', action='store_true', help='모든 토픽 삭제')
    args = parser.parse_args()

    try:
        if args.delete:
            confirm = input("⚠️  정말로 모든 토픽을 삭제하시겠습니까? (yes/no): ")
            if confirm.lower() == 'yes':
                delete_all_topics()
                print("\n토픽 삭제 후 다시 생성하려면 --delete 옵션 없이 실행하세요.")
            else:
                print("취소되었습니다.")
        else:
            create_topics()

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
