"""
고객 등급 갱신 배치 작업

- 10분마다 전체 고객의 등급을 갱신
- 6개월 누적 기준으로 등급 결정:
  - BRONZE: 기본 (조건 미달)
  - SILVER: 50만원 이상 + 5회 이상
  - GOLD: 200만원 이상 + 15회 이상
  - VIP: 500만원 이상 + 30회 이상
- 강등은 한 번에 1단계씩만 허용 (VIP→GOLD→SILVER→BRONZE)
"""

import os
import sys
import time
import logging
from datetime import datetime, timedelta

# 프로젝트 루트를 sys.path에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from database.database import SessionLocal
from database.models import User, Order

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================
# 등급 기준 (6개월 누적)
# ============================================================

GRADE_CRITERIA = {
    "VIP":     {"min_amount": 5_000_000, "min_orders": 30},
    "GOLD":    {"min_amount": 2_000_000, "min_orders": 15},
    "SILVER":  {"min_amount":   500_000, "min_orders": 5},
    "BRONZE":  {"min_amount":         0, "min_orders": 0},
}

GRADE_ORDER = ["BRONZE", "SILVER", "GOLD", "VIP"]

# 갱신 주기
REFRESH_INTERVAL = 600  # 10분 (초)


def determine_grade(total_amount: int, order_count: int) -> str:
    """누적 금액과 주문 횟수로 등급 결정"""
    for grade, criteria in GRADE_CRITERIA.items():
        if total_amount >= criteria["min_amount"] and order_count >= criteria["min_orders"]:
            return grade
    return "BRONZE"


def update_all_grades(db: Session, reference_date: datetime = None) -> dict:
    """
    전체 고객 등급 갱신

    Args:
        db: SQLAlchemy 세션
        reference_date: 기준 날짜 (None이면 현재 시각)

    Returns:
        갱신 통계 딕셔너리
    """
    if reference_date is None:
        reference_date = datetime.now()

    # 6개월 전 날짜
    six_months_ago = reference_date - timedelta(days=180)

    stats = {
        "total_users": 0,
        "upgraded": 0,
        "downgraded": 0,
        "unchanged": 0,
        "grade_counts": {"VIP": 0, "GOLD": 0, "SILVER": 0, "BRONZE": 0},
    }

    # 1. 6개월간 주문 집계 (user_id별 총 금액, 주문 수)
    order_summary = (
        db.query(
            Order.user_id,
            func.sum(Order.total_amount).label("total_amount"),
            func.count(Order.order_id).label("order_count"),
        )
        .filter(Order.created_at >= six_months_ago)
        .filter(Order.status == "Success")
        .group_by(Order.user_id)
        .all()
    )

    # user_id → (total_amount, order_count) 매핑
    user_orders = {}
    for row in order_summary:
        user_orders[row.user_id] = (row.total_amount or 0, row.order_count or 0)

    # 2. 전체 유저 조회 및 등급 갱신
    users = db.query(User).all()
    stats["total_users"] = len(users)

    for user in users:
        total_amount, order_count = user_orders.get(user.user_id, (0, 0))
        new_grade = determine_grade(total_amount, order_count)
        old_grade = user.grade

        if new_grade != old_grade:
            old_idx = GRADE_ORDER.index(old_grade) if old_grade in GRADE_ORDER else 0
            new_idx = GRADE_ORDER.index(new_grade)

            if new_idx > old_idx:
                # 승급: 제한 없이 즉시 반영
                stats["upgraded"] += 1
            else:
                # 강등: 한 번에 1단계만
                new_idx = old_idx - 1
                new_grade = GRADE_ORDER[new_idx]
                stats["downgraded"] += 1

            user.grade = new_grade
        else:
            stats["unchanged"] += 1

        stats["grade_counts"][new_grade] += 1

    # 3. 커밋
    db.commit()

    return stats


class GradeUpdaterWorker:
    """10분마다 등급을 갱신하는 워커"""

    def __init__(self, interval: int = REFRESH_INTERVAL):
        self.interval = interval
        self.running = True
        self.refresh_count = 0

    def run_once(self):
        """1회 등급 갱신 실행"""
        db = SessionLocal()
        try:
            stats = update_all_grades(db)
            self.refresh_count += 1

            logger.info(
                f"등급 갱신 #{self.refresh_count} 완료 - "
                f"총 {stats['total_users']}명 | "
                f"승급 {stats['upgraded']}명 | 강등 {stats['downgraded']}명 | "
                f"유지 {stats['unchanged']}명"
            )
            logger.info(
                f"  등급 분포: VIP {stats['grade_counts']['VIP']}명 | "
                f"GOLD {stats['grade_counts']['GOLD']}명 | "
                f"SILVER {stats['grade_counts']['SILVER']}명 | "
                f"BRONZE {stats['grade_counts']['BRONZE']}명"
            )

        except Exception as e:
            logger.error(f"등급 갱신 실패: {e}")
            import traceback
            traceback.print_exc()
        finally:
            db.close()

    def start(self):
        """워커 시작 (무한 루프)"""
        print("""
╔════════════════════════════════════════════════════════════╗
║          고객 등급 갱신 배치 워커 (10분 주기)               ║
╚════════════════════════════════════════════════════════════╝
        """)
        print(f"📋 설정:")
        print(f"  - 갱신 주기: {self.interval}초 ({self.interval // 60}분)")
        print(f"  - 등급 기준 (6개월 누적):")
        print(f"    VIP: 500만원 이상 + 30회 이상")
        print(f"    GOLD:    200만원 이상 + 15회 이상")
        print(f"    SILVER:  50만원 이상 + 5회 이상")
        print(f"    BRONZE:  기본 (조건 미달)")
        print(f"  - 강등: 한 번에 1단계씩만 (VIP→GOLD→SILVER→BRONZE)")
        print(f"  - Ctrl+C로 중지\n")

        # 최초 1회 즉시 실행
        logger.info("최초 등급 갱신 시작...")
        self.run_once()

        try:
            while self.running:
                time.sleep(self.interval)

                if not self.running:
                    break

                self.run_once()

        except KeyboardInterrupt:
            logger.info("종료 신호 수신...")
            self.running = False

        print(f"\n{'='*60}")
        print(f"📊 최종 통계: 총 {self.refresh_count}회 갱신 완료")
        print(f"{'='*60}\n")


def main():
    """메인 실행 함수"""
    import argparse

    parser = argparse.ArgumentParser(description='고객 등급 갱신 배치 작업')
    parser.add_argument(
        '--interval',
        type=int,
        default=REFRESH_INTERVAL,
        help=f'갱신 주기 (초) (기본값: {REFRESH_INTERVAL})'
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='1회만 실행 후 종료'
    )
    args = parser.parse_args()

    worker = GradeUpdaterWorker(interval=args.interval)

    if args.once:
        worker.run_once()
    else:
        worker.start()


if __name__ == "__main__":
    main()
