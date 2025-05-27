import requests
import os
from dotenv import load_dotenv
load_dotenv()

RAG_ENDPOINT = os.getenv("RAG_ENDPOINT", "http://localhost:8000/query")

if __name__ == "__main__":
    DB = ""
    embedding_model = ""
    rag_instance = (DB, embedding_model)
prompt = ""
# embedding_model(prompt, 3)

def call_rag_api(prompt: str, top_k: int = 3):
    return None