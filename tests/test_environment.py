"""
환경 테스트 스크립트

Docker 환경에서 모든 연결을 테스트합니다:
- PostgreSQL 연결
- Kafka 브로커 연결
- Kafka 토픽 확인
- 환경변수 확인
"""

import os
import sys
from datetime import datetime

# 색상 코드
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


def print_header(text):
    """헤더 출력"""
    print(f"\n{'='*60}")
    print(f"{BLUE}{text}{RESET}")
    print(f"{'='*60}\n")


def print_success(text):
    """성공 메시지"""
    print(f"{GREEN}✅ {text}{RESET}")


def print_error(text):
    """에러 메시지"""
    print(f"{RED}❌ {text}{RESET}")


def print_warning(text):
    """경고 메시지"""
    print(f"{YELLOW}⚠️  {text}{RESET}")


def print_info(text):
    """정보 메시지"""
    print(f"ℹ️  {text}")


def test_environment_variables():
    """환경변수 확인"""
    print_header("1. 환경변수 확인")

    env_vars = {
        'DB_TYPE': os.getenv('DB_TYPE'),
        'POSTGRES_HOST': os.getenv('POSTGRES_HOST'),
        'POSTGRES_PORT': os.getenv('POSTGRES_PORT'),
        'POSTGRES_USER': os.getenv('POSTGRES_USER'),
        'POSTGRES_DB': os.getenv('POSTGRES_DB'),
        'KAFKA_BOOTSTRAP_SERVERS': os.getenv('KAFKA_BOOTSTRAP_SERVERS'),
        'KAFKA_ENABLED': os.getenv('KAFKA_ENABLED'),
        'KAFKA_TOPIC_USERS': os.getenv('KAFKA_TOPIC_USERS'),
        'KAFKA_TOPIC_PRODUCTS': os.getenv('KAFKA_TOPIC_PRODUCTS'),
        'KAFKA_TOPIC_ORDERS': os.getenv('KAFKA_TOPIC_ORDERS'),
    }

    all_ok = True
    for key, value in env_vars.items():
        if value:
            print_success(f"{key} = {value}")
        else:
            print_error(f"{key} = (Not Set)")
            all_ok = False

    return all_ok


def test_python_packages():
    """Python 패키지 확인"""
    print_header("2. Python 패키지 확인")

    required_packages = [
        'sqlalchemy',
        'psycopg2',
        'confluent_kafka',
        'faker',
        'pandas',
        'python-dotenv'
    ]

    all_ok = True
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print_success(f"{package} 설치됨")
        except ImportError:
            print_error(f"{package} 설치 안 됨")
            all_ok = False

    return all_ok


def test_postgresql_connection():
    """PostgreSQL 연결 테스트"""
    print_header("3. PostgreSQL 연결 테스트")

    try:
        from database.database import engine, SQLALCHEMY_DATABASE_URL
        from sqlalchemy import text

        print_info(f"DB URL: {SQLALCHEMY_DATABASE_URL}")

        # 연결 테스트
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();"))
            version = result.fetchone()[0]
            print_success(f"PostgreSQL 연결 성공")
            print_info(f"버전: {version[:50]}...")

            # 테이블 확인
            result = conn.execute(text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """))
            tables = [row[0] for row in result]

            if tables:
                print_success(f"테이블 발견: {len(tables)}개")
                for table in tables:
                    print_info(f"  - {table}")

                # 데이터 개수 확인
                for table in tables:
                    try:
                        result = conn.execute(text(f"SELECT COUNT(*) FROM {table};"))
                        count = result.fetchone()[0]
                        print_info(f"  {table}: {count:,}건")
                    except Exception as e:
                        print_warning(f"  {table}: 조회 실패 - {e}")
            else:
                print_warning("테이블이 없습니다. 스키마를 생성해야 합니다.")

        return True

    except Exception as e:
        print_error(f"PostgreSQL 연결 실패: {e}")
        return False


def test_kafka_connection():
    """Kafka 연결 테스트"""
    print_header("4. Kafka 연결 테스트")

    try:
        from kafka.config import KAFKA_BOOTSTRAP_SERVERS
        from confluent_kafka.admin import AdminClient

        print_info(f"Bootstrap Servers: {KAFKA_BOOTSTRAP_SERVERS}")

        # AdminClient 생성
        admin_client = AdminClient({
            'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS
        })

        # 클러스터 메타데이터 조회
        metadata = admin_client.list_topics(timeout=10)

        print_success(f"Kafka 연결 성공")
        print_info(f"브로커 수: {len(metadata.brokers)}개")

        # 브로커 정보
        for broker_id, broker in metadata.brokers.items():
            print_info(f"  Broker {broker_id}: {broker.host}:{broker.port}")

        # 토픽 정보
        topics = [topic for topic in metadata.topics.keys() if not topic.startswith('_')]

        if topics:
            print_success(f"토픽 발견: {len(topics)}개")
            for topic_name in topics:
                topic_metadata = metadata.topics[topic_name]
                partitions = topic_metadata.partitions
                print_info(f"  - {topic_name}: {len(partitions)}개 파티션")

                for partition_id, partition_info in partitions.items():
                    print_info(
                        f"    파티션 {partition_id}: "
                        f"리더={partition_info.leader}, "
                        f"레플리카={partition_info.replicas}"
                    )
        else:
            print_warning("토픽이 없습니다. kafka/admin/setup_topics.py를 실행하세요.")

        return True

    except Exception as e:
        print_error(f"Kafka 연결 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_kafka_producer():
    """Kafka Producer 테스트"""
    print_header("5. Kafka Producer 테스트")

    try:
        from kafka.config import KAFKA_ENABLED

        if not KAFKA_ENABLED:
            print_warning("KAFKA_ENABLED=false 이므로 Producer 테스트 스킵")
            return True

        from kafka.producer import KafkaProducer
        from kafka.config import KAFKA_TOPIC_USERS

        # Producer 생성
        producer = KafkaProducer()
        print_success("Kafka Producer 생성 성공")

        # 테스트 메시지 발행
        test_message = {
            'user_id': 'test_user_001',
            'name': '테스트 유저',
            'email': 'test@example.com',
            'created_at': datetime.now()
        }

        result = producer.send_event(
            topic=KAFKA_TOPIC_USERS,
            key='test_user_001',
            data=test_message,
            event_type='user_created'
        )

        if result:
            print_success("테스트 메시지 발행 성공")
        else:
            print_error("테스트 메시지 발행 실패")

        producer.flush()
        producer.close()

        return result

    except Exception as e:
        print_error(f"Kafka Producer 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_data_generators():
    """데이터 생성기 테스트"""
    print_header("6. 데이터 생성기 테스트")

    try:
        from collect.user_generator import UserGenerator
        from collect.product_generator import ProductGenerator
        from collect.order_generator import OrderGenerator

        # User Generator
        user_gen = UserGenerator()
        users = user_gen.generate_batch(5)
        print_success(f"UserGenerator: {len(users)}명 생성")
        print_info(f"  예시: {users[0]['name']} ({users[0]['email']})")

        # Product Generator
        product_gen = ProductGenerator()
        products = product_gen.generate_batch(5)
        print_success(f"ProductGenerator: {len(products)}개 생성")
        print_info(f"  예시: {products[0]['name']} ({products[0]['price']:,}원)")

        # Order Generator
        order_gen = OrderGenerator()
        orders = order_gen.generate_batch(users, products, 5)
        print_success(f"OrderGenerator: {len(orders)}건 생성")
        print_info(f"  예시: {orders[0]['order_id'][:20]}... ({orders[0]['total_amount']:,}원)")

        return True

    except Exception as e:
        print_error(f"데이터 생성기 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """모든 테스트 실행"""
    print("""
    ╔════════════════════════════════════════════════════════════╗
    ║              환경 테스트 스크립트                           ║
    ╚════════════════════════════════════════════════════════════╝
    """)

    results = {
        '환경변수': test_environment_variables(),
        'Python 패키지': test_python_packages(),
        'PostgreSQL': test_postgresql_connection(),
        'Kafka 연결': test_kafka_connection(),
        'Kafka Producer': test_kafka_producer(),
        '데이터 생성기': test_data_generators(),
    }

    # 결과 요약
    print_header("테스트 결과 요약")

    success_count = sum(1 for v in results.values() if v)
    total_count = len(results)

    for test_name, result in results.items():
        if result:
            print_success(f"{test_name}: 성공")
        else:
            print_error(f"{test_name}: 실패")

    print(f"\n{'='*60}")
    if success_count == total_count:
        print_success(f"모든 테스트 통과! ({success_count}/{total_count})")
        print_success("환경이 정상적으로 구성되었습니다! 🎉")
        return 0
    else:
        print_warning(f"일부 테스트 실패 ({success_count}/{total_count})")
        print_warning("실패한 항목을 확인하고 수정하세요.")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
