# agent/shipping_agent.py
import json
import os
from tools.sql_tool import execute_sql_query
from tools.text_to_sql_tool import generate_and_validate_sql, save_sql_history
from llm.local_llm import query_llm

DATA_KEYWORDS = [
    "how many", "count", "total", "shipment", "account", "order", "package",
    "list", "show", "find", "get", "status", "date", "origin", "destination",
    "delayed", "region", "average", "avg", "sum", "max", "min", "most", "least",
    "group by", "filter by", "top", "city", "cost", "courier"
]

def agent_response(user_prompt: str) -> str:
    print(f"\n[DEBUG] Incoming prompt: {user_prompt}")
    
    # Simple keyword-based routing
    if any(keyword in user_prompt.lower() for keyword in DATA_KEYWORDS):
        print("[Agent]: Detected data-related query. Engaging Text-to-SQL tool...")
        
        # 1. Generate and Validate SQL using the new robust workflow
        # This function now handles generation, validation, and self-correction.
        sql = generate_and_validate_sql(user_prompt)

        # Check if the generation process failed
        if sql.startswith("--"):
            return f"❌ SQL Generation Error:\nAn error occurred while creating the query.\n\n**Details**:\n```{sql}```"

        print(f"[Agent]: ✅ Validated SQL received:\n{sql}")

        # 2. Execute the validated SQL
        success, raw_result_data = execute_sql_query(sql)

        if not success:
            try:
                error_data = json.loads(raw_result_data)
                error_msg = error_data.get('error', 'Unknown execution error')
            except json.JSONDecodeError:
                error_msg = raw_result_data
            return f"❌ SQL Execution Error:\n{error_msg}\n\n**Query**:\n```sql\n{sql}\n```"

        # 3. Format and return the result
        try:
            parsed_result = json.loads(raw_result_data)
            if not parsed_result.get("data"):
                return f"📭 No matching records found.\n\n--- 🧪 SQL ---\n```sql\n{sql}\n```"
            
            # Format the data for display
            columns = parsed_result.get("columns", [])
            data = parsed_result.get("data", [])
            
            # Simple count formatting
            if len(data) == 1 and len(columns) == 1 and "count" in columns[0].lower():
                 final_response = f"📊 Found **{data[0][0]}** matching records."
            else:
                 # Generic table formatting
                header = f"| {' | '.join(columns)} |"
                separator = f"|{'|'.join(['---'] * len(columns))}|"
                rows = [f"| {' | '.join(map(str, row))} |" for row in data]
                final_response = f"📦 Query Results:\n\n{header}\n{separator}\n" + "\n".join(rows)

            return f"{final_response}\n\n--- 🧪 SQL ---\n```sql\n{sql}\n```"

        except Exception as e:
            return f"⚠️ Error formatting results: {e}\n\n**Raw Data**:\n```json\n{raw_result_data}\n```\n\n**Query**:\n```sql\n{sql}\n```"
    else:
        print("[Agent]: Detected general query. Using general LLM...")
        return query_llm(user_prompt)