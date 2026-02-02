import random
from faker import Faker
from sqlalchemy.orm import Session
from database import crud, database

# 1. 설정
fake = Faker('ko_KR')

CATEGORIES = {
    "전자제품": {"price_min": 200000, "price_max": 3000000, "nouns": ["냉장고", "TV", "세탁기", "건조기", "노트북", "게이밍 모니터", "에어컨"]},
    "패션의류": {"price_min": 10000, "price_max": 300000, "nouns": ["티셔츠", "청바지", "패딩", "원피스", "슬랙스", "후드티", "바람막이"]},
    "식품": {"price_min": 3000, "price_max": 50000, "nouns": ["사과 5kg", "햇반 묶음", "김치 10kg", "삼겹살 600g", "생수 2L", "라면 5입"]},
    "생활용품": {"price_min": 2000, "price_max": 100000, "nouns": ["휴지 30롤", "물티슈", "샴푸", "바디워시", "수건 세트", "디퓨저"]}
}

ADJECTIVES = ["가성비", "프리미엄", "초특가", "친환경", "2024년형", "인기", "한정판", "럭셔리", "초경량", "저소음"]
BRANDS = ["삼성", "LG", "애플", "나이키", "아디다스", "쿠팡브랜드", "노브랜드", "다이소", "샤오미", "소니"]

def create_random_products(db: Session, num_products=100):
    print(f"📦 상품 {num_products}개 생성 및 DB 저장 시작...")
    
    count = 0
    for i in range(num_products):
        # 1. 카테고리 랜덤 선택
        cat_name = random.choice(list(CATEGORIES.keys()))
        cat_info = CATEGORIES[cat_name]
        
        # 2. 상품명 조합
        brand = random.choice(BRANDS)
        noun = random.choice(cat_info["nouns"])
        adj = random.choice(ADJECTIVES)
        model_code = fake.bothify(text='??-####').upper()
        
        product_name = f"{brand} {adj} {noun} ({model_code})"
        
        # 3. 가격 책정
        price = random.randint(cat_info["price_min"], cat_info["price_max"])
        price = (price // 100) * 100 
        
        product_data = {
            "product_id": f"P{fake.unique.random_number(digits=8)}", # Unique ID
            "name": product_name,
            "category": cat_name,
            "price": price,
            "brand": brand,
            "stock": random.randint(0, 500),
            "description": f"{brand}의 {adj} {noun}입니다. 믿고 사용하세요.",
            "created_at": fake.date_this_year()
        }
        
        try:
            crud.create_product(db, product_data)
            count += 1
        except Exception as e:
            print(f"Failed to create product: {e}")
            db.rollback()

        if (i + 1) % 50 == 0:
            print(f"   ... {i+1}개 처리 중")
            
    print(f"✅ 총 {count}개 상품 저장 완료!")
