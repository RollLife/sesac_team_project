import json
import os
import random
import uuid
from datetime import datetime

class OrderGenerator:
    # 한국은행 2024-2025 통계 기반 확률 매핑 (단위: %)
    PAYMENT_STATS = {
        "1020": {"methods": ["Card", "NaverPay", "KakaoPay", "Bank"], "weights": [45, 25, 20, 10]},
        "30s":  {"methods": ["Card", "NaverPay", "KakaoPay", "Bank"], "weights": [50, 20, 20, 10]},
        "40s":  {"methods": ["Card", "NaverPay", "KakaoPay", "Bank"], "weights": [65, 10, 15, 10]},
        "50plus": {"methods": ["Card", "Bank", "NaverPay", "KakaoPay"], "weights": [75, 15, 5, 5]}
    }

    # 기본 수량 설정 (카테고리 정보가 없을 때 사용)
    DEFAULT_QUANTITY = {
        "options": [1, 2, 3, 4, 5],
        "weights": [80, 10, 5, 3, 2]
    }

    def __init__(self):
        # product_rules.json에서 카테고리별 주문 규칙 로드
        self.category_rules = {}
        self._load_category_rules()

    def _load_category_rules(self):
        """product_rules.json에서 카테고리별 주문 규칙 로드"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(current_dir, 'product_rules.json')

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                categories = data.get('categories', {})

                for cat_name, cat_data in categories.items():
                    self.category_rules[cat_name] = {
                        'order_frequency': cat_data.get('order_frequency', 10),
                        'quantity_options': cat_data.get('quantity_options', self.DEFAULT_QUANTITY['options']),
                        'quantity_weights': cat_data.get('quantity_weights', self.DEFAULT_QUANTITY['weights'])
                    }
        except FileNotFoundError:
            print(f"Warning: product_rules.json not found. Using default quantity settings.")
        except json.JSONDecodeError as e:
            print(f"Warning: Failed to parse product_rules.json: {e}")

    def _get_stat_group(self, age):
        """연령에 따른 통계 그룹 반환"""
        if not age: return "40s" # 기본값
        if age < 30: return "1020"
        if age < 40: return "30s"
        if age < 50: return "40s"
        return "50plus"

    def _get_quantity(self, category):
        """카테고리에 따른 수량 결정"""
        if category and category in self.category_rules:
            rule = self.category_rules[category]
            return random.choices(
                rule['quantity_options'],
                weights=rule['quantity_weights'],
                k=1
            )[0]
        else:
            # 기본값 사용
            return random.choices(
                self.DEFAULT_QUANTITY['options'],
                weights=self.DEFAULT_QUANTITY['weights'],
                k=1
            )[0]

    def generate_order(self, user, product):
        """
        user: object or dict with 'user_id', 'name', 'age'
        product: object or dict with 'product_id', 'price', 'category'
        """
        # Determine attributes safely whether input is dict or object
        u_id = user['user_id'] if isinstance(user, dict) else user.user_id
        u_name = user['name'] if isinstance(user, dict) else user.name
        u_age = user['age'] if isinstance(user, dict) else user.age

        p_id = product['product_id'] if isinstance(product, dict) else product.product_id
        p_price = product['price'] if isinstance(product, dict) else product.price
        p_category = product.get('category') if isinstance(product, dict) else getattr(product, 'category', None)

        # Step 2: Determine Quantity (카테고리 기반)
        quantity = self._get_quantity(p_category)

        # Step 3: Payment Method Logic (통계 기반 로직으로 교체)
        group_key = self._get_stat_group(u_age)
        stat = self.PAYMENT_STATS[group_key]
        payment = random.choices(stat["methods"], weights=stat["weights"], k=1)[0]

        # Step 4: Calculate Amounts
        shipping_cost = random.choice([0, 2500, 3000])
        # Simple discount logic: maybe 0 to 10% of total price
        discount_amount = int((p_price * quantity) * random.uniform(0, 0.1))

        # Total Amount = Product Price * Quantity + Shipping - Discount
        total_amount = (p_price * quantity) + shipping_cost - discount_amount
        if total_amount < 0:
            total_amount = 0

        return {
            "order_id": str(uuid.uuid4()),
            "created_at": datetime.now(),
            "user_id": u_id,
            "user_name": u_name,
            "product_id": p_id,
            "quantity": quantity,
            "total_amount": total_amount,
            "shipping_cost": shipping_cost,
            "discount_amount": discount_amount,
            "payment_method": payment,
            "status": "Success",
            "created_datetime": datetime.now(),
            "updated_datetime": datetime.now()
        }

    def generate_batch(self, users, products, count=100):
        """
        users: list of user objects/dicts
        products: list of product objects/dicts

        카테고리별 order_frequency에 따라 상품 선택 빈도를 조정합니다.
        """
        if not users or not products:
            raise ValueError("Users and Products lists cannot be empty")

        # 상품별 가중치 계산 (카테고리의 order_frequency 기반)
        product_weights = []
        for p in products:
            category = p.get('category') if isinstance(p, dict) else getattr(p, 'category', None)
            if category and category in self.category_rules:
                weight = self.category_rules[category]['order_frequency']
            else:
                weight = 10  # 기본 가중치
            product_weights.append(weight)

        orders = []
        for _ in range(count):
            picked_user = random.choice(users)
            # 가중치 기반 상품 선택
            picked_product = random.choices(products, weights=product_weights, k=1)[0]
            orders.append(self.generate_order(picked_user, picked_product))
        return orders

if __name__ == "__main__":
    # Test logic
    print("Test Order Generation (with category-based rules)")

    mock_users = [
        {'user_id': 'u1', 'name': '홍길동', 'age': 25},
        {'user_id': 'u2', 'name': '김철수', 'age': 40}
    ]
    mock_products = [
        {'product_id': 'p1', 'price': 15000, 'category': '세제/위생'},      # 소모품: 다량 구매 가능
        {'product_id': 'p2', 'price': 2500000, 'category': '생활가전'},     # 고가: 1개만
        {'product_id': 'p3', 'price': 50000, 'category': '스킨케어'},       # 중가: 1-4개
        {'product_id': 'p4', 'price': 100000, 'category': '티켓/패스'},     # 인원수: 1-4개
    ]

    gen = OrderGenerator()
    orders = gen.generate_batch(mock_users, mock_products, 10)

    from pprint import pprint
    print("\n--- Generated Orders ---")
    for order in orders:
        product = next(p for p in mock_products if p['product_id'] == order['product_id'])
        print(f"Category: {product['category']:12} | Qty: {order['quantity']} | Total: {order['total_amount']:,}원")
