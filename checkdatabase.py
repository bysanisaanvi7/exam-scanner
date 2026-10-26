
from database import get_connection

with get_connection() as connection:
    tables = connection.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """).fetchall()

print("Tables created successfully:")
for table in tables:
    print("-", table["name"])
