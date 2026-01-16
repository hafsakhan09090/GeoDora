import sqlite3
import json

conn = sqlite3.connect('geography.db')
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("Tables in database:")
for table in tables:
    print(f"\n{table[0]}:")
    cursor.execute(f"PRAGMA table_info({table[0]})")
    columns = cursor.fetchall()
    for col in columns:
        print(f"  - {col[1]} ({col[2]})")
    
    # Show first row
    try:
        cursor.execute(f"SELECT * FROM {table[0]} LIMIT 1")
        row = cursor.fetchone()
        if row:
            print(f"  Sample data: {row}")
    except:
        pass

conn.close()