import time
import random
from database import crud, database
from collect.product_generator import ProductGenerator # 혹은 OrderGenerator
from utils.benchmark import measure_time

db = database.SessionLocal()

# 실제 서비스처럼 1건씩 처리하는 함수
def create_single_product_realistically():
    # 1. 데이터 생성 (가벼움)
    gen = ProductGenerator()
    data = gen.generate_batch(1)[0] # 1개만 생성

    print(data)
    
    # 2. [시뮬레이션] 무거운 작업 흉내내기 (Blocking I/O)
    # 이미지 업로드하고 검수받느라 오래 걸린다고 가정
    # delay = random.uniform(0.5, 2.0) # 0.5초 ~ 2초 랜덤 지연
    
    # delay = data['sleep']
    
    # del data['sleep']
    # time.sleep(delay) 
    
    # 3. DB 저장
    crud.create_product(db, data) # 실제 저장은 주석처리하거나 실행
    # print(f"🐢 [완료] {data['name']} 생성 (소요시간: {delay:.2f}s)")

@measure_time
def run_sequential_test(count=10):
    print(f"🐢 순차 처리 테스트 시작 ({count}건)...")
    for i in range(count):
        create_single_product_realistically()

if __name__ == "__main__":
    # 10개만 만드는데도 10~20초가 걸리는 걸 눈으로 확인
    run_sequential_test(10)