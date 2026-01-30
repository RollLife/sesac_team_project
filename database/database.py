import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from typing import Generator
# .env 로드 (python-dotenv가 있다면 사용, 없다면 os.environ 사용)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 환경 설정
DB_TYPE = os.getenv("DB_TYPE", "supabase")  # local, supabase, rds

def get_database_url():
    """환경변수에 따라 DB 연결 URL 반환"""
    
    if DB_TYPE == "local":
        user = os.getenv("POSTGRES_USER", "postgres")
        password = os.getenv("POSTGRES_PASSWORD", "password")
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = os.getenv("POSTGRES_PORT", "5432")
        db_name = os.getenv("POSTGRES_DB", "sesac_db")
        return f"postgresql://{user}:{password}@{host}:{port}/{db_name}"
    
    elif DB_TYPE == "supabase":
        # .env 예시: SUPABASE_DIRECT_URL=postgresql://postgres:[YOUR-PASSWORD]@db.xxxx.supabase.co:5432/postgres
        # 비밀번호가 포함되어 있지 않을 경우 치환 로직 추가
        db_url = os.getenv("SUPABASE_DIRECT_URL")
        password = os.getenv("SUPABASE_PASSWORD")
        
        if db_url and "[YOUR-PASSWORD]" in db_url and password:
            return db_url.replace("[YOUR-PASSWORD]", password)
        return db_url
        
    elif DB_TYPE == "rds":
        user = os.getenv("RDS_USER")
        password = os.getenv("RDS_PASSWORD")
        host = os.getenv("RDS_HOST")
        port = os.getenv("RDS_PORT", "5432")
        db_name = os.getenv("RDS_DB")
        return f"postgresql://{user}:{password}@{host}:{port}/{db_name}"
        
    else:
        raise ValueError(f"Unknown DB_TYPE: {DB_TYPE}")

SQLALCHEMY_DATABASE_URL = get_database_url()

# 엔진 생성
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    pool_pre_ping=True,  # 연결 끊김 방지
    echo=False           # SQL 로그 출력 여부
)

# 세션 생성기
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 모델의 기본 클래스
Base = declarative_base()

def get_db() -> Generator:
    """FastAPI 등의 의존성 주입을 위한 DB 세션 생성 함수"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
