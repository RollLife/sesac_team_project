-- 선택 기간 내 총매출
SELECT
  SUM(total_amount) as "총매출"
FROM orders
WHERE created_at >= $__timeFrom();

-- 연령대별 결제 수단
SELECT 
  user_age_group AS "연령대",
  count(*) FILTER (WHERE payment_method = 'Card') AS "Card",
  count(*) FILTER (WHERE payment_method = 'NaverPay') AS "NaverPay",
  count(*) FILTER (WHERE payment_method = 'KakaoPay') AS "KakaoPay",
  count(*) FILTER (WHERE payment_method = 'Bank') AS "Bank"
FROM orders
WHERE created_at >= $__timeFrom()
GROUP BY 1
ORDER BY 1 ASC;

-- 결제 수단별 점유율
SELECT 
  payment_method,
  ROUND(count(*) * 100.0 / SUM(count(*)) OVER(), 1) as percentage
FROM orders
WHERE created_at >= $__timeFrom()
GROUP BY payment_method;


-- 시간대별 주문 추세 (5분 기준)
-- 해당 문법에서는 Grafana에서 자동으로 KST로 인식함........ IDK..............
SELECT
  date_trunc('minute', created_at - INTERVAL '9 hours') - 
  (EXTRACT(minute FROM created_at - INTERVAL '9 hours')::int % 5) * INTERVAL '1 minute',
  count(*) as value,
  '주문 건수' as metric
FROM orders
WHERE created_at >= $__timeFrom()
GROUP BY 1
ORDER BY 1;


-- 구매 빈도 vs 객단가 분포
-- X: 구매횟수, Y: 평균객단가
SELECT
  COUNT(*) as frequency,
  AVG(total_amount) as avg_amount,
  user_id
FROM orders
WHERE status = 'Success'
GROUP BY user_id;


-- 시간대별 주문 추세 (막대그래프)
SELECT
  EXTRACT(HOUR FROM created_at)::text || '시' AS "시간대",
  COUNT(*) AS "주문수"
FROM orders
WHERE created_at >= NOW() - INTERVAL '1 day'
GROUP BY EXTRACT(HOUR FROM created_at)
ORDER BY 1;

-- 시간대별 주문 추세 (테이블용)
SELECT        -- 요일별, 시간대별 주문 건수 및 매출 추출
  CASE EXTRACT(DOW FROM created_at)
    WHEN 0 THEN '일'
    WHEN 1 THEN '월'
    WHEN 2 THEN '화'
    WHEN 3 THEN '수'
    WHEN 4 THEN '목'
    WHEN 5 THEN '금'
    WHEN 6 THEN '토'
  END AS "요일",
  EXTRACT(HOUR FROM created_at) || '시' AS "시간대",
  COUNT(*) AS "주문수",
  SUM(total_amount) AS "매출"
FROM orders
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY 1, EXTRACT(DOW FROM created_at), 2, EXTRACT(HOUR FROM created_at)
ORDER BY EXTRACT(DOW FROM created_at), EXTRACT(HOUR FROM created_at);


-- 장바구니 분석 (함께 구매된 카테고리)
-- 같은 사용자가 구매한 카테고리 조합 분석
WITH user_categories AS (
  SELECT 
    user_id,
    category
  FROM orders
  WHERE status = 'Success'
  GROUP BY user_id, category
)
SELECT
  a.category || ' + ' || b.category AS "카테고리_조합",
  COUNT(DISTINCT a.user_id) AS "동시구매고객수"
FROM user_categories a
JOIN user_categories b 
  ON a.user_id = b.user_id AND a.category < b.category
GROUP BY a.category, b.category
HAVING COUNT(DISTINCT a.user_id) >= 5
ORDER BY "동시구매고객수" DESC
LIMIT 20;


-- 브랜드별 매출 순위
SELECT
  p.brand AS "브랜드",
  SUM(o.total_amount) AS "매출"
FROM orders o
JOIN products p ON o.product_id = p.product_id
WHERE o.created_at >= $__timeFrom()
GROUP BY p.brand
ORDER BY "매출" DESC
LIMIT 20;


-- ============================================================
-- 핵심 매출 지표
-- ============================================================

-- 총 주문 건수
SELECT COUNT(*) as "총주문" 
FROM orders 
WHERE created_at >= $__timeFrom();

-- 평균 객단가
SELECT ROUND(AVG(total_amount)) as "평균객단가" 
FROM orders 
WHERE created_at >= $__timeFrom();


-- ============================================================
-- 고객 등급 분석 (grade_updater.py 기준: 6개월 누적)
-- VIP: 500만원+ / 30회+
-- GOLD: 200만원+ / 15회+
-- SILVER: 50만원+ / 5회+
-- BRONZE: 기본
-- ============================================================

-- 매출 최상위 고객 리스트 (상위 20%)
WITH user_total AS (
  SELECT
    u.name AS "고객명",
    u.email AS "이메일",
    SUM(o.total_amount) AS "총매출",
    COUNT(o.order_id) AS "주문수"
  FROM orders o
  JOIN users u ON o.user_id = u.user_id
  WHERE o.created_at >= $__timeFrom() AND o.status = 'Success'
  GROUP BY u.user_id, u.name, u.email
),
ranked_users AS (
  SELECT
    *,
    PERCENT_RANK() OVER (ORDER BY "총매출" DESC) as pct_rank
  FROM user_total
)
SELECT
  "고객명",
  "이메일",
  "총매출",
  "주문수"
FROM ranked_users
WHERE pct_rank <= 0.2
ORDER BY "총매출" DESC;


-- 등급별 고객 상세
SELECT
  grade as "등급",
  COUNT(DISTINCT user_id) as "고객수",
  ROUND(COUNT(DISTINCT user_id) * 100.0 / (SELECT COUNT(DISTINCT user_id) FROM orders WHERE created_at >= $__timeFrom() AND status = 'Success'), 1) as "비율(%)",
  SUM(total_spend) as "총매출",
  ROUND(AVG(total_spend), 0) as "인당평균매출"
FROM (
  SELECT
    user_id,
    SUM(total_amount) as total_spend,
    CASE
      WHEN SUM(total_amount) >= 5000000 AND COUNT(order_id) >= 30 THEN 'VIP'
      WHEN SUM(total_amount) >= 2000000 AND COUNT(order_id) >= 15 THEN 'GOLD'
      WHEN SUM(total_amount) >= 500000 AND COUNT(order_id) >= 5 THEN 'SILVER'
      ELSE 'BRONZE'
    END as grade
  FROM orders
  WHERE created_at >= $__timeFrom() AND status = 'Success'
  GROUP BY user_id
) sub
GROUP BY grade
ORDER BY
  CASE grade
    WHEN 'VIP' THEN 1
    WHEN 'GOLD' THEN 2
    WHEN 'SILVER' THEN 3
    WHEN 'BRONZE' THEN 4
  END;


-- 등급별 고객 분포 (파이차트용)
SELECT
  grade as "등급",
  COUNT(*) as "고객수"
FROM (
  SELECT
    user_id,
    CASE
      WHEN SUM(total_amount) >= 5000000 AND COUNT(order_id) >= 30 THEN 'VIP'
      WHEN SUM(total_amount) >= 2000000 AND COUNT(order_id) >= 15 THEN 'GOLD'
      WHEN SUM(total_amount) >= 500000 AND COUNT(order_id) >= 5 THEN 'SILVER'
      ELSE 'BRONZE'
    END as grade
  FROM orders
  WHERE created_at >= $__timeFrom() AND status = 'Success'
  GROUP BY user_id
) sub
GROUP BY grade
ORDER BY
  CASE grade
    WHEN 'BRONZE' THEN 1
    WHEN 'SILVER' THEN 2
    WHEN 'GOLD' THEN 3
    WHEN 'VIP' THEN 4
  END;


-- 등급별 매출 비중 (파이차트용)
SELECT
  grade as "등급",
  SUM(total_spend) as "매출"
FROM (
  SELECT
    user_id,
    SUM(total_amount) as total_spend,
    CASE
      WHEN SUM(total_amount) >= 5000000 AND COUNT(order_id) >= 30 THEN 'VIP'
      WHEN SUM(total_amount) >= 2000000 AND COUNT(order_id) >= 15 THEN 'GOLD'
      WHEN SUM(total_amount) >= 500000 AND COUNT(order_id) >= 5 THEN 'SILVER'
      ELSE 'BRONZE'
    END as grade
  FROM orders
  WHERE created_at >= $__timeFrom() AND status = 'Success'
  GROUP BY user_id
) sub
GROUP BY grade
ORDER BY
  CASE grade
    WHEN 'BRONZE' THEN 1
    WHEN 'SILVER' THEN 2
    WHEN 'GOLD' THEN 3
    WHEN 'VIP' THEN 4
  END;


-- ============================================================
-- 고객 유형 분석 (VIP / 일반 / 휴면)
-- ============================================================

-- 고객 유형 분포 (파이차트용)
WITH user_spend AS (
  SELECT user_id, COALESCE(SUM(total_amount), 0) as total_spend, COUNT(*) as order_count
  FROM orders
  WHERE created_at >= NOW() - INTERVAL '30 days'
  GROUP BY user_id
)
SELECT 
  CASE 
    WHEN total_spend >= 5000000 AND order_count >= 30 THEN 'VIP'
    WHEN total_spend >= 10000 THEN '일반'
    ELSE '휴면'
  END AS "세그먼트",
  COUNT(*) AS "고객수"
FROM user_spend
GROUP BY 1
ORDER BY 2 DESC;


-- 고객 유형별 매출 기여도 (가로 막대 차트용)
WITH user_spend AS (
  SELECT user_id, COALESCE(SUM(total_amount), 0) as total_spend, COUNT(*) as order_count
  FROM orders
  WHERE created_at >= NOW() - INTERVAL '30 days'
  GROUP BY user_id
)
SELECT 
  CASE 
    WHEN total_spend >= 5000000 AND order_count >= 30 THEN 'VIP'
    WHEN total_spend >= 10000 THEN '일반'
    ELSE '휴면'
  END AS "고객 유형",
  SUM(total_spend) AS "총매출"
FROM user_spend
GROUP BY 1
ORDER BY 2 DESC;


-- ============================================================
-- 지역별 분석
-- ============================================================

-- 지역별 주문 건수 (지도용)
SELECT 
    u.address_district as "지역",
    COUNT(o.order_id) as "주문건수",
    CASE u.address_district
        WHEN '서울' THEN 37.5665
        WHEN '경기' THEN 37.4138
        WHEN '인천' THEN 37.4563
        WHEN '부산' THEN 35.1796
        WHEN '대구' THEN 35.8714
        WHEN '대전' THEN 36.3504
        WHEN '광주' THEN 35.1595
        WHEN '울산' THEN 35.5384
        WHEN '강원' THEN 37.8228
        WHEN '충청' THEN 36.6357
        WHEN '경상' THEN 35.8000
        WHEN '전라' THEN 35.4000
        WHEN '제주' THEN 33.4996
    END as "latitude",
    CASE u.address_district
        WHEN '서울' THEN 126.9780
        WHEN '경기' THEN 127.5183
        WHEN '인천' THEN 126.7052
        WHEN '부산' THEN 129.0756
        WHEN '대구' THEN 128.6014
        WHEN '대전' THEN 127.3845
        WHEN '광주' THEN 126.8526
        WHEN '울산' THEN 129.3114
        WHEN '강원' THEN 128.1555
        WHEN '충청' THEN 127.4912
        WHEN '경상' THEN 128.5000
        WHEN '전라' THEN 127.0000
        WHEN '제주' THEN 126.5312
    END as "longitude"
FROM orders o
JOIN users u ON o.user_id = u.user_id
GROUP BY u.address_district;


-- 지역별 총 매출 (지도용)
SELECT 
    u.address_district as "지역",
    SUM(o.total_amount) as "총매출",
    CASE u.address_district
        WHEN '서울' THEN 37.5665
        WHEN '경기' THEN 37.4138
        WHEN '인천' THEN 37.4563
        WHEN '부산' THEN 35.1796
        WHEN '대구' THEN 35.8714
        WHEN '대전' THEN 36.3504
        WHEN '광주' THEN 35.1595
        WHEN '울산' THEN 35.5384
        WHEN '강원' THEN 37.8228
        WHEN '충청' THEN 36.6357
        WHEN '경상' THEN 35.8000
        WHEN '전라' THEN 35.4000
        WHEN '제주' THEN 33.4996
    END as "latitude",
    CASE u.address_district
        WHEN '서울' THEN 126.9780
        WHEN '경기' THEN 127.5183
        WHEN '인천' THEN 126.7052
        WHEN '부산' THEN 129.0756
        WHEN '대구' THEN 128.6014
        WHEN '대전' THEN 127.3845
        WHEN '광주' THEN 126.8526
        WHEN '울산' THEN 129.3114
        WHEN '강원' THEN 128.1555
        WHEN '충청' THEN 127.4912
        WHEN '경상' THEN 128.5000
        WHEN '전라' THEN 127.0000
        WHEN '제주' THEN 126.5312
    END as "longitude"
FROM orders o
JOIN users u ON o.user_id = u.user_id
GROUP BY u.address_district;