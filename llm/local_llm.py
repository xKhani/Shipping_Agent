# llm/local_llm.py
# Located at: D:\Shipping Agent\llm\local_llm.py

import requests
import json
from config import OLLAMA_API_BASE_URL, GENERAL_LLM_MODEL

def query_llm(prompt: str) -> str:
    """
    Sends a prompt to the local Ollama model (e.g., Mistral) for general queries.
    """
    try:
        response = requests.post(
            f"{OLLAMA_API_BASE_URL}/api/generate",
            json={
                "model": GENERAL_LLM_MODEL, # Uses the general LLM model from config
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": 1024} # Adjust as needed for response length
            },
            timeout=120 # Increased timeout for potentially longer LLM responses
        )
        response.raise_for_status()
        data = response.json()
        return data.get("response", "").strip()
    except requests.exceptions.ConnectionError:
        return f"Error: Could not connect to Ollama at {OLLAMA_API_BASE_URL}. Is 'ollama run {GENERAL_LLM_MODEL}' running?"
    except requests.exceptions.RequestException as e:
        return f"Error: Request to Ollama failed - {e}"
    except json.JSONDecodeError:
        return "Error: Invalid JSON response from Ollama."
    except Exception as e:
        return f"Error: An unexpected error occurred during LLM query - {e}"