# tools/utils.py
import re

def extract_sql_from_response(response: str) -> str:
    """
    Extracts the SQL query from the model's response.
    Prioritizes markdown code blocks, then falls back to trying to parse
    the response directly. Explicitly handles and removes '<s>' token.
    Includes extensive debugging prints.
    """
    print(f"\n[DEBUG - utils]: --- Starting extract_sql_from_response ---")
    print(f"[DEBUG - utils]: Initial raw response:\n'{response}'")

    if not response:
        print("[DEBUG - utils]: Response is empty, returning empty string.")
        return ""

    # Step 0: Robustly remove the '<s>' token immediately from the raw response
    # Using re.sub for more flexibility, accounting for potential leading/trailing whitespace around <s>
    # The \s* will match zero or more whitespace characters.
    cleaned_response = re.sub(r'\s*<s>\s*', '', response, flags=re.IGNORECASE).strip()
    print(f"[DEBUG - utils]: After stripping '<s>' (using regex) and initial .strip():\n'{cleaned_response}'")

    # 1. Try to find a SQL code block (e.g., ```sql ... ```)
    sql_block_match = re.search(r'```sql\n(.*?)```', cleaned_response, re.DOTALL)
    if sql_block_match:
        extracted = sql_block_match.group(1).strip()
        print(f"[DEBUG - utils]: Extracted from SQL code block:\n'{extracted}'")
        return extracted

    # 2. Try to find a generic code block (e.g., ``` ... ```)
    generic_block_match = re.search(r'```(?:\w+)?\n(.*?)```', cleaned_response, re.DOTALL)
    if generic_block_match:
        extracted_text = generic_block_match.group(1).strip()
        print(f"[DEBUG - utils]: Extracted from generic code block:\n'{extracted_text}'")
        # Basic check to see if the extracted text looks like SQL
        if re.match(r'^(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|EXPLAIN|WITH)\b', extracted_text, re.IGNORECASE):
            return extracted_text

    # 3. Fallback: Assume the cleaned response (or a significant part) is the SQL itself.
    # Remove common conversational prefixes or partial SQL prefixes if the model omitted SELECT
    cleaned_response_for_fallback = re.sub(
        r"^(?:Here is the SQL query:|The SQL query to answer the question is:|\n)\s*",
        "",
        cleaned_response,
        flags=re.IGNORECASE | re.MULTILINE
    ).strip()
    print(f"[DEBUG - utils]: After removing conversational prefixes (for fallback):\n'{cleaned_response_for_fallback}'")

    # If it now starts with a SQL keyword, return it
    if cleaned_response_for_fallback.lower().startswith(("select", "with", "insert", "update", "delete", "create", "alter", "drop", "explain")):
        print(f"[DEBUG - utils]: Fallback: Cleaned response starts with SQL keyword. Returning as-is.")
        return cleaned_response_for_fallback

    # Otherwise, assume it's the body of a SELECT clause and prepend SELECT
    print(f"[DEBUG - utils]: Fallback: Cleaned response does NOT start with SQL keyword. Prepending 'SELECT '.")
    return "SELECT " + cleaned_response_for_fallback