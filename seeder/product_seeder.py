import sys
import os

# Ensure project root is in sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

from sqlalchemy.orm import Session
from database import crud, database
from collect.product_generator import ProductGenerator

def seed_products(db: Session, count: int = 100):
    print(f"📦 상품 데이터 생성 및 수집 시작... (목표: {count}개)")
    
    generator = ProductGenerator()
    products_list = generator.generate_batch(count)
    
    success_count = 0
    for product_data in products_list:
        try:
            crud.create_product(db, product_data)
            success_count += 1
        except Exception as e:
            print(f"⚠️ 저장 실패 ({product_data['name']}): {e}")
            db.rollback()
            
    print(f"✅ 총 {success_count}개 상품이 데이터베이스에 저장되었습니다.")

if __name__ == "__main__":
    db = database.SessionLocal()
    try:
        seed_products(db, 10)
    finally:
        db.close()
