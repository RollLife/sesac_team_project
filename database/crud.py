from sqlalchemy.orm import Session
from . import models
from datetime import datetime
import uuid
import logging

# Kafka 관련 import
try:
    from kafka.config import KAFKA_ENABLED, KAFKA_TOPIC_USERS, KAFKA_TOPIC_PRODUCTS, KAFKA_TOPIC_ORDERS
    from kafka.producer import KafkaProducer as EventProducer
except ImportError:
    KAFKA_ENABLED = False
    logger = logging.getLogger(__name__)
    logger.warning("Kafka modules not available, Kafka publishing disabled")


def _publish_to_kafka(topic: str, key: str, data: dict, event_type: str):
    """Kafka 발행 헬퍼 함수"""
    if not KAFKA_ENABLED:
        return

    try:
        producer = EventProducer()
        producer.send_event(topic, key, data, event_type)
    except Exception as e:
        logging.warning(f"Kafka publish failed to {topic}: {e}")

# === Product CRUD ===
def create_product(db: Session, product_data: dict):
    db_product = models.Product(**product_data)
    db.add(db_product)
    db.commit()
    db.refresh(db_product)

    # Kafka 발행
    product_dict = {
        "product_id": db_product.product_id,
        "name": db_product.name,
        "category": db_product.category,
        "brand": db_product.brand,
        "price": db_product.price,
        "org_price": db_product.org_price,
        "discount_rate": db_product.discount_rate,
        "description": db_product.description,
        "stock": db_product.stock,
        "rating": db_product.rating,
        "review_count": db_product.review_count,
        "is_best": db_product.is_best,
        "order_count": db_product.order_count,
        "created_at": db_product.created_at,
        "created_datetime": db_product.created_datetime,
        "updated_datetime": db_product.created_datetime
    }
    _publish_to_kafka(KAFKA_TOPIC_PRODUCTS, db_product.product_id, product_dict, 'product_created')

    return db_product

def get_product(db: Session, product_id: str):
    # Select * from product where product_id == product_id
    return db.query(models.Product).filter(models.Product.product_id == product_id).first()

def get_products(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Product).offset(skip).limit(limit).all()

def update_product(db: Session, product_id: str, update_data: dict):
    db_product = get_product(db, product_id)
    if db_product:
        for key, value in update_data.items():
            setattr(db_product, key, value)
        db.commit()
        db.refresh(db_product)
    return db_product

def delete_product(db: Session, product_id: str):
    db_product = get_product(db, product_id)
    if db_product:
        db.delete(db_product)
        db.commit()
        return True
    return False

# === User CRUD ===
def create_user(db: Session, user_data: dict):
    # 가입일 처리 등 필요한 로직 추가 가능
    if "created_at" not in user_data:
        user_data["created_at"] = datetime.now()

    db_user = models.User(**user_data)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    # Kafka 발행
    user_dict = {
        "user_id": db_user.user_id,
        "name": db_user.name,
        "gender": db_user.gender,
        "age": db_user.age,
        "birth_year": db_user.birth_year,
        "address": db_user.address,
        "address_district": db_user.address_district,
        "email": db_user.email,
        "grade": db_user.grade,
        "status": db_user.status,
        "last_login_at": db_user.last_login_at,
        "marketing_agree": db_user.marketing_agree,
        "last_ordered_at": db_user.last_ordered_at,
        "random_seed": db_user.random_seed,
        "created_at": db_user.created_at,
        "created_datetime": db_user.created_datetime,
        "updated_datetime": db_user.created_datetime
    }
    _publish_to_kafka(KAFKA_TOPIC_USERS, db_user.user_id, user_dict, 'user_created')

    return db_user

def get_user(db: Session, user_id: str):
    return db.query(models.User).filter(models.User.user_id == user_id).first()

def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.User).offset(skip).limit(limit).all()

def delete_user(db: Session, user_id: str):
    db_user = get_user(db, user_id)
    if db_user:
        db.delete(db_user)
        db.commit()
        return True
    return False

# === Order CRUD & Denormalization ===
def create_order(db: Session, order_data: dict):
    # 1. user_id와 product_id로 관련 데이터 조회 (역정규화 필드 채우기 위함)
    user = get_user(db, order_data["user_id"])
    product = get_product(db, order_data["product_id"])
    
    if not user or not product:
        raise ValueError("User or Product not found")

    # 2. 역정규화 데이터 채우기
    # - category
    if "category" not in order_data:
        order_data["category"] = product.category
        
    # - user info
    if "user_region" not in order_data:
        # address에서 city 추출 (예: "서울시 강남구..." -> "서울시")
        # 단순히 user.address 앞부분을 쓰거나 user object에 region 필드가 있다면 사용
        # 여기서는 user.city(가상 필드이나 모델엔 없음) 대신 address 파싱
        order_data["user_region"] = user.address.split()[0] if user.address else "Unknown"

    if "user_gender" not in order_data:
        order_data["user_gender"] = user.gender
        
    if "user_age_group" not in order_data:
        if user.age:
            order_data["user_age_group"] = f"{user.age // 10 * 10}대"
        else:
            order_data["user_age_group"] = "Unknown"
            
    # 3. 주문 ID 생성 (UUID)
    if "order_id" not in order_data:
        order_data["order_id"] = str(uuid.uuid4())
        
    # 4. 저장
    db_order = models.Order(**order_data)
    db.add(db_order)
    db.commit()
    db.refresh(db_order)

    # 5. Kafka 발행
    order_dict = {
        "order_id": db_order.order_id,
        "created_at": db_order.created_at,
        "user_id": db_order.user_id,
        "product_id": db_order.product_id,
        "quantity": db_order.quantity,
        "total_amount": db_order.total_amount,
        "shipping_cost": db_order.shipping_cost,
        "discount_amount": db_order.discount_amount,
        "payment_method": db_order.payment_method,
        "status": db_order.status,
        "category": db_order.category,
        "user_region": db_order.user_region,
        "user_gender": db_order.user_gender,
        "user_age_group": db_order.user_age_group,
        "created_datetime": db_order.created_datetime,
        "updated_datetime": db_order.created_datetime
    }
    _publish_to_kafka(KAFKA_TOPIC_ORDERS, db_order.user_id, order_dict, 'order_created')

    return db_order
    
def get_order(db: Session, order_id: str):
    return db.query(models.Order).filter(models.Order.order_id == order_id).first()
