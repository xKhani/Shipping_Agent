from llm.local_llm import query_llm

print("--- Testing Local LLM (Mistral) ---")
prompt = "Summarize shipment delays in plain English"
response = query_llm(prompt)
print(f"Prompt: {prompt}")
print(f"Response: {response}")
print("-" * 30)

prompt2 = "Write a very short poem about a cat."
response2 = query_llm(prompt2)
print(f"Prompt: {prompt2}")
print(f"Response: {response2}")
print("-" * 30)