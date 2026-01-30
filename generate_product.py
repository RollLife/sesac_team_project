import pandas as pd
import random
from faker import Faker

# 1. 한국어 더미 데이터 생성기 설정
fake = Faker('ko_KR')

# 2. '재료' 준비 (이것만 좀 신경 써서 채워두면 리얼함이 확 올라감)
CATEGORIES = {
    "전자제품": {"price_min": 200000, "price_max": 3000000, "nouns": ["냉장고", "TV", "세탁기", "건조기", "노트북", "게이밍 모니터", "에어컨"]},
    "패션의류": {"price_min": 10000, "price_max": 300000, "nouns": ["티셔츠", "청바지", "패딩", "원피스", "슬랙스", "후드티", "바람막이"]},
    "식품": {"price_min": 3000, "price_max": 50000, "nouns": ["사과 5kg", "햇반 묶음", "김치 10kg", "삼겹살 600g", "생수 2L", "라면 5입"]},
    "생활용품": {"price_min": 2000, "price_max": 100000, "nouns": ["휴지 30롤", "물티슈", "샴푸", "바디워시", "수건 세트", "디퓨저"]}
}

ADJECTIVES = ["가성비", "프리미엄", "초특가", "친환경", "2024년형", "인기", "한정판", "럭셔리", "초경량", "저소음"]
BRANDS = ["삼성", "LG", "애플", "나이키", "아디다스", "쿠팡브랜드", "노브랜드", "다이소", "샤오미", "소니"]

def generate_products(num_products=1000):
    data = []
    
    print(f"📦 상품 {num_products}개 생성 시작...")
    
    for i in range(num_products):
        # 1. 카테고리 랜덤 선택
        cat_name = random.choice(list(CATEGORIES.keys()))
        cat_info = CATEGORIES[cat_name]
        
        # 2. 상품명 조합 (브랜드 + 형용사 + 명사 + 코드)
        brand = random.choice(BRANDS)
        noun = random.choice(cat_info["nouns"])
        adj = random.choice(ADJECTIVES)
        model_code = fake.bothify(text='??-####').upper() # 예: AB-1234
        
        product_name = f"{brand} {adj} {noun} ({model_code})"
        
        # 3. 가격 책정 (카테고리 범위 내에서 + 100원 단위로 끊기)
        price = random.randint(cat_info["price_min"], cat_info["price_max"])
        price = (price // 100) * 100 
        
        # 4. 데이터 적재
        row = {
            "product_id": f"P{str(i+1).zfill(6)}", # P000001
            "name": product_name,
            "category": cat_name,
            "price": price,
            "brand": brand,
            "stock": random.randint(0, 500), # 재고
            "created_at": fake.date_this_year().strftime("%Y-%m-%d") # 등록일
        }
        data.append(row)
        
        # 진행상황 표시 (너무 조용하면 답답하니까)
        if (i + 1) % (num_products // 10) == 0:
            print(f"   ... {i+1}개 생성 완료")

    return pd.DataFrame(data)

# 실행 (예: 100개만 먼저 뽑아보기)
df = generate_products(100)

# CSV로 저장 (나중에 DB에 넣을 때 이거 쓰면 됨)
df.to_csv("fake_products.csv", index=False, encoding="utf-8-sig")
print("✅ 'fake_products.csv' 저장 완료!")
print(df.head())