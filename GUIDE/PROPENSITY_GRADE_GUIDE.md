# 구매 성향 & 등급 갱신 시스템 가이드

고객의 **구매 성향 점수**를 기반으로 현실적인 주문을 생성하고, **등급 자동 갱신**으로 고객 라이프사이클을 시뮬레이션하는 시스템입니다.

## 시스템 개요

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   Redis Cache    │────▶│ Purchase         │────▶│  상위 200명      │
│  (1000명 캐싱)   │     │ Propensity       │     │  주문 후보 선택  │
└──────────────────┘     │ (성향 점수 계산)  │     └──────────────────┘
                         └──────────────────┘

┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   PostgreSQL     │────▶│ Grade Updater    │────▶│  등급 갱신       │
│  (주문 이력)     │     │ (6개월 누적)     │     │  VIP/GOLD/SILVER │
└──────────────────┘     └──────────────────┘     └──────────────────┘
```

## 1. 구매 성향 시스템 (`collect/purchase_propensity.py`)

### 점수 계산 공식

```
최종 점수 = 기본 점수(나이+성별+상태+마케팅+등급) × 시간대 변동 × 마케팅 부스트 × 생활 이벤트
```

### 1-1. 기본 점수 (0~100 범위, 합산)

캐싱된 고객의 기존 컬럼 5개를 조합합니다:

| 요소 | 값 | 점수 | 설명 |
|------|-----|------|------|
| **나이** | 10대 | 12 | |
| | 20대 | 20 | |
| | 30대 | **25** | 최대 소비층 |
| | 40대 | 22 | |
| | 50대이상 | 18 | |
| **성별** | F (여성) | **15** | 온라인 쇼핑 빈도 높음 |
| | M (남성) | 12 | |
| **활동 상태** | ACTIVE | **20** | |
| | DORMANT | 5 | |
| **마케팅 동의** | true | **15** | |
| | false | 8 | |
| **등급** | VIP | **25** | |
| | GOLD | 20 | |
| | SILVER | 15 | |
| | BRONZE | 10 | |

**예시**: 30대 여성, ACTIVE, 마케팅 동의, GOLD → 25 + 15 + 20 + 15 + 20 = **95점**

### 1-2. 시간대 변동 (연령대별 24시간 패턴)

각 연령대마다 활성 시간대가 다릅니다 (배수 0.1 ~ 1.8):

| 시간대 | 10대 | 20대 | 30대 | 40대 | 50대이상 |
|--------|------|------|------|------|----------|
| 00-05시 | 0.1~0.8 | 0.1~0.7 | 0.1~0.3 | 0.1~0.2 | 0.1 |
| 06-09시 | 0.2~0.5 | 0.2~0.7 | 0.3~0.9 | 0.4~1.0 | 0.5~1.3 |
| 10-12시 | 0.6~0.9 | 0.8~1.3 | 1.0~1.4 | 1.2~1.4 | **1.4~1.6** |
| 13-17시 | 0.7~1.0 | 0.8~1.1 | 0.8~1.2 | 0.8~1.2 | 0.7~1.2 |
| 18-19시 | 1.2~1.4 | 1.3~1.5 | 1.1~1.5 | 1.1~1.4 | 0.8~1.0 |
| **20-21시** | **1.6~1.8** | **1.7~1.8** | **1.6~1.8** | **1.3~1.6** | 0.8~1.1 |
| 22-23시 | 1.2~1.5 | 1.0~1.5 | 0.5~1.0 | 0.4~0.8 | 0.2~0.5 |

**특징**:
- 10~20대: 야간 활동 피크 (20~22시)
- 30~40대: 저녁 피크 (19~20시)
- 50대이상: 오전 피크 (10~12시)

### 1-3. 마케팅 프로모션 부스트

| 조건 | 확률 | 배수 |
|------|------|------|
| `marketing_agree == "true"` | 20% | **1.3x** |
| 그 외 | - | 1.0x (변동 없음) |

### 1-4. 생활 이벤트 (랜덤 소비 충동)

| 이벤트 | 확률 | 배수 | 설명 |
|--------|------|------|------|
| 보통 | 85% | 1.0x | 일상적 소비 |
| 소비 증가 | 12% | **1.5x** | 월급날, 보너스 등 |
| 대규모 지출 | 3% | **3.0x** | 이사, 결혼, 출산 등 |

### 1-5. 상위 200명 선택 (`select_top_buyers`)

```python
from collect.purchase_propensity import select_top_buyers

# 캐싱된 1000명에서 상위 200명 선택
top_buyers = select_top_buyers(users=cached_users, top_n=200, hour=current_hour)

# 결과: [(user_dict, score), (user_dict, score), ...]
for user, score in top_buyers:
    print(f"{user['name']}: {score:.1f}점")
```

## 2. 등급 갱신 시스템 (`apps/batch/grade_updater.py`)

### 등급 기준 (6개월 누적, AND 조건)

| 등급 | 누적 금액 | 주문 횟수 | 비고 |
|------|----------|----------|------|
| **VIP** | 200만원 이상 | 10회 이상 | 최상위 |
| **GOLD** | 100만원 이상 | 8회 이상 | |
| **SILVER** | 30만원 이상 | 3회 이상 | |
| **BRONZE** | 조건 미달 | - | 기본 등급 |

- 금액과 횟수 **두 조건 모두** 충족해야 해당 등급
- 높은 등급부터 순서대로 확인 (VIP → GOLD → SILVER → BRONZE)
- 조건 미달 시 **강등** 가능

### 갱신 주기

| 환경 | 주기 | 실행 방법 |
|------|------|----------|
| **실시간 시스템** | 10분마다 | `python -m apps.batch.grade_updater` |
| **1년치 스크립트** | 7일마다 | `generate_historical_data.py` 내부 호출 |
| **1회 실행** | 수동 | `python -m apps.batch.grade_updater --once` |

### 갱신 프로세스

```
1. 6개월간 주문 집계 (user_id별 총 금액, 주문 수)
   → WHERE created_at >= 6개월전 AND status = 'Success'

2. 전체 유저 조회

3. 각 유저별 새 등급 결정
   → determine_grade(total_amount, order_count)

4. 등급 변경 (승급/강등/유지 통계)

5. DB 커밋
```

### 실행 방법

```bash
# 10분 주기로 지속 실행 (기본)
python -m apps.batch.grade_updater

# 1회만 실행 후 종료
python -m apps.batch.grade_updater --once

# 커스텀 간격 (300초 = 5분)
python -m apps.batch.grade_updater --interval 300
```

### 로그 출력 예시

```
╔════════════════════════════════════════════════════════════╗
║          고객 등급 갱신 배치 워커 (10분 주기)               ║
╚════════════════════════════════════════════════════════════╝

2025-01-15 14:00:00 - 등급 갱신 #1 완료 - 총 44,583명 | 승급 1,234명 | 강등 567명 | 유지 42,782명
  등급 분포: VIP 89명 | GOLD 456명 | SILVER 2,345명 | BRONZE 41,693명
```

## 3. 등급과 구매 성향의 상호작용

등급이 올라가면 기본 점수가 올라가고, 구매 성향이 높아져 더 많은 주문을 생성합니다:

```
BRONZE(10점) → 주문 증가 → SILVER(15점) → 더 많은 주문 → GOLD(20점) → VIP(25점)
```

이 **양의 피드백 루프**가 현실적인 고객 라이프사이클을 시뮬레이션합니다:
- 구매 많은 고객 → 등급 상승 → 성향 점수 증가 → 더 많이 구매
- 구매 적은 고객 → 등급 유지/하락 → 성향 점수 낮음 → 적게 구매

## 4. API 레퍼런스

### purchase_propensity.py

| 함수 | 설명 | 파라미터 |
|------|------|---------|
| `calculate_base_score(user)` | 기본 성향 점수 (0~100) | user: Dict |
| `apply_time_variation(score, age_group, hour)` | 시간대 변동 적용 | score, age_group, hour |
| `apply_marketing_boost(score, marketing_agree)` | 마케팅 부스트 적용 | score, marketing_agree |
| `apply_life_event(score)` | 생활 이벤트 적용 | score |
| `calculate_propensity(user, hour)` | 최종 성향 점수 | user: Dict, hour: int |
| `select_top_buyers(users, top_n, hour)` | 상위 N명 선택 | users: List, top_n: int |

### grade_updater.py

| 함수/클래스 | 설명 | 파라미터 |
|------------|------|---------|
| `determine_grade(total_amount, order_count)` | 등급 결정 | 금액, 횟수 |
| `update_all_grades(db, reference_date)` | 전체 등급 갱신 | DB 세션, 기준일 |
| `GradeUpdaterWorker(interval)` | 배치 워커 | 간격 (초) |
| `GradeUpdaterWorker.start()` | 무한 루프 시작 | - |
| `GradeUpdaterWorker.run_once()` | 1회 실행 | - |

## 5. 커스터마이징

### 성향 점수 가중치 조정

`collect/purchase_propensity.py`에서 상수를 수정합니다:

```python
# 나이별 점수 변경
AGE_SCORE = {
    "10대": 12,
    "20대": 20,
    "30대": 25,   # 이 값을 변경
    ...
}

# 마케팅 부스트 확률/배수 변경
MARKETING_PROMO_CHANCE = 0.20   # 20% → 원하는 확률
MARKETING_PROMO_BOOST = 1.3     # 1.3x → 원하는 배수

# 생활 이벤트 비율 변경
LIFE_EVENT_WEIGHTS = [85, 12, 3]        # 보통/증가/대규모 비율
LIFE_EVENT_MULTIPLIERS = [1.0, 1.5, 3.0]  # 배수
```

### 등급 기준 조정

`apps/batch/grade_updater.py`에서 상수를 수정합니다:

```python
GRADE_CRITERIA = {
    "VIP": {"min_amount": 2_000_000, "min_orders": 10},
    "GOLD":   {"min_amount": 1_000_000, "min_orders": 8},
    "SILVER": {"min_amount":   300_000, "min_orders": 3},
    "BRONZE": {"min_amount":         0, "min_orders": 0},
}

# 갱신 주기 변경 (기본: 600초 = 10분)
REFRESH_INTERVAL = 600
```

## 관련 파일

| 파일 | 설명 |
|------|------|
| `collect/purchase_propensity.py` | 구매 성향 점수 시스템 |
| `apps/batch/grade_updater.py` | 고객 등급 갱신 배치 |
| `apps/seeders/realtime_generator.py` | 성향 기반 주문 생성 (실시간) |
| `scripts/generate_historical_data.py` | 성향 + 등급 적용 (1년치) |
| `cache/cache_worker.py` | 고객/상품 캐싱 (분리 적재) |
