import time
import csv
import os
from datetime import datetime
from functools import wraps

# 로그 저장할 파일명
LOG_FILE = "benchmark_results.csv"

def log_to_csv(func_name, count, duration):
    """결과를 CSV에 한 줄 추가하는 함수"""
    file_exists = os.path.isfile(LOG_FILE)
    
    with open(LOG_FILE, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # 파일이 처음 생길 때만 헤더(제목) 작성
        if not file_exists:
            writer.writerow(['timestamp', 'function_name', 'processed_count', 'duration_sec', 'tps(records/sec)'])
        
        # TPS (초당 처리 건수) 계산
        tps = round(count / duration, 2) if duration > 0 else 0
        
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            func_name,
            count,
            round(duration, 4), # 소수점 4자리까지
            tps
        ])

def measure_time(func):
    """함수 실행 시간을 측정하는 데코레이터"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter() # 정밀 측정 시작
        
        # 함수 실행 (여기서 실제 작업 수행)
        result = func(*args, **kwargs)
        
        end_time = time.perf_counter() # 측정 종료
        duration = end_time - start_time
        
        # 처리 건수(count) 파악하기
        # 1. 함수의 첫 번째 인자가 숫자면 그걸 건수로 간주 (예: num_products=100)
        # 2. 혹은 kwargs에 'count'나 'num_products'가 있으면 가져옴
        count = 0
        if args and isinstance(args[0], int):
            count = args[0]
        elif 'num_products' in kwargs:
            count = kwargs['num_products']
        elif 'count' in kwargs:
            count = kwargs['count']
            
        # 로그 저장
        log_to_csv(func.__name__, count, duration)
        
        print(f"⏱️  [{func.__name__}] {count}건 처리 완료 | 소요시간: {duration:.4f}초 | TPS: {count/duration:.1f}")
        return result
        
    return wrapper