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
            return f"❌ Sorry, I couldn't understand your question properly. Could you please rephrase it in a different way?"

        print(f"[Agent]: ✅ Validated SQL received:\n{sql}")

        # 2. Execute the validated SQL
        success, raw_result_data = execute_sql_query(sql)

        if not success:
            try:
                error_data = json.loads(raw_result_data)
                error_msg = error_data.get('error', 'Unknown execution error')
            except json.JSONDecodeError:
                error_msg = raw_result_data
            return f"❌ Sorry, I encountered an error while processing your request. Please try asking your question in a different way."

        # 3. Format and return the result
        try:
            parsed_result = json.loads(raw_result_data)
            if not parsed_result.get("data"):
                return f"📭 No matching records found for your query. Try adjusting your search criteria."
            
            # Format the data for display
            columns = parsed_result.get("columns", [])
            data = parsed_result.get("data", [])
            
            # Create a structured response for the LLM
            if len(data) == 1 and len(columns) == 1:
                if "count" in columns[0].lower():
                    raw_response = f"Found {data[0][0]} records."
                else:
                    raw_response = f"Result: {data[0][0]}"
            else:
                # Create a more natural response based on the data
                if len(data) <= 5:  # For small datasets, show details
                    if "city" in str(columns).lower():
                        cities = [row[0] for row in data]
                        raw_response = f"Found {len(data)} cities: {', '.join(cities)}"
                    elif "courier" in str(columns).lower():
                        couriers = [row[0] for row in data]
                        raw_response = f"Found {len(data)} couriers: {', '.join(couriers)}"
                    elif "cost" in str(columns).lower():
                        total_cost = sum(float(row[0]) for row in data if str(row[0]).replace('.', '').isdigit())
                        raw_response = f"Total cost: ₨{total_cost:,.2f}"
                    else:
                        raw_response = f"Found {len(data)} records with {len(columns)} columns of data."
                else:
                    # For larger datasets, provide summary
                    raw_response = f"Found {len(data)} records. Here are the first few:\n"
                    # Show first 3 rows as examples
                    for i, row in enumerate(data[:3]):
                        raw_response += f"• {', '.join(map(str, row))}\n"
                    if len(data) > 3:
                        raw_response += f"... and {len(data) - 3} more records."

            # For data queries, provide direct formatted responses
            if len(data) <= 10:  # For small datasets, format directly
                if "average" in user_prompt.lower() and "cost" in user_prompt.lower():
                    # Format average cost data
                    response_lines = []
                    for row in data:
                        if len(row) >= 3:
                            city, courier, avg_cost, count = row[0], row[1], row[2], row[3]
                            response_lines.append(f"• {city} - {courier}: ₨{avg_cost:.2f} ({count} shipments)")
                    return "\n".join(response_lines)
                elif "count" in user_prompt.lower():
                    # Simple count response
                    return f"Found {len(data)} records"
                else:
                    # Generic list format
                    response_lines = []
                    for row in data:
                        response_lines.append(f"• {', '.join(map(str, row))}")
                    return "\n".join(response_lines)
            else:
                # For larger datasets, use LLM but with strict formatting
                llm_prompt = f"""
                Based on this shipping data query result, provide a concise, direct answer:

                Original Question: {user_prompt}
                Data Result: {raw_response}
                Columns: {columns}

                Please provide a simple, direct response that:
                1. Directly answers the user's question
                2. Uses bullet points or numbered lists for multiple items
                3. Keeps it brief and to the point
                4. Avoids formal email-like language
                5. Focus on the data, not analysis

                Format examples:
                - For counts: "Found X records"
                - For lists: "• Item 1\n• Item 2\n• Item 3"
                - For summaries: "Total: X, Average: Y, Highest: Z"
                
                Keep it simple and direct, not like an email.
                """

                return query_llm(llm_prompt)

        except Exception as e:
            return f"⚠️ Sorry, I had trouble formatting the results. Please try asking your question again."
    else:
        print("[Agent]: Detected general query. Using general LLM...")
        return query_llm(user_prompt)