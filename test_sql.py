# test_sql.py
from tools.sql_tool import run_sql_query
import uuid # To generate a unique UUID for testing inserts

print("--- Testing SQL Tool ---")

# 1. Try inserting a dummy account to see if INSERT works
# We use uuid.uuid4() to generate a new UUID because the 'id' column is a UUID.
# ON CONFLICT (title) DO NOTHING prevents errors if you run this multiple times
# and the 'Test Account 1' title already exists.
insert_account_query = f"""
INSERT INTO public.account (id, type, title) VALUES
('{uuid.uuid4()}', 'Test Type', 'Test Account {uuid.uuid4()}')
ON CONFLICT (title) DO NOTHING;
"""
print("Attempting to insert a dummy account...")
insert_result = run_sql_query(insert_account_query)
print(insert_result)
print("-" * 30)

# 2. Query one of the tables created by your shipnest_schema.sql
# Let's try the 'account' table.
# Note: Using double quotes for column names that are mixed-case like "createdAt".
query_account_query = "SELECT id, type, title, \"createdAt\" FROM public.account LIMIT 5;"
print(f"Attempting to run SELECT query on 'account' table...")
select_result = run_sql_query(query_account_query)
print(select_result)
print("-" * 30)

# 3. Try to clean up the dummy data (optional, but good practice)
# delete_account_query = """
# DELETE FROM public.account WHERE title LIKE 'Test Account%';
# """
# print("Attempting to delete dummy accounts...")
# delete_result = run_sql_query(delete_account_query)
# print(delete_result)
# print("-" * 30)

# 4. Query again to confirm deletion (if you uncomment the delete)
# print(f"Attempting to run SELECT query on 'account' table after deletion...")
# select_after_delete_result = run_sql_query(query_account_query)
# print(select_after_delete_result)