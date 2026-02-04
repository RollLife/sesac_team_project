# 🚀 실행 순서 가이드
Jupyter 실행 & 테스트:

docker-compose up -d jupyter

브라우저로 localhost:8888 접속 (토큰은 docker-compose logs jupyter로 확인).

work/apps/spark/spark_streaming_test.ipynb 파일을 열고 셀을 하나씩 실행하며 데이터가 잘 나오는지 확인.

실전 스트리밍 실행:

테스트가 끝나면 터미널에서 아래 명령어로 실전 코드를 돌립니다.

Bash
docker exec -it spark_master /opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,org.postgresql:postgresql:42.6.0 \
  /app/apps/spark/streaming_analysis.py
Grafana 확인:

DB에 realtime_category_stats, realtime_age_stats, realtime_region_stats 3개 테이블이 자동으로 생기고 데이터가 쌓이기 시작할 겁니다!