# tools/sql_tool.py
import psycopg2
from psycopg2 import sql as pg_sql
import os
import re
import json
from decimal import Decimal # <--- IMPORTANT: Add this import!

# Database connection details from environment variables or config
DB_NAME = os.getenv("DB_NAME", "shipping_agent_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")

def is_safe_sql(sql_query: str) -> bool:
    """
    Performs a basic safety check to ensure only SELECT statements (or WITH ... SELECT) are allowed.
    This acts as a quick early-exit for unintended DML/DDL operations.
    """
    cleaned_sql = sql_query.strip().lower()
    # Allows SELECT statements, optionally preceded by a WITH clause
    return re.match(r"^(with\s+.*?select|select)\b", cleaned_sql) is not None

def execute_sql_query(sql_query: str) -> tuple:
    """
    Executes a given SQL query against the PostgreSQL database.
    Includes an initial safety check, EXPLAIN plan validation, and basic error handling.
    Returns (True, results_json_string) for success or (False, error_json_string) for failure.
    """
    conn = None
    cur = None
    try:
        print("[DEBUG] Validating SQL before execution...")

        # 0. Initial Safety Check
        if not is_safe_sql(sql_query):
            error_message = "Unsafe SQL query detected: Only SELECT statements are allowed."
            print(f"[ERROR] {error_message}\nQuery: {sql_query}")
            return False, json.dumps({"error": error_message})

        # 1. SQL Validation using EXPLAIN
        explain_query = f"EXPLAIN {sql_query}"
        print(f"[DEBUG] Attempting EXPLAIN validation:\n{explain_query}")

        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        cur = conn.cursor()

        try:
            cur.execute(explain_query)
            _ = cur.fetchone() # Fetch one result to ensure the query actually ran
            print("[DEBUG] EXPLAIN validation successful.")
        except psycopg2.Error as e:
            conn.rollback() # Rollback any partial transaction from EXPLAIN
            error_message = f"SQL Validation Error (EXPLAIN failed): {e}\nQuery: {sql_query}"
            print(f"[ERROR] {error_message}")
            return False, json.dumps({"error": error_message})

        # 2. Execute the actual query if EXPLAIN passed
        cur.execute(sql_query)

        # For SELECT queries, fetch results
        if sql_query.strip().lower().startswith("select"):
            columns = [desc[0] for desc in cur.description]
            raw_results = cur.fetchall() # Fetched raw results (might contain Decimal)
            conn.commit() # Commit any changes if SELECT implicitly started a transaction (good practice)
            print("[DEBUG] SQL query executed successfully.")

            # --- START OF FIX ---
            # Process results to handle Decimal types
            processed_results = []
            for row_tuple in raw_results:
                # Convert tuple to list for mutable processing, or directly create a dict
                processed_row = []
                for item in row_tuple:
                    if isinstance(item, Decimal):
                        processed_row.append(float(item)) # Convert Decimal to float
                    else:
                        processed_row.append(item)
                processed_results.append(processed_row)
            # --- END OF FIX ---

            # Return data as a JSON string using the processed_results
            return True, json.dumps({"columns": columns, "data": processed_results})
        else:
            conn.commit() # Commit for DML statements (INSERT, UPDATE, DELETE)
            print("[DEBUG] Non-SELECT SQL query executed successfully.")
            return True, json.dumps({"status": "success", "message": f"Command executed successfully. Rows affected: {cur.rowcount}"})

    except psycopg2.Error as e:
        if conn:
            conn.rollback() # Rollback any changes on error
        error_message = f"Database error during SQL execution: {sql_query}\nDetails: {e}"
        print(f"[ERROR] {error_message}")
        return False, json.dumps({"error": error_message})
    except Exception as e:
        error_message = f"An unexpected Python error occurred during SQL execution: {e}"
        print(f"[ERROR] {error_message}")
        return False, json.dumps({"error": error_message})
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    # Example usage:
    print("--- Testing valid SELECT query ---")
    success, result = execute_sql_query('SELECT "id", "name", "cost" FROM shipment LIMIT 2;') # Added cost for testing
    if success:
        print("Query Result:", result)
    else:
        print("Query Failed:", result)

    print("\n--- Testing invalid query (hallucinated table - should fail EXPLAIN) ---")
    success, result = execute_sql_query('SELECT id FROM non_existent_table;')
    if success:
        print("Query Result:", result)
    else:
        print("Query Failed:", result)

    print("\n--- Testing unsafe query (INSERT - should fail is_safe_sql) ---")
    success, result = execute_sql_query("INSERT INTO account (id, title) VALUES (1, 'Unsafe Test');")
    if success:
        print("Query Result:", result)
    else:
        print("Query Failed:", result)

    print("\n--- Testing syntax error query (should fail EXPLAIN) ---")
    success, result = execute_sql_query('SELECT FROM courier;')
    if success:
        print("Query Result:", result)
    else:
        print("Query Failed:", result)