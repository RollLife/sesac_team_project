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