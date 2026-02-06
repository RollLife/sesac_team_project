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

    def __init__(self):
        pass

    def _get_stat_group(self, age):
        """연령에 따른 통계 그룹 반환"""
        if not age: return "40s" # 기본값
        if age < 30: return "1020"
        if age < 40: return "30s"
        if age < 50: return "40s"
        return "50plus"

    def generate_order(self, user, product):
        """
        user: object or dict with 'user_id', 'name', 'age'
        product: object or dict with 'product_id', 'price'
        """
        # Determine attributes safely whether input is dict or object
        u_id = user['user_id'] if isinstance(user, dict) else user.user_id
        u_name = user['name'] if isinstance(user, dict) else user.name
        u_age = user['age'] if isinstance(user, dict) else user.age
        
        p_id = product['product_id'] if isinstance(product, dict) else product.product_id
        p_price = product['price'] if isinstance(product, dict) else product.price

        # Step 2: Determine Quantity
        quantity = random.choices([1, 2, 3, 4, 5], weights=[80, 10, 5, 3, 2], k=1)[0]
        
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
        """
        if not users or not products:
            raise ValueError("Users and Products lists cannot be empty")
            
        orders = []
        for _ in range(count):
            picked_user = random.choice(users)
            picked_product = random.choice(products)
            orders.append(self.generate_order(picked_user, picked_product))
        return orders

if __name__ == "__main__":
    # Test logic
    print("Test Order Generation")
    
    mock_users = [{'user_id': 'u1', 'name': '홍길동', 'age': 25}, {'user_id': 'u2', 'name': '김철수', 'age': 40}]
    mock_products = [{'product_id': 'p1', 'price': 1000}, {'product_id': 'p2', 'price': 5000}]
    
    gen = OrderGenerator()
    from pprint import pprint
    pprint(gen.generate_batch(mock_users, mock_products, 5))