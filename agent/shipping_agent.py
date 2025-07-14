# agent/shipping_agent.py
# Located at: D:\Shipping Agent\agent\shipping_agent.py
from tools.sql_tool import execute_sql_query
from tools.text_to_sql_tool import generate_sql_with_sqlcoder
from llm.local_llm import query_llm
import json

def agent_response(user_prompt: str) -> str:
    user_prompt_lower = user_prompt.lower()

    # === Rule 0: Explicitly route definitional/general questions to the general LLM ===
    general_query_keywords = [
        "what is", "explain", "tell me about", "define", "difference between",
        "how does", "what are", "who is", "why is", "when is", "where is",
        "describe", "meaning of", "tell me a joke", "capital of", "weather"
    ]

    if any(keyword in user_prompt_lower for keyword in general_query_keywords):
        print("[Agent]: Detected general/definitional query. Using general LLM (Mistral).")
        return query_llm(user_prompt)

    # === Rule 1: Handle data-related queries via SQLCoder ===
    data_keywords = [
        "how many", "count", "total", "shipment", "account", "order",
        "list", "show", "find", "get", "status", "date",
        "origin", "destination", "delayed", "from", "to", "region",
        "average", "sum", "max", "min", "group by", "filter by", "top"
    ]

    if any(keyword in user_prompt_lower for keyword in data_keywords):
        print("[Agent]: Detected data-related query. Generating SQL...")

        sql = generate_sql_with_sqlcoder(user_prompt)

        # Handle SQL generation errors
        if sql.startswith("-- SQLCoder error:"):
            return f"❌ SQL Generation Error:\n```\n{sql}\n```"
        if "error connecting to ollama" in sql.lower():
            return f"❌ SQLCoder Error: Could not connect to Ollama. Is 'ollama run sqlcoder' running?\nDetails:\n```sql\n{sql}\n```"
        if not sql.strip().lower().startswith("select"):
            return f"🚨 Invalid SQL generated (missing SELECT):\n```sql\n{sql}\n```"

        print(f"[Agent]: Generated SQL:\n```sql\n{sql}\n```")

        # === Step 2: Execute SQL and handle result ===
        try:
            # Unpack the tuple returned by execute_sql_query
            success, raw_result_data = execute_sql_query(sql)

            if not success:
                # If execution was not successful, raw_result_data is the error JSON string
                try:
                    error_data = json.loads(raw_result_data)
                    return f"❌ SQL Execution Error: {error_data.get('error', 'Unknown database error')}\n```sql\n{sql}\n```"
                except json.JSONDecodeError:
                    return f"❌ SQL Execution Error (invalid JSON format from DB tool):\n```\n{raw_result_data}\n```"

            # If execution was successful, raw_result_data is the result JSON string
            parsed_result = json.loads(raw_result_data)

            # --- MODIFIED LOGIC FOR HANDLING RESULTS ---
            final_response = ""
            if isinstance(parsed_result, dict) and "columns" in parsed_result and "data" in parsed_result:
                if not parsed_result["data"]: # Check if the 'data' list is empty
                    final_response = "📭 No matching records found for your query."
                else:
                    # Special case: count only
                    # Check if it's a single row with a 'count' key (common for COUNT(*) queries)
                    # AND ENSURE parsed_result["data"][0] IS A DICT
                    if (len(parsed_result["data"]) == 1 and
                        isinstance(parsed_result["data"][0], dict) and # <--- ADDED THIS CHECK
                        "count" in parsed_result["data"][0]):
                        final_response = f"📊 Found **{parsed_result['data'][0]['count']}** matching records."
                    # General case: tabular data
                    else:
                        rows = []
                        for i, row in enumerate(parsed_result["data"]): # Iterate over the 'data' list
                            # --- FIX START: Ensure 'row' is a dictionary before calling .items() ---
                            if not isinstance(row, dict):
                                print(f"[WARNING] Expected dictionary row for formatting, but got type: {type(row)}. Attempting conversion. Row content: {row}")
                                # Attempt to convert list/tuple row to dictionary using column names
                                if isinstance(row, (list, tuple)) and parsed_result.get("columns"):
                                    temp_row_dict = {}
                                    for j, col_val in enumerate(row):
                                        if j < len(parsed_result["columns"]):
                                            temp_row_dict[parsed_result["columns"][j]] = col_val
                                        else:
                                            # Fallback if data has more columns than listed, or unexpected structure
                                            temp_row_dict[f"unnamed_col_{j}"] = col_val
                                    row = temp_row_dict
                                else:
                                    # If conversion is not possible, add a specific error for this row
                                    items = [f"**ERROR**: Malformed or unparsable row data: {row}"]
                                    rows.append(f"{i+1}. " + ", ".join(items))
                                    continue # Skip to the next row
                            # --- FIX END ---

                            items = []
                            for key, value in row.items(): # This will now be safe if `row` is a dict
                                # Format UUIDs and timestamps for readability
                                if isinstance(value, str):
                                    if len(value) == 36 and '-' in value and value.count('-') == 4: # Basic UUID check
                                        value = f"`{value[:8]}...`"
                                    elif 'T' in value and ('-' in value or ':' in value): # Basic ISO datetime check
                                        value = value.split('T')[0] # Just show date part
                                items.append(f"**{key}**: {value}")
                            rows.append(f"{i+1}. " + ", ".join(items))
                        final_response = f"📦 Here’s what I found:\n\n" + "\n".join(rows)
            elif isinstance(parsed_result, dict) and "status" in parsed_result and parsed_result.get("status") == "success":
                # Handle non-SELECT queries that return a simple success message
                final_response = f"✅ Query executed successfully: {parsed_result.get('message', 'No specific message.')}"
            else: # Fallback for unexpected parsed_result format (e.g., if sql_tool.py returns something entirely different)
                final_response = f"📦 Unexpected Result Format from Database:\n```json\n{json.dumps(parsed_result, indent=2)}\n```"
            # --- END MODIFIED LOGIC ---
            
            # Add SQL query to the final answer for debugging
            return f"{final_response}\n\n--- 🧪 Generated SQL for debugging ---\n```sql\n{sql}\n```"


        except json.JSONDecodeError:
            # This catch is now for when raw_result_data is not a valid JSON string,
            # indicating a deeper issue within execute_sql_query's successful return
            return f"❌ Failed to parse database response as JSON.\nRaw data:\n```\n{raw_result_data}\n```"
        except Exception as e:
            # This catch is for any other unexpected Python errors during this agent's processing
            return f"⚠️ An unexpected error occurred during SQL result processing: {e}\n```sql\n{sql}\n```"

    # === Fallback: If no specific rule matches, use the general LLM ===
    print("[Agent]: No specific rule matched. Using general LLM (Mistral) as fallback.")
    return query_llm(user_prompt)