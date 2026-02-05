import sys
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, window, count, sum, current_timestamp, expr
from pyspark.sql.types import StructType, StringType, IntegerType, TimestampType

# ==========================================
# 1. Spark Session 생성
# ==========================================
spark = SparkSession.builder \
    .appName("EcommerceRealtimeAnalytics") \
    .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,org.postgresql:postgresql:42.6.0") \
    .config("spark.sql.shuffle.partitions", "2") \
    .getOrCreate()

spark.sparkContext.setLogLevel("ERROR")

# ==========================================
# 2. 공통 스키마 정의 (Nested Structure)
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
# 3. Kafka 데이터 읽기 & 파싱 (공통 소스)
# ==========================================
df_raw = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "kafka1:29092,kafka2:29093,kafka3:29094") \
    .option("subscribe", "orders") \
    .option("startingOffsets", "latest") \
    .load()

# JSON 파싱 및 데이터 평탄화 (Flatten)
df_parsed = df_raw.selectExpr("CAST(value AS STRING) as json_str") \
    .select(from_json(col("json_str"), final_schema).alias("data")) \
    .select("data.order.*") \
    .withWatermark("created_at", "10 minutes") # 지연 데이터 처리 (10분)

# ==========================================
# 4. DB 저장 도우미 함수 (Factory Pattern)
# ==========================================
def create_writer(table_name, ddl_string):
    """
    각 분석 스트림마다 별도의 저장 로직을 만들어주는 함수
    """
    def write_to_postgres(df, epoch_id):
        if df.count() == 0: return
        
        # JDBC 저장
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
    
    return write_to_postgres

# ==========================================
# 5. [분석 1] 카테고리별 매출 (1분 단위)
# ==========================================
df_category = df_parsed \
    .groupBy(window("created_at", "1 minute"), "category") \
    .agg(count("order_id").alias("total_orders"), sum("total_amount").alias("total_revenue")) \
    .select(col("window.start").alias("window_start"), "category", "total_orders", "total_revenue")

# 테이블 컬럼 타입 지정 (자동 생성용)
ddl_category = "window_start TIMESTAMP, category VARCHAR(50), total_orders INT, total_revenue BIGINT"

query_category = df_category.writeStream \
    .queryName("CategoryAnalysis") \
    .outputMode("update") \
    .foreachBatch(create_writer("realtime_category_stats", ddl_category)) \
    .trigger(processingTime="10 seconds") \
    .start()

# ==========================================
# 6. [분석 2] 연령대별 매출/주문수 (1분 단위)
# ==========================================
df_age = df_parsed \
    .groupBy(window("created_at", "1 minute"), "user_age_group") \
    .agg(count("order_id").alias("order_count"), sum("total_amount").alias("total_amt")) \
    .select(col("window.start").alias("window_start"), "user_age_group", "order_count", "total_amt")

ddl_age = "window_start TIMESTAMP, user_age_group VARCHAR(20), order_count INT, total_amt BIGINT"

query_age = df_age.writeStream \
    .queryName("AgeAnalysis") \
    .outputMode("update") \
    .foreachBatch(create_writer("realtime_age_stats", ddl_age)) \
    .trigger(processingTime="10 seconds") \
    .start()

# ==========================================
# 7. [분석 3] 지역별 주문량 (1분 단위)
# ==========================================
df_region = df_parsed \
    .groupBy(window("created_at", "1 minute"), "user_region") \
    .agg(count("order_id").alias("region_count")) \
    .select(col("window.start").alias("window_start"), "user_region", "region_count")

ddl_region = "window_start TIMESTAMP, user_region VARCHAR(20), region_count INT"

query_region = df_region.writeStream \
    .queryName("RegionAnalysis") \
    .outputMode("update") \
    .foreachBatch(create_writer("realtime_region_stats", ddl_region)) \
    .trigger(processingTime="10 seconds") \
    .start()

# ==========================================
# 8. 모든 스트림 대기
# ==========================================
print("🚀 3개의 실시간 분석 스트림이 시작되었습니다...")
spark.streams.awaitAnyTermination()