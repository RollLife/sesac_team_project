-- Stockout Warning (재고 0 이하)
-- 설명: 재고가 0이거나 음수인 상품 발견 시 경고
SELECT product_id, name, stock 
FROM products 
WHERE stock <= 0;

-- Data Integrity Error (할인율/가격 오류)
-- 설명: 할인율이 음수/100% 초과거나, 판매가가 정가보다 비싼 경우
SELECT product_id, name, discount_rate, price, org_price
FROM products 
WHERE discount_rate < 0 
   OR discount_rate > 100 
   OR price > org_price;

-- Abnormal Order (주문 금액 이상)
-- 설명: 가격이 음수(-)이거나 1,000만원 이상인 고액 주문
SELECT count(*)
FROM orders 
WHERE (total_amount < 0 OR total_amount >= 10000000)
  AND created_at >= NOW() - INTERVAL '10 minutes';