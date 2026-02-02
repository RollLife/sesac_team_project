import random
import time
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from database import crud, database, models

def create_random_orders(db: Session, num_orders=100):
    print("🚀 주문 생성 및 DB 저장 시작...")
    
    # 1. Available Pools
    # Note: For very large datasets, fetching all IDs might be memory intensive.
    # For this scale, it's fine.
    products = db.query(models.Product.product_id, models.Product.price, models.Product.category).limit(1000).all()
    users = db.query(models.User.user_id, models.User.age).limit(1000).all()
    
    if not products or not users:
        print("❌ 상품 또는 유저 데이터가 부족합니다. 먼저 상품/유저를 생성하세요.")
        return

    print(f"   -> 활용 가능: 상품 {len(products)}개, 유저 {len(users)}명")
    
    count = 0
    start_time = time.time()
    
    for i in range(num_orders):
        # Step 1: Pick Random User & Product
        picked_product = random.choice(products) # (id, price, category)
        picked_user = random.choice(users)       # (id, age)
        
        # Step 2: Determine Quantity
        quantity = random.choices([1, 2, 3, 4, 5], weights=[80, 10, 5, 3, 2], k=1)[0]
        
        # Step 3: Payment Method Logic
        payment = random.choice(["Card", "Bank", "Pay"])
        if picked_user.age and picked_user.age < 30:
             payment = random.choice(["Card", "NaverPay", "KakaoPay"])
        
        order_data = {
            "order_id": str(uuid.uuid4()),
            "created_at": datetime.now(),
            "user_id": picked_user.user_id,
            "product_id": picked_product.product_id,
            "quantity": quantity,
            "total_amount": picked_product.price * quantity,
            "payment_method": payment,
            "status": "Success"
            # Note: category, user_region, etc. will be auto-filled by crud.create_order
        }
        
        try:
            crud.create_order(db, order_data)
            count += 1
        except Exception as e:
            print(f"⚠️ 주문 생성 실패: {e}")
            db.rollback()
            
        # Logging & Performance
        if (i + 1) % 50 == 0:
            elapsed = time.time() - start_time
            print(f"   ... {i+1}건 처리 (경과: {elapsed:.2f}s)")
            
    print(f"✅ 총 {count}건 주문 저장 완료!")
