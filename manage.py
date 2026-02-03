import argparse
import sys
from database import database
from database import init_db as db_init
from seeder import user_seeder, product_seeder, order_seeder

def main():
    parser = argparse.ArgumentParser(description="SESAC Project Data Manager")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Init DB Command
    subparsers.add_parser("init-db", help="Initialize database tables")
    
    # Collect Users
    parser_users = subparsers.add_parser("users", help="Generate and collect User data")
    parser_users.add_argument("-n", "--number", type=int, default=100, help="Number of users to generate")
    
    # Collect Products
    parser_products = subparsers.add_parser("products", help="Generate and collect Product data")
    parser_products.add_argument("-n", "--number", type=int, default=100, help="Number of products to generate")
    
    # Collect Orders
    parser_orders = subparsers.add_parser("orders", help="Generate and collect Order data")
    parser_orders.add_argument("-n", "--number", type=int, default=100, help="Number of orders to generate")
    
    # Collect All
    parser_all = subparsers.add_parser("all", help="Generate all data (Users, Products, Orders)")
    parser_all.add_argument("-n", "--number", type=int, default=100, help="Number of items for each category")

    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Database Session
    db = database.SessionLocal()
    
    try:
        if args.command == "init-db":
            db_init.init_db()
            print("Database initialized successfully.")
            
        elif args.command == "users":
            user_seeder.seed_users(db, args.number)
            
        elif args.command == "products":
            product_seeder.seed_products(db, args.number)
            
        elif args.command == "orders":
            order_seeder.seed_orders(db, args.number)
            
        elif args.command == "all":
            print("--- 1. Users ---")
            user_seeder.seed_users(db, args.number)
            print("\n--- 2. Products ---")
            product_seeder.seed_products(db, args.number)
            print("\n--- 3. Orders ---")
            order_seeder.seed_orders(db, args.number)
            
    except Exception as e:
        print(f"Error executing command: {e}")
    finally:
        db.close()



# Initialize Tables (if not already done)
# python manage.py init-db

# Generate All Data (N items each)
# python manage.py all -n 100

# Generate Specific Data
# python manage.py users -n 50
# python manage.py products -n 20
# python manage.py orders -n 200

if __name__ == "__main__":
    main()
