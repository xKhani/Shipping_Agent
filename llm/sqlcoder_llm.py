import requests
import json
from config import OLLAMA_API_BASE_URL, OLLAMA_MODEL  

def generate_sql(prompt: str) -> str:
    try:
        response = requests.post(
            f"{OLLAMA_API_BASE_URL}/api/generate",  
            json={
                "model": OLLAMA_MODEL, 
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": 2000}
            }
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except requests.exceptions.ConnectionError:
        return f"-- SQLCoder error: Could not connect to Ollama at {OLLAMA_API_BASE_URL}. Is 'ollama run {OLLAMA_MODEL}' running?"
    except requests.exceptions.RequestException as e:
        return f"-- SQLCoder error: Request failed - {e}"
    except json.JSONDecodeError:
        return "-- SQLCoder error: Invalid JSON response from Ollama."
    except Exception as e:
        return f"-- SQLCoder error: An unexpected error occurred - {e}"
