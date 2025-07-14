# tools/text_to_sql_tool.py
import requests
import json
import re

# IMPORTANT: Ensure these imports are correct and files exist
from tools.schema_loader import fetch_schema_text, correct_column_name
from config import OLLAMA_API_BASE_URL, OLLAMA_MODEL
from tools.utils import extract_sql_from_response # Assuming this is your robust extractor

# Define a set of PostgreSQL reserved keywords that might be used as table names
# and need quoting. Expand this list as needed based on observed errors.
RESERVED_TABLES = {
    "order", "user", "group", "select", "where", "limit", "offset",
    "index", "column", "table", "from", "join", "by", "for"
}

# A comprehensive set of common SQL keywords to avoid accidentally quoting/correcting them as columns.
# This list helps the bare column corrector distinguish keywords from actual column names.
SQL_KEYWORDS = {
    "select", "from", "join", "where", "and", "or", "not", "as", "on", "in", "is", "null", "true", "false",
    "like", "ilike", "between", "case", "when", "then", "else", "end", "count", "sum", "avg", "min", "max",
    "distinct", "union", "except", "intersect", "having", "with", "values", "insert", "update", "delete",
    "set", "alter", "drop", "create", "table", "column", "view", "index", "function", "cast", "to",
    "now", "current_date", "current_timestamp", "date_trunc", "extract", "to_char", "nulls", "last", "first",
    "asc", "desc", "limit", "offset", "group by", "order by" # Extended keywords
}
# Add lowercased reserved tables to keywords to prevent them from being treated as bare columns
SQL_KEYWORDS.update({t.lower() for t in RESERVED_TABLES})


def quote_reserved_tables(sql_query: str) -> str:
    """
    Replaces unquoted reserved PostgreSQL table names with their quoted equivalents
    in FROM and JOIN clauses only.
    E.g., 'FROM order o' becomes 'FROM "order" o'
    """
    def replacer(match):
        keyword = match.group(1) # 'FROM' or 'JOIN'
        table_name = match.group(3).strip('"') # The actual table name (e.g., 'order')
        alias = match.group(4) or '' # The alias (e.g., 'o')

        if table_name.lower() in RESERVED_TABLES:
            # Reconstruct with quotes. Preserve original casing of table_name from SQL if possible.
            return f'{keyword} "{table_name}"{(" " + alias) if alias else ""}'
        return match.group(0) # No change if not reserved

    # Regex: (FROM|JOIN) followed by optional quotes, then table name, then optional alias
    # Group 1: FROM/JOIN, Group 2: opening quote, Group 3: table name, Group 4: alias
    return re.sub(r'(\bFROM\b|\bJOIN\b)\s+("?)([a-zA-Z_][a-zA-Z0-9_]*)\2\s*(\w*)?', replacer, sql_query, flags=re.IGNORECASE)


def clean_sql_with_schema_grounding(sql_query: str, schema_raw: list, column_lookup: dict) -> str:
    """
    Performs multi-pass post-processing on the generated SQL:
    1. Identifies table aliases.
    2. Corrects table.column (or alias.column) references to use correct casing and quoting.
    3. Corrects bare (unqualified) column names to use correct casing and quoting.
    4. Removes joins on hallucinated tables.
    """
    cleaned_sql = sql_query
    
    # --- Pass 1: Identify table aliases and active table names ---
    alias_map = {} # alias_lower -> actual_table_name_lower
    active_table_names_lower = set() # To store all unique lowercased actual table names in the query
    
    # This regex captures table names and their aliases from FROM/JOIN clauses
    # Group 2: table_name (unquoted)
    # Group 4: alias (unquoted, if 'AS' is used)
    table_alias_pattern = re.compile(
        r'(?:FROM|JOIN)\s+(?:("?)([\w_]+)\1)(?:\s+AS\s+("?)([\w_]+)\3)?',
        flags=re.IGNORECASE
    )
    
    for match in table_alias_pattern.finditer(cleaned_sql):
        table_name_in_sql = match.group(2).strip('"').lower()
        if match.group(4): # If an explicit alias is used (e.g., `table AS alias`)
            alias = match.group(4).strip('"').lower()
            alias_map[alias] = table_name_in_sql
        else: # If no explicit alias, the table name itself can act as an implicit alias
            alias_map[table_name_in_sql] = table_name_in_sql
        active_table_names_lower.add(table_name_in_sql)

    print(f"[DEBUG] Alias Map: {alias_map}")
    print(f"[DEBUG] Active Table Names: {active_table_names_lower}")

    # Determine the primary table for bare column grounding (heuristic: first table in FROM clause)
    main_table_for_bare_columns = None
    from_clause_match = re.search(r'\bFROM\s+("?)([\w_]+)\1', cleaned_sql, flags=re.IGNORECASE)
    if from_clause_match:
        candidate_table = from_clause_match.group(2).strip('"').lower()
        main_table_for_bare_columns = alias_map.get(candidate_table, candidate_table) # Resolve alias if it was main table

    if main_table_for_bare_columns:
        print(f"[DEBUG] Main table for bare column grounding: '{main_table_for_bare_columns}'")


    # --- Pass 2: Correct `table.column` or `alias.column` references ---
    def replace_table_column_reference(match):
        # match.group(1) is the full table/alias part (e.g., "s" or "shipment")
        # match.group(2) is the unquoted table/alias name (e.g., "s" or "shipment")
        # match.group(3) is the full column part (e.g., "id" or "order_number")
        # match.group(4) is the unquoted column name (e.g., "id" or "order_number")
        
        table_or_alias_part_original = match.group(1) # Keep original for output
        table_or_alias_part_lower = match.group(2).strip('"').lower() 
        column_part_from_sql_lower = match.group(4).strip('"').lower() 

        # Resolve alias to actual schema table name (lowercase)
        actual_table_name_lower = alias_map.get(table_or_alias_part_lower, table_or_alias_part_lower)
        
        # Get the correctly cased column name from schema_loader's lookup
        corrected_column = correct_column_name(
            actual_table_name_lower, 
            column_part_from_sql_lower,
            column_lookup
        )
        # Reconstruct: use the original table/alias part from SQL, and the corrected, quoted column name.
        return f'{table_or_alias_part_original.strip('"')}. "{corrected_column}"' 

    # Regex: ("?word"?).("?word"?)
    # This matches `table.column`, `alias.column`, `"table".column`, `table."column"`, etc.
    cleaned_sql = re.sub(
        r'("?([a-zA-Z_][a-zA-Z0-9_]*)"?)\.("?([a-zA-Z_][a-zA-Z0-9_]*)"?)',
        lambda m: replace_table_column_reference(m), 
        cleaned_sql, 
        flags=re.IGNORECASE
    )


    # --- Pass 3: Correct bare (unqualified) column names ---
    # This regex aims to find standalone words that are potential column names.
    # It avoids words that are:
    # - Preceded by a dot (e.g., `table.column`) or a quote and a dot (`"table".column`)
    # - Followed by an opening parenthesis (likely a function call)
    # - Known SQL keywords (handled by the callback)
    
    # Pattern to find words that are not part of table.column or alias.column, and not function calls
    # `(?<![."])`: Negative lookbehind to ensure not preceded by dot or quote
    # `\b([a-zA-Z_][a-zA-Z0-9_]*)\b`: Capture the word
    # `(?!\s*\()`: Negative lookahead to ensure not followed by optional whitespace and an open parenthesis
    pattern_bare_column = re.compile(r'(?<![."])\b([a-zA-Z_][a-zA-Z0-9_]*)\b(?!\s*\()', re.IGNORECASE)

    def bare_column_corrector(match):
        bare_identifier = match.group(1) # The captured word (e.g., 'shipped', 'delivery_date')
        lower_identifier = bare_identifier.lower()

        # Skip if it's a known SQL keyword (case-insensitive check)
        if lower_identifier in SQL_KEYWORDS:
            return bare_identifier # Return original, unchanged
        
        # Skip if it's a number (e.g., '1', '1.0')
        if re.fullmatch(r'\d+(\.\d+)?', bare_identifier):
            return bare_identifier

        # Skip if it's an alias itself (e.g., 's', 'o')
        if lower_identifier in alias_map:
            return bare_identifier

        # Attempt to correct and quote the bare column name
        corrected_name = bare_identifier # Default: no change, use original casing

        # Try to ground this bare column to the main table identified, or any active table
        if main_table_for_bare_columns:
            temp_corrected = correct_column_name(main_table_for_bare_columns, lower_identifier, column_lookup)
            if temp_corrected.lower() != lower_identifier: # If a correction was found (casing or fuzzy)
                corrected_name = temp_corrected
                print(f"[INFO] Schema Grounding: Correcting bare column '{bare_identifier}' to '\"{corrected_name}\"' (table: {main_table_for_bare_columns})")
                return f'"{corrected_name}"'
            elif (main_table_for_bare_columns, lower_identifier) in column_lookup:
                # It's correctly cased but not quoted, and exists in main table
                corrected_name = column_lookup[(main_table_for_bare_columns, lower_identifier)]
                print(f"[INFO] Schema Grounding: Quoting bare column '{bare_identifier}' to '\"{corrected_name}\"' (table: {main_table_for_bare_columns})")
                return f'"{corrected_name}"'
        
        # Fallback: If no main table context, or no correction found in main table,
        # try to find it in *any* active table and quote it.
        for alias_lower, actual_table_lower in alias_map.items():
            if (actual_table_lower, lower_identifier) in column_lookup:
                corrected_name = column_lookup[(actual_table_lower, lower_identifier)]
                print(f"[INFO] Schema Grounding: Quoting ambiguous bare column '{bare_identifier}' to '\"{corrected_name}\"' (found in {actual_table_lower})")
                return f'"{corrected_name}"'
            # Also check fuzzy matches in other tables
            temp_corrected = correct_column_name(actual_table_lower, lower_identifier, column_lookup)
            if temp_corrected.lower() != lower_identifier:
                corrected_name = temp_corrected
                print(f"[INFO] Schema Grounding: Correcting ambiguous bare column '{bare_identifier}' to '\"{corrected_name}\"' (fuzzy match in {actual_table_lower})")
                return f'"{corrected_name}"'

        return bare_identifier # Return original if no correction or quoting.

    # Apply the bare column quoting/correction after table.column correction
    cleaned_sql = pattern_bare_column.sub(bare_column_corrector, cleaned_sql)


    # --- Pass 4: Remove hallucinated JOINs ---
    valid_tables = {t["name"].lower() for t in schema_raw}
    temp_sql = cleaned_sql
    # Regex to capture the full JOIN clause
    # Group 2: Table name before AS (if alias not used)
    # Group 4: Alias name after AS (if AS is used)
    join_pattern = re.compile(r'\bJOIN\s+("?)([a-zA-Z_][a-zA-Z0-9_]*)\1(?:\s+AS\s+("?)([a-zA-Z_][a-zA-Z0-9_]*)\3)?\s+ON\s+.*?(?=\b(?:JOIN|WHERE|GROUP BY|ORDER BY|LIMIT|OFFSET|;)\b|$)', flags=re.IGNORECASE | re.DOTALL)
    matches = list(join_pattern.finditer(temp_sql))

    print(f"[DEBUG-JOIN] Valid Tables in Schema: {valid_tables}")

    for match in reversed(matches): # Process from right to left to avoid index issues
        full_join_clause = match.group(0)
        # Prioritize alias (group 4) if it exists, otherwise use the direct table name (group 2)
        joined_table_name_in_sql = (match.group(4) or match.group(2)).strip('"')
        
        # Resolve the alias to its true table name for schema validation
        resolved_joined_table_name = alias_map.get(joined_table_name_in_sql.lower(), joined_table_name_in_sql.lower())

        print(f"[DEBUG-JOIN] Processing JOIN clause: '{full_join_clause}'")
        print(f"[DEBUG-JOIN] Identified table/alias in SQL: '{joined_table_name_in_sql}'")
        print(f"[DEBUG-JOIN] Resolved table name for validation: '{resolved_joined_table_name}'")
        print(f"[DEBUG-JOIN] Check if '{resolved_joined_table_name}' in valid_tables: {resolved_joined_table_name in valid_tables}")

        if resolved_joined_table_name not in valid_tables:
            print(f"[INFO] Schema Grounding: Removing hallucinated JOIN on table: '{joined_table_name_in_sql}' (resolved to '{resolved_joined_table_name}')")
            # Remove the full join clause and replace with a single space
            temp_sql = temp_sql[:match.start()] + ' ' + temp_sql[match.end():]
            # Cleanup residual 'AND'/'OR' and excessive whitespace
            temp_sql = re.sub(r'\s+(AND|OR)\s+(AND|OR)\s*', r' \1 ', temp_sql, flags=re.IGNORECASE)
            temp_sql = re.sub(r'\s*(AND|OR)\s*(WHERE|GROUP|ORDER|HAVING|LIMIT|$)', r' \2', temp_sql, flags=re.IGNORECASE)
            temp_sql = re.sub(r'\s+(AND|OR)\s*$', '', temp_sql, flags=re.IGNORECASE)
            temp_sql = re.sub(r'\s{2,}', ' ', temp_sql).strip()

    cleaned_sql = temp_sql
    print(f"[DEBUG] Schema Grounding: SQL after schema-aware cleaning:\n'{cleaned_sql}'")
    return cleaned_sql


def generate_sql_with_sqlcoder(user_prompt: str) -> str:
    """
    Given a natural language question, this function queries SQLCoder (via Ollama)
    using the live database schema and returns the generated SQL.
    """
    try:
        # Fetch schema details, including raw schema and column lookup
        schema_text, relationships, schema_raw, column_lookup = fetch_schema_text()
        
        # Debug prints from previous issue (can be removed later if not needed)
        print(f"[DEBUG] Type of schema_text (from fetch_schema_text): {type(schema_text)}")
        if isinstance(schema_text, tuple):
            print(f"[DEBUG] Value of schema_text (if tuple): {schema_text}")
        else:
            print(f"[DEBUG] Value of schema_text (first 100 chars if string): {str(schema_text)[:100]}")

        if schema_text.startswith("[ERROR]"):
            return f"-- SQLCoder error: {schema_text}"

        print(f"\n[DEBUG] Schema Text Provided to SQLCoder:\n{schema_text}\n")

        # --- CORRECTED FEW-SHOT EXAMPLES HERE ---
        # The examples now explicitly include the "User's request:" and "SQL:" prefixes
        # to teach the model the exact input/output format.
        examples = """
User's request: How many shipments are currently pending?
SQL: SELECT COUNT(*) FROM shipment WHERE "internalStatus" = 'pending';

User's request: List all accounts created after 2024-01-01.
SQL: SELECT id, type, title FROM account WHERE "createdAt" > '2024-01-01';

User's request: Show the total cost of all shipments.
SQL: SELECT SUM(cost) FROM shipment;
"""

        prompt = f"""
You are a PostgreSQL SQL expert.
Based on the following schema, write a SQL query to answer the user's request.
Only return the SQL query, and nothing else. Do not add any explanations or text.

{schema_text}

{examples}

User's request: {user_prompt}
SQL:
"""

        response = requests.post(
            f"{OLLAMA_API_BASE_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": 2000}
            },
            timeout=60
        )
        response.raise_for_status()
        raw_response = response.json().get("response", "").strip()
        print("[DEBUG] Raw response from SQLCoder:\n", raw_response)

        extracted_sql = extract_sql_from_response(raw_response)
        
        # CORRECTED ORDER: Quote reserved tables first, then perform schema grounding
        # This ensures reserved table names are quoted BEFORE alias mapping and column grounding.
        sql_with_reserved_quoted = quote_reserved_tables(extracted_sql)

        # Apply schema grounding: alias resolution, table.column correction, bare column correction, hallucinated JOIN removal
        final_sql = clean_sql_with_schema_grounding(sql_with_reserved_quoted, schema_raw, column_lookup)

        # --- NEW FIX FOR ORDER BY ON COUNT(*) ---
        # This fix is applied *after* all other grounding, as it's a semantic correction.
        if re.match(r"^\s*SELECT\s+COUNT\s*\(\*\)\s+FROM", final_sql, re.IGNORECASE):
            # Remove any ORDER BY clause from such queries
            # This regex will remove 'ORDER BY ...' from the end of the query string.
            final_sql = re.sub(r"\s+ORDER BY\s+.*$", "", final_sql, flags=re.IGNORECASE).strip()
            print("[DEBUG] Removed ORDER BY from COUNT(*) query.")
        # --- END NEW FIX ---


        if final_sql.strip().lower() in ["select", "select;"]:
            return "⚠️ SQL generation failed — query was incomplete. Please try rephrasing."

        print("[DEBUG] Final Processed SQL (after all cleanup and quoting):\n", final_sql)
        return final_sql

    except requests.exceptions.ConnectionError:
        return f"-- SQLCoder error: Could not connect to Ollama at {OLLAMA_API_BASE_URL}. Is 'ollama run {OLLAMA_MODEL}' running?"
    except requests.exceptions.RequestException as e:
        return f"-- SQLCoder error: Request failed - {e}"
    except json.JSONDecodeError:
        return "-- SQLCoder error: Invalid JSON response from Ollama."
    except Exception as e:
        return f"-- SQLCoder error: An unexpected error occurred - {e}"


if __name__ == "__main__":
    user_input = input("Ask your data question: ")
    sql = generate_sql_with_sqlcoder(user_input)
    print("\nGenerated SQL:\n", sql)