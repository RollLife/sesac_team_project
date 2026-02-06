"""
1년치 과거 주문 데이터 생성 스크립트 (1회성)

- 기간: 2025년 1월 1일 ~ 2025년 12월 31일
- 목표: 약 50,000건 주문 (소규모 쇼핑몰 성장 시나리오)
- 성장 패턴: 월 ~3,000건 → ~6,000건 점진적 성장
- 기존 시스템 정합성 유지 (models.py, scenario_engine.py, generators)

※ 유저/상품은 initial_seeder.py로 생성된 기존 데이터(유저 1만명, 상품 2만개) 사용
"""

import os
import sys
import random
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
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

from faker import Faker
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# 프로젝트 모듈 임포트 (환경변수 설정 후)
from database.models import Base, User, Product, Order
from collect.scenario_engine import (
    SCENARIOS, BASELINE_CONFIG, AVAILABLE_CATEGORIES,
    HOURLY_MULTIPLIER, _cat_weights
)
from collect.order_generator import OrderGenerator

fake = Faker('ko_KR')

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
            3: {"scenario": 3, "desc": "블랙프라이데이", "weight": 2.0},  # 대폭 증가
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
    """1년치 과거 데이터 생성기 (기존 유저/상품 활용)"""

    def __init__(self, session, year: int = 2025):
        self.session = session
        self.year = year
        self.order_gen = OrderGenerator()

        # DB에서 로드할 캐시
        self.users_cache: List[Dict] = []
        self.products_cache: List[Dict] = []

        # 통계
        self.stats = defaultdict(int)

    def load_existing_data(self):
        """DB에서 기존 유저/상품 데이터 로드 (생성시간 순서로)"""
        print("\n" + "=" * 60)
        print("Loading existing users and products from DB...")
        print("=" * 60)

        # 유저 로드 (생성시간 순서로 가장 먼저 생성된 1만명)
        print("  Loading users (oldest 10,000 by created_at)...")
        result = self.session.execute(text("""
            SELECT user_id, name, gender, age, address_district
            FROM users
            ORDER BY created_at ASC
            LIMIT 10000
        """))

        for row in result:
            self.users_cache.append({
                'user_id': row[0],
                'name': row[1],
                'gender': row[2],
                'age': row[3],
                'address_district': row[4],
            })

        print(f"    Loaded {len(self.users_cache):,} users")

        # 상품 로드 (생성시간 순서로 가장 먼저 생성된 2만개)
        print("  Loading products (oldest 20,000 by created_at)...")
        result = self.session.execute(text("""
            SELECT product_id, name, category, price, brand
            FROM products
            ORDER BY created_at ASC
            LIMIT 20000
        """))

        for row in result:
            self.products_cache.append({
                'product_id': row[0],
                'name': row[1],
                'category': row[2],
                'price': row[3],
                'brand': row[4],
            })

        print(f"    Loaded {len(self.products_cache):,} products")
        print("=" * 60)

        if len(self.users_cache) == 0 or len(self.products_cache) == 0:
            raise ValueError(
                "DB에 유저 또는 상품 데이터가 없습니다.\n"
                "먼저 initial_seeder.py를 실행하여 데이터를 생성하세요."
            )

    def generate_order_for_datetime(
        self,
        user: Dict,
        product: Dict,
        order_datetime: datetime,
        _config: Dict[str, Any]  # 시나리오 config (현재 미사용, 호환성 유지)
    ) -> Dict:
        """특정 시간에 맞는 주문 데이터 생성 (시나리오 적용)

        Note: 수량은 order_generator.py의 카테고리 기반 규칙을 사용합니다.
              (product_rules.json의 quantity_options/quantity_weights)
        """

        # 기본 주문 생성 (카테고리 기반 수량이 이미 적용됨)
        order_data = self.order_gen.generate_order(user, product)

        # 시간 조정
        order_data['created_at'] = order_datetime

        # 역정규화 필드 추가
        order_data['category'] = product.get('category', '')
        order_data['user_region'] = user.get('address_district', '')
        order_data['user_gender'] = user.get('gender', '')
        order_data['user_age_group'] = get_age_group(user.get('age'))

        # 수량은 order_generator에서 카테고리 기반으로 이미 결정됨
        # (생활가전: 1개, 세제/위생: 1~6개 등)

        return order_data

    def select_user_by_scenario(self, config: Dict[str, Any]) -> Dict:
        """시나리오 가중치에 맞는 유저 선택"""
        if not self.users_cache:
            return None

        gender_weights = config.get('gender_weights', {'M': 50, 'F': 50})
        age_weights = config.get('age_group_weights', {
            "10대": 10, "20대": 25, "30대": 25, "40대": 25, "50대이상": 15
        })

        # 복합 가중치 계산
        scored_users = []
        for user in self.users_cache:
            gender = user.get('gender', 'M')
            age_group = get_age_group(user.get('age'))

            gender_score = gender_weights.get(gender, 50)
            age_score = age_weights.get(age_group, 10)

            total_score = (gender_score / 100) * (age_score / 100) * 100
            scored_users.append((user, max(0.1, total_score)))  # 최소값 보장

        users, scores = zip(*scored_users)
        return random.choices(users, weights=scores, k=1)[0]

    def select_product_by_scenario(self, config: Dict[str, Any]) -> Dict:
        """시나리오 가중치에 맞는 상품 선택

        시나리오의 category_weights와 product_rules.json의 order_frequency를
        함께 반영하여 상품을 선택합니다.
        """
        if not self.products_cache:
            return None

        scenario_weights = config.get('category_weights', {})

        scored_products = []
        for product in self.products_cache:
            category = product.get('category', '')

            # 1) 시나리오 가중치 (이벤트/시즌별 카테고리 부스트)
            scenario_score = scenario_weights.get(category, 5.0)

            # 2) 기본 주문 빈도 (product_rules.json의 order_frequency)
            if category in self.order_gen.category_rules:
                frequency_score = self.order_gen.category_rules[category]['order_frequency']
            else:
                frequency_score = 10  # 기본값

            # 두 가중치를 곱하여 최종 점수 계산
            total_score = scenario_score * (frequency_score / 10)
            scored_products.append((product, max(0.1, total_score)))

        products, scores = zip(*scored_products)
        return random.choices(products, weights=scores, k=1)[0]

    def generate_orders_for_day(
        self,
        target_date: datetime,
        order_count: int,
        config: Dict[str, Any]
    ) -> List[Dict]:
        """하루치 주문 데이터 생성 (시간대별 분포 적용)"""
        orders = []

        # 시간대별 주문 분배
        hourly_counts = {}
        total_multiplier = sum(HOURLY_MULTIPLIER.values())

        for hour, mult in HOURLY_MULTIPLIER.items():
            hourly_counts[hour] = int(order_count * (mult / total_multiplier))

        # 반올림 오차 보정
        diff = order_count - sum(hourly_counts.values())
        if diff > 0:
            # 피크 시간대에 추가
            for hour in [20, 19, 18, 21]:
                if diff <= 0:
                    break
                hourly_counts[hour] += 1
                diff -= 1

        # 시간대별 주문 생성
        for hour, count in hourly_counts.items():
            for _ in range(count):
                # 분, 초 랜덤
                minute = random.randint(0, 59)
                second = random.randint(0, 59)
                order_datetime = target_date.replace(hour=hour, minute=minute, second=second)

                # 유저/상품 선택 (시나리오 가중치 적용)
                user = self.select_user_by_scenario(config)
                product = self.select_product_by_scenario(config)

                if user and product:
                    order = self.generate_order_for_datetime(user, product, order_datetime, config)
                    orders.append(order)

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

    def generate_month(self, month: int) -> Dict[str, int]:
        """한 달치 데이터 생성 (주문만)"""
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

        # 일별 주문 생성
        month_orders = 0
        current_date = start_date

        while current_date <= end_date:
            week_num = get_week_of_month(current_date)
            week_plan = month_plan['weeks'].get(week_num, {'scenario': 0, 'weight': 1.0})

            scenario_num = week_plan['scenario']
            weight = week_plan['weight']

            # 하루 기본 주문량 계산
            daily_base = base_orders / total_days

            # 요일 가중치 (주말 증가)
            weekday = current_date.weekday()
            if weekday >= 5:  # 토, 일
                day_weight = 1.3
            elif weekday == 4:  # 금
                day_weight = 1.15
            else:
                day_weight = 0.95

            daily_orders = int(daily_base * weight * day_weight)

            # 시나리오 설정 가져오기
            config = get_scenario_config(scenario_num)

            # 주문 생성
            orders = self.generate_orders_for_day(current_date, daily_orders, config)

            # DB 저장
            saved = self.save_orders_to_db(orders)
            month_orders += saved

            # 진행 표시 (매 5일마다)
            if current_date.day % 5 == 0 or current_date.day == 1:
                scenario_desc = week_plan.get('desc', 'Default')
                print(f"    {current_date.strftime('%m/%d')} - {saved} orders (Scenario: {scenario_desc})")

            current_date += timedelta(days=1)

        print(f"\n  [DONE] Month {month}: {month_orders:,} orders")

        self.stats[f'{month}'] = month_orders
        return {'orders': month_orders}

    def run(self):
        """전체 1년치 데이터 생성 실행"""
        print("\n" + "=" * 70)
        print("Historical Order Data Generator")
        print(f"  Period: {self.year}-01-01 ~ {self.year}-12-31")
        print(f"  Target: ~50,000 orders")
        print(f"  Using existing users (10,000) and products (20,000)")
        print("=" * 70)

        # 기존 데이터 로드
        self.load_existing_data()

        total_orders = 0

        for month in range(1, 13):
            month_stats = self.generate_month(month)
            total_orders += month_stats['orders']

        # 최종 통계 출력
        print("\n" + "=" * 70)
        print("Generation Complete!")
        print("=" * 70)
        print(f"  Total orders: {total_orders:,}")
        print("\n  Monthly breakdown:")
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
    print("=" * 70)

    # DB 연결 확인
    print("\nConnecting to database...")
    try:
        session, engine = get_db_session()

        # 연결 테스트
        result = session.execute(text("SELECT 1")).fetchone()
        print("  [OK] PostgreSQL connected")

        # 현재 데이터 현황 확인
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

    # 사용자 확인
    print("\n[WARNING] This script will generate ~50,000 orders for 2025.")
    print("  Existing orders will NOT be deleted.")

    confirm = input("\nProceed? (y/N): ").strip().lower()
    if confirm != 'y':
        print("Cancelled.")
        return

    # 데이터 생성 실행
    generator = HistoricalDataGenerator(session, year=2025)

    try:
        stats = generator.run()

        # 최종 DB 현황
        print("\nFinal DB status:")
        user_count = session.execute(text("SELECT COUNT(*) FROM users")).scalar()
        product_count = session.execute(text("SELECT COUNT(*) FROM products")).scalar()
        order_count = session.execute(text("SELECT COUNT(*) FROM orders")).scalar()
        print(f"  Users: {user_count:,}")
        print(f"  Products: {product_count:,}")
        print(f"  Orders: {order_count:,}")

        # 2025년 데이터 확인
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
