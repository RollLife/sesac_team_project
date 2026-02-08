# Historical Data Generation Guide

1년치 과거 주문 데이터를 생성하여 Grafana 분석용 데이터를 준비하는 가이드입니다.

## 개요

### 목적
- 데이터 분석팀의 Grafana 대시보드 분석을 위한 과거 데이터 생성
- 계절별/시간대별 현실적인 주문 패턴 반영
- 20가지 시나리오 이벤트를 활용한 유의미한 분석 데이터
- **구매 성향 기반 고객 선택**으로 현실적인 구매 패턴 생성
- **등급 자동 갱신**으로 시간에 따른 고객 등급 변화 반영

### 생성 데이터
| 항목 | 내용 |
|------|------|
| 기간 | 2025년 1월 1일 ~ 12월 31일 |
| 주문 수 | 약 50,000건 |
| 성장 패턴 | 월 3,000건 → 6,000건 점진적 성장 |
| 기반 데이터 | 기존 유저 1만명, 상품 2만개 활용 |
| 캐시 풀 | 첫 7일 random_seed, 이후 600+400 분리 |
| 등급 갱신 | 7일마다 6개월 누적 기준 |

## 핵심 기능

### 1. 고객 풀 분리 적재 (실시간 시스템과 동일)

스크립트 실행 시 실시간 캐시 시스템과 동일한 분리 적재 방식을 사용합니다:

```
첫 7일: random_seed 기반 랜덤 풀 (초기 데이터 부족 시기)
이후:   구매이력 600명 (last_ordered_at ASC) + 미구매 400명 (created_at DESC)
```

**상품 풀:**
```
인기상품 700개 (order_count DESC) + 신상품 300개 (order_count == 0, created_at DESC)
```

### 2. 구매 성향 기반 고객 선택

각 주문 생성 시 고객 풀에서 **구매 성향 점수**를 계산하여 선택합니다:

```
최종 점수 = 기본 점수(나이+성별+상태+마케팅+등급) × 시간대 변동 × 마케팅 부스트 × 생활 이벤트
```

| 성향 요소 | 설명 |
|-----------|------|
| 나이 | 30~40대 높은 점수, 20대/50대 중간 |
| 성별 | 여성 약간 높은 기본점수 |
| 활동 상태 | ACTIVE > DORMANT |
| 마케팅 동의 | 동의 시 20% 확률로 1.3x 부스트 |
| 등급 | VIP(1.5x) > GOLD(1.3x) > SILVER(1.1x) > BRONZE(1.0x) |
| 시간대 | 연령별 24시간 가중치 패턴 |
| 생활 이벤트 | 85% 일반(1.0x), 12% 소비증가(1.5x), 3% 대량구매(3.0x) |

### 3. 등급 자동 갱신 (7일마다)

스크립트 실행 중 7일마다 고객 등급을 갱신합니다:

| 등급 | 6개월 누적 금액 | 주문 횟수 |
|------|----------------|----------|
| VIP | 300만원 이상 | 15회 이상 |
| GOLD | 100만원 이상 | 8회 이상 |
| SILVER | 30만원 이상 | 3회 이상 |
| BRONZE | 기본 (조건 미달) | - |

### 4. DB 추적 데이터 반영

스크립트 종료 시 다음 데이터를 DB에 일괄 반영합니다:
- `users.last_ordered_at`: 마지막 주문 시간 업데이트
- `products.order_count`: 누적 판매 수 업데이트

## 실행 순서

### 1단계: 초기 데이터 확인

`initial_seeder.py`로 생성된 기본 데이터가 DB에 있어야 합니다.

```bash
# DB 데이터 확인
docker exec local_postgres psql -U postgres -d sesac_db -c "
  SELECT 'users' as table_name, COUNT(*) FROM users
  UNION ALL SELECT 'products', COUNT(*) FROM products
  UNION ALL SELECT 'orders', COUNT(*) FROM orders;"
```

**필수 조건:**
- Users: 최소 1,000명 이상
- Products: 최소 1,000개 이상

### 2단계: 과거 데이터 생성 실행

```bash
cd c:\Users\USER\sesac_team_project
python scripts/generate_historical_data.py
```

### 3단계: 확인 프롬프트

```
======================================================================
Historical Order Data Generator
  Generates 1 year of order data using existing users/products
  - Purchase propensity based customer selection
  - Weekly grade updates (6-month cumulative)
  - 600+400 user pool split (purchased + new)
======================================================================

Connecting to database...
  [OK] PostgreSQL connected

Current DB status:
  Users: 44,583
  Products: 157,171
  Orders: 477,651

[WARNING] This script will generate ~50,000 orders for 2025.
  Existing orders will NOT be deleted.

Proceed? (y/N): y
```

`y` 입력 후 생성이 시작됩니다.

## 월별/주별 이벤트 계획표

### 월별 목표 주문량 및 성장 곡선

```
 1월: ~3,000건  ######
 2월: ~3,200건  ######
 3월: ~3,400건  #######
 4월: ~3,600건  #######
 5월: ~3,800건  ########
 6월: ~4,000건  ########
 7월: ~4,300건  #########
 8월: ~4,600건  #########
 9월: ~4,900건  ##########
10월: ~5,200건  ##########
11월: ~5,500건  ###########
12월: ~6,000건  ############
```

### 월별 시나리오 배치

| 월 | 주차 | 시나리오 | 설명 |
|----|------|----------|------|
| **1월** | 1-2주 | 13 | 새해 다이어트/헬스 시즌 |
| | 3-4주 | 4 | 설날 선물세트 |
| **2월** | 1주 | 4 | 설날 연휴 마무리 |
| | 2주 | 0 | 기본 패턴 |
| | 3-4주 | 11 | 신학기 준비 |
| **3월** | 1-2주 | 11 | 신학기 시즌 |
| | 3주 | 12 | 결혼/혼수 시즌 |
| | 4주 | 5 | 봄 패션 |
| **4월** | 1,4주 | 10 | 봄 캠핑 |
| | 2주 | 15 | 골프 시즌 |
| | 3주 | 12 | 결혼/혼수 시즌 |
| **5월** | 1-2주 | 9 | 어버이날 건강식품 |
| | 3주 | 7 | 뷰티 인플루언서 |
| | 4주 | 10 | 캠핑 시즌 |
| **6월** | 1-2주 | 5 | 여름 패션/뷰티 |
| | 3-4주 | 16 | 여름 여행 준비 |
| **7월** | 1,4주 | 5 | 여름 패션 |
| | 2-3주 | 16 | 여행 성수기 (피크) |
| **8월** | 1주 | 16 | 여행 성수기 |
| | 2주 | 5 | 여름 패션 세일 |
| | 3주 | 18 | 가전 할인 행사 |
| | 4주 | 11 | 개학 준비 |
| **9월** | 1-2주 | 4 | 추석 선물세트 |
| | 3주 | 10 | 가을 캠핑 |
| | 4주 | 15 | 가을 골프 |
| **10월** | 1주 | 10 | 캠핑 시즌 |
| | 2주 | 15 | 골프 시즌 |
| | 3-4주 | 6 | 겨울 준비/FW 신상 |
| **11월** | 1주 | 6 | 겨울 패딩 |
| | 2주 | 18 | 가전 할인 |
| | **3-4주** | **3** | **블랙프라이데이 (2배 증가)** |
| **12월** | 1주 | 6 | 겨울 패딩 |
| | 2주 | 16 | 연말 여행 |
| | 3주 | 20 | 연말 대량 주문 |
| | 4주 | 8 | MZ세대 연말 쇼핑 |

## 20가지 시나리오 목록

| # | 시나리오 | 주요 특징 |
|---|----------|----------|
| 0 | 기본 패턴 | 현실적 이커머스 분포 |
| 1 | 여성 구매고객 대량 유입 | F:90%, 스킨케어/패션 |
| 2 | 남성 IT/게이밍 폭주 | M:85%, IT/게이밍 35% |
| 3 | 블랙프라이데이 | 대규모 세일, 전 카테고리 |
| 4 | 설날/추석 선물세트 | 건강식품, 40-50대 |
| 5 | 여름 패션/뷰티 | SS 30%, 여행 관련 |
| 6 | 겨울 패딩/방한용품 | FW 35%, 가전 |
| 7 | 뷰티 인플루언서 바이럴 | F:85%, 10-20대 |
| 8 | MZ세대 트렌드 쇼핑 | 10-20대 80% |
| 9 | 5060 건강/식품 | 50대 이상 53% |
| 10 | 캠핑 시즌 | M:65%, 캠핑 30% |
| 11 | 신학기 시즌 | 사무/IT, 10-20대 |
| 12 | 결혼/혼수 시즌 | 가전/가구, 30대 |
| 13 | 새해 다이어트/헬스 | 영양제, 신선식품 |
| 14 | 육아맘 생필품 | F:90%, 세제/위생 |
| 15 | 골프 시즌 | M:70%, 40-50대 |
| 16 | 여행 성수기 | 항공 30%, 숙박 30% |
| 17 | 새벽배송 식품 | 신선 30%, 육류 25% |
| 18 | 가전 할인 행사 | 생활가전 30%, IT 25% |
| 19 | 평일 심야 소량 | 최소 주문량 |
| 20 | 전 카테고리 균등 | 대량 주문, 균등 분포 |

## 시간대별 주문 분포

기존 `scenario_engine.py`의 `HOURLY_MULTIPLIER` 적용:

```
시간    배수    그래프
00-05   0.01~0.15   |
06-09   0.08~0.80   ||
10-11   1.30~1.60   ||||||||
12-14   1.00~1.40   |||||||
15-17   1.10~1.40   |||||||
18-19   1.80~2.20   |||||||||||
20시    3.00        |||||||||||||||||  (피크)
21시    2.50        ||||||||||||||
22-23   0.50~1.50   |||||
```

## 요일별 가중치

| 요일 | 가중치 | 설명 |
|------|--------|------|
| 월~목 | 0.95 | 평일 기본 |
| 금요일 | 1.15 | 주말 준비 |
| 토~일 | 1.30 | 주말 피크 |

## 데이터 정합성

### 기존 시스템과의 호환성

스크립트는 기존 시스템의 모든 규칙을 준수합니다:

| 항목 | 준수 내용 |
|------|----------|
| 테이블 구조 | `models.py`의 User, Product, Order 스키마 |
| 시나리오 | `scenario_engine.py`의 20가지 프리셋 |
| 주문 생성 | `order_generator.py`의 결제수단/수량 로직 |
| 역정규화 | category, user_region, user_gender, user_age_group |
| 캐시 풀 | 실시간 시스템과 동일한 600+400 / 700+300 분리 |
| 구매 성향 | `purchase_propensity.py`의 성향 점수 시스템 |
| 등급 갱신 | `grade_updater.py`의 6개월 누적 기준 |

### 역정규화 필드 자동 채움

```python
order.category = product.category
order.user_region = user.address_district
order.user_gender = user.gender
order.user_age_group = f"{user.age // 10 * 10}대"
```

### DB 추적 데이터 반영

스크립트 종료 시 다음 데이터가 DB에 일괄 반영됩니다:

```python
# 유저: 마지막 주문 시간 업데이트
UPDATE users SET last_ordered_at = ? WHERE user_id = ?

# 상품: 누적 판매 수 업데이트
UPDATE products SET order_count = ? WHERE product_id = ?
```

## 예상 실행 시간

| 월 수 | 예상 시간 |
|-------|----------|
| 1개월 | ~30초 |
| 6개월 | ~3분 |
| 12개월 | ~5-10분 |

## 생성 결과 확인

### DB에서 확인

```sql
-- 2025년 월별 주문 통계
SELECT
    DATE_TRUNC('month', created_at) as month,
    COUNT(*) as orders
FROM orders
WHERE created_at >= '2025-01-01' AND created_at < '2026-01-01'
GROUP BY 1
ORDER BY 1;

-- 등급별 고객 분포
SELECT grade, COUNT(*) FROM users GROUP BY grade ORDER BY COUNT(*) DESC;

-- 구매이력/미구매 분포
SELECT
  COUNT(*) FILTER (WHERE last_ordered_at IS NOT NULL) as purchased,
  COUNT(*) FILTER (WHERE last_ordered_at IS NULL) as new_users
FROM users;

-- 상품별 누적 판매 수 상위
SELECT product_id, name, order_count
FROM products
ORDER BY order_count DESC
LIMIT 20;
```

### Grafana 대시보드

생성된 데이터로 다음 분석이 가능합니다:
- 월별/주별 매출 추이
- 시간대별 주문 패턴
- 계절별 카테고리 인기도
- 연령대별/성별 구매 패턴
- 시나리오 이벤트 효과 분석
- **고객 등급별 매출 기여도**
- **등급 변화 추이 (BRONZE → SILVER → GOLD → VIP)**

## 문제 해결

### DB 연결 실패

```bash
# Docker 실행 확인
docker ps | grep postgres

# PostgreSQL 시작
docker-compose up -d postgres
```

### 유저/상품 데이터 부족

```bash
# initial_seeder.py 실행
python apps/seeders/initial_seeder.py
```

### 스크립트 중단 시

- 기존에 생성된 데이터는 DB에 남아있음
- 다시 실행하면 추가로 생성됨 (중복 주문 ID 없음)
- 필요시 2025년 데이터만 삭제 후 재실행:

```sql
DELETE FROM orders
WHERE created_at >= '2025-01-01' AND created_at < '2026-01-01';
```

## 관련 파일

| 파일 | 설명 |
|------|------|
| `scripts/generate_historical_data.py` | 과거 데이터 생성 스크립트 |
| `apps/seeders/initial_seeder.py` | 초기 유저/상품 생성 |
| `collect/scenario_engine.py` | 20가지 시나리오 정의 |
| `collect/order_generator.py` | 주문 생성 로직 |
| `collect/purchase_propensity.py` | 구매 성향 점수 시스템 |
| `apps/batch/grade_updater.py` | 고객 등급 갱신 |
| `database/models.py` | 테이블 스키마 |
