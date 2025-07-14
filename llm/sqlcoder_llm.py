# llm/sqlcoder_llm.py
import requests
import json

def generate_sql(prompt: str) -> str:
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "sqlcoder", # <--- CHANGED THIS TO "sqlcoder"
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": 2000}
            }
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except requests.exceptions.ConnectionError:
        return "-- SQLCoder error: Could not connect to Ollama. Is 'ollama run sqlcoder' running?"
    except requests.exceptions.RequestException as e:
        return f"-- SQLCoder error: Request failed - {e}"
    except json.JSONDecodeError:
        return "-- SQLCoder error: Invalid JSON response from Ollama."
    except Exception as e:
        return f"-- SQLCoder error: An unexpected error occurred - {e}"