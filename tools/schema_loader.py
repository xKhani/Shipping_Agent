# tools/schema_loader.py

import requests
import json
import re
from Levenshtein import distance # Assuming you have python-Levenshtein installed
from collections import defaultdict # To group columns by table for fuzzy matching

# Define your OLLAMA_API_BASE_URL (replace with your actual URL or import from config)
# from config import OLLAMA_API_BASE_URL # Uncomment if you have this in config.py
OLLAMA_API_BASE_URL = "http://localhost:11434" # Default if not using config.py

def fetch_schema_text():
    try:
        # Fetch schema from Ollama's /api/tags endpoint or a predefined schema
        # For simplicity, let's use a hardcoded example schema similar to previous context
        # In a real application, this would dynamically pull from your DB or a schema service.
        
        # Example schema structure (replace with your actual schema details)
        schema_data = {
            "tables": [
                {
                    "name": "shipment",
                    "columns": [
                        {"name": "id", "type": "INTEGER", "description": "Primary key"},
                        {"name": "orderId", "type": "INTEGER", "description": "Foreign key to order table"},
                        {"name": "courierServiceTypeId", "type": "INTEGER", "description": "Foreign key to courier table"},
                        {"name": "deliveryDate", "type": "DATE", "description": "Date of delivery"},
                        {"name": "shipped", "type": "BOOLEAN", "description": "Whether the shipment has been shipped"},
                        {"name": "createdAt", "type": "TIMESTAMP", "description": "Timestamp of creation"}
                    ]
                },
                {
                    "name": "order",
                    "columns": [
                        {"name": "id", "type": "INTEGER", "description": "Primary key"},
                        {"name": "orderNumber", "type": "TEXT", "description": "Unique order identifier"},
                        {"name": "accountId", "type": "INTEGER", "description": "Foreign key to account table"}, # <--- Assuming this is the actual name
                        {"name": "shippingAccountId", "type": "INTEGER", "description": "Foreign key to shipping account table"},
                        {"name": "shipToId", "type": "INTEGER", "description": "Foreign key to shipment table for shipping address"}
                    ]
                },
                {
                    "name": "courier",
                    "columns": [
                        {"name": "id", "type": "INTEGER", "description": "Primary key"},
                        {"name": "name", "type": "TEXT", "description": "Name of the courier"}
                    ]
                },
                {
                    "name": "account",
                    "columns": [
                        {"name": "id", "type": "INTEGER", "description": "Primary key"},
                        {"name": "title", "type": "TEXT", "description": "Title of the account"}
                    ]
                }
                # ... add other tables as per your actual schema
            ],
            "relationships": [
                {"from_table": "shipment", "from_column": "orderId", "to_table": "order", "to_column": "id"},
                {"from_table": "shipment", "from_column": "courierServiceTypeId", "to_table": "courier", "to_column": "id"},
                {"from_table": "order", "from_column": "accountId", "to_table": "account", "to_column": "id"} # <--- Relationship using assumed 'accountId'
            ]
        }

        schema_text_lines = []
        column_lookup = {} # (table_lower, column_lower) -> original_column_name
        
        for table in schema_data["tables"]:
            table_name = table["name"]
            table_name_lower = table_name.lower()
            schema_text_lines.append(f"CREATE TABLE {table_name} (")
            col_definitions = []
            for col in table["columns"]:
                col_name = col["name"]
                col_type = col["type"]
                col_desc = col.get("description", "")
                
                col_definitions.append(f'  "{col_name}" {col_type} -- {col_desc}')
                column_lookup[(table_name_lower, col_name.lower())] = col_name
            schema_text_lines.append(",\n".join(col_definitions))
            schema_text_lines.append(");")

        relationships_text = []
        for rel in schema_data["relationships"]:
            relationships_text.append(
                f"-- {rel['from_table']}.{rel['from_column']} -> {rel['to_table']}.{rel['to_column']}"
            )
        
        full_schema_text = "\n".join(schema_text_lines) + "\n\n" + "\n".join(relationships_text)

        # print(f"[DEBUG] Generated Column Lookup: {column_lookup}") # Uncomment to see the full lookup table

        return full_schema_text, schema_data["relationships"], schema_data["tables"], column_lookup

    except Exception as e:
        return f"[ERROR] Failed to load schema: {e}", None, None, None

def correct_column_name(table_name_lower: str, column_name_from_sql_lower: str, column_lookup: dict) -> str:
    """
    Corrects a column name to its exact case as per the schema, or finds a fuzzy match.
    """
    print(f"[DEBUG-CORRECT_COL] Called for table '{table_name_lower}', column '{column_name_from_sql_lower}'")

    # 1. Direct match (case-insensitive)
    if (table_name_lower, column_name_from_sql_lower) in column_lookup:
        corrected = column_lookup[(table_name_lower, column_name_from_sql_lower)]
        print(f"[DEBUG-CORRECT_COL] Direct match found: '{corrected}'")
        return corrected

    # 2. Try fuzzy matching (Levenshtein distance)
    best_match_name = column_name_from_sql_lower
    min_distance = 2 # Max allowed Levenshtein distance for correction (e.g., 'id' vs 'ID' is 0, 'created_at' vs 'createdAt' might be higher)

    for (tbl_lower, col_lower), original_col_name in column_lookup.items():
        if tbl_lower == table_name_lower: # Only consider columns from the same table
            distance_val = distance(column_name_from_sql_lower, col_lower)
            if distance_val < min_distance:
                min_distance = distance_val
                best_match_name = original_col_name
    
    if best_match_name != column_name_from_sql_lower:
        print(f"[DEBUG-CORRECT_COL] Fuzzy match found: '{best_match_name}' (distance {min_distance}) for '{column_name_from_sql_lower}'")
        return best_match_name
    
    # 3. If no direct or fuzzy match, return the original lowercased column name from SQL
    # This means the column was not found in the schema or was too different.
    print(f"[DEBUG-CORRECT_COL] No correction found. Returning original: '{column_name_from_sql_lower}'")
    return column_name_from_sql_lower

if __name__ == "__main__":
    schema_text, rels, raw, col_lookup = fetch_schema_text()
    if schema_text.startswith("[ERROR]"):
        print(schema_text)
    else:
        print("\n--- SCHEMA TEXT ---")
        print(schema_text)
        print("\n--- RAW STRUCTURE ---")
        for t in raw:
            print(f"{t['name']}: {[c['name'] for c in t['columns']]}")
        print("\n--- COLUMN LOOKUP ---")
        for k, v in col_lookup.items():
            print(f"{k} -> {v}")
        print("\n--- TEST COLUMN CORRECTION ---")
        print(f"shipment.shippingaccountid -> shipment.{correct_column_name('shipment', 'shippingaccountid', col_lookup)}")
        print(f"order.order_number -> order.{correct_column_name('order', 'order_number', col_lookup)}") # Example of a common typo