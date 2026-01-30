import pandas as pd
import random
from faker import Faker
from datetime import datetime

# 1. 한국어 더미 데이터 설정
fake = Faker('ko_KR')

# 2. 설정값
NUM_USERS = 1000  # 생성할 유저 수
GRADES = ["BRONZE", "SILVER", "GOLD", "VIP"]
GRADE_WEIGHTS = [60, 25, 10, 5]  # 등급별 비율 (VIP는 적게)

# 주요 도시 리스트 (데이터 분석 시 지역별 통계를 위해 깔끔하게 정리)
CITIES = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "경기", "강원", "충청", "전라", "경상", "제주"]

def generate_users(num_users=1000):
    data = []
    print(f"👥 고객 데이터 {num_users}명 생성 시작...")

    for i in range(num_users):
        # 1. 기본 인적사항
        uid = f"U_{str(i+1).zfill(4)}" # U_0001
        name = fake.name()
        
        # 2. 성별 및 나이 (구매 패턴 분석용)
        gender = random.choice(["M", "F"])
        age = random.randint(20, 60) # 20~60세
        birth_year = datetime.now().year - age
        
        # 3. 주소 (시/도 단위 추출)
        city = random.choice(CITIES)
        address_detail = fake.street_address()
        full_address = f"{city} {address_detail}"

        # 4. 멤버십 등급 (구매 확률에 영향을 줄 수 있음)
        grade = random.choices(GRADES, weights=GRADE_WEIGHTS, k=1)[0]

        # 5. 데이터 적재
        row = {
            "user_id": uid,
            "name": name,
            "gender": gender,
            "age": age,
            "birth_year": birth_year,
            "address": full_address,
            "city": city, # 분석 편의를 위해 지역 컬럼 분리
            "grade": grade,
            "email": fake.email(),
            "created_at": fake.date_this_decade().strftime("%Y-%m-%d") # 가입일
        }
        data.append(row)

        if (i + 1) % (num_users // 10) == 0:
            print(f"   ... {i+1}명 생성 완료")

    return pd.DataFrame(data)

# 실행 및 저장
if __name__ == "__main__":
    df_users = generate_users(NUM_USERS)
    df_users.to_csv("fake_users.csv", index=False, encoding="utf-8-sig")
    print("✅ 'fake_users.csv' 저장 완료!")
    print(df_users.head())