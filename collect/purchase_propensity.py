"""
구매 성향 시스템

캐싱된 고객 1000명의 기존 컬럼(age, gender, status, marketing_agree, grade)을
조합하여 기본 성향 점수를 계산하고, 변동 요인(시간대, 마케팅 프로모션, 생활 이벤트)을
적용하여 최종 구매 성향을 결정한다.

최종 성향 점수가 높은 상위 N명만 실제 주문을 생성한다.
"""

import random
from datetime import datetime
from typing import List, Dict, Any, Tuple


# ============================================================
# 기본 성향 점수 가중치 (합산 방식, 0~100 범위)
# ============================================================

AGE_SCORE = {
    "10대": 12,
    "20대": 20,
    "30대": 25,   # 최대 소비층
    "40대": 22,
    "50대이상": 18,
}

GENDER_SCORE = {
    "F": 15,      # 온라인 쇼핑 빈도 높음
    "M": 12,
}

STATUS_SCORE = {
    "ACTIVE": 20,
    "DORMANT": 5,
}

MARKETING_SCORE = {
    "true": 15,
    "false": 8,
}

GRADE_SCORE = {
    "VIP": 25,
    "GOLD": 20,
    "SILVER": 15,
    "BRONZE": 10,
}


# ============================================================
# 시간대별 변동 계수 (연령대별 피크 시간이 다름)
# ============================================================

# 시간대별 활성도 (0~23시)
TIME_VARIATION = {
    # 연령대: {시간: 배수}
    "10대": {
        0: 0.8, 1: 0.5, 2: 0.2, 3: 0.1, 4: 0.1, 5: 0.1,
        6: 0.2, 7: 0.3, 8: 0.4, 9: 0.5, 10: 0.6, 11: 0.7,
        12: 0.9, 13: 0.8, 14: 0.7, 15: 0.8, 16: 0.9, 17: 1.0,
        18: 1.2, 19: 1.4, 20: 1.6, 21: 1.8, 22: 1.5, 23: 1.2,
    },
    "20대": {
        0: 0.7, 1: 0.4, 2: 0.2, 3: 0.1, 4: 0.1, 5: 0.1,
        6: 0.2, 7: 0.4, 8: 0.6, 9: 0.7, 10: 0.8, 11: 1.0,
        12: 1.3, 13: 1.1, 14: 0.9, 15: 0.8, 16: 0.9, 17: 1.0,
        18: 1.3, 19: 1.5, 20: 1.7, 21: 1.8, 22: 1.5, 23: 1.0,
    },
    "30대": {
        0: 0.3, 1: 0.1, 2: 0.1, 3: 0.1, 4: 0.1, 5: 0.1,
        6: 0.3, 7: 0.5, 8: 0.7, 9: 0.9, 10: 1.0, 11: 1.2,
        12: 1.4, 13: 1.2, 14: 1.0, 15: 0.9, 16: 0.8, 17: 0.9,
        18: 1.1, 19: 1.5, 20: 1.8, 21: 1.6, 22: 1.0, 23: 0.5,
    },
    "40대": {
        0: 0.2, 1: 0.1, 2: 0.1, 3: 0.1, 4: 0.1, 5: 0.2,
        6: 0.4, 7: 0.6, 8: 0.8, 9: 1.0, 10: 1.2, 11: 1.3,
        12: 1.4, 13: 1.2, 14: 1.0, 15: 0.9, 16: 0.8, 17: 0.9,
        18: 1.1, 19: 1.4, 20: 1.6, 21: 1.3, 22: 0.8, 23: 0.4,
    },
    "50대이상": {
        0: 0.1, 1: 0.1, 2: 0.1, 3: 0.1, 4: 0.1, 5: 0.3,
        6: 0.5, 7: 0.8, 8: 1.0, 9: 1.3, 10: 1.5, 11: 1.6,
        12: 1.4, 13: 1.2, 14: 1.0, 15: 0.9, 16: 0.8, 17: 0.7,
        18: 0.8, 19: 1.0, 20: 1.1, 21: 0.8, 22: 0.5, 23: 0.2,
    },
}

# 마케팅 프로모션 부스트 (마케팅 동의자 대상, 일정 확률로 적용)
MARKETING_PROMO_CHANCE = 0.20   # 20% 확률
MARKETING_PROMO_BOOST = 1.3     # 1.3배 부스트

# 생활 이벤트 (랜덤 소비 충동)
LIFE_EVENT_WEIGHTS = [85, 12, 3]       # 보통 / 소비증가 / 대규모지출
LIFE_EVENT_MULTIPLIERS = [1.0, 1.5, 3.0]


def _get_age_group(age) -> str:
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


def calculate_base_score(user: Dict[str, Any]) -> float:
    """
    기본 구매 성향 점수 계산 (0~100 범위)
    기존 컬럼 조합: age, gender, status, marketing_agree, grade
    """
    age_group = _get_age_group(user.get('age'))
    gender = user.get('gender', 'M')
    status = user.get('status', 'ACTIVE')
    marketing = user.get('marketing_agree', 'false')
    grade = user.get('grade', 'BRONZE')

    score = (
        AGE_SCORE.get(age_group, 15)
        + GENDER_SCORE.get(gender, 12)
        + STATUS_SCORE.get(status, 10)
        + MARKETING_SCORE.get(marketing, 8)
        + GRADE_SCORE.get(grade, 10)
    )
    return score


def apply_time_variation(base_score: float, age_group: str, hour: int = None) -> float:
    """시간대별 변동 계수 적용 (연령대별 피크 시간 반영)"""
    if hour is None:
        hour = datetime.now().hour

    time_map = TIME_VARIATION.get(age_group, TIME_VARIATION["30대"])
    multiplier = time_map.get(hour, 1.0)

    return base_score * multiplier


def apply_marketing_boost(score: float, marketing_agree: str) -> float:
    """마케팅 동의자에게 프로모션 부스트 적용 (20% 확률)"""
    if marketing_agree == "true" and random.random() < MARKETING_PROMO_CHANCE:
        return score * MARKETING_PROMO_BOOST
    return score


def apply_life_event(score: float) -> float:
    """생활 이벤트(랜덤 소비 충동) 적용"""
    event = random.choices(
        LIFE_EVENT_MULTIPLIERS,
        weights=LIFE_EVENT_WEIGHTS,
        k=1
    )[0]
    return score * event


def calculate_propensity(user: Dict[str, Any], hour: int = None) -> float:
    """
    최종 구매 성향 점수 계산
    = 기본 점수 × 시간대 변동 × 마케팅 부스트 × 생활 이벤트
    """
    base = calculate_base_score(user)

    age_group = _get_age_group(user.get('age'))
    score = apply_time_variation(base, age_group, hour)
    score = apply_marketing_boost(score, user.get('marketing_agree', 'false'))
    score = apply_life_event(score)

    return score


def select_top_buyers(
    users: List[Dict[str, Any]],
    top_n: int,
    hour: int = None,
) -> List[Tuple[Dict[str, Any], float]]:
    """
    캐싱된 고객 리스트에서 구매 성향 상위 N명 선택

    Args:
        users: 캐싱된 고객 딕셔너리 리스트 (최대 1000명)
        top_n: 선택할 상위 인원 수
        hour: 시간 (None이면 현재 시간 사용)

    Returns:
        (user_dict, propensity_score) 튜플 리스트 (점수 높은 순)
    """
    if not users:
        return []

    # 각 고객의 구매 성향 점수 계산
    scored = [(user, calculate_propensity(user, hour)) for user in users]

    # 점수 높은 순 정렬
    scored.sort(key=lambda x: x[1], reverse=True)

    # 상위 N명 선택
    return scored[:top_n]
