# 연령대별 결제 수단
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

# 결제 수단별 점유율
SELECT 
  payment_method,
  count(*) as count,
  ROUND(count(*) * 100.0 / SUM(count(*)) OVER(), 2) as percentage
FROM orders
WHERE created_at >= $__timeFrom()
GROUP BY payment_method;

# 시간대별 주문 추세 (분 기준)
SELECT
  date_trunc('minute', created_at) as time,
  count(*) as value,
  '주문 건수' as metric
FROM orders
WHERE created_at >= NOW() - INTERVAL '1 hour'
GROUP BY 1
ORDER BY 1;