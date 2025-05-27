import streamlit as st
import requests
import os
import json
from dotenv import load_dotenv
from bs4 import BeautifulSoup
load_dotenv()

UPSTAGE_API_KEY = os.getenv("UPSTAGE_API_KEY")

def process_document(file_bytes, force_ocr: bool):
    url = "https://api.upstage.ai/v1/document-digitization"
    headers = {"Authorization": f"Bearer {UPSTAGE_API_KEY}"}
    files   = {
        "document": ("document.pdf", file_bytes, "application/pdf")
    }
    data = {
        "ocr": "force" if force_ocr else "auto",
        "coordinates": "true",
        "chart_recognition": "false",
        "output_formats": json.dumps(["html"]),
        "model": "document-parse",
        "base64_encoding": json.dumps([])
    }

    try:
        response = requests.post(url, headers=headers, files=files, data=data)
        response.raise_for_status()
        result = response.json()

        html_content = result.get("content", {}).get("html", "").strip()

        if not html_content:
            st.warning("No plain text found in the document.")
            return None, None
        
        soup = BeautifulSoup(html_content, "html.parser")
        plain_text = soup.get_text("\n")

        return plain_text, None
    
    except Exception as e:
        return None, e
    
