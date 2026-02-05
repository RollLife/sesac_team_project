import json
import os
import random
from faker import Faker

fake = Faker('ko_KR')

class ProductGenerator:
    def __init__(self):
        # 현재 실행 중인 파일(product_generator.py)의 위치를 기준으로 json 경로 찾기
        current_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(current_dir, 'product_rules.json')
        
        # JSON 파일 로드
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.rules = data['categories']
                self.common_prefixes = data['common_prefixes']
        except FileNotFoundError:
            print(f"Error: '{json_path}' 파일을 찾을 수 없습니다.")
            self.rules = {}
            self.common_prefixes = []
            
        self.categories = list(self.rules.keys())

    def generate_name(self, category):
        """카테고리에 맞는 리얼한 상품명과 브랜드 생성"""
        rule = self.rules.get(category)
        if not rule:
            return "알 수 없는 상품", "Unknown"
        
        # 템플릿 선택
        template = random.choice(rule['templates'])
        
        # 템플릿 채우기 (context 생성)
        context = {}
        for key, word_list in rule['keywords'].items():
            context[key] = random.choice(word_list)
            
        # 템플릿 포맷팅
        try:
            name = template.format(**context)
        except KeyError:
            name = template
            
        # 접두사 추가 (30% 확률) - 특정 카테고리 제외
        # 여행/티켓/스포츠 카테고리: prefix 전체 제외
        no_prefix_categories = ["항공", "숙박", "티켓/패스", "골프", "캠핑"]
        # 가전/IT: [1+1] 제외 (냉장고 1+1 등 이상함)
        limited_prefix_categories = ["생활가전", "IT/게이밍"]
        excluded_prefixes_for_limited = ["[1+1]"]
        
        if category not in no_prefix_categories and random.random() < 0.3:
            if category in limited_prefix_categories:
                valid_prefixes = [p for p in self.common_prefixes if p not in excluded_prefixes_for_limited]
            else:
                valid_prefixes = self.common_prefixes
            
            if valid_prefixes:
                prefix = random.choice(valid_prefixes)
                name = f"{prefix} {name}"
            
        return name, context.get('brand', 'Unknown')

    def generate_product(self):
        """단일 상품 데이터 생성 (비즈니스 로직 반영)"""
        if not self.categories:
            return None

        category_name = random.choice(self.categories)
        rule = self.rules[category_name]
        
        name, brand = self.generate_name(category_name)
        
        # 가격 결정 로직 (브랜드 등급 반영)
        # JSON에는 없지만 로직을 위해 코드 내에 유지
        premium_brands = ["삼성", "LG", "애플", "다이슨", "설화수", "에스티로더", "정관장", "나이키", "타이틀리스트", "신라호텔", "발뮤다", "소니"]
        brand_multiplier = random.uniform(1.3, 1.8) if brand in premium_brands else random.uniform(0.7, 1.1)

        price_min = rule.get('price_min', 10000)
        price_max = rule.get('price_max', 100000)
        
        # 기본 랜덤 가격에 브랜드 가중치 적용 및 100원 단위 절사
        raw_price = random.randint(price_min, price_max) * brand_multiplier
        price = int(max(price_min, min(raw_price, price_max * 1.5)) // 100) * 100 
        
        # 할인 로직 (40% 확률로 할인 적용)
        if random.random() < 0.4:
            org_price = int(price * random.uniform(1.1, 1.6) // 100) * 100
        else:
            org_price = price
            
        discount_rate = (org_price - price) / org_price if org_price > price else 0
        
        # 데이터의 입체감을 위한 평점 및 리뷰 데이터 시나리오
        rating = round(random.uniform(4.0, 5.0), 1) if brand in premium_brands else round(random.uniform(3.0, 4.8), 1)
        review_count = random.randint(50, 2500) if brand in premium_brands else random.randint(0, 500)

        return {
            "product_id": f"P{fake.unique.random_number(digits=8)}",
            "name": name,
            "category": category_name,
            "price": price,
            "brand": brand,
            "stock": random.randint(0, 500),
            "description": f"{brand}의 {name}입니다. {category_name} 인기 추천 상품입니다.",
            "created_at": fake.date_this_year().isoformat(),
            "org_price": org_price,
            "discount_rate": discount_rate,
            "rating": rating,
            "review_count": review_count,
            "is_best": "Y" if review_count > 1000 and rating > 4.5 else "N"
        }

    def generate_batch(self, count=100):
        """지정된 수량만큼 상품 리스트 생성"""
        return [self.generate_product() for _ in range(count)]

if __name__ == "__main__":
    from pprint import pprint
    print(">>> JSON 기반 상품 데이터 생성 테스트")
    generator = ProductGenerator()
    products = generator.generate_batch(5)
    pprint(products)