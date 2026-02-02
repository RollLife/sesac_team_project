import sys
import os
import time

# Ensure project root is in sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

from sqlalchemy.orm import Session
from database import crud, database, models
from collect.order_generator import OrderGenerator

def seed_orders(db: Session, count: int = 100):
    print("🚀 주문 데이터 생성 및 DB 저장 시작...")
    
    # 1. Available Pools
    products = db.query(models.Product.product_id, models.Product.price, models.Product.category).limit(1000).all()
    users = db.query(models.User.user_id, models.User.age).limit(1000).all()
    
    if not products or not users:
        print("❌ 상품 또는 유저 데이터가 부족합니다. 먼저 상품/유저를 생성하세요.")
        return

    print(f"   -> 활용 가능: 상품 {len(products)}개, 유저 {len(users)}명")
    
    generator = OrderGenerator()
    orders_list = generator.generate_batch(users, products, count)
    
    success_count = 0
    start_time = time.time()
    
    for i, order_data in enumerate(orders_list):
        try:
            crud.create_order(db, order_data)
            success_count += 1
        except Exception as e:
            print(f"⚠️ 주문 생성 실패: {e}")
            db.rollback()
            
        if (i + 1) % 50 == 0:
            elapsed = time.time() - start_time
            print(f"   ... {i+1}건 처리 (경과: {elapsed:.2f}s)")
            
    print(f"✅ 총 {success_count}건 주문 저장 완료!")

if __name__ == "__main__":
    db = database.SessionLocal()
    try:
        seed_orders(db, 10)
    finally:
        db.close()
