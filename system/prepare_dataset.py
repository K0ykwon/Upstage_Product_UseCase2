import os
import json
from tqdm import tqdm
from typing import List, Dict, Any
import requests
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()

# Define paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DATA_DIR = os.path.join(BASE_DIR, 'data', 'raw', 'gov-report')
OUTPUT_DATA_PATH = os.path.join(BASE_DIR, 'data', 'govreport.json')

# Solar LLM API configuration
SOLAR_API_KEY = os.getenv('SOLAR_API_KEY')
SOLAR_API_URL = "https://api.upstage.ai/v1/solar/chat/completions"  # 예시 URL, 실제 URL로 수정 필요

def translate_with_solar(text: str) -> str:
    """
    Solar LLM을 사용하여 영어 텍스트를 한국어로 번역
    
    Args:
        text: 번역할 영어 텍스트
        
    Returns:
        번역된 한국어 텍스트
    """
    if not text.strip():
        return ""
        
    headers = {
        "Authorization": f"Bearer {SOLAR_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # 텍스트가 너무 길면 청크로 나누어 번역
    max_chunk_size = 4000  # Solar LLM의 최대 입력 길이에 맞게 조정 필요
    chunks = [text[i:i + max_chunk_size] for i in range(0, len(text), max_chunk_size)]
    translated_chunks = []
    
    for chunk in chunks:
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": "You are a professional translator. Translate the following English text to Korean. Maintain the original meaning and tone. If the text contains technical terms or proper nouns, translate them appropriately."
                },
                {
                    "role": "user",
                    "content": chunk
                }
            ],
            "temperature": 0.3,
            "max_tokens": 4000
        }
        
        try:
            response = requests.post(SOLAR_API_URL, headers=headers, json=payload)
            response.raise_for_status()
            translated_text = response.json()['choices'][0]['message']['content']
            translated_chunks.append(translated_text)
            
            # API 호출 간 딜레이
            time.sleep(1)
            
        except Exception as e:
            print(f"Translation error: {e}")
            # 에러 발생 시 원본 텍스트 반환
            translated_chunks.append(chunk)
    
    return " ".join(translated_chunks)

def extract_text_from_structured_report(report_data: Any) -> str:
    """
    Extracts plain text from the nested, structured report data.
    This is a basic implementation assuming the report structure contains strings or lists of strings.
    May need refinement based on the actual data structure.
    """
    if isinstance(report_data, str):
        return report_data
    elif isinstance(report_data, list):
        return " ".join([extract_text_from_structured_report(item) for item in report_data])
    elif isinstance(report_data, dict):
        # Recursively process values in dictionary, joining with spaces
        return " ".join([extract_text_from_structured_report(value) for value in report_data.values()])
    else:
        return "" # Handle other data types

def prepare_dataset(raw_data_dir: str, output_path: str):
    """
    Loads JSON files from raw_data_dir, extracts relevant info,
    translates to Korean, and saves as a single JSON list for processing.
    """
    all_documents = []
    report_folders = ['crs', 'gao']

    print(f"Loading data from: {raw_data_dir}")

    for folder_name in report_folders:
        folder_path = os.path.join(raw_data_dir, folder_name)
        if not os.path.exists(folder_path):
            print(f"Warning: Folder not found: {folder_path}. Skipping.")
            continue

        print(f"Processing folder: {folder_name}")
        json_files = [f for f in os.listdir(folder_path) if f.endswith('.json')]

        for file_name in tqdm(json_files, desc=f"Processing {folder_name} files"):
            file_path = os.path.join(folder_path, file_name)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    doc_data = json.load(f)

                doc_id = doc_data.get('id', file_name.replace('.json', ''))
                
                # Extract and clean English text
                raw_report_text = doc_data.get('report', '')
                cleaned_report_text = extract_text_from_structured_report(raw_report_text)
                
                # Translate to Korean
                print(f"\nTranslating document {doc_id}...")
                translated_text = translate_with_solar(cleaned_report_text)
                
                # Extract and translate summary
                summary_text = ""
                if folder_name == 'crs':
                    summary_text = doc_data.get('summary', '')
                elif folder_name == 'gao':
                    summary_data = doc_data.get('highlight', '')
                    summary_text = extract_text_from_structured_report(summary_data)
                
                # Translate summary
                if summary_text:
                    print(f"Translating summary for document {doc_id}...")
                    translated_summary = translate_with_solar(summary_text)
                else:
                    translated_summary = ""

                metadata = {
                    'title': doc_data.get('title', ''),
                    'released_date': doc_data.get('released_date', ''),
                    'published_date': doc_data.get('published_date', ''),
                    'url': doc_data.get('url', ''),
                    'source_folder': folder_name
                }

                all_documents.append({
                    'id': doc_id,
                    'text': translated_text,
                    'summary': translated_summary,
                    'metadata': metadata
                })

                # Save progress after each document
                output_dir = os.path.dirname(output_path)
                os.makedirs(output_dir, exist_ok=True)
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(all_documents, f, ensure_ascii=False, indent=2)

            except Exception as e:
                print(f"Error processing file {file_path}: {e}")
                continue

    print(f"Successfully prepared {len(all_documents)} documents.")

if __name__ == "__main__":
    if not SOLAR_API_KEY:
        raise ValueError("SOLAR_API_KEY environment variable is not set. Please set it in .env file.")
    
    prepare_dataset(RAW_DATA_DIR, OUTPUT_DATA_PATH) 