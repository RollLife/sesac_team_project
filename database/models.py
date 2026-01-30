from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Float, VARCHAR
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base
import uuid

class Product(Base):
    __tablename__ = "products"

    product_id = Column(String(50), primary_key=True, index=True, comment="상품 코드 (PK)")
    category = Column(String(50), nullable=False, comment="카테고리")
    name = Column(String(200), nullable=False, comment="상품명")
    price = Column(Integer, nullable=False, comment="단가")
    description = Column(Text, nullable=True, comment="상품 설명")
    
    # 추가 필드 (generate_product.py 참고)
    brand = Column(String(100), nullable=True, comment="브랜드")
    stock = Column(Integer, default=0, comment="재고")
    created_at = Column(DateTime, default=datetime.now, comment="등록일")

    # 관계 설정 (Order와 연결)
    orders = relationship("Order", back_populates="product")

class User(Base):
    __tablename__ = "users"

    user_id = Column(String(50), primary_key=True, index=True, comment="유저 ID (PK)")
    name = Column(String(100), nullable=False, comment="이름")
    gender = Column(String(10), nullable=True, comment="성별 (M, F)")
    age = Column(Integer, nullable=True, comment="나이")
    birth_year = Column(Integer, nullable=True, comment="출생년도") # script에 있음
    address = Column(String(255), nullable=True, comment="전체 주소")
    address_district = Column(String(100), nullable=True, comment="주소 (구 단위)") # 분석용
    email = Column(String(100), nullable=True, comment="이메일")
    grade = Column(String(20), nullable=True, comment="멤버십 등급")
    created_at = Column(DateTime, default=datetime.now, comment="가입일")

    # 관계 설정
    orders = relationship("Order", back_populates="user")

class Order(Base):
    __tablename__ = "orders"

    order_id = Column(String(100), primary_key=True, index=True, default=lambda: str(uuid.uuid4()), comment="주문 고유 번호 (UUID)")
    created_at = Column(DateTime, default=datetime.now, comment="주문 발생 시간")
    
    user_id = Column(String(50), ForeignKey("users.user_id"), nullable=False, comment="FK: 유저 ID")
    product_id = Column(String(50), ForeignKey("products.product_id"), nullable=False, comment="FK: 상품 ID")
    
    quantity = Column(Integer, nullable=False, default=1, comment="주문 수량")
    total_amount = Column(Integer, nullable=False, comment="총 결제 금액")
    
    # 결제/상태 정보 (generate_orders.py 참고)
    payment_method = Column(String(50), nullable=True, comment="결제 수단")
    status = Column(String(20), default="Success", comment="주문 상태")

    # [분석용 역정규화 필드] - 조인 비용 절감
    category = Column(String(50), nullable=True, comment="상품 카테고리 (Snapshot)")
    user_region = Column(String(100), nullable=True, comment="유저 지역 (Snapshot)")
    user_gender = Column(String(10), nullable=True, comment="유저 성별 (Snapshot)")
    user_age_group = Column(String(20), nullable=True, comment="연령대 (Snapshot)") # ex: 20대, 30대

    # 관계 설정
    user = relationship("User", back_populates="orders")
    product = relationship("Product", back_populates="orders")