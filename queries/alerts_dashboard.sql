-- 재고 부족 알림판 (Stockout List)
SELECT 
    product_id as "상품코드",
    name as "상품명",
    stock as "현재재고"
FROM products 
WHERE stock <= 0
ORDER BY stock ASC;

-- 데이터 오류 적발판 (Data Integrity) 
SELECT 
    product_id as "상품코드",
    name as "상품명",
    price as "판매가",
    org_price as "정가",
    discount_rate as "할인율"
FROM products 
WHERE discount_rate < 0 
   OR discount_rate > 100 
   OR price > org_price;

-- 이상 주문 추적판 (Abnormal Orders)
SELECT 
    order_id as "주문번호",
    total_amount as "결제금액",
    TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI:SS') as "주문시간"
FROM orders 
WHERE (total_amount < 0 OR total_amount >= 10000000)
ORDER BY created_at DESC 
LIMIT 100;

-- 이상 주문 상세
SELECT 
    o.order_id as "주문번호",
    u.name as "구매자명",
    o.total_amount as "결제금액",
    TO_CHAR(o.created_at, 'YYYY-MM-DD HH24:MI:SS') as "주문시간"
FROM orders o
LEFT JOIN users u ON o.user_id = u.user_id
WHERE (o.total_amount < 0 OR o.total_amount >= 10000000)
ORDER BY o.created_at DESC 
LIMIT 100;