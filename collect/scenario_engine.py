"""
시나리오 엔진 - 프리셋 기반

20개의 사전 정의된 시나리오 중 선택하여
주문 생성 파라미터를 반환한다.
시나리오는 일시적 이벤트이며, 타이머 종료 후 기본 패턴으로 복귀한다.
"""

from datetime import datetime
from typing import Dict, Any, List

AVAILABLE_CATEGORIES = [
    "SS(봄여름)", "FW(가을겨울)",
    "스킨케어", "기능성(안티에이징)",
    "신선(과일/채소)", "육류/가공",
    "생활가전", "IT/게이밍",
    "세제/위생", "화지/제지",
    "건강식품", "영양제",
    "소파/침대", "사무/학생",
    "골프", "캠핑",
    "항공", "숙박", "티켓/패스",
]


def _cat_weights(**overrides) -> Dict[str, float]:
    """기본 균등 가중치에서 특정 카테고리만 오버라이드"""
    base = {cat: 2 for cat in AVAILABLE_CATEGORIES}
    remaining = 100
    for cat, w in overrides.items():
        base[cat] = w
        remaining -= w
    non_override = [c for c in AVAILABLE_CATEGORIES if c not in overrides]
    if non_override:
        each = max(remaining / len(non_override), 0.5)
        for c in non_override:
            base[c] = round(each, 1)
    return base


# ============================================================
# 시간대별 주문량 배수 (한국 이커머스 실측 기반)
# 1.0 = 평균, 새벽 최저 → 점심/저녁 피크
# ============================================================
HOURLY_MULTIPLIER = {
    0: 0.15, 1: 0.05, 2: 0.02, 3: 0.01, 4: 0.01, 5: 0.03,
    6: 0.08, 7: 0.20, 8: 0.50, 9: 0.80, 10: 1.30, 11: 1.60,
    12: 1.40, 13: 1.10, 14: 1.00, 15: 1.10, 16: 1.20, 17: 1.40,
    18: 1.80, 19: 2.20, 20: 3.00, 21: 2.50, 22: 1.50, 23: 0.50,
}

# ============================================================
# 시간대별 자동 시나리오 매핑
# - 21~23시: 새벽배송 식품 집중 (17번)
# - 0~5시: 심야 소량 주문 (19번)
# - 그 외: None (기본 패턴 사용)
# ============================================================
TIME_BASED_SCENARIO = {
    0: 19, 1: 19, 2: 19, 3: 19, 4: 19, 5: 19,  # 심야 소량
    21: 17, 22: 17, 23: 17,  # 새벽배송 식품
}


def get_hourly_multiplier() -> float:
    """현재 시각 기준 주문량 배수 반환"""
    return HOURLY_MULTIPLIER.get(datetime.now().hour, 1.0)


def get_time_based_scenario_number() -> int | None:
    """현재 시각 기준 자동 적용 시나리오 번호 반환 (없으면 None)"""
    return TIME_BASED_SCENARIO.get(datetime.now().hour)


# ============================================================
# 기본 패턴 (현실적 이커머스 분포)
# - 카테고리: 한국 이커머스 시장 점유율 기반
# - 성별: 온라인 쇼핑 성비 약 45:55 (남:여)
# - 연령: 20-30대 중심, 40대 상당, 10대/50대+ 소수
# ============================================================
BASELINE_CONFIG = {
    "description": "기본 패턴 (현실적 분포)",
    "order_volume": {"min": 10, "max": 50},
    "interval": {"min": 0.3, "max": 1.0},
    "peak_probability": 0.02,
    "peak_volume": {"min": 80, "max": 150},
    "gender_weights": {"M": 45, "F": 55},
    "age_group_weights": {"10대": 8, "20대": 28, "30대": 28, "40대": 22, "50대이상": 14},
    "category_weights": _cat_weights(**{
        "신선(과일/채소)": 12, "육류/가공": 10,  # [High] 주 1회 이상 구매
        "세제/위생": 8, "화지/제지": 6,        # [High] 월 1-2회 구매
        "SS(봄여름)": 9, "FW(가을겨울)": 9,    # [Mid] 계절/월별 구매
        "스킨케어": 8, "영양제": 6,            # [Mid] 재구매 주기 있음
        "생활가전": 5, "IT/게이밍": 5,         # [Low] 고단가, 긴 주
        "기능성(안티에이징)": 4, "건강식품": 4,
        "소파/침대": 2, "사무/학생": 2,        # [Rare] 이사/시즌 이슈
        "골프": 2, "캠핑": 2,
        "항공": 2, "숙박": 2, "티켓/패스": 2,
    }),
    "quantity_weights": [75, 13, 7, 3, 2],
}


# ============================================================
# 20개 프리셋 시나리오 (일시적 이벤트)
# ============================================================
SCENARIOS: Dict[int, Dict[str, Any]] = {
    1: {
        "description": "여성 구매고객 대량 유입",
        "order_volume": {"min": 80, "max": 200},
        "interval": {"min": 0.3, "max": 1.0},
        "peak_probability": 0.10,
        "peak_volume": {"min": 200, "max": 400},
        "gender_weights": {"M": 10, "F": 90},
        "age_group_weights": {"10대": 10, "20대": 35, "30대": 30, "40대": 15, "50대이상": 10},
        "category_weights": _cat_weights(**{
            "스킨케어": 20, "기능성(안티에이징)": 15,
            "SS(봄여름)": 18, "FW(가을겨울)": 12,
            "영양제": 8,
        }),
        "quantity_weights": [60, 20, 10, 5, 5],
    },
    2: {
        "description": "남성 IT/게이밍 폭주",
        "order_volume": {"min": 50, "max": 150},
        "interval": {"min": 0.2, "max": 0.6},
        "peak_probability": 0.08,
        "peak_volume": {"min": 150, "max": 300},
        "gender_weights": {"M": 85, "F": 15},
        "age_group_weights": {"10대": 25, "20대": 35, "30대": 25, "40대": 10, "50대이상": 5},
        "category_weights": _cat_weights(**{
            "IT/게이밍": 35, "생활가전": 10,
            "사무/학생": 10,
        }),
        "quantity_weights": [85, 10, 3, 1, 1],
    },
    3: {
        "description": "블랙프라이데이 대규모 세일",
        "order_volume": {"min": 150, "max": 400},
        "interval": {"min": 0.1, "max": 0.5},
        "peak_probability": 0.30,
        "peak_volume": {"min": 400, "max": 800},
        "gender_weights": {"M": 50, "F": 50},
        "age_group_weights": {"10대": 15, "20대": 30, "30대": 30, "40대": 15, "50대이상": 10},
        "category_weights": _cat_weights(**{
            "생활가전": 15, "IT/게이밍": 15,
            "FW(가을겨울)": 12, "기능성(안티에이징)": 10,
            "소파/침대": 8,
        }),
        "quantity_weights": [50, 25, 15, 5, 5],
    },
    4: {
        "description": "설날/추석 선물세트 시즌",
        "order_volume": {"min": 60, "max": 180},
        "interval": {"min": 0.3, "max": 1.0},
        "peak_probability": 0.05,
        "peak_volume": {"min": 200, "max": 350},
        "gender_weights": {"M": 40, "F": 60},
        "age_group_weights": {"10대": 5, "20대": 15, "30대": 25, "40대": 30, "50대이상": 25},
        "category_weights": _cat_weights(**{
            "건강식품": 25, "영양제": 15,
            "육류/가공": 15, "신선(과일/채소)": 12,
            "기능성(안티에이징)": 8,
        }),
        "quantity_weights": [40, 30, 15, 10, 5],
    },
    5: {
        "description": "여름 패션/뷰티 시즌",
        "order_volume": {"min": 40, "max": 120},
        "interval": {"min": 0.3, "max": 0.8},
        "peak_probability": 0.05,
        "peak_volume": {"min": 150, "max": 250},
        "gender_weights": {"M": 40, "F": 60},
        "age_group_weights": {"10대": 20, "20대": 35, "30대": 25, "40대": 15, "50대이상": 5},
        "category_weights": _cat_weights(**{
            "SS(봄여름)": 30, "스킨케어": 20,
            "캠핑": 8, "항공": 8, "숙박": 8,
        }),
        "quantity_weights": [70, 15, 10, 3, 2],
    },
    6: {
        "description": "겨울 패딩/방한용품 시즌",
        "order_volume": {"min": 40, "max": 120},
        "interval": {"min": 0.3, "max": 0.8},
        "peak_probability": 0.05,
        "peak_volume": {"min": 150, "max": 250},
        "gender_weights": {"M": 45, "F": 55},
        "age_group_weights": {"10대": 15, "20대": 25, "30대": 25, "40대": 20, "50대이상": 15},
        "category_weights": _cat_weights(**{
            "FW(가을겨울)": 35, "생활가전": 12,
            "세제/위생": 8, "육류/가공": 8,
        }),
        "quantity_weights": [75, 15, 5, 3, 2],
    },
    7: {
        "description": "뷰티 인플루언서 바이럴",
        "order_volume": {"min": 100, "max": 250},
        "interval": {"min": 0.1, "max": 0.5},
        "peak_probability": 0.15,
        "peak_volume": {"min": 250, "max": 500},
        "gender_weights": {"M": 15, "F": 85},
        "age_group_weights": {"10대": 25, "20대": 40, "30대": 25, "40대": 8, "50대이상": 2},
        "category_weights": _cat_weights(**{
            "스킨케어": 35, "기능성(안티에이징)": 20,
            "영양제": 8, "SS(봄여름)": 8,
        }),
        "quantity_weights": [55, 25, 12, 5, 3],
    },
    8: {
        "description": "MZ세대 (10-20대) 트렌드 쇼핑",
        "order_volume": {"min": 60, "max": 150},
        "interval": {"min": 0.2, "max": 0.6},
        "peak_probability": 0.08,
        "peak_volume": {"min": 150, "max": 300},
        "gender_weights": {"M": 45, "F": 55},
        "age_group_weights": {"10대": 35, "20대": 45, "30대": 15, "40대": 4, "50대이상": 1},
        "category_weights": _cat_weights(**{
            "SS(봄여름)": 15, "FW(가을겨울)": 10,
            "스킨케어": 15, "IT/게이밍": 15,
            "티켓/패스": 8,
        }),
        "quantity_weights": [80, 12, 5, 2, 1],
    },
    9: {
        "description": "5060 건강/식품 집중 구매",
        "order_volume": {"min": 20, "max": 80},
        "interval": {"min": 0.5, "max": 1.5},
        "peak_probability": 0.03,
        "peak_volume": {"min": 80, "max": 150},
        "gender_weights": {"M": 40, "F": 60},
        "age_group_weights": {"10대": 2, "20대": 5, "30대": 10, "40대": 30, "50대이상": 53},
        "category_weights": _cat_weights(**{
            "건강식품": 25, "영양제": 20,
            "신선(과일/채소)": 15, "육류/가공": 10,
        }),
        "quantity_weights": [50, 25, 15, 5, 5],
    },
    10: {
        "description": "캠핑 시즌 (봄/가을)",
        "order_volume": {"min": 30, "max": 100},
        "interval": {"min": 0.3, "max": 1.0},
        "peak_probability": 0.05,
        "peak_volume": {"min": 100, "max": 200},
        "gender_weights": {"M": 65, "F": 35},
        "age_group_weights": {"10대": 5, "20대": 20, "30대": 35, "40대": 30, "50대이상": 10},
        "category_weights": _cat_weights(**{
            "캠핑": 30, "육류/가공": 15,
            "세제/위생": 8, "티켓/패스": 8,
        }),
        "quantity_weights": [60, 20, 10, 5, 5],
    },
    11: {
        "description": "신학기 시즌 (가구/IT)",
        "order_volume": {"min": 40, "max": 100},
        "interval": {"min": 0.3, "max": 0.8},
        "peak_probability": 0.05,
        "peak_volume": {"min": 100, "max": 200},
        "gender_weights": {"M": 50, "F": 50},
        "age_group_weights": {"10대": 30, "20대": 40, "30대": 15, "40대": 10, "50대이상": 5},
        "category_weights": _cat_weights(**{
            "사무/학생": 25, "IT/게이밍": 25,
            "세제/위생": 8, "화지/제지": 5,
        }),
        "quantity_weights": [85, 10, 3, 1, 1],
    },
    12: {
        "description": "결혼/혼수 시즌",
        "order_volume": {"min": 30, "max": 80},
        "interval": {"min": 0.5, "max": 1.5},
        "peak_probability": 0.03,
        "peak_volume": {"min": 80, "max": 150},
        "gender_weights": {"M": 35, "F": 65},
        "age_group_weights": {"10대": 2, "20대": 20, "30대": 50, "40대": 20, "50대이상": 8},
        "category_weights": _cat_weights(**{
            "생활가전": 25, "소파/침대": 25,
            "세제/위생": 10, "화지/제지": 5,
        }),
        "quantity_weights": [70, 15, 10, 3, 2],
    },
    13: {
        "description": "새해 다이어트/헬스 시즌",
        "order_volume": {"min": 40, "max": 120},
        "interval": {"min": 0.3, "max": 0.8},
        "peak_probability": 0.05,
        "peak_volume": {"min": 120, "max": 250},
        "gender_weights": {"M": 40, "F": 60},
        "age_group_weights": {"10대": 10, "20대": 30, "30대": 30, "40대": 20, "50대이상": 10},
        "category_weights": _cat_weights(**{
            "영양제": 25, "골프": 5,
            "캠핑": 5, "신선(과일/채소)": 15,
            "SS(봄여름)": 10,
        }),
        "quantity_weights": [60, 20, 10, 5, 5],
    },
    14: {
        "description": "육아맘 생필품 대량 구매",
        "order_volume": {"min": 40, "max": 100},
        "interval": {"min": 0.3, "max": 1.0},
        "peak_probability": 0.05,
        "peak_volume": {"min": 100, "max": 200},
        "gender_weights": {"M": 10, "F": 90},
        "age_group_weights": {"10대": 2, "20대": 15, "30대": 50, "40대": 28, "50대이상": 5},
        "category_weights": _cat_weights(**{
            "세제/위생": 25, "화지/제지": 20,
            "신선(과일/채소)": 15, "육류/가공": 10,
            "영양제": 8,
        }),
        "quantity_weights": [30, 25, 20, 15, 10],
    },
    15: {
        "description": "골프 시즌 (봄/가을)",
        "order_volume": {"min": 20, "max": 60},
        "interval": {"min": 0.5, "max": 1.5},
        "peak_probability": 0.03,
        "peak_volume": {"min": 60, "max": 120},
        "gender_weights": {"M": 70, "F": 30},
        "age_group_weights": {"10대": 2, "20대": 10, "30대": 25, "40대": 35, "50대이상": 28},
        "category_weights": _cat_weights(**{
            "골프": 40, "SS(봄여름)": 12,
            "항공": 8, "숙박": 8, "티켓/패스": 5,
        }),
        "quantity_weights": [80, 12, 5, 2, 1],
    },
    16: {
        "description": "여행 성수기 (여름/연말)",
        "order_volume": {"min": 50, "max": 130},
        "interval": {"min": 0.3, "max": 0.8},
        "peak_probability": 0.08,
        "peak_volume": {"min": 130, "max": 250},
        "gender_weights": {"M": 45, "F": 55},
        "age_group_weights": {"10대": 10, "20대": 30, "30대": 30, "40대": 20, "50대이상": 10},
        "category_weights": _cat_weights(**{
            "항공": 30, "숙박": 30, "티켓/패스": 20,
            "SS(봄여름)": 10, "스킨케어": 8,
        }),
        "quantity_weights": [70, 20, 5, 3, 2],
    },
    17: {
        "description": "새벽배송 식품 집중",
        "order_volume": {"min": 30, "max": 90},
        "interval": {"min": 0.3, "max": 1.0},
        "peak_probability": 0.05,
        "peak_volume": {"min": 90, "max": 180},
        "gender_weights": {"M": 35, "F": 65},
        "age_group_weights": {"10대": 5, "20대": 20, "30대": 35, "40대": 25, "50대이상": 15},
        "category_weights": _cat_weights(**{
            "신선(과일/채소)": 30, "육류/가공": 25,
            "세제/위생": 10, "화지/제지": 8,
        }),
        "quantity_weights": [40, 25, 20, 10, 5],
    },
    18: {
        "description": "가전 할인 행사 (빅세일)",
        "order_volume": {"min": 80, "max": 200},
        "interval": {"min": 0.2, "max": 0.6},
        "peak_probability": 0.15,
        "peak_volume": {"min": 200, "max": 400},
        "gender_weights": {"M": 55, "F": 45},
        "age_group_weights": {"10대": 5, "20대": 20, "30대": 30, "40대": 30, "50대이상": 15},
        "category_weights": _cat_weights(**{
            "생활가전": 30, "IT/게이밍": 25,
            "소파/침대": 10,
        }),
        "quantity_weights": [85, 10, 3, 1, 1],
    },
    19: {
        "description": "평일 심야 소량 주문",
        "order_volume": {"min": 3, "max": 15},
        "interval": {"min": 1.0, "max": 3.0},
        "peak_probability": 0.01,
        "peak_volume": {"min": 20, "max": 40},
        "gender_weights": {"M": 55, "F": 45},
        "age_group_weights": {"10대": 10, "20대": 35, "30대": 30, "40대": 15, "50대이상": 10},
        "category_weights": _cat_weights(**{
            "신선(과일/채소)": 12, "세제/위생": 10,
            "스킨케어": 10, "IT/게이밍": 10,
        }),
        "quantity_weights": [90, 7, 2, 1, 0],
    },
    20: {
        "description": "전 카테고리 균등 대량 주문",
        "order_volume": {"min": 100, "max": 300},
        "interval": {"min": 0.1, "max": 0.4},
        "peak_probability": 0.10,
        "peak_volume": {"min": 300, "max": 600},
        "gender_weights": {"M": 50, "F": 50},
        "age_group_weights": {"10대": 15, "20대": 25, "30대": 25, "40대": 20, "50대이상": 15},
        "category_weights": {cat: round(100 / len(AVAILABLE_CATEGORIES), 1) for cat in AVAILABLE_CATEGORIES},
        "quantity_weights": [70, 15, 8, 4, 3],
    },
}

DEFAULT_CONFIG = BASELINE_CONFIG


def estimate_duration_minutes(config: Dict[str, Any], target_orders: int = 10000) -> int:
    """시나리오 설정으로부터 유의미한 데이터 수집 권장 시간(분) 계산"""
    ov = config["order_volume"]
    iv = config["interval"]
    avg_volume = (ov["min"] + ov["max"]) / 2
    avg_interval = (iv["min"] + iv["max"]) / 2

    peak_prob = config.get("peak_probability", 0.02)
    pv = config.get("peak_volume", {"min": 100, "max": 200})
    avg_peak = (pv["min"] + pv["max"]) / 2

    effective_avg = avg_volume * (1 - peak_prob) + avg_peak * peak_prob
    tps = effective_avg / avg_interval if avg_interval > 0 else effective_avg
    seconds = target_orders / tps if tps > 0 else 300
    return max(1, round(seconds / 60))


class ScenarioEngine:
    """프리셋 기반 시나리오 엔진"""

    def __init__(self):
        self.current_config: Dict[str, Any] = DEFAULT_CONFIG.copy()

    def get_scenario(self, number: int) -> Dict[str, Any]:
        """번호로 시나리오 선택"""
        config = SCENARIOS.get(number)
        if config is None:
            print(f"⚠️ {number}번 시나리오가 없습니다. 기본 시나리오를 사용합니다.")
            config = DEFAULT_CONFIG
        self.current_config = config.copy()
        return self.current_config

    def get_current_config(self) -> Dict[str, Any]:
        return self.current_config

    def get_time_based_config(self) -> Dict[str, Any]:
        """
        현재 시각 기준으로 자동 시나리오 적용된 config 반환
        - 21~23시: 17번 (새벽배송 식품) 특성 적용
        - 0~5시: 19번 (심야 소량) 특성 적용
        - 그 외: 기본 패턴 사용

        주문량(order_volume)은 HOURLY_MULTIPLIER가 제어하므로,
        여기서는 카테고리/성별/연령 가중치만 시나리오에서 가져옴
        """
        scenario_num = get_time_based_scenario_number()

        if scenario_num is None:
            # 기본 패턴 사용
            self.current_config = BASELINE_CONFIG.copy()
            return self.current_config

        # 시간대 시나리오 가져오기
        time_scenario = SCENARIOS.get(scenario_num, BASELINE_CONFIG)

        # 기본 패턴 복사 후 시나리오 특성만 병합
        merged = BASELINE_CONFIG.copy()
        merged["description"] = f"[자동] {time_scenario['description']}"
        merged["gender_weights"] = time_scenario["gender_weights"]
        merged["age_group_weights"] = time_scenario["age_group_weights"]
        merged["category_weights"] = time_scenario["category_weights"]
        merged["quantity_weights"] = time_scenario["quantity_weights"]

        # 심야(19번)는 주문량도 줄임 (HOURLY_MULTIPLIER와 시너지)
        if scenario_num == 19:
            merged["order_volume"] = time_scenario["order_volume"]
            merged["interval"] = time_scenario["interval"]
            merged["peak_probability"] = time_scenario["peak_probability"]
            merged["peak_volume"] = time_scenario["peak_volume"]

        self.current_config = merged
        return self.current_config

    @staticmethod
    def list_scenarios() -> List[Dict[str, Any]]:
        """전체 시나리오 목록 반환"""
        return [{"number": k, "description": v["description"]} for k, v in SCENARIOS.items()]

    @staticmethod
    def print_menu():
        """시나리오 선택 메뉴 출력"""
        print("\n╔════════════════════════════════════════════════════════════════╗")
        print("║                  시나리오 선택 메뉴                           ║")
        print("╠════════════════════════════════════════════════════════════════╣")
        print("║                                                                ║")
        print("║  [성별/연령 특화]                                              ║")
        for num in [1, 2, 8, 9, 14]:
            s = SCENARIOS[num]
            dur = estimate_duration_minutes(s)
            print(f"║  {num:>2}. {s['description']:<28} (~{dur}분)              ║")
        print("║  [시즌/이벤트]                                                 ║")
        for num in [3, 4, 5, 6, 12, 13]:
            s = SCENARIOS[num]
            dur = estimate_duration_minutes(s)
            print(f"║  {num:>2}. {s['description']:<28} (~{dur}분)              ║")
        print("║  [카테고리 특화]                                               ║")
        for num in [7, 10, 11, 15, 16, 17, 18]:
            s = SCENARIOS[num]
            dur = estimate_duration_minutes(s)
            print(f"║  {num:>2}. {s['description']:<28} (~{dur}분)              ║")
        print("║  [트래픽 패턴]                                                 ║")
        for num in [19, 20]:
            s = SCENARIOS[num]
            dur = estimate_duration_minutes(s)
            print(f"║  {num:>2}. {s['description']:<28} (~{dur}분)              ║")
        print("║                                                                ║")
        print("╚════════════════════════════════════════════════════════════════╝")


if __name__ == "__main__":
    from pprint import pprint

    engine = ScenarioEngine()
    engine.print_menu()
    print()

    while True:
        try:
            raw = input("📝 시나리오 번호를 입력하세요 (exit 종료): ").strip()
        except EOFError:
            break

        if not raw:
            continue
        if raw.lower() == "exit":
            print("종료합니다.")
            break

        try:
            num = int(raw)
        except ValueError:
            print("⚠️ 숫자를 입력해주세요.")
            continue

        config = engine.get_scenario(num)
        dur = estimate_duration_minutes(config)
        desc = config["description"]
        gw = config["gender_weights"]
        ov = config["order_volume"]
        top_cats = sorted(config["category_weights"].items(), key=lambda x: x[1], reverse=True)[:3]

        print(f"\n  ✅ [{num}] {desc}")
        print(f"     권장 실행 시간: ~{dur}분 (약 10,000건 수집)")
        print(f"     주문량: {ov['min']}~{ov['max']}건/배치")
        print(f"     성별: M={gw['M']}% F={gw['F']}%")
        print(f"     인기 카테고리: {', '.join(f'{c}({w}%)' for c, w in top_cats)}")
        print()