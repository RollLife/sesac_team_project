"""
1년치 과거 주문 데이터 생성 스크립트 (1회성)

- 기간: 2025년 1월 1일 ~ 2025년 12월 31일
- 목표: 약 50,000건 주문 (소규모 쇼핑몰 성장 시나리오)
- 성장 패턴: 월 ~3,000건 → ~6,000건 점진적 성장

변경사항:
- 첫 1주: 전체 유저 중 랜덤 1000명 풀
- 이후: 구매이력 600명 + 미구매 400명 분리 적재
- 구매 성향 기반 고객 선택 (demographics + 변동 요인)
- 주간 등급 갱신 (6개월 누적 기준)
- last_ordered_at / order_count 실시간 추적

※ 유저/상품은 initial_seeder.py로 생성된 기존 데이터(유저 1만명, 상품 2만개) 사용
"""

import os
import sys
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any
from collections import defaultdict

# 프로젝트 루트 경로 추가
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 환경변수 먼저 설정 (DB 모듈 임포트 전에 필수)
os.environ["DB_TYPE"] = "local"
os.environ["POSTGRES_HOST"] = "localhost"
os.environ["POSTGRES_PORT"] = "5432"
os.environ["POSTGRES_USER"] = "postgres"
os.environ["POSTGRES_PASSWORD"] = "password"
os.environ["POSTGRES_DB"] = "sesac_db"

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# 프로젝트 모듈 임포트 (환경변수 설정 후)
from database.models import Order
from collect.scenario_engine import (
    SCENARIOS, BASELINE_CONFIG,
    HOURLY_MULTIPLIER,
)
from collect.order_generator import OrderGenerator
from collect.purchase_propensity import calculate_propensity
from apps.batch.grade_updater import update_all_grades

# ============================================================
# 월별/주별 이벤트 계획표
# ============================================================
MONTHLY_EVENT_PLAN = {
    1: {
        "name": "1월 - 새해/설날",
        "base_orders": 3000,
        "weeks": {
            1: {"scenario": 13, "desc": "새해 다이어트/헬스", "weight": 0.8},
            2: {"scenario": 13, "desc": "새해 다이어트/헬스", "weight": 0.7},
            3: {"scenario": 4, "desc": "설날 선물세트", "weight": 1.2},
            4: {"scenario": 4, "desc": "설날 선물세트", "weight": 1.3},
        }
    },
    2: {
        "name": "2월 - 신학기 준비",
        "base_orders": 3200,
        "weeks": {
            1: {"scenario": 4, "desc": "설날 연휴 마무리", "weight": 0.9},
            2: {"scenario": 0, "desc": "기본 패턴", "weight": 1.0},
            3: {"scenario": 11, "desc": "신학기 준비", "weight": 1.1},
            4: {"scenario": 11, "desc": "신학기 준비", "weight": 1.2},
        }
    },
    3: {
        "name": "3월 - 신학기/봄",
        "base_orders": 3400,
        "weeks": {
            1: {"scenario": 11, "desc": "신학기 시즌", "weight": 1.3},
            2: {"scenario": 11, "desc": "신학기 시즌", "weight": 1.1},
            3: {"scenario": 12, "desc": "결혼/혼수 시즌 시작", "weight": 1.0},
            4: {"scenario": 5, "desc": "봄 패션", "weight": 1.0},
        }
    },
    4: {
        "name": "4월 - 봄 캠핑/골프",
        "base_orders": 3600,
        "weeks": {
            1: {"scenario": 10, "desc": "봄 캠핑", "weight": 1.1},
            2: {"scenario": 15, "desc": "골프 시즌", "weight": 1.0},
            3: {"scenario": 12, "desc": "결혼/혼수 시즌", "weight": 1.2},
            4: {"scenario": 10, "desc": "봄 캠핑", "weight": 1.1},
        }
    },
    5: {
        "name": "5월 - 가정의달",
        "base_orders": 3800,
        "weeks": {
            1: {"scenario": 9, "desc": "어버이날 건강식품", "weight": 1.3},
            2: {"scenario": 9, "desc": "어버이날 건강식품", "weight": 1.4},
            3: {"scenario": 7, "desc": "뷰티 인플루언서", "weight": 1.1},
            4: {"scenario": 10, "desc": "캠핑 시즌", "weight": 1.0},
        }
    },
    6: {
        "name": "6월 - 여름 시작",
        "base_orders": 4000,
        "weeks": {
            1: {"scenario": 5, "desc": "여름 패션/뷰티", "weight": 1.1},
            2: {"scenario": 5, "desc": "여름 패션/뷰티", "weight": 1.2},
            3: {"scenario": 16, "desc": "여름 여행 준비", "weight": 1.1},
            4: {"scenario": 16, "desc": "여름 여행 준비", "weight": 1.2},
        }
    },
    7: {
        "name": "7월 - 여름 성수기",
        "base_orders": 4300,
        "weeks": {
            1: {"scenario": 5, "desc": "여름 패션", "weight": 1.2},
            2: {"scenario": 16, "desc": "여행 성수기", "weight": 1.4},
            3: {"scenario": 16, "desc": "여행 성수기", "weight": 1.5},
            4: {"scenario": 5, "desc": "여름 패션", "weight": 1.1},
        }
    },
    8: {
        "name": "8월 - 여름 막바지",
        "base_orders": 4600,
        "weeks": {
            1: {"scenario": 16, "desc": "여행 성수기", "weight": 1.3},
            2: {"scenario": 5, "desc": "여름 패션 세일", "weight": 1.2},
            3: {"scenario": 18, "desc": "가전 할인 행사", "weight": 1.4},
            4: {"scenario": 11, "desc": "개학 준비", "weight": 1.1},
        }
    },
    9: {
        "name": "9월 - 추석/가을",
        "base_orders": 4900,
        "weeks": {
            1: {"scenario": 4, "desc": "추석 선물세트", "weight": 1.3},
            2: {"scenario": 4, "desc": "추석 선물세트", "weight": 1.5},
            3: {"scenario": 10, "desc": "가을 캠핑", "weight": 1.1},
            4: {"scenario": 15, "desc": "가을 골프", "weight": 1.0},
        }
    },
    10: {
        "name": "10월 - 가을 아웃도어",
        "base_orders": 5200,
        "weeks": {
            1: {"scenario": 10, "desc": "캠핑 시즌", "weight": 1.2},
            2: {"scenario": 15, "desc": "골프 시즌", "weight": 1.1},
            3: {"scenario": 6, "desc": "겨울 준비", "weight": 1.0},
            4: {"scenario": 6, "desc": "FW 신상", "weight": 1.2},
        }
    },
    11: {
        "name": "11월 - 블랙프라이데이",
        "base_orders": 5500,
        "weeks": {
            1: {"scenario": 6, "desc": "겨울 패딩", "weight": 1.1},
            2: {"scenario": 18, "desc": "가전 할인", "weight": 1.3},
            3: {"scenario": 3, "desc": "블랙프라이데이", "weight": 2.0},
            4: {"scenario": 3, "desc": "블랙프라이데이", "weight": 1.8},
        }
    },
    12: {
        "name": "12월 - 연말/크리스마스",
        "base_orders": 6000,
        "weeks": {
            1: {"scenario": 6, "desc": "겨울 패딩", "weight": 1.2},
            2: {"scenario": 16, "desc": "연말 여행", "weight": 1.3},
            3: {"scenario": 20, "desc": "연말 대량 주문", "weight": 1.4},
            4: {"scenario": 8, "desc": "MZ세대 연말 쇼핑", "weight": 1.3},
        }
    },
}


# ============================================================
# 유틸리티 함수
# ============================================================

def get_db_session():
    """데이터베이스 세션 생성 (로컬 PostgreSQL)"""
    db_url = "postgresql://postgres:password@localhost:5432/sesac_db"
    engine = create_engine(db_url, echo=False)
    Session = sessionmaker(bind=engine)
    return Session(), engine


def get_week_of_month(date: datetime) -> int:
    """해당 날짜가 그 달의 몇 번째 주인지 반환 (1~4)"""
    first_day = date.replace(day=1)
    day_of_month = date.day
    adjusted_day = day_of_month + first_day.weekday()
    week = min(4, (adjusted_day - 1) // 7 + 1)
    return week


def get_scenario_config(scenario_num: int) -> Dict[str, Any]:
    """시나리오 번호로 설정 반환 (0이면 기본 패턴)"""
    if scenario_num == 0:
        return BASELINE_CONFIG.copy()
    return SCENARIOS.get(scenario_num, BASELINE_CONFIG).copy()


def get_age_group(age: int) -> str:
    """나이를 연령대 문자열로 변환"""
    if age is None:
        return "30대"
    if age < 20:
        return "10대"
    elif age < 30:
        return "20대"
    elif age < 40:
        return "30대"
    elif age < 50:
        return "40대"
    else:
        return "50대이상"


# ============================================================
# 데이터 생성 클래스
# ============================================================

class HistoricalDataGenerator:
    """1년치 과거 데이터 생성기 (구매이력/미구매 분리 적재 + 성향 기반)"""

    # 캐시 풀 설정
    USER_PURCHASED_LIMIT = 600
    USER_NEW_LIMIT = 400
    PRODUCT_POPULAR_LIMIT = 700
    PRODUCT_NEW_LIMIT = 300
    POOL_SIZE = 1000

    # 구매 성향 상위 N명
    TOP_N_BUYERS = 200

    # 첫 주 랜덤 기간 (일)
    RANDOM_PHASE_DAYS = 7

    # 등급 갱신 주기 (일)
    GRADE_UPDATE_INTERVAL_DAYS = 7

    def __init__(self, session, year: int = 2025):
        self.session = session
        self.year = year
        self.order_gen = OrderGenerator()

        # 전체 유저/상품 (DB에서 로드)
        self.all_users: List[Dict] = []
        self.all_products: List[Dict] = []

        # 인메모리 추적 (주문 발생 시 업데이트)
        self.user_last_ordered: Dict[str, datetime] = {}  # user_id -> last order datetime
        self.product_order_counts: Dict[str, int] = {}    # product_id -> count

        # 통계
        self.stats = defaultdict(int)
        self.start_date = datetime(year, 1, 1)

    def load_existing_data(self):
        """DB에서 기존 유저/상품 데이터 로드 (구매 성향 계산에 필요한 필드 포함)"""
        print("\n" + "=" * 60)
        print("Loading existing users and products from DB...")
        print("=" * 60)

        # 유저 로드 (성향 계산에 필요한 필드 포함)
        print("  Loading users...")
        result = self.session.execute(text("""
            SELECT user_id, name, gender, age, address_district,
                   status, marketing_agree, grade, random_seed, created_at
            FROM users
            ORDER BY created_at ASC
            LIMIT 10000
        """))

        for row in result:
            user = {
                'user_id': row[0],
                'name': row[1],
                'gender': row[2],
                'age': row[3],
                'address_district': row[4],
                'status': row[5] or 'ACTIVE',
                'marketing_agree': row[6] or 'false',
                'grade': row[7] or 'BRONZE',
                'random_seed': row[8] or random.random(),
                'created_at': row[9],
            }
            self.all_users.append(user)
            # product_order_counts 초기화
            self.product_order_counts[user['user_id']] = 0

        print(f"    Loaded {len(self.all_users):,} users")

        # 상품 로드
        print("  Loading products...")
        result = self.session.execute(text("""
            SELECT product_id, name, category, price, brand, created_at
            FROM products
            ORDER BY created_at ASC
            LIMIT 20000
        """))

        for row in result:
            product = {
                'product_id': row[0],
                'name': row[1],
                'category': row[2],
                'price': row[3],
                'brand': row[4],
                'created_at': row[5],
            }
            self.all_products.append(product)
            self.product_order_counts[product['product_id']] = 0

        print(f"    Loaded {len(self.all_products):,} products")
        print("=" * 60)

        if not self.all_users or not self.all_products:
            raise ValueError(
                "DB에 유저 또는 상품 데이터가 없습니다.\n"
                "먼저 initial_seeder.py를 실행하여 데이터를 생성하세요."
            )

    # ========================================
    # 풀 선택 (600+400 / 700+300 분리 적재)
    # ========================================

    def get_user_pool(self, current_date: datetime) -> List[Dict]:
        """
        현재 날짜 기준 유저 풀 선택
        - 첫 1주: 전체 유저 중 랜덤 1000명
        - 이후: 구매이력 600명(last_ordered_at ASC) + 미구매 400명(created_at DESC)
        """
        days_elapsed = (current_date - self.start_date).days

        if days_elapsed < self.RANDOM_PHASE_DAYS:
            # 첫 1주: 랜덤 선택 (random_seed 기반 정렬)
            sorted_users = sorted(self.all_users, key=lambda u: u.get('random_seed', 0))
            # random_seed 기준으로 정렬 후 상위 1000명 선택
            return sorted_users[:self.POOL_SIZE]

        # 이후: 구매이력/미구매 분리 적재
        purchased = [u for u in self.all_users if u['user_id'] in self.user_last_ordered]
        new_users = [u for u in self.all_users if u['user_id'] not in self.user_last_ordered]

        # 구매이력 고객: last_ordered_at 오래된 순 (재구매 기회 제공)
        purchased.sort(key=lambda u: self.user_last_ordered.get(u['user_id'], datetime.min))

        # 미구매 고객: created_at 최신순
        new_users.sort(key=lambda u: u.get('created_at') or datetime.min, reverse=True)

        # 미구매 부족 시 구매이력 풀 확대
        new_count = min(self.USER_NEW_LIMIT, len(new_users))
        purchased_count = self.POOL_SIZE - new_count

        pool = purchased[:purchased_count] + new_users[:new_count]
        return pool

    def get_product_pool(self) -> List[Dict]:
        """
        상품 풀 선택: 인기 700개(order_count DESC) + 신상품 300개(order_count==0, created_at DESC)
        """
        has_orders = [p for p in self.all_products
                      if self.product_order_counts.get(p['product_id'], 0) > 0]
        no_orders = [p for p in self.all_products
                     if self.product_order_counts.get(p['product_id'], 0) == 0]

        # 인기상품: order_count 높은 순
        has_orders.sort(
            key=lambda p: self.product_order_counts.get(p['product_id'], 0),
            reverse=True
        )
        # 신상품: created_at 최신순
        no_orders.sort(key=lambda p: p.get('created_at') or datetime.min, reverse=True)

        new_count = min(self.PRODUCT_NEW_LIMIT, len(no_orders))
        popular_count = self.POOL_SIZE - new_count

        pool = has_orders[:popular_count] + no_orders[:new_count]
        return pool

    # ========================================
    # 구매 성향 기반 선택
    # ========================================

    def select_buyer_by_propensity(
        self,
        user_pool: List[Dict],
        config: Dict[str, Any],
        hour: int,
    ) -> Dict:
        """구매 성향 + 시나리오 가중치로 유저 선택"""
        if not user_pool:
            return None

        # 구매 성향 점수 계산
        scored = []
        for user in user_pool:
            propensity = calculate_propensity(user, hour)

            # 시나리오 가중치도 반영
            gender_w = config.get("gender_weights", {"M": 50, "F": 50})
            age_w = config.get("age_group_weights", {})
            g_score = gender_w.get(user.get("gender", "M"), 50) / 50
            a_score = age_w.get(get_age_group(user.get("age")), 20) / 20

            final_score = propensity * g_score * a_score
            scored.append((user, max(0.1, final_score)))

        users, scores = zip(*scored)
        return random.choices(users, weights=scores, k=1)[0]

    def select_product_by_scenario(self, product_pool: List[Dict], config: Dict[str, Any]) -> Dict:
        """시나리오 가중치 + 카테고리 빈도에 맞는 상품 선택"""
        if not product_pool:
            return None

        scenario_weights = config.get('category_weights', {})

        scored = []
        for product in product_pool:
            category = product.get('category', '')

            scenario_score = scenario_weights.get(category, 5.0)

            if category in self.order_gen.category_rules:
                frequency_score = self.order_gen.category_rules[category]['order_frequency']
            else:
                frequency_score = 10

            total_score = scenario_score * (frequency_score / 10)
            scored.append((product, max(0.1, total_score)))

        products, scores = zip(*scored)
        return random.choices(products, weights=scores, k=1)[0]

    # ========================================
    # 주문 생성 및 추적
    # ========================================

    def generate_order_for_datetime(
        self,
        user: Dict,
        product: Dict,
        order_datetime: datetime,
    ) -> Dict:
        """특정 시간에 맞는 주문 데이터 생성"""
        order_data = self.order_gen.generate_order(user, product)

        # 시간 조정
        order_data['created_at'] = order_datetime

        # 역정규화 필드 추가
        order_data['category'] = product.get('category', '')
        order_data['user_region'] = user.get('address_district', '')
        order_data['user_gender'] = user.get('gender', '')
        order_data['user_age_group'] = get_age_group(user.get('age'))

        return order_data

    def track_order(self, order_data: Dict, order_datetime: datetime):
        """주문 발생 시 인메모리 추적 데이터 업데이트"""
        user_id = order_data['user_id']
        product_id = order_data['product_id']

        # user last_ordered_at 갱신
        prev = self.user_last_ordered.get(user_id)
        if prev is None or order_datetime > prev:
            self.user_last_ordered[user_id] = order_datetime

        # product order_count 증가
        self.product_order_counts[product_id] = \
            self.product_order_counts.get(product_id, 0) + 1

    def update_grades_in_memory(self, reference_date: datetime):
        """DB에 이미 저장된 주문 데이터로 등급 갱신 후 인메모리 동기화"""
        # DB에 이미 저장된 데이터로 갱신
        stats = update_all_grades(self.session, reference_date)

        # 인메모리 유저 딕셔너리의 grade도 동기화
        grade_map = {}
        result = self.session.execute(text("SELECT user_id, grade FROM users"))
        for row in result:
            grade_map[row[0]] = row[1]

        for user in self.all_users:
            if user['user_id'] in grade_map:
                user['grade'] = grade_map[user['user_id']]

        return stats

    # ========================================
    # 일별/월별 생성
    # ========================================

    def generate_orders_for_day(
        self,
        target_date: datetime,
        order_count: int,
        config: Dict[str, Any],
    ) -> List[Dict]:
        """하루치 주문 데이터 생성 (시간대별 분포 + 성향 기반 선택)"""
        orders = []

        # 유저/상품 풀 가져오기
        user_pool = self.get_user_pool(target_date)
        product_pool = self.get_product_pool()

        # 시간대별 주문 분배
        hourly_counts = {}
        total_multiplier = sum(HOURLY_MULTIPLIER.values())

        for hour, mult in HOURLY_MULTIPLIER.items():
            hourly_counts[hour] = int(order_count * (mult / total_multiplier))

        # 반올림 오차 보정
        diff = order_count - sum(hourly_counts.values())
        if diff > 0:
            for hour in [20, 19, 18, 21]:
                if diff <= 0:
                    break
                hourly_counts[hour] += 1
                diff -= 1

        # 시간대별 주문 생성
        for hour, count in hourly_counts.items():
            for _ in range(count):
                minute = random.randint(0, 59)
                second = random.randint(0, 59)
                order_datetime = target_date.replace(hour=hour, minute=minute, second=second)

                # 구매 성향 기반 유저 선택
                user = self.select_buyer_by_propensity(user_pool, config, hour)
                product = self.select_product_by_scenario(product_pool, config)

                if user and product:
                    order = self.generate_order_for_datetime(user, product, order_datetime)
                    orders.append(order)

                    # 인메모리 추적 업데이트
                    self.track_order(order, order_datetime)

        return orders

    def save_orders_to_db(self, orders: List[Dict]) -> int:
        """주문 데이터 DB 저장"""
        saved = 0
        for order_data in orders:
            try:
                order = Order(
                    order_id=order_data['order_id'],
                    created_at=order_data['created_at'],
                    user_id=order_data['user_id'],
                    product_id=order_data['product_id'],
                    quantity=order_data['quantity'],
                    total_amount=order_data['total_amount'],
                    shipping_cost=order_data['shipping_cost'],
                    discount_amount=order_data['discount_amount'],
                    payment_method=order_data['payment_method'],
                    status=order_data['status'],
                    category=order_data.get('category', ''),
                    user_name=order_data.get('user_name', ''),
                    user_region=order_data.get('user_region', ''),
                    user_gender=order_data.get('user_gender', ''),
                    user_age_group=order_data.get('user_age_group', ''),
                )
                self.session.add(order)
                saved += 1
            except Exception as e:
                print(f"  [WARN] Order save failed: {e}")
                continue

        self.session.commit()
        return saved

    def flush_tracking_to_db(self):
        """인메모리 추적 데이터를 DB에 반영 (last_ordered_at, order_count)"""
        print("\n  Flushing tracking data to DB...")

        # 유저 last_ordered_at 갱신
        updated_users = 0
        for user_id, last_ordered in self.user_last_ordered.items():
            self.session.execute(
                text("UPDATE users SET last_ordered_at = :dt WHERE user_id = :uid"),
                {"dt": last_ordered, "uid": user_id}
            )
            updated_users += 1

        # 상품 order_count 갱신
        updated_products = 0
        for product_id, count in self.product_order_counts.items():
            if count > 0 and not product_id.startswith('U_'):  # user_id 제외
                self.session.execute(
                    text("UPDATE products SET order_count = :cnt WHERE product_id = :pid"),
                    {"cnt": count, "pid": product_id}
                )
                updated_products += 1

        self.session.commit()
        print(f"    Updated {updated_users:,} users, {updated_products:,} products")

    def generate_month(self, month: int) -> Dict[str, int]:
        """한 달치 데이터 생성"""
        month_plan = MONTHLY_EVENT_PLAN[month]
        month_name = month_plan['name']
        base_orders = month_plan['base_orders']

        print(f"\n{'='*60}")
        print(f"[Month {month}] {month_name}")
        print(f"  Target orders: ~{base_orders:,}")
        print(f"{'='*60}")

        # 월의 시작/끝 날짜
        start_date = datetime(self.year, month, 1)
        if month == 12:
            end_date = datetime(self.year, 12, 31)
        else:
            end_date = datetime(self.year, month + 1, 1) - timedelta(days=1)

        total_days = (end_date - start_date).days + 1

        month_orders = 0
        current_date = start_date
        last_grade_update = None

        while current_date <= end_date:
            week_num = get_week_of_month(current_date)
            week_plan = month_plan['weeks'].get(week_num, {'scenario': 0, 'weight': 1.0})

            scenario_num = week_plan['scenario']
            weight = week_plan['weight']

            # 하루 기본 주문량 계산
            daily_base = base_orders / total_days

            # 요일 가중치 (주말 증가)
            weekday = current_date.weekday()
            if weekday >= 5:
                day_weight = 1.3
            elif weekday == 4:
                day_weight = 1.15
            else:
                day_weight = 0.95

            daily_orders = int(daily_base * weight * day_weight)

            config = get_scenario_config(scenario_num)

            # 주문 생성
            orders = self.generate_orders_for_day(current_date, daily_orders, config)
            saved = self.save_orders_to_db(orders)
            month_orders += saved

            # 주간 등급 갱신 (7일마다)
            days_from_start = (current_date - self.start_date).days
            if days_from_start > 0 and days_from_start % self.GRADE_UPDATE_INTERVAL_DAYS == 0:
                if last_grade_update != current_date:
                    print(f"\n    🔄 등급 갱신 (Day {days_from_start})...")
                    grade_stats = self.update_grades_in_memory(current_date)
                    print(f"       승급 {grade_stats['upgraded']}명 | "
                          f"강등 {grade_stats['downgraded']}명 | "
                          f"VIP:{grade_stats['grade_counts']['VIP']} "
                          f"GOLD:{grade_stats['grade_counts']['GOLD']} "
                          f"SILVER:{grade_stats['grade_counts']['SILVER']} "
                          f"BRONZE:{grade_stats['grade_counts']['BRONZE']}")
                    last_grade_update = current_date

            # 진행 표시 (매 5일마다)
            if current_date.day % 5 == 0 or current_date.day == 1:
                scenario_desc = week_plan.get('desc', 'Default')
                days_elapsed = (current_date - self.start_date).days
                phase = "RANDOM" if days_elapsed < self.RANDOM_PHASE_DAYS else "600+400"
                purchased = len(self.user_last_ordered)
                print(f"    {current_date.strftime('%m/%d')} - {saved} orders "
                      f"(Scenario: {scenario_desc}) [{phase}] "
                      f"구매고객: {purchased:,}명")

            current_date += timedelta(days=1)

        print(f"\n  [DONE] Month {month}: {month_orders:,} orders")

        self.stats[f'{month}'] = month_orders
        return {'orders': month_orders}

    def run(self):
        """전체 1년치 데이터 생성 실행"""
        print("\n" + "=" * 70)
        print("Historical Order Data Generator (구매이력/미구매 분리 적재 + 성향 기반)")
        print(f"  Period: {self.year}-01-01 ~ {self.year}-12-31")
        print(f"  Target: ~50,000 orders")
        print(f"  첫 {self.RANDOM_PHASE_DAYS}일: 랜덤 풀, 이후: 600+400 분리 적재")
        print(f"  등급 갱신: {self.GRADE_UPDATE_INTERVAL_DAYS}일마다")
        print("=" * 70)

        self.load_existing_data()

        total_orders = 0

        for month in range(1, 13):
            month_stats = self.generate_month(month)
            total_orders += month_stats['orders']

        # 인메모리 추적 데이터 DB 반영
        self.flush_tracking_to_db()

        # 최종 등급 갱신
        print("\n  🔄 최종 등급 갱신...")
        final_grades = self.update_grades_in_memory(datetime(self.year, 12, 31))

        # 최종 통계
        print("\n" + "=" * 70)
        print("Generation Complete!")
        print("=" * 70)
        print(f"  Total orders: {total_orders:,}")
        print(f"  구매 고객: {len(self.user_last_ordered):,}명")
        print(f"\n  최종 등급 분포:")
        for grade in ["VIP", "GOLD", "SILVER", "BRONZE"]:
            count = final_grades['grade_counts'][grade]
            print(f"    {grade:8}: {count:>5,}명")
        print(f"\n  Monthly breakdown:")
        for month in range(1, 13):
            count = self.stats.get(str(month), 0)
            bar = '#' * (count // 500)
            print(f"    {month:2}월: {count:>5,} {bar}")
        print("=" * 70)

        return {'orders': total_orders}


# ============================================================
# 메인 실행
# ============================================================

def main():
    print("=" * 70)
    print("Historical Order Data Generator")
    print("  Generates 1 year of order data using existing users/products")
    print("  Features: 600+400 split, propensity scoring, weekly grade updates")
    print("=" * 70)

    print("\nConnecting to database...")
    try:
        session, _engine = get_db_session()

        session.execute(text("SELECT 1")).fetchone()
        print("  [OK] PostgreSQL connected")

        user_count = session.execute(text("SELECT COUNT(*) FROM users")).scalar()
        product_count = session.execute(text("SELECT COUNT(*) FROM products")).scalar()
        order_count = session.execute(text("SELECT COUNT(*) FROM orders")).scalar()

        print(f"\nCurrent DB status:")
        print(f"  Users: {user_count:,}")
        print(f"  Products: {product_count:,}")
        print(f"  Orders: {order_count:,}")

        if user_count < 1000 or product_count < 1000:
            print("\n[ERROR] Not enough users or products in DB.")
            print("  Please run initial_seeder.py first to create base data.")
            return

    except Exception as e:
        print(f"  [FAIL] DB connection failed: {e}")
        print("\nMake sure Docker is running:")
        print("  docker-compose up -d postgres")
        return

    print("\n[WARNING] This script will generate ~50,000 orders for 2025.")
    print("  Existing orders will NOT be deleted.")

    confirm = input("\nProceed? (y/N): ").strip().lower()
    if confirm != 'y':
        print("Cancelled.")
        return

    generator = HistoricalDataGenerator(session, year=2025)

    try:
        stats = generator.run()

        print("\nFinal DB status:")
        user_count = session.execute(text("SELECT COUNT(*) FROM users")).scalar()
        product_count = session.execute(text("SELECT COUNT(*) FROM products")).scalar()
        order_count = session.execute(text("SELECT COUNT(*) FROM orders")).scalar()
        print(f"  Users: {user_count:,}")
        print(f"  Products: {product_count:,}")
        print(f"  Orders: {order_count:,}")

        orders_2025 = session.execute(text("""
            SELECT COUNT(*) FROM orders
            WHERE created_at >= '2025-01-01' AND created_at < '2026-01-01'
        """)).scalar()
        print(f"\n  Orders in 2025: {orders_2025:,}")

    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] Cancelled by user.")
        session.rollback()
    except Exception as e:
        print(f"\n[ERROR] {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
