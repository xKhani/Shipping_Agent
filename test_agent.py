# test_agent.py
from agent.shipping_agent import agent_response # Import from your custom agent
# Removed 'import asyncio' as it's not needed for synchronous code

# No longer an async function
def main():
    print("--- Testing Custom Rule-Based Agent ---")

    # Make sure your database has some data in the tables if you want meaningful SQL results.
    # You can re-run 'python test_sql.py' if you have a script for dummy data.

    # Question 1: Should trigger SQL for account count
    question1 = "How many accounts are there?"
    print(f"\nQuestion 1: {question1}")
    response1 = agent_response(question1) # Direct call, no await
    print("🧠 Agent Response:\n", response1)
    print("-" * 30)

    # Question 2: Should trigger SQL for listing accounts
    question2 = "List the titles and types of the first 5 accounts."
    print(f"\nQuestion 2: {question2}")
    response2 = agent_response(question2) # Direct call
    print("🧠 Agent Response:\n", response2)
    print("-" * 30)

    # Question 3: Should trigger SQL for delayed shipments (if 'status' column exists in 'shipment' table)
    question3 = "How many shipments were delayed?"
    print(f"\nQuestion 3: {question3}")
    response3 = agent_response(question3) # Direct call
    print("🧠 Agent Response:\n", response3)
    print("-" * 30)

    # Question 4: Should fall back to LLM for general knowledge
    question4 = "Summarize the concept of a supply chain for me."
    print(f"\nQuestion 4: {question4}")
    response4 = agent_response(question4) # Direct call
    print("🧠 Agent Response:\n", response4)
    print("-" * 30)

# Run the synchronous main function
if __name__ == "__main__":
    main() 