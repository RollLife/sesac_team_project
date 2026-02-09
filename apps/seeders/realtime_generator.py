"""
실시간 데이터 생성 시뮬레이터 (시나리오 모드)

- 20개 프리셋 시나리오 중 선택하여 주문 생성 파라미터 결정
- 실행 중 번호 입력으로 시나리오 실시간 전환 가능
- Redis 캐시에서 유저/상품 데이터를 가져와서 주문 생성
"""

import os
import sys
import time
import random
import threading
import argparse
from datetime import datetime

# 프로젝트 루트를 sys.path에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from collect.product_generator import ProductGenerator
from collect.order_generator import OrderGenerator
from collect.purchase_propensity import select_top_buyers
from collect.scenario_engine import (
    ScenarioEngine, BASELINE_CONFIG,
    estimate_duration_minutes, get_hourly_multiplier,
    get_time_based_scenario_number,
)

# Kafka Producer import
from kafka.producer import KafkaProducer
from kafka.config import KAFKA_TOPIC_ORDERS, KAFKA_TOPIC_PRODUCTS

# Redis Cache import
from cache.client import get_redis_client


class RealtimeDataGenerator:
    """실시간 데이터 생성 시뮬레이터 (시나리오 모드 지원)"""

    def __init__(self, scenario_number=None):
        self.running = True
        self.stats = {
            'orders_created': 0,
            'products_created': 0,
            'orders_failed': 0,
            'products_failed': 0,
            'start_time': None
        }
        self.lock = threading.Lock()

        # 시나리오 엔진
        self.scenario_engine = ScenarioEngine()
        self.scenario_config = BASELINE_CONFIG.copy()
        self.initial_scenario_number = scenario_number

        # 시나리오 타이머 상태
        self.scenario_number = None          # 현재 시나리오 번호 (None = 기본 패턴)
        self.scenario_start_time = None      # 시나리오 시작 시각 (time.time)
        self.scenario_duration = None        # 시나리오 지속 시간 (초)
        self.last_checked_hour = None        # 시간대 자동 전환용

    # ========================================
    # 시나리오 타이머 관리
    # ========================================

    def _apply_scenario(self, number: int):
        """시나리오를 적용하고 타이머를 시작한다."""
        config = self.scenario_engine.get_scenario(number)

        if config.get('no_auto_revert'):
            # 자동 종료 없음 — 사용자가 직접 0번으로 복귀해야 함
            with self.lock:
                self.scenario_config = config
                self.scenario_number = number
                self.scenario_start_time = None
                self.scenario_duration = None
            print(f"\n🔄 시나리오 {number} ({config['description']}) 적용됨 (⚡ 수동 종료 대기)\n")
        else:
            duration_min = estimate_duration_minutes(config)
            with self.lock:
                self.scenario_config = config
                self.scenario_number = number
                self.scenario_start_time = time.time()
                self.scenario_duration = duration_min * 60  # → 초
            print(f"\n🔄 시나리오 {number} ({config['description']}) 적용됨 (⏱️ ~{duration_min}분)\n")

    def _revert_to_baseline(self):
        """기본 패턴으로 복귀 (시간대별 자동 시나리오 적용)"""
        time_scenario_num = get_time_based_scenario_number()

        with self.lock:
            self.scenario_start_time = None
            self.scenario_duration = None

            if time_scenario_num is not None:
                # 시간대별 자동 시나리오 적용
                self.scenario_config = self.scenario_engine.get_time_based_config()
                self.scenario_number = None  # 수동 시나리오 아님
                desc = self.scenario_config.get('description', '')
                print(f"\n⏰ 시나리오 타이머 종료 → {desc}\n")
            else:
                # 순수 기본 패턴
                self.scenario_config = BASELINE_CONFIG.copy()
                self.scenario_number = None
                print("\n⏰ 시나리오 타이머 종료 → 기본 패턴으로 복귀합니다.\n")

    def _check_scenario_timer(self):
        """타이머 만료 시 기본 패턴으로 자동 복귀"""
        with self.lock:
            if self.scenario_start_time is None or self.scenario_duration is None:
                return
            elapsed = time.time() - self.scenario_start_time
            if elapsed < self.scenario_duration:
                return
        # lock 밖에서 복귀 (내부에서 lock 획득)
        self._revert_to_baseline()

    def _get_scenario_remaining(self):
        """남은 시간(초) 반환. 타이머 없으면 None"""
        if self.scenario_start_time is None or self.scenario_duration is None:
            return None
        remaining = self.scenario_duration - (time.time() - self.scenario_start_time)
        return max(0, remaining)

    def _check_time_based_scenario(self):
        """
        시간대가 바뀌면 자동으로 시나리오 전환
        - 수동 시나리오(타이머 있음)가 실행 중이면 무시
        - 시간대별 자동 시나리오만 자동 전환
        """
        current_hour = datetime.now().hour

        # 이미 같은 시간대면 스킵
        if self.last_checked_hour == current_hour:
            return

        # 수동 시나리오 실행 중이면 스킵 (타이머가 있는 경우)
        if self.scenario_start_time is not None:
            return

        self.last_checked_hour = current_hour
        time_scenario_num = get_time_based_scenario_number()

        with self.lock:
            if time_scenario_num is not None:
                # 시간대별 자동 시나리오 적용
                new_config = self.scenario_engine.get_time_based_config()
                desc = new_config.get('description', '')

                # 이미 같은 시나리오면 스킵
                if self.scenario_config.get('description') != desc:
                    self.scenario_config = new_config
                    print(f"\n🕐 시간대 변경 → {desc}\n")
            else:
                # 기본 패턴으로 전환 (이전에 자동 시나리오였던 경우)
                if '[자동]' in self.scenario_config.get('description', ''):
                    self.scenario_config = BASELINE_CONFIG.copy()
                    print(f"\n🕐 시간대 변경 → 기본 패턴 (현실적 분포)\n")

    # ========================================
    # 시나리오 기반 유저/상품 선택
    # ========================================

    @staticmethod
    def _get_age_group(age):
        """나이 → 연령대 문자열"""
        if not age:
            return "30대"
        if age < 20:
            return "10대"
        if age < 30:
            return "20대"
        if age < 40:
            return "30대"
        if age < 50:
            return "40대"
        return "50대이상"

    def _weighted_select_user(self, user_pool, config):
        """시나리오 가중치에 따라 유저 풀에서 선택"""
        if not user_pool:
            return None

        gender_w = config.get("gender_weights", {"M": 50, "F": 50})
        age_w = config.get("age_group_weights", {})

        scores = []
        for user in user_pool:
            g = gender_w.get(user.get("gender", "M"), 50)
            a = age_w.get(self._get_age_group(user.get("age")), 20)
            scores.append(max(g * a, 0.1))

        return random.choices(user_pool, weights=scores, k=1)[0]

    def _weighted_select_product(self, product_pool, config):
        """시나리오 가중치에 따라 상품 풀에서 선택"""
        if not product_pool:
            return None

        cat_w = config.get("category_weights", {})
        scores = [max(cat_w.get(p.get("category", "Unknown"), 1), 0.1) for p in product_pool]

        return random.choices(product_pool, weights=scores, k=1)[0]

    def get_scenario_config(self):
        """thread-safe 시나리오 설정 읽기"""
        with self.lock:
            return self.scenario_config.copy()

    # ========================================
    # 주문 생성 (시나리오 기반)
    # ========================================

    def generate_orders_continuously(self):
        """
        주문 데이터를 지속적으로 생성 - 구매 성향 기반
        - 3~5초 간격으로 1건씩 생성
        - 캐싱된 고객 중 구매 성향 상위 N명에서 선택
        """
        order_generator = OrderGenerator()
        kafka_producer = KafkaProducer()
        redis_client = get_redis_client()

        ORDER_INTERVAL_MIN = 3.0  # 최소 간격 (초)
        ORDER_INTERVAL_MAX = 5.0  # 최대 간격 (초)

        print("🚀 주문 데이터 생성 스레드 시작 (구매 성향 기반)...")
        print(f"   - 주문 간격: {ORDER_INTERVAL_MIN}~{ORDER_INTERVAL_MAX}초")
        print(f"   - 캐시 1000명 전체에서 성향점수 가중치로 선택")

        # Redis 연결 대기
        retry_count = 0
        while not redis_client.is_connected() and retry_count < 10:
            print(f"⏳ Redis 연결 대기 중... ({retry_count + 1}/10)")
            time.sleep(3)
            redis_client.reconnect()
            retry_count += 1

        if not redis_client.is_connected():
            print("❌ Redis 연결 실패. 주문 생성을 시작할 수 없습니다.")
            return

        # 성향 풀 캐시 (주기적으로 갱신)
        propensity_pool = []
        last_propensity_refresh = 0
        PROPENSITY_REFRESH_INTERVAL = 50  # 캐시 갱신 주기와 동일 (50초)

        try:
            while self.running:
                # 타이머 만료 체크 → 기본 패턴 복귀
                self._check_scenario_timer()

                # 시간대 변경 체크 → 자동 시나리오 전환
                self._check_time_based_scenario()

                config = self.get_scenario_config()

                # 1. 구매 성향 풀 갱신 (50초마다 또는 풀이 비었을 때)
                now = time.time()
                if not propensity_pool or (now - last_propensity_refresh) >= PROPENSITY_REFRESH_INTERVAL:
                    try:
                        user_pool = redis_client.get_random_users(count=1000)
                        if user_pool:
                            propensity_pool = select_top_buyers(user_pool, len(user_pool))
                            last_propensity_refresh = now
                        else:
                            print("⚠️ Redis 캐시에 유저 데이터가 없습니다. cache-worker가 실행 중인지 확인하세요.")
                            time.sleep(5)
                            continue
                    except Exception as e:
                        print(f"❌ 구매 성향 계산 실패: {e}")
                        time.sleep(5)
                        continue

                # 2. 상품 풀 가져오기
                try:
                    product_pool = redis_client.get_random_products(count=200)
                    if not product_pool:
                        print("⚠️ Redis 캐시에 상품 데이터가 없습니다.")
                        time.sleep(5)
                        continue
                except Exception as e:
                    print(f"❌ Redis 조회 실패: {e}")
                    time.sleep(5)
                    continue

                # 3. 성향 점수 기반 가중치로 고객 선택 + 장바구니 구매
                #    burst_orders가 있으면 틱당 여러 명 동시 주문 (폭증 시나리오)
                try:
                    users_only = [u for u, _ in propensity_pool]

                    # 틱당 주문자 수 결정
                    burst_cfg = config.get('burst_orders')
                    if burst_cfg:
                        num_buyers = random.randint(burst_cfg['min'], burst_cfg['max'])
                    else:
                        num_buyers = 1

                    for _ in range(num_buyers):
                        # 시나리오 가중치도 반영
                        user = self._weighted_select_user(users_only, config)

                        if not user:
                            continue

                        # 장바구니: 1~10개 상품을 한번에 구매
                        cart_size = order_generator.get_cart_size()
                        cart_timestamp = datetime.now()

                        for _ in range(cart_size):
                            product = self._weighted_select_product(product_pool, config)
                            if not product:
                                continue

                            order_data = order_generator.generate_order(user, product)

                            # 역정규화 데이터 추가
                            order_data['category'] = product.get('category', 'Unknown')
                            user_address = user.get('address', '')
                            order_data['user_region'] = user_address.split()[0] if user_address else "Unknown"
                            order_data['user_gender'] = user.get('gender', 'Unknown')
                            user_age = user.get('age')
                            order_data['user_age_group'] = f"{user_age // 10 * 10}대" if user_age else "Unknown"
                            order_data['created_at'] = cart_timestamp

                            # Kafka에 발행
                            kafka_producer.send_event(
                                topic=KAFKA_TOPIC_ORDERS,
                                key=order_data['user_id'],
                                data=order_data,
                                event_type='order_created'
                            )

                            with self.lock:
                                self.stats['orders_created'] += 1

                    # 로그 출력 (50건마다)
                    with self.lock:
                        total_orders = self.stats['orders_created']
                    if total_orders % 50 == 0:
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        elapsed = time.time() - self.stats['start_time'] if self.stats['start_time'] else 0
                        tps = total_orders / elapsed if elapsed > 0 else 0
                        scenario_desc = config.get("description", "기본")
                        burst_label = f" x{num_buyers}명" if num_buyers > 1 else ""
                        print(f"[{timestamp}] 🛒 주문 누적: {total_orders:,}건{burst_label} | "
                              f"TPS: {tps:.2f} | 📋 {scenario_desc}")

                except Exception as e:
                    with self.lock:
                        self.stats['orders_failed'] += 1

                # 4. 대기 시간 결정
                #    realtime_interval이 있으면 시나리오 오버라이드 사용 (폭증 모드)
                rt_interval = config.get('realtime_interval')
                if rt_interval:
                    sleep_time = random.uniform(rt_interval['min'], rt_interval['max'])
                else:
                    sleep_time = random.uniform(ORDER_INTERVAL_MIN, ORDER_INTERVAL_MAX)
                    # 시간대별 대기시간 보정 (새벽엔 더 느리게, 피크엔 더 빠르게)
                    hourly_mult = get_hourly_multiplier()
                    if hourly_mult > 0:
                        sleep_time = sleep_time / hourly_mult
                    sleep_time = max(1.0, min(sleep_time, 30.0))  # 1초~30초 범위 제한

                time.sleep(sleep_time)

        except Exception as e:
            print(f"❌ 주문 생성 스레드 오류: {e}")
            import traceback
            traceback.print_exc()
        finally:
            kafka_producer.flush()
            print("🛑 주문 데이터 생성 스레드 종료")

    def generate_products_continuously(self):
        """상품 데이터를 지속적으로 생성 (6~8초 간격, 1건씩) - Kafka에만 발행"""
        kafka_producer = KafkaProducer()
        product_generator = ProductGenerator()

        PRODUCT_INTERVAL_MIN = 6.0  # 최소 간격 (초)
        PRODUCT_INTERVAL_MAX = 8.0  # 최대 간격 (초)

        print("🚀 상품 데이터 생성 스레드 시작 (Kafka 발행 모드)...")
        print(f"   - 상품 간격: {PRODUCT_INTERVAL_MIN}~{PRODUCT_INTERVAL_MAX}초, 1건씩")

        try:
            while self.running:
                # 1. 1건 생성
                products_list = product_generator.generate_batch(1)

                for product_data in products_list:
                    try:
                        # sleep 필드 제거
                        if 'sleep' in product_data:
                            del product_data['sleep']

                        # created_at 추가
                        product_data['created_at'] = datetime.now()

                        # Kafka에만 발행 (DB 저장은 Consumer가 담당)
                        kafka_producer.send_event(
                            topic=KAFKA_TOPIC_PRODUCTS,
                            key=product_data['product_id'],
                            data=product_data,
                            event_type='product_created'
                        )

                        with self.lock:
                            self.stats['products_created'] += 1

                    except Exception as e:
                        with self.lock:
                            self.stats['products_failed'] += 1

                # 2. 로그 출력 (10건마다)
                with self.lock:
                    total_products = self.stats['products_created']
                if total_products % 10 == 0:
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    elapsed = time.time() - self.stats['start_time'] if self.stats['start_time'] else 0
                    tps = total_products / elapsed if elapsed > 0 else 0
                    print(f"[{timestamp}] 📦 상품 누적: {total_products:,}개 | TPS: {tps:.2f}")

                # 3. 6~8초 대기
                wait_time = random.uniform(PRODUCT_INTERVAL_MIN, PRODUCT_INTERVAL_MAX)
                time.sleep(wait_time)

        except Exception as e:
            print(f"❌ 상품 생성 스레드 오류: {e}")
            import traceback
            traceback.print_exc()
        finally:
            kafka_producer.flush()
            print("🛑 상품 데이터 생성 스레드 종료")

    def print_stats_periodically(self):
        """통계를 주기적으로 출력 (10초마다) + 카운트다운 표시"""
        try:
            while self.running:
                time.sleep(10)

                if not self.running:
                    break

                with self.lock:
                    elapsed = time.time() - self.stats['start_time'] if self.stats['start_time'] else 0
                    orders_tps = self.stats['orders_created'] / elapsed if elapsed > 0 else 0
                    products_tps = self.stats['products_created'] / elapsed if elapsed > 0 else 0
                    config = self.scenario_config
                    sc_num = self.scenario_number
                    remaining = self._get_scenario_remaining()

                # 시나리오 상태 표시
                if sc_num is not None and remaining is not None:
                    mins, secs = divmod(int(remaining), 60)
                    scenario_line = (f"   ⏱️ [{sc_num}] {config.get('description', '기본')} "
                                     f"— 남은시간 {mins}:{secs:02d}")
                elif sc_num is not None:
                    scenario_line = (f"   ⚡ [{sc_num}] {config.get('description', '기본')} "
                                     f"— 수동 종료 대기")
                else:
                    scenario_line = f"   📋 기본 패턴 (현실적 분포)"

                # 시간대 배수 표시
                hourly = get_hourly_multiplier()

                print(f"\n{'='*60}")
                print(f"📊 통계 (경과시간: {elapsed:.1f}초 / {elapsed/60:.1f}분)")
                print(scenario_line)
                print(f"   🕐 현재 시간대 보정: x{hourly:.2f}")
                print(f"{'='*60}")
                print(f"  🛒 주문:  성공 {self.stats['orders_created']:,}건 | "
                      f"실패 {self.stats['orders_failed']}건 | TPS: {orders_tps:.2f}")
                print(f"  📦 상품:  성공 {self.stats['products_created']:,}개 | "
                      f"실패 {self.stats['products_failed']}개 | TPS: {products_tps:.2f}")
                print(f"{'='*60}\n")

        except Exception as e:
            print(f"❌ 통계 출력 스레드 오류: {e}")

    def poll_redis_scenario(self):
        """Redis 키(scenario:current)를 폴링하여 시나리오를 전환하는 스레드"""
        redis_client = get_redis_client()
        last_value = None

        print("📡 Redis 시나리오 폴링 시작 (scenario:current 키 감시)")

        while self.running:
            try:
                if redis_client.is_connected() and redis_client.client:
                    val = redis_client.client.get('scenario:current')
                    if val is not None and val != last_value:
                        last_value = val
                        try:
                            num = int(val)
                        except ValueError:
                            continue
                        if num == 0:
                            self._revert_to_baseline()
                        else:
                            self._apply_scenario(num)
            except Exception:
                pass
            time.sleep(2)

    def start(self):
        """실시간 데이터 생성 시작"""
        print("""
    ╔════════════════════════════════════════════════════════════╗
    ║      실시간 데이터 생성 시뮬레이터 (시나리오 모드)         ║
    ╚════════════════════════════════════════════════════════════╝
        """)

        # 초기 시나리오 적용
        if self.initial_scenario_number:
            self._apply_scenario(self.initial_scenario_number)
        else:
            # 시간대별 자동 시나리오 체크
            time_scenario_num = get_time_based_scenario_number()
            if time_scenario_num is not None:
                self.scenario_config = self.scenario_engine.get_time_based_config()
                self.last_checked_hour = datetime.now().hour
                desc = self.scenario_config.get('description', '')
                print(f"✅ 시간대별 자동 시나리오 적용: {desc}")
            else:
                print("✅ 기본 패턴 (현실적 분포)으로 시작합니다.")
            print("💡 시나리오 전환: scenario_changer.py 실행\n")

        print("📋 생성 규칙:")
        print("  - 🛒 주문: 3~5초 간격, 장바구니(1~10개) 단위 구매")
        print("  - 📦 상품: 6~8초 간격으로 1건씩 생성")
        print("  - 🧠 구매 성향: 기본(인구통계) × 시간대 × 마케팅 × 생활이벤트")
        print("  - 🕐 시간대별 트래픽 자동 보정 (새벽 저조 → 저녁 피크)")
        print("  - ⏱️ 시나리오 타이머 종료 시 기본 패턴으로 자동 복귀")
        print("  - Ctrl+C로 중지\n")

        # 시작 시간 기록
        self.stats['start_time'] = time.time()

        # 스레드 생성 및 시작
        order_thread = threading.Thread(target=self.generate_orders_continuously, daemon=True)
        product_thread = threading.Thread(target=self.generate_products_continuously, daemon=True)
        stats_thread = threading.Thread(target=self.print_stats_periodically, daemon=True)
        scenario_thread = threading.Thread(target=self.poll_redis_scenario, daemon=True)

        order_thread.start()
        product_thread.start()
        stats_thread.start()
        scenario_thread.start()

        print("✅ 실시간 데이터 생성 시작! (Ctrl+C로 중지)\n")

        try:
            # 메인 스레드는 대기 (Ctrl+C까지)
            while True:
                time.sleep(1)

        except KeyboardInterrupt:
            print("\n\n⚠️ 종료 신호 수신. 스레드를 정리하는 중...")
            self.running = False

            # 스레드 종료 대기 (최대 5초)
            order_thread.join(timeout=5)
            product_thread.join(timeout=5)
            stats_thread.join(timeout=5)

            # 최종 통계 출력
            elapsed = time.time() - self.stats['start_time']
            sc_desc = self.scenario_config.get('description', '기본 패턴')
            sc_label = f"[{self.scenario_number}] {sc_desc}" if self.scenario_number else sc_desc
            print(f"\n{'#'*60}")
            print("# 📊 최종 통계")
            print(f"{'#'*60}")
            print(f"  총 실행시간: {elapsed:.1f}초 ({elapsed/60:.1f}분)")
            print(f"  📋 마지막 시나리오: {sc_label}")
            print(f"  🛒 주문 생성: {self.stats['orders_created']:,}건 (실패: {self.stats['orders_failed']})")
            print(f"  📦 상품 생성: {self.stats['products_created']:,}개 (실패: {self.stats['products_failed']})")
            print(f"{'#'*60}\n")

            print("✅ 모든 스레드가 정상 종료되었습니다.")


def main():
    """메인 실행 함수"""
    parser = argparse.ArgumentParser(description="실시간 데이터 생성 시뮬레이터 (시나리오 모드)")
    parser.add_argument(
        "--scenario", "-s",
        type=int,
        default=None,
        help="시나리오 번호 (1~20, 예: --scenario 4 → 블랙프라이데이)"
    )
    args = parser.parse_args()

    generator = RealtimeDataGenerator(scenario_number=args.scenario)
    generator.start()


if __name__ == "__main__":
    main()
