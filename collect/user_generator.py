import random
from faker import Faker
from datetime import datetime, timedelta

fake = Faker('ko_KR')

# 모든 신규 고객은 BRONZE에서 시작 (등급은 배치 작업으로 갱신)
DEFAULT_GRADE = "BRONZE"

# 실제 대한민국 인구 분포와 유사한 가중치 적용 (경기/서울 집중)
CITIES = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "경기", "강원", "충청", "전라", "경상", "제주"]
CITY_WEIGHTS = [18, 7, 5, 6, 3, 3, 2, 25, 3, 10, 8, 8, 2] # 합이 100에 가깝도록 조정

# 이메일 도메인을 국내 환경에 맞게 리얼하게
EMAIL_DOMAINS = ["naver.com", "gmail.com", "daum.net", "kakao.com", "icloud.com"]

class UserGenerator:
    def __init__(self):
        pass

    def generate_user(self):
        uid = f"U_{fake.unique.random_number(digits=8)}"
        name = fake.name()
        gender = random.choice(["M", "F"])
        
        # 구매력이 있는 20~50대 비중을 높임 (가중치 적용 예시)
        age = random.choices(
            [random.randint(20, 29), random.randint(30, 39), random.randint(40, 49), random.randint(50, 60)],
            weights=[30, 30, 25, 15], # 2030 세대가 60%
            k=1
        )[0]
        birth_year = datetime.now().year - age
        
        # 인구 비례 도시 선택
        city = random.choices(CITIES, weights=CITY_WEIGHTS, k=1)[0]
        address_detail = fake.street_address()
        full_address = f"{city} {address_detail}"
        
        grade = DEFAULT_GRADE
        
        # 리얼한 이메일 생성
        email_id = fake.user_name()
        email_domain = random.choice(EMAIL_DOMAINS)
        email = f"{email_id}@{email_domain}"

        # 가입일 생성 (최근 5년 이내)
        created_at = fake.date_time_between(start_date="-5y", end_date="now")
        
        # 마지막 접속일 (가입일 이후 ~ 현재 사이)
        # 20%의 확률로 '휴면 유저'(접속 안 함) 시뮬레이션
        if random.random() < 0.2:
             last_login_at = created_at # 가입하고 접속 안 함
             status = "DORMANT" # 휴면
        else:
             last_login_at = fake.date_time_between(start_date=created_at, end_date="now")
             status = "ACTIVE" # 활동

        return {
            "user_id": uid,
            "name": name,
            "gender": gender,
            "age": age,
            "birth_year": birth_year,
            "address": full_address,
            "address_district": city,
            "grade": grade,
            "email": email,
            "created_at": created_at.isoformat(),
            "last_login_at": last_login_at.isoformat(),
            "status": status,
            "marketing_agree": random.choice(["true", "false"]),
            "random_seed": random.random(),
            "created_datetime": datetime.now(),
            "updated_datetime": datetime.now()
        }

    def generate_batch(self, count=100):
        return [self.generate_user() for _ in range(count)]

if __name__ == "__main__":
    from pprint import pprint
    gen = UserGenerator()
    pprint(gen.generate_batch(5))