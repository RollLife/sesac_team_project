import sys
import os
import time
import random

# Ensure project root is in sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

from sqlalchemy.orm import Session
from database import crud, database
from collect.user_generator import UserGenerator

def seed_users(db: Session, count: int = 100):
    print(f"👥 고객 데이터 생성 및 수집 시작... (목표: {count}명)")
    
    generator = UserGenerator()
    users_list = generator.generate_batch(count)
    
    success_count = 0
    for user_data in users_list:
        try:
            # --- [Simulation] 서버 처리 지연 ---
            # 주문(Order)은 결제 대기 등이 있어서 좀 더 길게(0.5~1.0초) 잡고
            # 유저/상품은 짧게(0.05~0.2초) 잡는 디테일을 추천!
            time.sleep(random.uniform(0.05, 0.2)) 
            # ---------------------------------
            crud.create_user(db, user_data)
            success_count += 1
        except Exception as e:
            print(f"⚠️ 저장 실패 ({user_data['name']}): {e}")
            db.rollback()

    print(f"✅ 총 {success_count}명 유저가 데이터베이스에 저장되었습니다.")

if __name__ == "__main__":
    db = database.SessionLocal()
    try:
        seed_users(db, 10)
    finally:
        db.close()
