import random
import uuid
from datetime import datetime

class OrderGenerator:
    def __init__(self):
        pass

    def generate_order(self, user, product):
        """
        user: object or dict with 'user_id', 'age'
        product: object or dict with 'product_id', 'price'
        """
        # Determine attributes safely whether input is dict or object
        u_id = user['user_id'] if isinstance(user, dict) else user.user_id
        u_age = user['age'] if isinstance(user, dict) else user.age
        
        p_id = product['product_id'] if isinstance(product, dict) else product.product_id
        p_price = product['price'] if isinstance(product, dict) else product.price

        # Step 2: Determine Quantity
        quantity = random.choices([1, 2, 3, 4, 5], weights=[80, 10, 5, 3, 2], k=1)[0]
        
        # Step 3: Payment Method Logic
        payment = random.choice(["Card", "Bank", "Pay"])
        if u_age and u_age < 30:
             payment = random.choice(["Card", "NaverPay", "KakaoPay"])
        
        return {
            "order_id": str(uuid.uuid4()),
            "created_at": datetime.now(),
            "user_id": u_id,
            "product_id": p_id,
            "quantity": quantity,
            "total_amount": p_price * quantity,
            "payment_method": payment,
            "status": "Success"
            # Category and region handling might be done in DB/Seeder layer or here if data available
            # Current logic in crud handles destructuring/denormalization
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
    
    mock_users = [{'user_id': 'u1', 'age': 25}, {'user_id': 'u2', 'age': 40}]
    mock_products = [{'product_id': 'p1', 'price': 1000}, {'product_id': 'p2', 'price': 5000}]
    
    gen = OrderGenerator()
    from pprint import pprint
    pprint(gen.generate_batch(mock_users, mock_products, 5))
