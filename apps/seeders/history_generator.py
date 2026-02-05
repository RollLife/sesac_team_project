#!/usr/bin/env python3
"""
history_generator.py
====================
쇼핑몰 1년치 히스토리 데이터 생성기 (독립 실행형)

- SQLite 파일 DB에 고객 50,000 / 상품 10,000 / 주문 1,000,000건 생성
- 프로젝트 내 다른 모듈(database/, kafka/, cache/) 의존성 0
- 성장 곡선 + 시즌 패턴 + 고객-상품 연관성 반영

실행: python apps/seeders/history_generator.py
"""

import os
import sys
import io
import random
import uuid
import math
import time
from datetime import datetime, timedelta
from collections import defaultdict

# Windows 콘솔 UTF-8 출력 보장
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from faker import Faker
from sqlalchemy import (
    create_engine, Column, String, Integer, Float, Text, DateTime,
    ForeignKey, event,
)
from sqlalchemy.orm import declarative_base, sessionmaker

# ════════════════════════════════════════════════════════════════
# Configuration
# ════════════════════════════════════════════════════════════════
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, "history_data.db")
DB_URL = f"sqlite:///{DB_PATH}"

START_DATE = datetime(2025, 2, 1)
END_DATE = datetime(2026, 2, 1)

TOTAL_USERS = 50_000
TOTAL_PRODUCTS = 10_000
TOTAL_ORDERS = 1_000_000

BATCH_SIZE = 10_000
GROWTH_RATE = 0.2  # 지수 성장률 (월별)

fake = Faker("ko_KR")
Base = declarative_base()


# ════════════════════════════════════════════════════════════════
# SQLAlchemy Models (database/models.py 스키마 미러링, SQLite용)
# ════════════════════════════════════════════════════════════════
class Product(Base):
    __tablename__ = "products"
    product_id = Column(String(50), primary_key=True, index=True)
    category = Column(String(50), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    org_price = Column(Integer, nullable=True)
    price = Column(Integer, nullable=False)
    discount_rate = Column(Float, nullable=True)
    description = Column(Text, nullable=True)
    brand = Column(String(100), nullable=True, index=True)
    stock = Column(Integer, nullable=False, default=0)
    rating = Column(Float, nullable=True)
    review_count = Column(Integer, nullable=False, default=0)
    is_best = Column(String(1), nullable=False, default="N")
    created_at = Column(DateTime, nullable=False)
    last_cached_at = Column(DateTime, nullable=True)


class User(Base):
    __tablename__ = "users"
    user_id = Column(String(50), primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    gender = Column(String(10), nullable=True)
    age = Column(Integer, nullable=True)
    birth_year = Column(Integer, nullable=True)
    address = Column(String(255), nullable=True)
    address_district = Column(String(100), nullable=True, index=True)
    email = Column(String(100), nullable=True)
    grade = Column(String(20), nullable=True)
    status = Column(String(20), nullable=False, default="ACTIVE")
    last_login_at = Column(DateTime, nullable=True)
    marketing_agree = Column(String(5), nullable=False, default="false")
    created_at = Column(DateTime, nullable=False)
    last_cached_at = Column(DateTime, nullable=True)


class Order(Base):
    __tablename__ = "orders"
    order_id = Column(String(100), primary_key=True, index=True)
    created_at = Column(DateTime, nullable=False, index=True)
    user_id = Column(String(50), ForeignKey("users.user_id"), nullable=False, index=True)
    product_id = Column(String(50), ForeignKey("products.product_id"), nullable=False, index=True)
    quantity = Column(Integer, nullable=False, default=1)
    total_amount = Column(Integer, nullable=False)
    shipping_cost = Column(Integer, nullable=False, default=0)
    discount_amount = Column(Integer, nullable=False, default=0)
    payment_method = Column(String(50), nullable=True)
    status = Column(String(20), nullable=False, default="Success", index=True)
    category = Column(String(50), nullable=True)
    user_name = Column(String(100), nullable=True)
    user_region = Column(String(100), nullable=True)
    user_gender = Column(String(10), nullable=True)
    user_age_group = Column(String(20), nullable=True)


# ════════════════════════════════════════════════════════════════
# 상품 규칙 데이터 (product_rules.json 내장)
# ════════════════════════════════════════════════════════════════
COMMON_PREFIXES = [
    "[단독구성]", "[방송최저가]", "[본사직영]", "[1+1]", "[체험분증정]",
    "[MD픽]", "[한정수량]", "[쿠폰가]", "[로켓배송]", "[역대급혜택]", "[오늘만특가]",
]

PRODUCT_RULES = {
    "패션_SS(봄여름)": {
        "price_min": 15000, "price_max": 150000,
        "templates": ["{brand} {season} {adj} {noun} {color}", "{brand} {material} {noun} 1+1 특가"],
        "keywords": {
            "brand": ["나이키", "아디다스", "폴로", "지오다노", "탑텐", "스파오", "파타고니아"],
            "season": ["25SS", "여름 신상", "봄 신상"],
            "adj": ["링클프리", "와이드핏", "쿨링", "초경량", "통기성좋은"],
            "noun": ["반팔티", "린넨셔츠", "조거팬츠", "반바지", "원피스", "슬랙스"],
            "material": ["린넨", "매쉬", "수피마코튼", "시어서커"],
            "color": ["화이트", "스카이블루", "베이지", "네이비"],
        },
    },
    "패션_FW(가을겨울)": {
        "price_min": 30000, "price_max": 800000,
        "templates": ["{brand} {season} {adj} {noun} {color}", "{brand} {material} {noun} 한정수량"],
        "keywords": {
            "brand": ["노스페이스", "나이키", "디스커버리", "내셔널지오그래픽", "몽클레어"],
            "season": ["25FW", "겨울 신상", "가을 신상"],
            "adj": ["헤비", "경량", "방풍", "발열", "기모안감"],
            "noun": ["롱패딩", "숏패딩", "후리스", "맨투맨", "코트", "니트"],
            "material": ["구스다운", "캐시미어", "울 100%", "플리스"],
            "color": ["블랙", "차콜", "그레이", "카키"],
        },
    },
    "뷰티_스킨케어": {
        "price_min": 10000, "price_max": 150000,
        "templates": ["{brand} {adj} {noun} {volume}", "{brand} {line} {noun} 1+1 기획"],
        "keywords": {
            "brand": ["이니스프리", "닥터지", "라운드랩", "토리든", "아누아", "피지오겔"],
            "line": ["그린티", "시카", "자작나무", "히알루론"],
            "adj": ["진정", "순한", "저자극", "수분가득", "쿨링"],
            "noun": ["토너", "로션", "수분크림", "클렌징폼", "마스크팩", "선크림"],
            "volume": ["300ml", "500ml", "대용량", "1+1"],
        },
    },
    "뷰티_기능성(안티에이징)": {
        "price_min": 50000, "price_max": 500000,
        "templates": ["{brand} {line} {adj} {noun} {volume}", "{brand} {ingredient} {noun} 세트"],
        "keywords": {
            "brand": ["설화수", "헤라", "에스티로더", "아이오페", "SK2", "랑콤"],
            "line": ["자음", "갈색병", "슈퍼바이탈", "피테라"],
            "ingredient": ["레티놀", "콜라겐", "펩타이드", "PDRN"],
            "noun": ["에센스", "앰플", "아이크림", "영양크림", "리프팅크림"],
            "adj": ["주름개선", "미백", "고영양", "탄력", "안티에이징"],
            "volume": ["30ml", "50ml", "세트"],
        },
    },
    "식품_신선(과일/채소)": {
        "price_min": 10000, "price_max": 80000,
        "templates": ["{location} {adj} {noun} {weight}", "[산지직송] {location} {noun} {weight}"],
        "keywords": {
            "location": ["성주", "나주", "제주", "청송", "영주", "논산"],
            "adj": ["고당도", "꿀", "GAP인증", "프리미엄", "새벽수확"],
            "noun": ["참외", "사과", "배", "딸기", "샤인머스캣", "감귤", "고구마"],
            "weight": ["2kg", "3kg", "5kg", "10kg"],
        },
    },
    "식품_육류/가공": {
        "price_min": 20000, "price_max": 200000,
        "templates": ["{brand} {adj} {noun} {weight}", "{grade} {location} {noun} 선물세트"],
        "keywords": {
            "brand": ["하림", "도드람", "농협안심", "횡성축협", "비비고"],
            "location": ["횡성", "이천", "제주"],
            "adj": ["숙성", "무항생제", "HACCP인증", "냉장"],
            "noun": ["삼겹살", "목살", "한우 등심", "닭가슴살", "양념갈비"],
            "grade": ["1++등급", "1등급", "프리미엄"],
            "weight": ["500g", "1kg", "600g x 3팩"],
        },
    },
    "가전_생활(백색가전)": {
        "price_min": 500000, "price_max": 5000000,
        "templates": ["{brand} {year}년형 {adj} {noun} {suffix}", "{brand} {spec} {noun}"],
        "keywords": {
            "brand": ["삼성", "LG", "발뮤다", "다이슨", "쿠쿠", "로보락"],
            "noun": ["냉장고", "세탁기", "건조기", "식기세척기", "로봇청소기", "공기청정기"],
            "spec": ["1등급", "대용량", "AI기능"],
            "adj": ["비스포크", "오브제", "스팀", "저소음"],
            "year": ["2025", "2026"],
            "suffix": ["방문설치", "폐가전수거", "무상AS 3년"],
        },
    },
    "가전_IT/게이밍": {
        "price_min": 100000, "price_max": 3000000,
        "templates": ["{brand} {spec} {noun} {model}", "{brand} {adj} {noun} ({refresh_rate})"],
        "keywords": {
            "brand": ["삼성", "LG", "애플", "로지텍", "ASUS", "MSI"],
            "noun": ["노트북", "게이밍 모니터", "기계식 키보드", "마우스", "태블릿"],
            "spec": ["RTX4060", "i9-14세대", "M3칩", "32GB RAM"],
            "adj": ["초경량", "고성능", "커브드", "무선"],
            "refresh_rate": ["144Hz", "240Hz", "4K", "OLED"],
            "model": ["그램", "맥북에어", "오디세이"],
        },
    },
    "생활_세제/위생": {
        "price_min": 5000, "price_max": 50000,
        "templates": ["{brand} {adj} {noun} {capacity} x {count}개", "{brand} {noun} 리필 대용량"],
        "keywords": {
            "brand": ["다우니", "퍼실", "피죤", "유한락스", "페브리즈"],
            "adj": ["실내건조", "초고농축", "향기좋은", "강력세척"],
            "noun": ["세탁세제", "섬유유연제", "주방세제", "세정제", "물티슈"],
            "capacity": ["2.5L", "3L", "1L"],
            "count": ["3", "4", "6"],
        },
    },
    "생활_화지/제지": {
        "price_min": 10000, "price_max": 40000,
        "templates": ["{brand} {adj} {noun} {spec} {count}롤", "{brand} {noun} {count}롤 x 2팩"],
        "keywords": {
            "brand": ["크리넥스", "코디", "깨끗한나라", "잘풀리는집"],
            "adj": ["도톰한", "순수천연펄프", "무형광"],
            "noun": ["두루마리 휴지", "키친타올", "미용티슈"],
            "spec": ["3겹", "4겹"],
            "count": ["30", "24", "12"],
        },
    },
    "건강식품_전통": {
        "price_min": 30000, "price_max": 500000,
        "templates": ["{brand} {process} {ingredient} {noun} {amount}", "[효도선물] {brand} {ingredient} {noun}"],
        "keywords": {
            "brand": ["정관장", "한삼인", "농협", "종근당건강", "광동"],
            "ingredient": ["홍삼", "녹용", "침향", "흑마늘", "도라지배즙"],
            "noun": ["진액", "환", "스틱", "골드"],
            "process": ["3단계 발효", "전통방식", "구증구포", "저온추출"],
            "amount": ["30포", "60포", "100포"],
        },
    },
    "건강식품_영양제": {
        "price_min": 15000, "price_max": 150000,
        "templates": ["{brand} {adj} {ingredient} {noun}", "{brand} {ingredient} {noun} {amount} 1+1"],
        "keywords": {
            "brand": ["고려은단", "뉴트리원", "덴프스", "에스더포뮬러", "종근당"],
            "ingredient": ["루테인", "오메가3", "비타민D", "저분자 콜라겐", "유산균", "밀크씨슬"],
            "noun": ["캡슐", "정", "구미", "타블렛"],
            "adj": ["고함량", "식물성", "흡수율 높은"],
            "amount": ["3개월분", "6개월분", "180정"],
        },
    },
    "가구_대형(소파/침대)": {
        "price_min": 300000, "price_max": 3000000,
        "templates": ["{brand} {material} {noun} {size}", "{brand} {adj} {noun} 풀세트"],
        "keywords": {
            "brand": ["한샘", "리바트", "까사미아", "에이스침대", "시몬스"],
            "material": ["이태리 천연가죽", "원목", "세라믹"],
            "noun": ["소파", "침대 프레임", "식탁", "매트리스"],
            "adj": ["푹신한", "호텔식", "모듈형", "리클라이너"],
            "size": ["4인용", "킹사이즈", "퀸사이즈"],
        },
    },
    "가구_사무/학생": {
        "price_min": 50000, "price_max": 500000,
        "templates": ["{brand} {adj} {noun} ({model})", "{brand} {noun} + {opt} 세트"],
        "keywords": {
            "brand": ["시디즈", "데스커", "일룸", "듀오백"],
            "noun": ["메쉬 의자", "컴퓨터 책상", "독서실 책상", "책장"],
            "adj": ["인체공학적", "높이조절", "허리가 편한"],
            "model": ["T50", "T80"],
            "opt": ["LED조명", "멀티탭"],
        },
    },
    "스포츠_골프": {
        "price_min": 50000, "price_max": 1500000,
        "templates": ["{brand} {year} {spec} {noun}", "{brand} {adj} {noun} 풀세트"],
        "keywords": {
            "brand": ["타이틀리스트", "테일러메이드", "핑", "캘러웨이", "PXG"],
            "noun": ["드라이버", "아이언 세트", "퍼터", "캐디백", "골프화"],
            "spec": ["카본 페이스", "단조", "보아 시스템"],
            "adj": ["비거리 향상", "관용성 좋은", "초경량"],
            "year": ["2025", "2026"],
        },
    },
    "스포츠_캠핑": {
        "price_min": 20000, "price_max": 2000000,
        "templates": ["{brand} {adj} {noun} {size}", "[감성캠핑] {brand} {noun} ({color})"],
        "keywords": {
            "brand": ["스노우피크", "콜맨", "코베아", "헬리녹스", "노르디스크"],
            "noun": ["리빙쉘 텐트", "타프", "캠핑의자", "야전침대", "랜턴", "화로대"],
            "adj": ["원터치", "방수", "초경량", "감성"],
            "size": ["4인용", "대형", "패밀리사이즈"],
            "color": ["카키", "탄", "아이보리"],
        },
    },
    "여행_항공/숙박": {
        "price_min": 50000, "price_max": 2000000,
        "templates": ["[항공권] {location} {adj} 왕복 ({airline})", "{location} {hotel} {room} {count}박"],
        "keywords": {
            "location": ["제주", "오사카", "다낭", "방콕", "후쿠오카"],
            "airline": ["대한항공", "제주항공", "티웨이", "진에어"],
            "hotel": ["신라호텔", "하얏트", "롯데호텔", "풀빌라"],
            "room": ["오션뷰", "스위트룸", "디럭스룸"],
            "adj": ["직항", "특가", "얼리버드"],
            "count": ["1", "2", "3"],
        },
    },
    "여행_티켓/패스": {
        "price_min": 10000, "price_max": 100000,
        "templates": ["[입장권] {location} {activity} {people}인권", "{location} {activity} 자유이용권"],
        "keywords": {
            "location": ["제주", "서울", "부산", "용인"],
            "activity": ["아쿠아리움", "테마파크", "워터파크", "사파리"],
            "people": ["1", "2"],
        },
    },
}

CATEGORIES = list(PRODUCT_RULES.keys())

# 프리미엄 브랜드 (가격 프리미엄 + 높은 평점)
PREMIUM_BRANDS = {
    "삼성", "LG", "애플", "다이슨", "발뮤다", "설화수", "에스티로더", "SK2", "랑콤",
    "나이키", "몽클레어", "정관장", "타이틀리스트", "PXG", "스노우피크", "노르디스크",
    "에이스침대", "시몬스", "MSI",
}

# 카테고리별 상품 수 가중치 (패션/뷰티 많고, 가구/여행 적음)
CATEGORY_PRODUCT_WEIGHTS = {
    "패션_SS(봄여름)": 1.2, "패션_FW(가을겨울)": 1.2,
    "뷰티_스킨케어": 1.0, "뷰티_기능성(안티에이징)": 0.7,
    "식품_신선(과일/채소)": 1.0, "식품_육류/가공": 0.8,
    "가전_생활(백색가전)": 0.5, "가전_IT/게이밍": 0.7,
    "생활_세제/위생": 0.8, "생활_화지/제지": 0.5,
    "건강식품_전통": 0.6, "건강식품_영양제": 0.7,
    "가구_대형(소파/침대)": 0.4, "가구_사무/학생": 0.5,
    "스포츠_골프": 0.5, "스포츠_캠핑": 0.5,
    "여행_항공/숙박": 0.4, "여행_티켓/패스": 0.4,
}


# ════════════════════════════════════════════════════════════════
# 인구통계 상수
# ════════════════════════════════════════════════════════════════
CITIES = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "경기", "강원", "충청", "전라", "경상", "제주"]
CITY_WEIGHTS = [18, 7, 5, 6, 3, 3, 2, 25, 3, 10, 8, 8, 2]
EMAIL_DOMAINS = ["naver.com", "gmail.com", "daum.net", "kakao.com", "icloud.com"]
GRADES = ["BRONZE", "SILVER", "GOLD", "VIP"]
GRADE_WEIGHTS = [60, 25, 10, 5]

# 결제수단 (연령대별, 한국은행 2024-2025 통계 기반)
PAYMENT_STATS = {
    "10대": {"methods": ["Card", "NaverPay", "KakaoPay", "Bank"], "weights": [45, 25, 20, 10]},
    "20대": {"methods": ["Card", "NaverPay", "KakaoPay", "Bank"], "weights": [45, 25, 20, 10]},
    "30대": {"methods": ["Card", "NaverPay", "KakaoPay", "Bank"], "weights": [50, 20, 20, 10]},
    "40대": {"methods": ["Card", "NaverPay", "KakaoPay", "Bank"], "weights": [65, 10, 15, 10]},
    "50대": {"methods": ["Card", "Bank", "NaverPay", "KakaoPay"], "weights": [75, 15, 5, 5]},
    "60대": {"methods": ["Card", "Bank", "NaverPay", "KakaoPay"], "weights": [75, 15, 5, 5]},
}


# ════════════════════════════════════════════════════════════════
# 시즌/이벤트 엔진
# ════════════════════════════════════════════════════════════════
# (이름, 시작일, 종료일, 전체 주문량 배수, 카테고리별 부스트)
SEASONAL_EVENTS = [
    ("설날", datetime(2026, 1, 26), datetime(2026, 2, 1), 1.8, {
        "식품_신선(과일/채소)": 2.0, "식품_육류/가공": 2.0,
        "건강식품_전통": 2.5, "건강식품_영양제": 1.5, "여행_항공/숙박": 1.8,
    }),
    ("발렌타인", datetime(2025, 2, 10), datetime(2025, 2, 15), 1.3, {
        "뷰티_스킨케어": 1.5, "뷰티_기능성(안티에이징)": 1.5, "식품_신선(과일/채소)": 1.3,
    }),
    ("화이트데이", datetime(2025, 3, 10), datetime(2025, 3, 15), 1.3, {
        "뷰티_스킨케어": 1.5, "뷰티_기능성(안티에이징)": 1.5,
    }),
    ("봄시즌", datetime(2025, 3, 15), datetime(2025, 5, 31), 1.15, {
        "패션_SS(봄여름)": 2.0, "스포츠_캠핑": 1.5, "스포츠_골프": 1.3,
    }),
    ("어린이날", datetime(2025, 5, 1), datetime(2025, 5, 6), 1.3, {
        "여행_티켓/패스": 2.0, "여행_항공/숙박": 1.5,
    }),
    ("여름세일", datetime(2025, 7, 1), datetime(2025, 8, 31), 1.3, {
        "패션_SS(봄여름)": 1.8, "가전_생활(백색가전)": 1.5, "가전_IT/게이밍": 1.3,
        "여행_항공/숙박": 1.8, "여행_티켓/패스": 1.5,
    }),
    ("추석", datetime(2025, 10, 3), datetime(2025, 10, 8), 1.8, {
        "식품_신선(과일/채소)": 2.5, "식품_육류/가공": 2.5,
        "건강식품_전통": 2.5, "건강식품_영양제": 1.5, "여행_항공/숙박": 2.0,
    }),
    ("가을시즌", datetime(2025, 9, 1), datetime(2025, 11, 15), 1.1, {
        "패션_FW(가을겨울)": 2.0, "스포츠_캠핑": 1.3,
    }),
    ("블랙프라이데이", datetime(2025, 11, 21), datetime(2025, 12, 2), 2.0, {
        "가전_생활(백색가전)": 2.5, "가전_IT/게이밍": 2.5,
        "패션_FW(가을겨울)": 2.0, "뷰티_기능성(안티에이징)": 1.8,
    }),
    ("크리스마스", datetime(2025, 12, 15), datetime(2025, 12, 31), 1.5, {
        "뷰티_기능성(안티에이징)": 2.0, "뷰티_스킨케어": 1.5,
        "가전_IT/게이밍": 1.8, "여행_항공/숙박": 1.5, "패션_FW(가을겨울)": 1.5,
    }),
    ("새해", datetime(2026, 1, 1), datetime(2026, 1, 5), 1.3, {
        "건강식품_영양제": 1.8, "건강식품_전통": 1.5,
        "스포츠_골프": 1.3, "스포츠_캠핑": 1.2,
    }),
]

# 시간대별 주문 가중치 (0~23시)
HOURLY_WEIGHTS = [
    2, 1, 1, 1, 1, 1,   # 00-05: 심야
    2, 3, 3, 5, 5, 5,   # 06-11: 아침~오전
    8, 7, 5, 5, 5, 6,   # 12-17: 점심~오후
    6, 8, 10, 10, 8, 4,  # 18-23: 저녁 피크
]

# 요일별 배수 (월=0 ~ 일=6)
WEEKDAY_MULTIPLIERS = [1.0, 1.0, 1.0, 1.0, 1.0, 1.2, 1.15]


# ════════════════════════════════════════════════════════════════
# 고객-상품 연관성 엔진
# ════════════════════════════════════════════════════════════════
# 성별 × 카테고리 기본 선호도
GENDER_CATEGORY_PREFS = {
    "F": {
        "뷰티_스킨케어": 0.14, "뷰티_기능성(안티에이징)": 0.11,
        "패션_SS(봄여름)": 0.10, "패션_FW(가을겨울)": 0.10,
        "식품_신선(과일/채소)": 0.08, "식품_육류/가공": 0.04,
        "건강식품_영양제": 0.07, "건강식품_전통": 0.04,
        "생활_세제/위생": 0.08, "생활_화지/제지": 0.06,
        "가전_생활(백색가전)": 0.04, "가전_IT/게이밍": 0.02,
        "가구_대형(소파/침대)": 0.03, "가구_사무/학생": 0.02,
        "스포츠_골프": 0.01, "스포츠_캠핑": 0.02,
        "여행_항공/숙박": 0.02, "여행_티켓/패스": 0.02,
    },
    "M": {
        "가전_IT/게이밍": 0.12, "가전_생활(백색가전)": 0.06,
        "스포츠_골프": 0.08, "스포츠_캠핑": 0.07,
        "패션_SS(봄여름)": 0.08, "패션_FW(가을겨울)": 0.08,
        "식품_신선(과일/채소)": 0.05, "식품_육류/가공": 0.08,
        "건강식품_영양제": 0.05, "건강식품_전통": 0.05,
        "생활_세제/위생": 0.04, "생활_화지/제지": 0.03,
        "뷰티_스킨케어": 0.04, "뷰티_기능성(안티에이징)": 0.02,
        "가구_대형(소파/침대)": 0.04, "가구_사무/학생": 0.04,
        "여행_항공/숙박": 0.04, "여행_티켓/패스": 0.03,
    },
}

# 연령대 × 카테고리 보정 계수 (1.0 = 기본, >1.0 = 선호)
AGE_CATEGORY_BOOST = {
    "20대": {
        "패션_SS(봄여름)": 1.5, "패션_FW(가을겨울)": 1.5,
        "뷰티_스킨케어": 1.4, "뷰티_기능성(안티에이징)": 0.5,
        "가전_IT/게이밍": 1.3, "여행_항공/숙박": 1.2, "여행_티켓/패스": 1.3,
    },
    "30대": {
        "식품_신선(과일/채소)": 1.3, "식품_육류/가공": 1.2,
        "생활_세제/위생": 1.4, "생활_화지/제지": 1.3,
        "가구_대형(소파/침대)": 1.3, "가구_사무/학생": 1.2,
        "가전_생활(백색가전)": 1.2,
    },
    "40대": {
        "건강식품_전통": 1.4, "건강식품_영양제": 1.3,
        "가전_생활(백색가전)": 1.2, "가전_IT/게이밍": 1.1,
        "가구_대형(소파/침대)": 1.2, "스포츠_골프": 1.5,
    },
    "50대": {
        "건강식품_전통": 1.6, "건강식품_영양제": 1.4,
        "식품_신선(과일/채소)": 1.3, "식품_육류/가공": 1.2,
        "여행_항공/숙박": 1.3, "가전_생활(백색가전)": 1.2, "스포츠_골프": 1.4,
    },
    "60대": {
        "건강식품_전통": 1.8, "건강식품_영양제": 1.5,
        "식품_신선(과일/채소)": 1.4, "여행_항공/숙박": 1.3,
    },
}

# 장바구니 연관 구매 (카테고리 → [(연관 카테고리, 동시구매 확률)])
BASKET_CORRELATIONS = {
    "뷰티_스킨케어": [("뷰티_기능성(안티에이징)", 0.35)],
    "뷰티_기능성(안티에이징)": [("뷰티_스킨케어", 0.30)],
    "패션_SS(봄여름)": [("스포츠_캠핑", 0.20), ("스포츠_골프", 0.10)],
    "패션_FW(가을겨울)": [("스포츠_캠핑", 0.15)],
    "식품_신선(과일/채소)": [("식품_육류/가공", 0.40)],
    "식품_육류/가공": [("식품_신선(과일/채소)", 0.35)],
    "가전_생활(백색가전)": [("생활_세제/위생", 0.25)],
    "가구_대형(소파/침대)": [("가구_사무/학생", 0.30)],
    "가구_사무/학생": [("가구_대형(소파/침대)", 0.20)],
    "건강식품_전통": [("건강식품_영양제", 0.30)],
    "건강식품_영양제": [("건강식품_전통", 0.25)],
    "여행_항공/숙박": [("여행_티켓/패스", 0.45)],
    "여행_티켓/패스": [("여행_항공/숙박", 0.30)],
}


# ════════════════════════════════════════════════════════════════
# 성장 곡선 엔진
# ════════════════════════════════════════════════════════════════
def compute_monthly_growth(num_months=12):
    """지수 성장 곡선: 초기 소규모 -> 후반 대규모"""
    raw = [math.exp(GROWTH_RATE * i) for i in range(num_months)]
    total = sum(raw)
    return [w / total for w in raw]


def distribute_to_months(total_count, monthly_growth):
    """total_count를 월별 성장 비율로 분배 (합계 정확히 total_count)"""
    counts = [int(total_count * w) for w in monthly_growth]
    remainder = total_count - sum(counts)
    fracs = [(total_count * monthly_growth[i]) % 1 for i in range(len(monthly_growth))]
    for idx in sorted(range(len(fracs)), key=lambda i: fracs[i], reverse=True)[:remainder]:
        counts[idx] += 1
    return counts


def days_in_month(year, month):
    """해당 월의 일수 반환"""
    if month == 12:
        return (datetime(year + 1, 1, 1) - datetime(year, 12, 1)).days
    return (datetime(year, month + 1, 1) - datetime(year, month, 1)).days


# ════════════════════════════════════════════════════════════════
# 시즌/이벤트 함수
# ════════════════════════════════════════════════════════════════
def get_seasonal_multiplier(date):
    """해당 날짜의 시즌 이벤트 기반 주문량 배수 (최대 3.0)"""
    mult = 1.0
    for _, start, end, m, _ in SEASONAL_EVENTS:
        if start <= date <= end:
            mult *= m
    return min(mult, 3.0)


def get_category_boost(date, category):
    """해당 날짜/카테고리의 시즌 부스트 (최대 4.0)"""
    boost = 1.0
    for _, start, end, _, cat_boosts in SEASONAL_EVENTS:
        if start <= date <= end:
            boost *= cat_boosts.get(category, 1.0)
    return min(boost, 4.0)


# ════════════════════════════════════════════════════════════════
# 연관성 엔진
# ════════════════════════════════════════════════════════════════
def get_age_group(age):
    if age is None:
        return "30대"
    decade = (age // 10) * 10
    return f"{decade}대"


def compute_category_weights(gender, age_group, date, available_categories):
    """성별 × 연령 × 시즌 반영한 카테고리 가중치 계산"""
    base = GENDER_CATEGORY_PREFS.get(gender, GENDER_CATEGORY_PREFS["M"])
    age_boost = AGE_CATEGORY_BOOST.get(age_group, {})

    weights = []
    for cat in available_categories:
        w = base.get(cat, 0.03)
        w *= age_boost.get(cat, 1.0)
        w *= get_category_boost(date, cat)
        weights.append(max(w, 0.001))

    return weights


# ════════════════════════════════════════════════════════════════
# 상품 생성
# ════════════════════════════════════════════════════════════════
def generate_product_name(category):
    """카테고리 규칙 기반 상품명 + 브랜드 생성"""
    rule = PRODUCT_RULES[category]
    template = random.choice(rule["templates"])

    context = {}
    for key, words in rule["keywords"].items():
        context[key] = random.choice(words)

    try:
        name = template.format(**context)
    except KeyError:
        name = template

    if random.random() < 0.3:
        name = f"{random.choice(COMMON_PREFIXES)} {name}"

    brand = context.get("brand", "Unknown")
    return name, brand


def generate_products(monthly_growth):
    """상품 10,000건 생성 (월별 성장 곡선 + 카테고리 분포)"""
    products = []
    monthly_counts = distribute_to_months(TOTAL_PRODUCTS, monthly_growth)

    # 카테고리 가중치 리스트
    cat_list = list(CATEGORY_PRODUCT_WEIGHTS.keys())
    cat_w = [CATEGORY_PRODUCT_WEIGHTS[c] for c in cat_list]

    pid_counter = 0
    for month_idx, month_count in enumerate(monthly_counts):
        month_date = START_DATE + timedelta(days=30 * month_idx)
        y, m = month_date.year, month_date.month
        dim = days_in_month(y, m)

        for _ in range(month_count):
            category = random.choices(cat_list, weights=cat_w, k=1)[0]
            name, brand = generate_product_name(category)
            rule = PRODUCT_RULES[category]
            is_premium = brand in PREMIUM_BRANDS
            brand_mult = random.uniform(1.3, 1.8) if is_premium else random.uniform(0.7, 1.1)

            raw_price = random.randint(rule["price_min"], rule["price_max"]) * brand_mult
            price = int(max(rule["price_min"], min(raw_price, rule["price_max"] * 1.5)) // 100) * 100

            if random.random() < 0.4:
                org_price = int(price * random.uniform(1.1, 1.6) // 100) * 100
            else:
                org_price = price
            discount_rate = round((org_price - price) / org_price, 2) if org_price > price else 0.0

            rating = round(random.uniform(4.0, 5.0), 1) if is_premium else round(random.uniform(3.0, 4.8), 1)
            review_count = random.randint(50, 2500) if is_premium else random.randint(0, 500)

            created_at = datetime(y, m, 1) + timedelta(
                days=random.randint(0, dim - 1),
                hours=random.randint(9, 18),
                minutes=random.randint(0, 59),
            )
            if created_at >= END_DATE:
                created_at = END_DATE - timedelta(hours=random.randint(1, 24))

            pid_counter += 1
            products.append({
                "product_id": f"P{pid_counter:08d}",
                "category": category,
                "name": name,
                "org_price": org_price,
                "price": price,
                "discount_rate": discount_rate,
                "description": f"{brand} {category} best item",
                "brand": brand,
                "stock": random.randint(10, 500),
                "rating": rating,
                "review_count": review_count,
                "is_best": "Y" if review_count > 1000 and rating > 4.5 else "N",
                "created_at": created_at,
            })

    products.sort(key=lambda p: p["created_at"])
    return products


# ════════════════════════════════════════════════════════════════
# 유저 생성
# ════════════════════════════════════════════════════════════════
def generate_users(monthly_growth):
    """유저 50,000명 생성 (월별 성장 곡선 + 인구통계 분포)"""
    users = []
    uid_counter = 0
    monthly_counts = distribute_to_months(TOTAL_USERS, monthly_growth)

    for month_idx, month_count in enumerate(monthly_counts):
        month_date = START_DATE + timedelta(days=30 * month_idx)

        for _ in range(month_count):
            gender = random.choice(["M", "F"])
            age = random.choices(
                [random.randint(20, 29), random.randint(30, 39),
                 random.randint(40, 49), random.randint(50, 65)],
                weights=[30, 30, 25, 15], k=1,
            )[0]
            birth_year = 2025 - age

            city = random.choices(CITIES, weights=CITY_WEIGHTS, k=1)[0]
            address = f"{city} {fake.street_address()}"
            email = f"{fake.user_name()}@{random.choice(EMAIL_DOMAINS)}"

            # 등급: 초기 가입자 → 높은 등급 확률 증가 (오래된 고객)
            months_active = 12 - month_idx
            if months_active >= 9:
                grade = random.choices(GRADES, weights=[30, 35, 25, 10], k=1)[0]
            elif months_active >= 6:
                grade = random.choices(GRADES, weights=[45, 30, 17, 8], k=1)[0]
            elif months_active >= 3:
                grade = random.choices(GRADES, weights=[55, 28, 12, 5], k=1)[0]
            else:
                grade = random.choices(GRADES, weights=[70, 20, 8, 2], k=1)[0]

            # 가입일: 해당 월 내 랜덤
            y, m = month_date.year, month_date.month
            dim = days_in_month(y, m)
            created_at = datetime(y, m, 1) + timedelta(
                days=random.randint(0, dim - 1),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59),
            )
            if created_at >= END_DATE:
                created_at = END_DATE - timedelta(hours=random.randint(1, 48))

            # 휴면 유저 20%
            if random.random() < 0.2:
                last_login_at = created_at
                status = "DORMANT"
            else:
                days_since = (END_DATE - created_at).days
                login_offset = random.randint(0, max(1, days_since))
                last_login_at = created_at + timedelta(days=login_offset)
                if last_login_at >= END_DATE:
                    last_login_at = END_DATE - timedelta(hours=random.randint(1, 24))
                status = "ACTIVE"

            uid_counter += 1
            users.append({
                "user_id": f"U{uid_counter:08d}",
                "name": fake.name(),
                "gender": gender,
                "age": age,
                "birth_year": birth_year,
                "address": address,
                "address_district": city,
                "email": email,
                "grade": grade,
                "status": status,
                "last_login_at": last_login_at,
                "marketing_agree": random.choice(["true", "false"]),
                "created_at": created_at,
            })

    users.sort(key=lambda u: u["created_at"])
    return users


# ════════════════════════════════════════════════════════════════
# 주문 생성
# ════════════════════════════════════════════════════════════════
def generate_order(user, product, order_dt):
    """단일 주문 레코드 생성"""
    age_group = get_age_group(user["age"])
    stat = PAYMENT_STATS.get(age_group, PAYMENT_STATS["30대"])
    payment = random.choices(stat["methods"], weights=stat["weights"], k=1)[0]

    quantity = random.choices([1, 2, 3, 4, 5], weights=[80, 10, 5, 3, 2], k=1)[0]
    subtotal = product["price"] * quantity
    shipping = random.choice([0, 0, 0, 2500, 3000])  # 60% 무배
    discount = int(subtotal * random.uniform(0, 0.1))
    total = max(0, subtotal + shipping - discount)

    status = random.choices(
        ["Success", "Cancel", "Return"], weights=[93, 4, 3], k=1,
    )[0]

    region = user["address_district"]

    return {
        "order_id": str(uuid.uuid4()),
        "created_at": order_dt,
        "user_id": user["user_id"],
        "product_id": product["product_id"],
        "quantity": quantity,
        "total_amount": total,
        "shipping_cost": shipping,
        "discount_amount": discount,
        "payment_method": payment,
        "status": status,
        "category": product["category"],
        "user_name": user["name"],
        "user_region": region,
        "user_gender": user["gender"],
        "user_age_group": age_group,
    }


def precompute_daily_order_counts(monthly_growth):
    """365일 각각의 주문 수를 미리 계산 (합계 = TOTAL_ORDERS)"""
    total_days = (END_DATE - START_DATE).days
    daily_raw = []

    for day_offset in range(total_days):
        date = START_DATE + timedelta(days=day_offset)
        month_idx = (date.year - START_DATE.year) * 12 + date.month - START_DATE.month
        if month_idx >= len(monthly_growth):
            month_idx = len(monthly_growth) - 1

        growth_w = monthly_growth[month_idx]
        dim = days_in_month(date.year, date.month)
        daily_growth = growth_w / dim
        seasonal_m = get_seasonal_multiplier(date)
        weekday_m = WEEKDAY_MULTIPLIERS[date.weekday()]

        daily_raw.append(daily_growth * seasonal_m * weekday_m)

    # 정규화 → 합계가 정확히 TOTAL_ORDERS
    raw_sum = sum(daily_raw)
    daily_counts = [int(TOTAL_ORDERS * w / raw_sum) for w in daily_raw]

    # 반올림 오차 보정
    remainder = TOTAL_ORDERS - sum(daily_counts)
    fracs = [(TOTAL_ORDERS * daily_raw[i] / raw_sum) % 1 for i in range(total_days)]
    top_idx = sorted(range(total_days), key=lambda i: fracs[i], reverse=True)
    for i in top_idx[:remainder]:
        daily_counts[i] += 1

    return daily_counts


def generate_orders(session, users, products, monthly_growth):
    """주문 1,000,000건 생성 (일별 루프 + 연관성 엔진)"""
    total_days = (END_DATE - START_DATE).days
    daily_counts = precompute_daily_order_counts(monthly_growth)

    # 유저를 created_at 순으로 정렬 (이미 정렬됨) + 날짜 리스트
    user_dates = [u["created_at"] for u in users]

    # 유저 선택 가중치 (등급 + 활성 상태)
    grade_mult = {"VIP": 3.0, "GOLD": 2.0, "SILVER": 1.5, "BRONZE": 1.0}
    user_base_weights = []
    for u in users:
        w = 1.0 if u["status"] == "ACTIVE" else 0.05
        w *= grade_mult.get(u["grade"], 1.0)
        user_base_weights.append(w)

    # 상품을 카테고리별로 인덱싱
    products_by_cat = defaultdict(list)
    product_dates = [p["created_at"] for p in products]
    # 상품도 created_at 순으로 정렬됨 → 점진적으로 추가
    prod_idx = 0

    batch = []
    total_generated = 0
    start_time = time.time()

    for day_offset in range(total_days):
        current_date = START_DATE + timedelta(days=day_offset)
        end_of_day = current_date + timedelta(days=1)
        target = daily_counts[day_offset]

        if target == 0:
            continue

        # 해당일까지 등록된 상품 추가
        while prod_idx < len(products) and products[prod_idx]["created_at"] < end_of_day:
            p = products[prod_idx]
            products_by_cat[p["category"]].append(p)
            prod_idx += 1

        # 해당일까지 가입한 유저 인덱스 찾기 (이진 탐색)
        user_end = _bisect_right_dt(user_dates, end_of_day)
        if user_end == 0:
            continue

        avail_weights = user_base_weights[:user_end]
        available_categories = [c for c in CATEGORIES if products_by_cat.get(c)]
        if not available_categories:
            continue

        # 해당일 유저 일괄 선택
        selected_users = random.choices(users[:user_end], weights=avail_weights, k=target)

        i = 0
        while i < target:
            user = selected_users[i] if i < len(selected_users) else random.choices(
                users[:user_end], weights=avail_weights, k=1
            )[0]

            # 카테고리 선택 (연관성 엔진)
            age_group = get_age_group(user["age"])
            cat_weights = compute_category_weights(
                user["gender"], age_group, current_date, available_categories,
            )
            category = random.choices(available_categories, weights=cat_weights, k=1)[0]

            cat_products = products_by_cat.get(category)
            if not cat_products:
                i += 1
                continue

            product = random.choice(cat_products)

            # 시간 배정
            hour = random.choices(range(24), weights=HOURLY_WEIGHTS, k=1)[0]
            order_dt = current_date.replace(
                hour=hour, minute=random.randint(0, 59), second=random.randint(0, 59),
            )

            batch.append(generate_order(user, product, order_dt))
            i += 1
            total_generated += 1

            # 장바구니 연관 구매 (같은 유저, 같은 시각)
            if i < target and random.random() < 0.25:
                correlations = BASKET_CORRELATIONS.get(category, [])
                for corr_cat, prob in correlations:
                    if i >= target:
                        break
                    if random.random() < prob:
                        corr_products = products_by_cat.get(corr_cat)
                        if corr_products:
                            corr_product = random.choice(corr_products)
                            batch.append(generate_order(user, corr_product, order_dt))
                            i += 1
                            total_generated += 1

            # 배치 플러시
            if len(batch) >= BATCH_SIZE:
                session.bulk_insert_mappings(Order, batch)
                session.commit()
                elapsed = time.time() - start_time
                speed = total_generated / elapsed if elapsed > 0 else 0
                print_progress(
                    total_generated, TOTAL_ORDERS,
                    prefix="  주문 생성",
                    suffix=f"({total_generated:,}/{TOTAL_ORDERS:,}) {speed:,.0f} rows/s",
                )
                batch.clear()

    # 남은 배치 플러시
    if batch:
        session.bulk_insert_mappings(Order, batch)
        session.commit()

    elapsed = time.time() - start_time
    print_progress(total_generated, TOTAL_ORDERS, prefix="  주문 생성",
                   suffix=f"완료! ({total_generated:,}건, {elapsed:.1f}s)")
    print()
    return total_generated


def _bisect_right_dt(sorted_dates, target):
    """datetime 리스트에서 이진 탐색"""
    lo, hi = 0, len(sorted_dates)
    while lo < hi:
        mid = (lo + hi) // 2
        if sorted_dates[mid] <= target:
            lo = mid + 1
        else:
            hi = mid
    return lo


# ════════════════════════════════════════════════════════════════
# 진행률 표시
# ════════════════════════════════════════════════════════════════
def print_progress(current, total, prefix="", suffix="", length=40):
    if total == 0:
        return
    pct = min(current / total, 1.0)
    filled = int(length * pct)
    bar = "#" * filled + "-" * (length - filled)
    sys.stdout.write(f"\r{prefix} |{bar}| {pct:.1%} {suffix}")
    sys.stdout.flush()


# ════════════════════════════════════════════════════════════════
# 요약 통계
# ════════════════════════════════════════════════════════════════
def print_summary(engine):
    """생성된 데이터 요약 통계 출력"""
    from sqlalchemy import text

    with engine.connect() as conn:
        user_cnt = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
        prod_cnt = conn.execute(text("SELECT COUNT(*) FROM products")).scalar()
        order_cnt = conn.execute(text("SELECT COUNT(*) FROM orders")).scalar()

        print("\n" + "=" * 60)
        print("  데이터 생성 완료 요약")
        print("=" * 60)
        print(f"  DB 경로  : {DB_PATH}")
        print(f"  기간     : {START_DATE.date()} ~ {END_DATE.date()}")
        print(f"  유저     : {user_cnt:>10,}명")
        print(f"  상품     : {prod_cnt:>10,}개")
        print(f"  주문     : {order_cnt:>10,}건")

        # 월별 주문 분포
        print("\n  [월별 주문 분포]")
        rows = conn.execute(text("""
            SELECT strftime('%Y-%m', created_at) AS month, COUNT(*) AS cnt,
                   SUM(total_amount) AS revenue
            FROM orders GROUP BY month ORDER BY month
        """)).fetchall()
        for row in rows:
            bar = "▓" * max(1, row[1] // 5000)
            print(f"    {row[0]}: {row[1]:>8,}건  매출 {row[2]:>14,}원  {bar}")

        # 성별 × 카테고리 Top 5
        print("\n  [성별 주문 Top 5 카테고리]")
        for gender in ["F", "M"]:
            label = "여성" if gender == "F" else "남성"
            rows = conn.execute(text(f"""
                SELECT category, COUNT(*) AS cnt FROM orders
                WHERE user_gender = '{gender}'
                GROUP BY category ORDER BY cnt DESC LIMIT 5
            """)).fetchall()
            cats = ", ".join([f"{r[0]}({r[1]:,})" for r in rows])
            print(f"    {label}: {cats}")

        # 연령대별 주문 분포
        print("\n  [연령대별 주문 분포]")
        rows = conn.execute(text("""
            SELECT user_age_group, COUNT(*) AS cnt,
                   ROUND(AVG(total_amount)) AS avg_amount
            FROM orders GROUP BY user_age_group ORDER BY user_age_group
        """)).fetchall()
        for row in rows:
            print(f"    {row[0]}: {row[1]:>8,}건  평균 {int(row[2]):>8,}원")

        # 시간대별 주문 분포
        print("\n  [시간대별 주문 피크]")
        rows = conn.execute(text("""
            SELECT CAST(strftime('%H', created_at) AS INTEGER) AS hour, COUNT(*) AS cnt
            FROM orders GROUP BY hour ORDER BY hour
        """)).fetchall()
        peak_hours = sorted(rows, key=lambda r: r[1], reverse=True)[:3]
        low_hours = sorted(rows, key=lambda r: r[1])[:3]
        peaks = ", ".join([f"{r[0]}시({r[1]:,})" for r in peak_hours])
        lows = ", ".join([f"{r[0]}시({r[1]:,})" for r in low_hours])
        print(f"    피크: {peaks}")
        print(f"    저조: {lows}")

        # 파일 크기
        size_mb = os.path.getsize(DB_PATH) / (1024 * 1024)
        print(f"\n  DB 파일 크기: {size_mb:.1f} MB")
        print("=" * 60)


# ════════════════════════════════════════════════════════════════
# 메인 실행
# ════════════════════════════════════════════════════════════════
def main():
    print("=" * 60)
    print("  쇼핑몰 히스토리 데이터 생성기")
    print(f"  기간: {START_DATE.date()} ~ {END_DATE.date()}")
    print(f"  규모: 유저 {TOTAL_USERS:,} / 상품 {TOTAL_PRODUCTS:,} / 주문 {TOTAL_ORDERS:,}")
    print(f"  DB: {DB_PATH}")
    print("=" * 60)

    # 기존 DB 삭제
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print("  기존 DB 파일 삭제됨")

    # SQLite 엔진 생성 + WAL 모드
    engine = create_engine(DB_URL, echo=False)

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=-64000")  # 64MB 캐시
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.close()

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    total_start = time.time()
    monthly_growth = compute_monthly_growth()

    # Phase 1: 상품 생성
    print("\n[Phase 1] 상품 생성 중...")
    t0 = time.time()
    products = generate_products(monthly_growth)
    # 배치 삽입
    for i in range(0, len(products), BATCH_SIZE):
        session.bulk_insert_mappings(Product, products[i : i + BATCH_SIZE])
        session.commit()
    print(f"  완료: {len(products):,}개 ({time.time() - t0:.1f}s)")

    # Phase 2: 유저 생성
    print("\n[Phase 2] 유저 생성 중...")
    t0 = time.time()
    users = generate_users(monthly_growth)
    for i in range(0, len(users), BATCH_SIZE):
        session.bulk_insert_mappings(User, users[i : i + BATCH_SIZE])
        session.commit()
    print(f"  완료: {len(users):,}명 ({time.time() - t0:.1f}s)")

    # Phase 3: 주문 생성
    print("\n[Phase 3] 주문 생성 중...")
    t0 = time.time()
    order_count = generate_orders(session, users, products, monthly_growth)
    print(f"  완료: {order_count:,}건 ({time.time() - t0:.1f}s)")

    session.close()

    total_elapsed = time.time() - total_start
    print(f"\n  총 소요 시간: {total_elapsed:.1f}s")

    # 요약 통계
    print_summary(engine)


if __name__ == "__main__":
    main()
