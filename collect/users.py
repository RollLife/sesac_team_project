import random
from faker import Faker
from datetime import datetime
from sqlalchemy.orm import Session
from database import crud, database

fake = Faker('ko_KR')

GRADES = ["BRONZE", "SILVER", "GOLD", "VIP"]
GRADE_WEIGHTS = [60, 25, 10, 5]
CITIES = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "경기", "강원", "충청", "전라", "경상", "제주"]

def create_random_users(db: Session, num_users=100):
    print(f"👥 고객 {num_users}명 생성 및 DB 저장 시작...")
    
    count = 0
    for i in range(num_users):
        uid = f"U_{fake.unique.random_number(digits=8)}"
        name = fake.name()
        gender = random.choice(["M", "F"])
        age = random.randint(20, 60)
        birth_year = datetime.now().year - age
        
        city = random.choice(CITIES)
        address_detail = fake.street_address()
        full_address = f"{city} {address_detail}"
        
        grade = random.choices(GRADES, weights=GRADE_WEIGHTS, k=1)[0]
        
        user_data = {
            "user_id": uid,
            "name": name,
            "gender": gender,
            "age": age,
            "birth_year": birth_year,
            "address": full_address,
            "address_district": city, # 분석용 구/시 단위
            "grade": grade,
            "email": fake.email(),
            "created_at": fake.date_this_decade()
        }
        
        try:
            crud.create_user(db, user_data)
            count += 1
        except Exception as e:
            print(f"Failed to create user: {e}")
            db.rollback()

        if (i + 1) % 50 == 0:
            print(f"   ... {i+1}명 처리 중")
            
    print(f"✅ 총 {count}명 유저 저장 완료!")
