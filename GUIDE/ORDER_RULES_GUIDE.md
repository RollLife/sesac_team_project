# 주문 생성 규칙 가이드

## 개요

주문 데이터의 현실성을 높이기 위해 카테고리별 주문 규칙을 도입했습니다.

**변경 사항:**
- `product_rules.json`: 각 카테고리에 주문 관련 설정 추가
- `order_generator.py`: 새로운 규칙을 적용하도록 수정

---

## 추가된 필드

`product_rules.json`의 각 카테고리에 다음 3개 필드가 추가되었습니다:

| 필드 | 타입 | 설명 |
|------|------|------|
| `order_frequency` | int | 주문 빈도 가중치 (높을수록 자주 주문됨) |
| `quantity_options` | int[] | 가능한 수량 옵션 |
| `quantity_weights` | int[] | 각 수량의 선택 확률 (%) |

### 예시

```json
"생활가전": {
  "price_min": 500000,
  "price_max": 5000000,
  "order_frequency": 2,
  "quantity_options": [1],
  "quantity_weights": [100],
  ...
}
```

위 설정의 의미:
- 주문 빈도 2 (다른 카테고리 대비 낮음)
- 수량은 항상 1개 (100% 확률)

---

## 카테고리별 설정 요약

| 카테고리 | 주문빈도 | 수량 옵션 | 수량 확률 | 설명 |
|----------|---------|----------|----------|------|
| **세제/위생** | 22 | 1-6개 | 15/25/25/18/12/5 | 소모품, 대량 구매 빈번 |
| **신선(과일/채소)** | 20 | 1-3개 | 55/30/15 | 일상 식품 |
| **화지/제지** | 20 | 1-4개 | 20/35/30/15 | 소모품 |
| **스킨케어** | 18 | 1-4개 | 45/30/18/7 | 뷰티 소모품 |
| **육류/가공** | 16 | 1-3개 | 50/35/15 | 식품 |
| **영양제** | 14 | 1-4개 | 40/35/18/7 | 건강 소모품 |
| **SS(봄여름)** | 12 | 1-3개 | 70/20/10 | 의류 |
| **건강식품** | 10 | 1-3개 | 55/30/15 | 선물용 多 |
| **FW(가을겨울)** | 10 | 1-2개 | 80/20 | 고가 의류 |
| **기능성(안티에이징)** | 8 | 1-2개 | 85/15 | 고가 화장품 |
| **티켓/패스** | 8 | 1-4개 | 20/35/30/15 | 인원수 개념 |
| **항공** | 6 | 1-4개 | 25/45/20/10 | 인원수 개념 |
| **숙박** | 6 | 1-3개 | 50/35/15 | 박 수 개념 |
| **사무/학생** | 5 | 1-2개 | 90/10 | 가구류 |
| **IT/게이밍** | 4 | 1-2개 | 92/8 | 고가 전자기기 |
| **캠핑** | 4 | 1-2개 | 85/15 | 레저 장비 |
| **골프** | 3 | 1-2개 | 88/12 | 고가 스포츠 |
| **생활가전** | 2 | 1개 | 100 | 냉장고/세탁기 등 |
| **소파/침대** | 2 | 1개 | 100 | 대형 가구 |

---

## 동작 방식

### 1. 수량 결정 (`_get_quantity`)

```python
# 상품의 카테고리에서 규칙 조회
rule = self.category_rules[category]

# 가중치 기반 랜덤 선택
quantity = random.choices(
    rule['quantity_options'],  # [1, 2, 3]
    weights=rule['quantity_weights'],  # [70, 20, 10]
    k=1
)[0]
```

### 2. 상품 선택 빈도 (`generate_batch`)

```python
# 각 상품의 카테고리별 order_frequency를 가중치로 사용
product_weights = [
    category_rules[p['category']]['order_frequency']
    for p in products
]

# 가중치 기반 상품 선택
picked_product = random.choices(products, weights=product_weights, k=1)[0]
```

---

## 설정 변경 방법

### 수량 옵션 변경

`product_rules.json`에서 해당 카테고리의 `quantity_options`와 `quantity_weights`를 수정합니다.

```json
"스킨케어": {
  "quantity_options": [1, 2, 3, 4, 5],  // 5개까지 허용
  "quantity_weights": [30, 30, 20, 15, 5]  // 확률 조정
}
```

**주의:** `quantity_options`와 `quantity_weights`의 길이는 반드시 같아야 합니다.

### 주문 빈도 변경

`order_frequency` 값을 조정합니다. 상대적인 값이므로 다른 카테고리와의 비율을 고려하세요.

```json
"생활가전": {
  "order_frequency": 5  // 2 → 5로 증가시키면 주문 빈도 2.5배 증가
}
```

---

## 기존 코드와의 호환성

- `product`에 `category` 필드가 없으면 기본 수량 설정 사용
- `product_rules.json`이 없어도 기본값으로 동작
- 기존 API 인터페이스 변경 없음

---

## 테스트

```bash
cd collect
python order_generator.py
```

출력 예시:
```
Category: 세제/위생    | Qty: 3 | Total: 45,000원
Category: 생활가전     | Qty: 1 | Total: 2,500,000원
Category: 스킨케어     | Qty: 2 | Total: 100,000원
Category: 티켓/패스    | Qty: 4 | Total: 400,000원
```

---

## 과거 데이터 생성 (generate_historical_data.py)

`scripts/generate_historical_data.py`도 동일한 규칙을 사용합니다.

### 적용 방식

1. **수량 결정**: `order_generator.py`의 카테고리 기반 규칙 사용
2. **상품 선택 빈도**: 시나리오 가중치 × order_frequency

```python
# select_product_by_scenario()
scenario_score = scenario_weights.get(category, 5.0)  # 시나리오별 부스트
frequency_score = order_frequency / 10                 # 기본 빈도
total_score = scenario_score * frequency_score         # 최종 점수
```

### 1년치 데이터 재생성

```bash
cd scripts
python generate_historical_data.py
```

**주의**: 기존 orders 데이터는 삭제되지 않습니다. 필요시 수동 삭제 후 실행하세요.
