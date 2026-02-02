# DB Structure & ORM Implementation Guide

This project uses **SQLAlchemy** with a modular structure to support **Local PostgreSQL**, **Supabase**, and **AWS RDS**.

## 1. Setup Environment
Ensure your `.env` file contains the database connection details.

### Local PostgreSQL
To use the local database via Docker Compose:
```bash
# Start the local database
docker-compose up -d
```
Add to `.env`:
```ini
DB_TYPE=local
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
POSTGRES_DB=sesac_db
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

### Supabase
To use Supabase:
Add to `.env`:
```ini
DB_TYPE=supabase
SUPABASE_DIRECT_URL=postgresql://postgres:[YOUR-PASSWORD]@db.xxxx.supabase.co:5432/postgres
SUPABASE_PASSWORD=your_actual_password
```
*(The code automatically replaces `[YOUR-PASSWORD]` with `SUPABASE_PASSWORD` if present)*

### AWS RDS
To use RDS:
Add to `.env`:
```ini
DB_TYPE=rds
RDS_USER=admin
RDS_PASSWORD=your_rds_password
RDS_HOST=your-rds-endpoint.amazonaws.com
RDS_DB=sesac_db
```

## 2. Install Dependencies
You need to install the following packages:
```bash
pip install sqlalchemy psycopg2-binary python-dotenv
```

## 3. Operations

### Initialize Database (Create Tables)
Run the following command to create tables for the configured `DB_TYPE`:
```bash
python -m database.init_db
```

### Using CRUD Operations
Import the `crud` module to interact with the database.

```python
from database import database, crud, models

# Start a session
db = database.SessionLocal()

# Create a User
new_user = crud.create_user(db, {
    "user_id": "U_001",
    "name": "Hong Gil Dong",
    "gender": "M",
    "age": 30,
    "address": "Seoul Gangnam-gu ..."
})

# Create a Product
new_product = crud.create_product(db, {
    "product_id": "P1001",
    "name": "MacBook Pro",
    "category": "Electronics",
    "price": 3000000
})

# Create an Order (Denormalized fields are auto-filled)
new_order = crud.create_order(db, {
    "user_id": "U_001",
    "product_id": "P1001",
    "quantity": 1,
    "total_amount": 3000000
})

# Commit and close
db.close()
```
