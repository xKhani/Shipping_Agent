import requests
import json
import re
import os
from datetime import datetime
from tools.schema_loader import fetch_schema_text
from tools.sql_tool import validate_sql_syntax
from config import OLLAMA_API_BASE_URL, OLLAMA_MODEL

HISTORY_FILE = os.path.join("tools", "sql_history.json")
NEGATIVE_FILE = os.path.join("tools", "sql_negative_history.json")
MAX_ATTEMPTS = 10

def load_few_shot_examples():
    """Loads good examples from history to guide the LLM."""
    if not os.path.exists(HISTORY_FILE):
        return ""
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # Take the 5 most recent, non-error examples
        examples = "\n\n".join([f"User's request: {h['prompt']}\nSQL: {h['sql']}" for h in data[-5:]])
        return f"### Good Query Examples\n{examples}"
    except (json.JSONDecodeError, IOError, IndexError):
        return ""

def load_negative_examples():
    """Loads bad examples from history to show the LLM what to avoid."""
    if not os.path.exists(NEGATIVE_FILE):
        return ""
    try:
        with open(NEGATIVE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # Take the 3 most recent bad examples
        lines = [
            f"User's request: {h['prompt']}\n-- This is an example of a bad query to avoid:\n-- {h['bad_sql']}\n-- The error was: {h['reason']}"
            for h in data[-3:]
        ]
        return "\n\n### Bad Query Examples (What to Avoid)\n" + "\n\n".join(lines) if lines else ""
    except (json.JSONDecodeError, IOError, IndexError):
        return ""

def save_sql_history(prompt, sql):
    """Saves a successfully validated query to the history."""
    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except (json.JSONDecodeError, IOError):
            history = []
    history.append({"prompt": prompt, "sql": sql, "timestamp": datetime.now().isoformat()})
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history[-50:], f, indent=2)

def save_sql_negative_history(prompt, bad_sql, reason):
    """Saves a failed query and the reason for the failure."""
    history = []
    if os.path.exists(NEGATIVE_FILE):
        try:
            with open(NEGATIVE_FILE, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except (json.JSONDecodeError, IOError):
            history = []
    history.append({
        "prompt": prompt,
        "bad_sql": bad_sql,
        "reason": reason,
        "timestamp": datetime.now().isoformat()
    })
    with open(NEGATIVE_FILE, 'w', encoding='utf-8') as f:
        json.dump(history[-50:], f, indent=2)

def _call_llm(system_prompt: str, user_prompt: str) -> str:
    """
    A centralized function to call the Ollama API using the /api/chat endpoint.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    try:
        response = requests.post(
            f"{OLLAMA_API_BASE_URL}/api/chat",  # Use the /api/chat endpoint
            json={
                "model": OLLAMA_MODEL,
                "messages": messages,
                "stream": False,
                "options": {"temperature": 0.0} # num_predict is not needed for chat
            },
            timeout=90
        )
        response.raise_for_status()
        # The response structure is different for /api/chat
        return response.json().get("message", {}).get("content", "").strip()
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Ollama request failed: {e}")
        return f"-- SQL generation failed due to connection error: {e}"

def extract_sql_from_response(response: str) -> str:
    """
    A robust function to extract SQL from a markdown block.
    This is simpler and more reliable than the old multi-regex approach.
    """
    match = re.search(r'```sql\n(.*?)\n```', response, re.DOTALL)
    if match:
        sql = match.group(1).strip()
        # Remove trailing semicolon if it exists, which can cause issues with some DB drivers
        if sql.endswith(';'):
            sql = sql[:-1]
        return sql

    # Fallback: if no markdown, assume the whole response is the query
    response = response.strip()
    if response.lower().startswith("select"):
        if response.endswith(';'):
            response = response[:-1]
        return response
    
    return "" # Return empty if no SQL is found

def generate_and_validate_sql(user_prompt: str) -> str:
    """
    The main orchestrator for the "Generate, Validate, Correct" workflow.
    """
    schema_text, _, _, _ = fetch_schema_text()
    if schema_text.startswith("[ERROR]"):
        return f"-- SQL Generation Error: {schema_text}"
    
    # --- Build the System Prompt (the model's instructions) ---
    # This is sent once and contains the core rules and examples.
    
    # **CRITICAL CHANGE**: Load and include the examples!
    few_shot_examples = load_few_shot_examples()
    negative_examples = load_negative_examples()

    system_prompt = f"""
You are an expert PostgreSQL data analyst. Your sole purpose is to write correct, efficient, and syntactically valid PostgreSQL queries based on a user's request and a provided database schema.

### Response Requirements
1.  You MUST wrap the final PostgreSQL query in a single markdown block: ```sql\n[YOUR QUERY HERE]\n```.
2.  Do NOT include any other text, explanations, or comments outside the markdown block. The response should ONLY contain the markdown block with the SQL.

### Critical SQL Rules
1.  **DATES & SHIPMENTS:** The `shipment` table has NO date column. For any request about shipment dates (e.g., "when was it shipped?", "shipments in July"), you MUST JOIN `shipment` with `order` on `shipment."orderId" = "order"."id"` and use the `order."createdAt"` column for date filtering. Example: `... JOIN "order" o ON s."orderId" = o."id" WHERE EXTRACT(MONTH FROM o."createdAt") = 7`.
2.  **JOINING FOR ADDRESS:** To get city or address info for a shipment, you MUST JOIN `shipment` with `pii` on `shipment."shipToId" = pii."id"`.
3.  **COLUMN/TABLE QUOTING:** ALWAYS use double quotes around table and column names (e.g., "shipment", "createdAt"). NEVER use backticks (`).
4.  **DATE/TIME OUTPUT:** When selecting a date or timestamp column (like "createdAt"), cast it to a string using `::TEXT` to ensure it's readable. Example: `SELECT "createdAt"::TEXT FROM "order"`.
5.  **NON-EXISTENT COLUMNS:** The columns `shippedAt` and `deliveredAt` DO NOT EXIST. Do not hallucinate them. Use the rule #1 for shipment dates.
6.  **CLAUSE ORDER:** Always respect the SQL clause order: SELECT -> FROM -> JOIN -> WHERE -> GROUP BY -> ORDER BY -> LIMIT.

"""

    sql_candidate = ""
    last_error = "No valid SQL was generated by the model."
    current_user_prompt = f"""
### Database Schema
{schema_text}

---
### User's Request
{user_prompt}
"""

    for attempt in range(MAX_ATTEMPTS):
        print(f"[INFO] Text-to-SQL attempt {attempt + 1}/{MAX_ATTEMPTS}...")

        # For correction attempts, we modify the user prompt to include the error context.
        if attempt > 0:
            current_user_prompt = f"""
You previously generated an incorrect SQL query. Please analyze the error and fix it.
You MUST follow the rules provided in the system prompt. Pay special attention to the rules about dates and joins.

        ### Original Request
        {user_prompt}
        
        ### The FAILED SQL Query
        ```sql
        {sql_candidate}
        
        The Database Error Message
        
        "{last_error}"
        
        Database Schema
        
        {schema_text}
        
        Your task is to rewrite the query to fix the error. Return ONLY the corrected SQL in a markdown block.
        """
        
        raw_response = _call_llm(system_prompt, current_user_prompt)
        sql_candidate = extract_sql_from_response(raw_response)
    
        if not sql_candidate:
            print("[WARN] No SQL block found in the LLM response.")
            last_error = "No SQL block was found in the response."
            continue
        
        print(f"[DEBUG] Attempt {attempt + 1} generated SQL:\n{sql_candidate}")
    
        is_valid, error_or_success_msg = validate_sql_syntax(sql_candidate)
    
        if is_valid:
            print("[INFO] ✅ SQL syntax is valid.")
            save_sql_history(user_prompt, sql_candidate)
            return sql_candidate
        else:
            print(f"[WARN] ❌ SQL validation failed: {error_or_success_msg}")
            last_error = error_or_success_msg
            # The loop will now use the updated `current_user_prompt` for the next attempt
        
        # If all attempts fail
        print(f"[ERROR] All Text-to-SQL attempts failed for prompt: '{user_prompt}'")
