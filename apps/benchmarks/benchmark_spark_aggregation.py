"""
Spark 집계 벤치마크

Spark SQL을 사용한 분산 집계 성능을 측정합니다.
PostgreSQL 집계와 비교하기 위한 벤치마크입니다.

주의: 이 스크립트는 Spark 환경에서 실행해야 합니다.
"""

import os
import sys
import time
from datetime import datetime

# Spark 관련 import
try:
    from pyspark.sql import SparkSession
    from pyspark.sql.functions import col, count, sum as spark_sum, avg, date_trunc, date_format
    SPARK_AVAILABLE = True
except ImportError:
    SPARK_AVAILABLE = False
    print("⚠️ PySpark가 설치되지 않았습니다. Spark 환경에서 실행하세요.")

# 벤치마크 설정
NUM_ITERATIONS = int(os.environ.get('BENCHMARK_ITERATIONS', 10))
POSTGRES_URL = os.environ.get('POSTGRES_URL', 'jdbc:postgresql://postgres:5432/sesac_db')
POSTGRES_USER = os.environ.get('POSTGRES_USER', 'postgres')
POSTGRES_PASSWORD = os.environ.get('POSTGRES_PASSWORD', 'password')


def run_spark_benchmark():
    """Spark 집계 벤치마크 실행"""
    
    if not SPARK_AVAILABLE:
        print("❌ Spark를 사용할 수 없습니다.")
        return None
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║           Spark SQL 집계 벤치마크                            ║
╠══════════════════════════════════════════════════════════════╣
║  반복 횟수: {NUM_ITERATIONS:>10}회                                   ║
║  JDBC URL: {POSTGRES_URL[:40]:<40}     ║
╚══════════════════════════════════════════════════════════════╝
""")

    # Spark 세션 생성
    print("🚀 Spark 세션 초기화 중...")
    spark = SparkSession.builder \
        .appName("SparkBenchmark") \
        .config("spark.jars.packages", "org.postgresql:postgresql:42.6.0") \
        .config("spark.sql.shuffle.partitions", "4") \
        .getOrCreate()
    
    spark.sparkContext.setLogLevel("ERROR")
    
    # 데이터 로드
    print("📊 데이터 로드 중...")
    
    try:
        orders_df = spark.read \
            .format("jdbc") \
            .option("url", POSTGRES_URL) \
            .option("dbtable", "orders") \
            .option("user", POSTGRES_USER) \
            .option("password", POSTGRES_PASSWORD) \
            .option("driver", "org.postgresql.Driver") \
            .load()
        
        products_df = spark.read \
            .format("jdbc") \
            .option("url", POSTGRES_URL) \
            .option("dbtable", "products") \
            .option("user", POSTGRES_USER) \
            .option("password", POSTGRES_PASSWORD) \
            .option("driver", "org.postgresql.Driver") \
            .load()
        
        users_df = spark.read \
            .format("jdbc") \
            .option("url", POSTGRES_URL) \
            .option("dbtable", "users") \
            .option("user", POSTGRES_USER) \
            .option("password", POSTGRES_PASSWORD) \
            .option("driver", "org.postgresql.Driver") \
            .load()
        
        # 캐싱 (공정한 비교를 위해)
        orders_df.cache()
        products_df.cache()
        users_df.cache()
        
        # 레코드 수 확인
        order_count = orders_df.count()
        print(f"📊 orders 테이블 레코드 수: {order_count:,}건")
        
    except Exception as e:
        print(f"❌ 데이터 로드 오류: {e}")
        spark.stop()
        return None

    print(f"\n🚀 Spark 집계 벤치마크 시작...")
    print("-" * 60)
    
    total_start = time.perf_counter()
    all_latencies = []
    query_results = {}
    
    for iteration in range(NUM_ITERATIONS):
        iteration_start = time.perf_counter()
        
        # 1. 카테고리별 매출
        q1_start = time.perf_counter()
        category_stats = orders_df.join(products_df, orders_df.product_id == products_df.id) \
            .groupBy("category") \
            .agg(
                count("*").alias("order_count"),
                spark_sum("total_amount").alias("total_revenue"),
                avg("total_amount").alias("avg_order_value")
            ) \
            .orderBy(col("total_revenue").desc())
        category_result = category_stats.collect()
        q1_time = (time.perf_counter() - q1_start) * 1000
        all_latencies.append(q1_time)
        if 'category_revenue' not in query_results:
            query_results['category_revenue'] = {'latencies': [], 'row_count': len(category_result)}
        query_results['category_revenue']['latencies'].append(q1_time)
        
        # 2. 결제수단별 통계
        q2_start = time.perf_counter()
        payment_stats = orders_df \
            .groupBy("payment_method") \
            .agg(
                count("*").alias("count"),
                spark_sum("total_amount").alias("total_revenue"),
                avg("total_amount").alias("avg_amount")
            ) \
            .orderBy(col("count").desc())
        payment_result = payment_stats.collect()
        q2_time = (time.perf_counter() - q2_start) * 1000
        all_latencies.append(q2_time)
        if 'payment_stats' not in query_results:
            query_results['payment_stats'] = {'latencies': [], 'row_count': len(payment_result)}
        query_results['payment_stats']['latencies'].append(q2_time)
        
        # 3. 시간별 주문
        q3_start = time.perf_counter()
        hourly_orders = orders_df \
            .withColumn("hour", date_trunc("hour", "created_at")) \
            .groupBy("hour") \
            .agg(
                count("*").alias("order_count"),
                spark_sum("total_amount").alias("revenue")
            ) \
            .orderBy(col("hour").desc()) \
            .limit(24)
        hourly_result = hourly_orders.collect()
        q3_time = (time.perf_counter() - q3_start) * 1000
        all_latencies.append(q3_time)
        if 'hourly_orders' not in query_results:
            query_results['hourly_orders'] = {'latencies': [], 'row_count': len(hourly_result)}
        query_results['hourly_orders']['latencies'].append(q3_time)
        
        # 4. 유저 등급별 통계
        q4_start = time.perf_counter()
        user_stats = orders_df.join(users_df, orders_df.user_id == users_df.id) \
            .groupBy("grade") \
            .agg(
                count("*").alias("total_orders"),
                spark_sum("total_amount").alias("total_spent"),
                avg("total_amount").alias("avg_order")
            ) \
            .orderBy(col("total_spent").desc())
        user_result = user_stats.collect()
        q4_time = (time.perf_counter() - q4_start) * 1000
        all_latencies.append(q4_time)
        if 'user_stats' not in query_results:
            query_results['user_stats'] = {'latencies': [], 'row_count': len(user_result)}
        query_results['user_stats']['latencies'].append(q4_time)
        
        # 5. Top 20 상품
        q5_start = time.perf_counter()
        top_products = orders_df.join(products_df, orders_df.product_id == products_df.id) \
            .groupBy("name", "category") \
            .agg(
                count("*").alias("order_count"),
                spark_sum("total_amount").alias("total_revenue")
            ) \
            .orderBy(col("order_count").desc()) \
            .limit(20)
        top_result = top_products.collect()
        q5_time = (time.perf_counter() - q5_start) * 1000
        all_latencies.append(q5_time)
        if 'top_products' not in query_results:
            query_results['top_products'] = {'latencies': [], 'row_count': len(top_result)}
        query_results['top_products']['latencies'].append(q5_time)
        
        # 6. 일별 트렌드
        q6_start = time.perf_counter()
        daily_trend = orders_df \
            .withColumn("date", date_format("created_at", "yyyy-MM-dd")) \
            .groupBy("date") \
            .agg(
                count("*").alias("order_count"),
                spark_sum("total_amount").alias("daily_revenue")
            ) \
            .orderBy(col("date").desc()) \
            .limit(30)
        daily_result = daily_trend.collect()
        q6_time = (time.perf_counter() - q6_start) * 1000
        all_latencies.append(q6_time)
        if 'daily_trend' not in query_results:
            query_results['daily_trend'] = {'latencies': [], 'row_count': len(daily_result)}
        query_results['daily_trend']['latencies'].append(q6_time)
        
        iteration_time = (time.perf_counter() - iteration_start) * 1000
        
        # 진행률 출력
        if (iteration + 1) % max(1, NUM_ITERATIONS // 5) == 0:
            progress = (iteration + 1) / NUM_ITERATIONS * 100
            print(f"  ⏳ {progress:.0f}% 완료 | 반복 {iteration + 1}/{NUM_ITERATIONS} | {iteration_time:.1f}ms")

    total_duration = time.perf_counter() - total_start

    # 쿼리별 결과 요약
    print(f"\n{'='*60}")
    print("쿼리별 성능 분석")
    print(f"{'='*60}")
    print(f"{'쿼리명':<20} {'결과행':<8} {'평균(ms)':<10} {'최소(ms)':<10} {'최대(ms)':<10}")
    print("-" * 60)
    
    for query_name, data in query_results.items():
        latencies = data['latencies']
        if latencies:
            avg_lat = sum(latencies) / len(latencies)
            min_lat = min(latencies)
            max_lat = max(latencies)
            print(f"{query_name:<20} {data['row_count']:<8} {avg_lat:<10.2f} {min_lat:<10.2f} {max_lat:<10.2f}")

    # 결과 저장을 위해 프로젝트 루트의 benchmark_common 사용
    # (Spark 환경에서는 직접 JSON 저장)
    result_data = {
        "test_name": "Spark SQL 집계 쿼리",
        "mode": "spark",
        "total_records": len(query_results) * NUM_ITERATIONS,
        "duration_seconds": total_duration,
        "records_per_second": (len(query_results) * NUM_ITERATIONS) / total_duration if total_duration > 0 else 0,
        "avg_latency_ms": sum(all_latencies) / len(all_latencies) if all_latencies else 0,
        "min_latency_ms": min(all_latencies) if all_latencies else 0,
        "max_latency_ms": max(all_latencies) if all_latencies else 0,
        "success_count": len(query_results) * NUM_ITERATIONS,
        "failure_count": 0,
        "timestamp": datetime.now().isoformat(),
        "extra_info": {
            "query_count": len(query_results),
            "iterations": NUM_ITERATIONS,
            "total_orders": order_count,
            "query_stats": {
                name: {
                    'avg_ms': sum(data['latencies']) / len(data['latencies']) if data['latencies'] else 0,
                    'row_count': data['row_count']
                }
                for name, data in query_results.items()
            }
        }
    }
    
    # 결과 파일 저장
    import json
    result_dir = "/app/benchmark_results"
    os.makedirs(result_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = os.path.join(result_dir, f"spark_benchmark_spark_{timestamp}.json")
    
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(result_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ 결과 저장: {result_file}")
    
    # 결과 요약 출력
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                    벤치마크 결과 요약                         ║
╠══════════════════════════════════════════════════════════════╣
║  테스트: Spark SQL 집계 쿼리                                  ║
║  모드: SPARK                                                  ║
╠══════════════════════════════════════════════════════════════╣
║  총 쿼리: {len(query_results) * NUM_ITERATIONS:>10,}개                              ║
║  소요 시간: {total_duration:>10.2f}초                             ║
║  QPS:       {result_data['records_per_second']:>10.2f} queries/sec                  ║
╠══════════════════════════════════════════════════════════════╣
║  평균 지연: {result_data['avg_latency_ms']:>10.2f}ms                               ║
║  최소 지연: {result_data['min_latency_ms']:>10.2f}ms                               ║
║  최대 지연: {result_data['max_latency_ms']:>10.2f}ms                               ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    spark.stop()
    return result_data


if __name__ == "__main__":
    result = run_spark_benchmark()
    if result:
        print("\n✅ Spark 집계 벤치마크 완료!")
    else:
        print("\n❌ 벤치마크 실패")
        sys.exit(1)
