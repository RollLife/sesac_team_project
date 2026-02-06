import sys
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, window, count, sum, avg, current_timestamp, expr
from pyspark.sql.types import StructType, StringType, IntegerType, TimestampType

# ==========================================
# 1. Spark Session 생성
# ==========================================
spark = SparkSession.builder \
    .appName("EcommerceRealtimeAnalytics") \
    .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,org.postgresql:postgresql:42.6.0") \
    .config("spark.sql.shuffle.partitions", "4") \
    .getOrCreate()

spark.sparkContext.setLogLevel("ERROR")

# ==========================================
# 2. 스키마 정의 (Kafka 데이터 구조)
# ==========================================
order_details_schema = StructType() \
    .add("order_id", StringType()) \
    .add("user_id", StringType()) \
    .add("product_id", StringType()) \
    .add("category", StringType()) \
    .add("quantity", IntegerType()) \
    .add("total_amount", IntegerType()) \
    .add("payment_method", StringType()) \
    .add("user_region", StringType()) \
    .add("user_age_group", StringType()) \
    .add("created_at", TimestampType())

final_schema = StructType() \
    .add("event_type", StringType()) \
    .add("timestamp", StringType()) \
    .add("order", order_details_schema)

# ==========================================
# 3. Kafka 데이터 읽기
# ==========================================
df_raw = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "kafka1:29092,kafka2:29093,kafka3:29094") \
    .option("subscribe", "orders") \
    .option("startingOffsets", "latest") \
    .load()

# 데이터 파싱 및 Watermark 설정 (지연 데이터 10분 허용)
df_parsed = df_raw.selectExpr("CAST(value AS STRING) as json_str") \
    .select(from_json(col("json_str"), final_schema).alias("data")) \
    .select("data.order.*") \
    .withWatermark("created_at", "10 minutes")

# ==========================================
# 4. 저장 도우미 함수 (Append 모드용)
# ==========================================
def create_writer_append(table_name, ddl_string):
    def write_to_postgres(df, epoch_id):
        if df.count() == 0: return
        df.write \
            .format("jdbc") \
            .option("url", "jdbc:postgresql://postgres:5432/sesac_db") \
            .option("driver", "org.postgresql.Driver") \
            .option("dbtable", table_name) \
            .option("user", "postgres") \
            .option("password", "password") \
            .mode("append") \
            .option("createTableColumnTypes", ddl_string) \
            .save()
        print(f"✅ [{table_name}] Batch {epoch_id} 저장 완료 ({df.count()}건)")
        sys.stdout.flush()
    return write_to_postgres

# ==========================================
# 5. [분석 1] 카테고리별 매출 (기존)
# ==========================================
df_category = df_parsed \
    .groupBy(window("created_at", "1 minute"), "category") \
    .agg(count("order_id").alias("total_orders"), sum("total_amount").alias("total_revenue")) \
    .select(col("window.start").alias("window_start"), "category", "total_orders", "total_revenue")

ddl_category = "window_start TIMESTAMP, category VARCHAR(50), total_orders INT, total_revenue BIGINT"

query_category = df_category.writeStream \
    .queryName("CategoryAnalysis") \
    .outputMode("update") \
    .foreachBatch(create_writer_append("realtime_category_stats", ddl_category)) \
    .trigger(processingTime="10 seconds") \
    .start()

# ==========================================
# 6. [분석 2] 결제 수단별 점유율 (신규 - 파이차트용)
# ==========================================
df_payment = df_parsed \
    .groupBy(window("created_at", "1 minute"), "payment_method") \
    .agg(count("order_id").alias("count"), sum("total_amount").alias("revenue")) \
    .select(col("window.start").alias("window_start"), "payment_method", "count", "revenue")

ddl_payment = "window_start TIMESTAMP, payment_method VARCHAR(20), count INT, revenue BIGINT"

query_payment = df_payment.writeStream \
    .queryName("PaymentAnalysis") \
    .outputMode("update") \
    .foreachBatch(create_writer_append("realtime_payment_stats", ddl_payment)) \
    .trigger(processingTime="10 seconds") \
    .start()

# ==========================================
# 7. [분석 3] 연령대 x 결제수단 상세 분석 (신규 - 누적 막대용)
# ==========================================
# 예: 20대가 카카오페이를 얼마나 썼나?
df_age_payment = df_parsed \
    .groupBy(window("created_at", "1 minute"), "user_age_group", "payment_method") \
    .agg(count("order_id").alias("count")) \
    .select(col("window.start").alias("window_start"), "user_age_group", "payment_method", "count")

ddl_age_payment = "window_start TIMESTAMP, user_age_group VARCHAR(20), payment_method VARCHAR(20), count INT"

query_age_payment = df_age_payment.writeStream \
    .queryName("AgePaymentAnalysis") \
    .outputMode("update") \
    .foreachBatch(create_writer_append("realtime_age_payment_stats", ddl_age_payment)) \
    .trigger(processingTime="10 seconds") \
    .start()

# ==========================================
# 8. [분석 4] 유저별 누적 통계 (신규 - 산점도용, Overwrite 모드)
# ==========================================
# 주의: 이 분석은 '시간 윈도우'가 없습니다. 태초부터 지금까지의 누적입니다.
df_user_stats = df_parsed \
    .groupBy("user_id") \
    .agg(
        count("order_id").alias("total_count"),
        sum("total_amount").alias("total_spent"),
        avg("total_amount").alias("avg_ticket")
    ) \
    .select("user_id", "total_count", "total_spent", "avg_ticket")

# 유저 통계는 데이터가 계속 갱신되므로 'Overwrite' 모드를 사용하는 별도 함수 필요
def save_user_stats_overwrite(df, epoch_id):
    if df.count() == 0: return
    df.write \
        .format("jdbc") \
        .option("url", "jdbc:postgresql://postgres:5432/sesac_db") \
        .option("driver", "org.postgresql.Driver") \
        .option("dbtable", "realtime_user_stats") \
        .option("user", "postgres") \
        .option("password", "password") \
        .mode("overwrite") \
        .save() # 테이블을 싹 비우고 현재 상태로 덮어씌움
    print(f"✅ [UserStats] Batch {epoch_id} : 유저 {df.count()}명 통계 갱신 완료")

query_user_stats = df_user_stats.writeStream \
    .queryName("UserStatsAnalysis") \
    .outputMode("complete") \
    .foreachBatch(save_user_stats_overwrite) \
    .trigger(processingTime="5 seconds") \
    .start()

# ==========================================
# 9. 실행 대기
# ==========================================
print("🚀 4개의 실시간 분석(Category, Payment, Age+Payment, UserStats)이 시작되었습니다...")
spark.streams.awaitAnyTermination()