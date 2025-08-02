# config.py
import os
from dotenv import load_dotenv

load_dotenv()  # Load variables from .env

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"), # <-- Load from .env
    "password": os.getenv("DB_PASSWORD") # <-- Load from .env
}

# Ollama Configuration
OLLAMA_API_BASE_URL = os.getenv("OLLAMA_API_BASE_URL", "http://localhost:11434/")
OLLAMA_MODEL = "qwen3:4b"
GENERAL_LLM_MODEL = os.getenv("GENERAL_LLM_MODEL", "mistral")


