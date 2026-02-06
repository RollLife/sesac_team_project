from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from .database import Base
import uuid

class Product(Base):
    __tablename__ = "products"

    product_id = Column(String(50), primary_key=True, index=True, comment="상품 코드 (PK)")
    category = Column(String(50), nullable=False, index=True, comment="카테고리") # 분석 자주 하므로 인덱스 추가
    name = Column(String(200), nullable=False, comment="상품명")

    org_price = Column(Integer, nullable=True, comment="정가 (할인율 분석용)")
    price = Column(Integer, nullable=False, comment="단가")
    discount_rate = Column(Float, nullable=True, comment="할인율 (할인율 분석용)")
    description = Column(Text, nullable=True, comment="상품 설명")

    brand = Column(String(100), nullable=True, index=True, comment="브랜드") # 브랜드별 분석용 인덱스
    stock = Column(Integer, default=0, comment="재고")
    
    # 평점/리뷰 분석용
    rating = Column(Float, nullable=True, comment="평점")
    review_count = Column(Integer, default=0, comment="리뷰 수")
    is_best = Column(String(1), default="N", comment="베스트 상품 여부")
    
    created_at = Column(DateTime, default=datetime.now, comment="등록일")
    last_cached_at = Column(DateTime, nullable=True, index=True, comment="마지막 캐시 적재 시간 (Aging용)")
    
    created_datetime = Column(DateTime, server_default=func.now(), nullable=False, comment="실제 추가되는 시각")
    updated_datetime = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False, comment="실제 수정되는 시각")

    orders = relationship("Order", back_populates="product")

    def __repr__(self):
        return f"<Product(id={self.product_id}, name={self.name})>"

class User(Base):
    __tablename__ = "users"

    user_id = Column(String(50), primary_key=True, index=True, comment="유저 ID (PK)")
    name = Column(String(100), nullable=False, comment="이름")
    gender = Column(String(10), nullable=True, comment="성별 (M, F)")
    age = Column(Integer, nullable=True, comment="나이")
    birth_year = Column(Integer, nullable=True, comment="출생년도")

    address = Column(String(255), nullable=True, comment="전체 주소")
    address_district = Column(String(100), nullable=True, index=True, comment="주소 (구 단위)") # 지역별 분석용 인덱스

    email = Column(String(100), nullable=True, comment="이메일")
    grade = Column(String(20), nullable=True, comment="멤버십 등급")
    
    # 유저 활동 분석용
    status = Column(String(20), default="ACTIVE", comment="활동/휴면 상태")
    last_login_at = Column(DateTime, nullable=True, comment="마지막 로그인 일시")
    marketing_agree = Column(String(5), default="false", comment="마케팅 동의 여부")
    
    created_at = Column(DateTime, default=datetime.now, comment="가입일")
    last_cached_at = Column(DateTime, nullable=True, index=True, comment="마지막 캐시 적재 시간 (Aging용)")
    
    created_datetime = Column(DateTime, server_default=func.now(), nullable=False, comment="실제 추가되는 시각")
    updated_datetime = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False, comment="실제 수정되는 시각")

    orders = relationship("Order", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.user_id}, name={self.name})>"

class Order(Base):
    __tablename__ = "orders"

    # UUID는 DB에서 생성하기보다 Python에서 생성해서 넣는 게 분산 처리에 유리함
    order_id = Column(String(100), primary_key=True, index=True, comment="주문 고유 번호")
    created_at = Column(DateTime, default=datetime.now, index=True, comment="주문 발생 시간") # ⭐ 시계열 분석 필수 인덱스
    
    user_id = Column(String(50), ForeignKey("users.user_id"), nullable=False, index=True, comment="FK: 유저 ID")
    product_id = Column(String(50), ForeignKey("products.product_id"), nullable=False, index=True, comment="FK: 상품 ID")
    
    quantity = Column(Integer, nullable=False, default=1, comment="주문 수량")
    total_amount = Column(Integer, nullable=False, comment="총 결제 금액 (상품가*수량 + 배송비 - 할인)")
    shipping_cost = Column(Integer, default=0, comment="배송비 (객단가 분석용)")
    discount_amount = Column(Integer, default=0, comment="할인액 (객단가 분석용)")
    
    payment_method = Column(String(50), nullable=True, comment="결제 수단")
    status = Column(String(20), default="Success", index=True, comment="주문 상태") # 상태별 필터링용 인덱스

    # [분석용 역정규화 필드 (Snapshot)]
    category = Column(String(50), nullable=True, comment="상품 카테고리 (Snapshot)")
    user_name = Column(String(100), nullable=True, comment="유저 이름 (Snapshot)")
    user_region = Column(String(100), nullable=True, comment="유저 지역 (Snapshot)")
    user_gender = Column(String(10), nullable=True, comment="유저 성별 (Snapshot)")
    user_age_group = Column(String(20), nullable=True, comment="연령대 (Snapshot)")

    user = relationship("User", back_populates="orders")
    product = relationship("Product", back_populates="orders")

    created_datetime = Column(DateTime, server_default=func.now(), nullable=False, comment="실제 추가되는 시각")
    updated_datetime = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False, comment="실제 수정되는 시각")

    def __repr__(self):
        return f"<Order(id={self.order_id}, amount={self.total_amount})>"