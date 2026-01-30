import pandas as pd
import random
import time
import json
from datetime import datetime

# === 1. 데이터 로드 (상품 & 고객) ===
def load_data():
    try:
        # 상품 데이터 로드
        df_products = pd.read_csv("fake_products.csv")
        # 고객 데이터 로드 (NEW!)
        df_users = pd.read_csv("fake_users.csv")
        return df_products, df_users
    except FileNotFoundError as e:
        print(f"❌ 데이터 파일이 없습니다: {e}")
        print("   -> generate_product.py 와 generate_users.py를 먼저 실행하세요.")
        exit()

df_products, df_users = load_data()

# === 2. 전처리 (속도 최적화) ===
# 상품 관련 (파레토 법칙 유지)
total_products = len(df_products)
num_hot_items = int(total_products * 0.2)
hot_indices = random.sample(range(total_products), num_hot_items)
df_products['weight'] = 1
df_products.loc[hot_indices, 'weight'] = 50

product_list = df_products.to_dict('records')
product_weights = df_products['weight'].tolist()

# 고객 관련 (NEW!)
# VIP 고객은 주문 빈도를 더 높게 설정해볼까요? (선택 사항)
# 간단하게 MVP에서는 그냥 리스트로 변환합니다.
user_list = df_users.to_dict('records')

print(f"🚀 로드 완료: 상품 {len(product_list)}개, 고객 {len(user_list)}명")

# === 검증 및 저장 로직 추가 ===
def validate_order(order):
    if order['total_amount'] < 0: return False, "금액 오류"
    if not order['user_id']: return False, "유저 ID 누락"
    return True, "정상"

def save_to_jsonl(order, filename="orders.jsonl"):
    with open(filename, "a", encoding="utf-8") as f:
        f.write(json.dumps(order, ensure_ascii=False) + "\n")


# === 3. 주문 생성 함수 ===
def generate_fake_order():
    # [Step 1] 상품 선정 (기존 로직)
    picked_product = random.choices(product_list, weights=product_weights, k=1)[0]
    
    # [Step 2] 고객 선정 (NEW!)
    # 랜덤으로 한 명 뽑기 (나중엔 접속 시간대별 활성 유저 로직 등을 넣을 수 있음)
    picked_user = random.choice(user_list)
    
    # [Step 3] 수량 결정
    quantity = random.choices([1, 2, 3, 4, 5], weights=[80, 10, 5, 3, 2], k=1)[0]
    
    # [Step 4] 주문 데이터 조립
    order_data = {
        "order_id": f"ORD-{int(time.time()*10000)}", # ID 충돌 방지 위해 자릿수 늘림
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        
        # --- 고객 정보 매핑 ---
        "user_id": picked_user['user_id'],
        "user_name": picked_user['name'],     # 편의상 이름 포함
        "user_grade": picked_user['grade'],   # 등급 포함 (분석용)
        "user_city": picked_user['city'],     # 지역 포함 (분석용)
        
        # --- 상품 정보 매핑 ---
        "product_id": picked_product['product_id'],
        "product_name": picked_product['name'],
        "category": picked_product['category'],
        
        # --- 결제 정보 ---
        "price": int(picked_product['price']),
        "quantity": quantity,
        "total_amount": int(picked_product['price'] * quantity),
        "payment_method": random.choice(["Card", "Bank", "Pay", "BitCoin" if picked_user['age'] < 40 else "Card"]), # 재미 요소: 젊은 층 비트코인
        "status": "Success"
    }
    
    return order_data

# === 4. 실행 루프 ===
# === 메인 실행 루프 ===
if __name__ == "__main__":
    print("🚀 주문 생성기 V3 가동 (검증+로깅 포함)")
    
    order_count = 0
    start_time = time.time()
    
    try:
        while True:
            # 1. 주문 생성
            order = generate_fake_order() # v2의 함수 사용
            
            # [Chaos] 2% 확률로 데이터 오염 시키기
            if random.random() < 0.02:
                order['total_amount'] = -10000 # 에러 주입
            
            # 2. 데이터 검증
            is_valid, msg = validate_order(order)
            
            if is_valid:
                # 3. 정상 데이터: 저장 및 출력
                save_to_jsonl(order)
                print(f"✅ [OK] {order['user_name']} - {order['product_name']}")
                order_count += 1
            else:
                # 4. 비정상 데이터: 에러 로그만 남김 (저장 X)
                print(f"⚠️ [SKIP] 데이터 오류 발생: {msg} (Order ID: {order['order_id']})")

            # 5. 퍼포먼스 체크 (100건마다 속도 측정)
            if order_count % 100 == 0 and order_count > 0:
                elapsed = time.time() - start_time
                ops = order_count / elapsed
                print(f"📊 [Stat] 현재 처리 속도: {ops:.2f} OPS (총 {order_count}건)")

            time.sleep(random.uniform(0.01, 0.1)) # 속도 좀 높임

    except KeyboardInterrupt:
        print("\n🛑 시스템 종료")