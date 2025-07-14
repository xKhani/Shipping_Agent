# tools/utils.py
import re

def extract_sql_from_response(response: str) -> str:
    """
    Extracts the SQL query from the model's response.
    Prioritizes markdown code blocks, then looks for 'SQL:' tags (especially the last one),
    and finally falls back to trying to parse the response directly.
    Includes extensive debugging prints.
    """
    print(f"\n[DEBUG - utils]: --- Starting extract_sql_from_response ---")
    print(f"[DEBUG - utils]: Initial raw response:\n'{response}'")

    if not response:
        print("[DEBUG - utils]: Response is empty, returning empty string.")
        return ""

    # Step 0: Robustly remove the '<s>' token immediately from the raw response
    cleaned_response = re.sub(r'\s*<s>\s*', '', response, flags=re.IGNORECASE).strip()
    # Also remove the </s> token if present
    cleaned_response = re.sub(r'\s*<\/s>\s*$', '', cleaned_response, flags=re.IGNORECASE).strip()
    print(f"[DEBUG - utils]: After stripping '<s>' and '</s>' (using regex) and initial .strip():\n'{cleaned_response}'")

    extracted_sql = ""

    # 1. Try to find a SQL code block (e.g., ```sql ... ```)
    sql_block_match = re.search(r'```sql\n(.*?)```', cleaned_response, re.DOTALL)
    if sql_block_match:
        extracted_sql = sql_block_match.group(1).strip()
        print(f"[DEBUG - utils]: Extracted from SQL code block:\n'{extracted_sql}'")
        # Go to final cleanup
        return _perform_final_sql_cleanup(extracted_sql)

    # 2. Try to find a generic code block (e.g., ``` ... ```)
    generic_block_match = re.search(r'```(?:\w+)?\n(.*?)```', cleaned_response, re.DOTALL)
    if generic_block_match:
        extracted_text = generic_block_match.group(1).strip()
        print(f"[DEBUG - utils]: Extracted from generic code block:\n'{extracted_text}'")
        # Basic check to see if the extracted text looks like SQL
        if re.match(r'^(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|EXPLAIN|WITH)\b', extracted_text, re.IGNORECASE):
            extracted_sql = extracted_text
            # Go to final cleanup
            return _perform_final_sql_cleanup(extracted_sql)

    # 3. NEW: Look for "SQL:" tags, especially the LAST one (for few-shot examples)
    # This regex attempts to capture the content immediately following "SQL:"
    # up until the next "User's request:", "SQL:", or the end of the string.
    # It's designed to work with multi-line responses containing examples.
    sql_segments = re.findall(
        r'(?:^|\n)\s*SQL:\s*(.*?)(?=\n\s*(?:User\'s request\s*:|SQL:)|$)',
        cleaned_response,
        re.IGNORECASE | re.DOTALL
    )
    
    if sql_segments:
        # The last captured segment is most likely the actual response to the current query.
        extracted_sql = sql_segments[-1].strip()
        print(f"[DEBUG - utils]: Extracted content after last 'SQL:' segment:\n'{extracted_sql}'")
        # Go to final cleanup
        return _perform_final_sql_cleanup(extracted_sql)
    else:
        print(f"[DEBUG - utils]: 'SQL:' tag pattern not found.")


    # 4. Fallback: Assume the cleaned response (or a significant part) is the SQL itself.
    # Remove common conversational prefixes or partial SQL prefixes if the model omitted SELECT
    extracted_sql = re.sub(
        r"^(?:Here is the SQL query:|The SQL query to answer the question is:|\n)\s*",
        "",
        cleaned_response, # Use cleaned_response here, as blocks/tags weren't found
        flags=re.IGNORECASE | re.MULTILINE
    ).strip()
    print(f"[DEBUG - utils]: After removing conversational prefixes (for fallback):\n'{extracted_sql}'")

    # Final check for fallback: if it now starts with a SQL keyword, return it
    if extracted_sql.lower().startswith(("select", "with", "insert", "update", "delete", "create", "alter", "drop", "explain")):
        print(f"[DEBUG - utils]: Fallback: Cleaned response starts with SQL keyword. Returning as-is.")
        return _perform_final_sql_cleanup(extracted_sql)
    else:
        # Otherwise, assume it's the body of a SELECT clause and prepend SELECT
        print(f"[DEBUG - utils]: Fallback: Cleaned response does NOT start with SQL keyword. Prepending 'SELECT '.")
        return _perform_final_sql_cleanup("SELECT " + extracted_sql)


def _perform_final_sql_cleanup(sql_string: str) -> str:
    """
    Helper function to apply final cleaning steps to the extracted SQL.
    """
    # Remove any stray markdown fences that might have been missed
    sql_string = re.sub(r"^(```sql|```)\s*", "", sql_string, flags=re.IGNORECASE | re.MULTILINE).strip()
    sql_string = re.sub(r"\s*```$", "", sql_string, flags=re.IGNORECASE | re.MULTILINE).strip()
    
    # Remove trailing semicolon for consistency
    final_sql = sql_string.rstrip(';').strip()

    # Final sanity check: if the extracted content doesn't seem like SQL, return empty.
    sql_keywords_start = ["SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP", "WITH", "TRUNCATE", "CALL", "EXEC"]
    if not any(final_sql.upper().startswith(kw) for kw in sql_keywords_start):
        print(f"[DEBUG - utils]: Final extracted content does not start with a common SQL keyword. Returning empty string.")
        return "" # Indicate that valid SQL could not be extracted

    print(f"[DEBUG - utils]: --- Finished extract_sql_from_response ---")
    print(f"[DEBUG - utils]: Final extracted SQL:\n'{final_sql}'")
    return final_sql