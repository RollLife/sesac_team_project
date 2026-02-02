import random
from faker import Faker
from datetime import datetime

fake = Faker('ko_KR')

GRADES = ["BRONZE", "SILVER", "GOLD", "VIP"]
GRADE_WEIGHTS = [60, 25, 10, 5]
CITIES = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "경기", "강원", "충청", "전라", "경상", "제주"]

class UserGenerator:
    def __init__(self):
        pass

    def generate_user(self):
        uid = f"U_{fake.unique.random_number(digits=8)}"
        name = fake.name()
        gender = random.choice(["M", "F"])
        age = random.randint(20, 60)
        birth_year = datetime.now().year - age
        
        city = random.choice(CITIES)
        address_detail = fake.street_address()
        full_address = f"{city} {address_detail}"
        
        grade = random.choices(GRADES, weights=GRADE_WEIGHTS, k=1)[0]
        
        return {
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

    def generate_batch(self, count=100):
        return [self.generate_user() for _ in range(count)]

if __name__ == "__main__":
    from pprint import pprint
    gen = UserGenerator()
    pprint(gen.generate_batch(5))
