
# tools/sql_tool.py
import psycopg2
import json
import os
import re
from decimal import Decimal

# Database connection details
DB_NAME = os.getenv("DB_NAME", "shipnest_schema")
DB_USER = "postgres"
DB_PASSWORD = "1972"
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")

def _is_safe_query(sql_query: str) -> bool:
    """A basic check to ensure only read-only queries are run."""
    return re.match(r"^\s*(SELECT|WITH)\b", sql_query.strip(), re.IGNORECASE) is not None

def validate_sql_syntax(sql_query: str) -> tuple[bool, str]:
    """
    Validates the SQL query using EXPLAIN without executing it.
    This is the primary method for checking syntax before execution.
    Returns (True, "Valid syntax") on success, or (False, "Error message") on failure.
    """
    if not _is_safe_query(sql_query):
        return False, "Unsafe query detected: Only SELECT or WITH statements are allowed."

    conn = None
    try:
        conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT)
        with conn.cursor() as cur:
            cur.execute(f"EXPLAIN {sql_query}")
        return True, "Valid syntax"
    except psycopg2.Error as e:
        # Return a clean, simple error message
        error_message = str(e).splitlines()[0]
        return False, error_message
    except Exception as e:
        return False, f"An unexpected validation error occurred: {e}"
    finally:
        if conn:
            conn.close()

def execute_sql_query(sql_query: str) -> tuple[bool, str]:
    """
    Executes a pre-validated SQL query.
    Assumes `validate_sql_syntax` has already been called.
    """
    # Safety check is still a good idea, even if validation was done
    if not _is_safe_query(sql_query):
        return False, json.dumps({"error": "Unsafe query detected. Execution halted."})

    conn = None
    try:
        conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT)
        with conn.cursor() as cur:
            cur.execute(sql_query)
            
            if cur.description:
                columns = [desc[0] for desc in cur.description]
                raw_results = cur.fetchall()
                
                # Process results to handle non-serializable types like Decimal
                processed_results = []
                for row in raw_results:
                    processed_row = []
                    for item in row:
                        if isinstance(item, Decimal):
                            processed_row.append(float(item))
                        else:
                            processed_row.append(item)
                    processed_results.append(processed_row)
                
                return True, json.dumps({"columns": columns, "data": processed_results})
            else:
                # For statements that don't return rows
                return True, json.dumps({"status": "success", "rows_affected": cur.rowcount})

    except psycopg2.Error as e:
        error_message = f"Database execution error: {str(e).splitlines()[0]}"
        print(f"[ERROR] {error_message}\nQuery: {sql_query}")
        return False, json.dumps({"error": error_message})
    except Exception as e:
        error_message = f"An unexpected Python error occurred during execution: {e}"
        print(f"[ERROR] {error_message}")
        return False, json.dumps({"error": error_message})
    finally:
        if conn:
            conn.close()