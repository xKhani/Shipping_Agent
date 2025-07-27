# agent/shipping_agent.py
import json
import os
from tools.sql_tool import execute_sql_query
from tools.text_to_sql_tool import generate_sql_with_sqlcoder, save_sql_history
from llm.local_llm import query_llm

# Path to history file
HISTORY_PATH = os.path.join(os.path.dirname(__file__), '..', 'tools', 'sql_history.json')

def agent_response(user_prompt: str) -> str:
    print(f"[DEBUG] Incoming prompt: {user_prompt}")
    user_prompt_lower = user_prompt.lower()

    # Explicit keywords for general LLM
    general_query_keywords = [
        "what is", "explain", "tell me about", "define", "difference between",
        "who is", "why is", "when is", "where is", "describe",
        "meaning of", "capital of", "weather", "joke"
    ]

    # Keywords that imply data queries
    data_keywords = [
        "how many", "count", "total", "shipment", "account", "order", "package",
        "list", "show", "find", "get", "status", "date", "origin", "destination",
        "delayed", "region", "average", "avg", "sum", "max", "min",
        "group by", "filter by", "top", "city", "cost"
    ]

    # Check if data query
    if any(keyword in user_prompt_lower for keyword in data_keywords):
        print("[Agent]: Detected data-related query. Generating SQL...")
        sql = generate_sql_with_sqlcoder(user_prompt)

        if sql.startswith("-- SQLCoder error:"):
            return f"❌ SQL Generation Error:\n```\n{sql}\n```"
        if not sql.strip().lower().startswith("select"):
            return f"🚨 Invalid SQL generated:\n```sql\n{sql}\n```"

        print(f"[Agent]: ✅ SQL generated:\n{sql}")

        try:
            success, raw_result_data = execute_sql_query(sql)
            if not success:
                try:
                    error_data = json.loads(raw_result_data)
                    return f"❌ SQL Execution Error: {error_data.get('error','Unknown error')}\n```sql\n{sql}\n```"
                except json.JSONDecodeError:
                    return f"❌ SQL Execution Error:\n```\n{raw_result_data}\n```"

            parsed_result = json.loads(raw_result_data)
            final_response = ""

            if isinstance(parsed_result, dict) and "columns" in parsed_result and "data" in parsed_result:
                if not parsed_result["data"]:
                    final_response = "📭 No matching records found."
                else:
                    if (
                        len(parsed_result["data"]) == 1 and
                        isinstance(parsed_result["data"][0], dict) and
                        any("count" in k.lower() for k in parsed_result["data"][0].keys())
                    ):
                        key = list(parsed_result["data"][0].keys())[0]
                        final_response = f"📊 Found **{parsed_result['data'][0][key]}** matching records."
                    else:
                        rows = []
                        for i, row in enumerate(parsed_result["data"]):
                            if not isinstance(row, dict):
                                if isinstance(row, (list, tuple)) and parsed_result.get("columns"):
                                    row = {parsed_result["columns"][j]: row[j] for j in range(len(row))}
                                else:
                                    rows.append(f"{i+1}. (Unparseable row: {row})")
                                    continue
                            items = []
                            for key, value in row.items():
                                if isinstance(value, str):
                                    if len(value) == 36 and value.count('-') == 4:
                                        value = f"`{value[:8]}...`"
                                    elif 'T' in value and ('-' in value or ':' in value):
                                        value = value.split('T')[0]
                                items.append(f"**{key}**: {value}")
                            rows.append(f"{i+1}. " + ", ".join(items))
                        final_response = f"📦 Results:\n\n" + "\n".join(rows)
            else:
                final_response = f"📦 Raw Result:\n```json\n{json.dumps(parsed_result,indent=2)}\n```"

            # ✅ Save to history for future few-shot examples
            save_sql_history(HISTORY_PATH, user_prompt, sql)

            return f"{final_response}\n\n--- 🧪 SQL ---\n```sql\n{sql}\n```"

        except Exception as e:
            return f"⚠️ Unexpected error: {e}\n```sql\n{sql}\n```"

    # Otherwise, definitional
    if any(keyword in user_prompt_lower for keyword in general_query_keywords):
        print("[Agent]: Detected general/definitional query. Using general LLM (Mistral).")
        return query_llm(user_prompt)

    # Fallback
    print("[Agent]: Fallback to general LLM.")
    return query_llm(user_prompt)
