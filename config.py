# config.py
import os
from dotenv import load_dotenv

load_dotenv() # This line loads variables from your .env file into os.environ

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"), # Default to localhost if not found in .env
    "port": os.getenv("DB_PORT", 5432),       # Default to 5432 if not found
    "dbname": os.getenv("DB_NAME"),           # Must be provided in .env
    "user": os.getenv("DB_USER"),             # Must be provided in .env
    "password": os.getenv("DB_PASSWORD"),     # Must be provided in .env
}


# Ollama Configuration
OLLAMA_API_BASE_URL = os.getenv("OLLAMA_API_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "sqlcoder") # Model for SQL generation (e.g., "sqlcoder")
GENERAL_LLM_MODEL = os.getenv("GENERAL_LLM_MODEL", "mistral") # Model for general chat (e.g., "mistral")
