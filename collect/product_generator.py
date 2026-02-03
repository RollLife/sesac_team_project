import random
from faker import Faker
try:
    from .data_loader import REALISTIC_RULES, PREFIXES
except ImportError:
    from data_loader import REALISTIC_RULES, PREFIXES

fake = Faker('ko_KR')

class ProductGenerator:
    def __init__(self):
        self.categories = list(REALISTIC_RULES.keys())

    def generate_name(self, category):
        """카테고리에 맞는 리얼한 상품명과 브랜드 생성"""
        rule = REALISTIC_RULES.get(category)
        if not rule:
            return "알 수 없는 상품", "Unknown"
        
        # 템플릿 선택
        template = random.choice(rule['templates'])
        
        # 템플릿 채우기
        context = {}
        for key, word_list in rule['keywords'].items():
            context[key] = random.choice(word_list)
            
        name = template.format(**context)
        
        # 접두사 추가 (30%)
        if random.random() < 0.3:
            prefix = random.choice(PREFIXES)
            name = f"{prefix} {name}"
            
        return name, context.get('brand', 'Unknown')

    def generate_product(self):
        """단일 상품 데이터 생성 (DB 의존성 없음)"""
        category_name = random.choice(self.categories)
        rule = REALISTIC_RULES[category_name]
        
        name, brand = self.generate_name(category_name)
        
        price_min = rule.get('price_min', 10000)
        price_max = rule.get('price_max', 100000)
        price = random.randint(price_min, price_max)
        price = (price // 100) * 100 
        org_price = int(price * random.uniform(1.1, 1.5))
        discount_rate = (org_price - price) / org_price
        
        return {
            "product_id": f"P{fake.unique.random_number(digits=8)}",
            "name": name,
            "category": category_name,
            "price": price,
            "brand": brand,
            "stock": random.randint(0, 500),
            "description": f"{brand}의 {name}입니다. 믿고 사용하세요.",
            "created_at": fake.date_this_year(),
            "org_price": org_price,
            "discount_rate": discount_rate,
            #"sleep": random.uniform(0.5, 5.0) # 지연 시간
        }

    def generate_batch(self, count=100):
        """지정된 수량만큼 상품 리스트 생성"""
        return [self.generate_product() for _ in range(count)]


if __name__ == "__main__":
    # 디버깅을 위한 코드 (직접 실행 시 출력)
    from pprint import pprint
    print(">>> 5개의 샘플 상품 생성 테스트")
    generator = ProductGenerator()
    products = generator.generate_batch(5)
    pprint(products)

