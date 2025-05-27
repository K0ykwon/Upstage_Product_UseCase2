import os
import json
import requests
from tqdm import tqdm
import logging
from dotenv import load_dotenv
import pandas as pd
from datetime import datetime
import re
from bs4 import BeautifulSoup

# 환경 변수 로드
load_dotenv()

# Get the absolute path to the project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(PROJECT_ROOT, 'data', 'logs', 'document_parsing.log')),
        logging.StreamHandler()
    ]
)

def clean_html(html_content):
    """HTML에서 불필요한 요소를 제거하고 텍스트만 추출"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 제거할 요소들
    elements_to_remove = [
        # 페이지 번호 (일반적인 패턴)
        soup.find_all('div', class_=lambda x: x and ('page' in x.lower() or 'pagenum' in x.lower())),
        soup.find_all('span', class_=lambda x: x and ('page' in x.lower() or 'pagenum' in x.lower())),
        
        # 머리말/꼬리말
        soup.find_all('header'),
        soup.find_all('footer'),
        
        # 목차 (TOC)
        soup.find_all('div', class_=lambda x: x and 'toc' in x.lower()),
        soup.find_all('div', id=lambda x: x and 'toc' in x.lower()),
        
        # 표 캡션
        soup.find_all('caption'),
        
        # 페이지 번호를 포함할 수 있는 다른 요소들
        soup.find_all('div', style=lambda x: x and 'page' in x.lower()),
        soup.find_all('span', style=lambda x: x and 'page' in x.lower())
    ]
    
    # 모든 제거할 요소들을 평탄화
    for elements in elements_to_remove:
        for element in elements:
            element.decompose()
    
    # 연속된 공백 제거 및 텍스트 정리
    text = soup.get_text(separator=' ', strip=True)
    text = re.sub(r'\s+', ' ', text)  # 여러 공백을 하나로
    text = re.sub(r'\n\s*\n', '\n', text)  # 빈 줄 제거
    
    # "Ordering Information" 이후의 내용 제거
    ordering_info_index = text.find("Ordering Information")
    if ordering_info_index != -1:
        text = text[:ordering_info_index].strip()
    
    return text.strip()

def extract_text_with_upstage(pdf_path: str) -> dict:
    """
    Upstage Document Parsing API를 사용하여 PDF에서 텍스트와 테이블을 추출합니다.
    """
    try:
        api_key = os.getenv('UPSTAGE_API_KEY')
        if not api_key:
            raise ValueError("UPSTAGE_API_KEY environment variable is not set")

        url = "https://api.upstage.ai/v1/document-digitization"
        headers = {"Authorization": f"Bearer {api_key}"}
        files = {"document": open(pdf_path, "rb")}
        data = {
            "ocr": "force",
            "base64_encoding": "['table']",
            "model": "document-parse"
        }

        logging.info(f"Sending request to Upstage API for {pdf_path}")
        response = requests.post(url, headers=headers, files=files, data=data)
        
        if response.status_code == 200:
            result = response.json()
            logging.info(f"API Response for {pdf_path}: {json.dumps(result, indent=2)}")

            # content에서 html 추출 후 태그 제거
            html_content = result.get('content', {}).get('html', '')
            clean_text = clean_html(html_content)
            logging.info(f"Extracted and cleaned text for {pdf_path}: {repr(clean_text[:500])}")

            return {
                'text': clean_text,
                'tables': result.get('tables', []),
                'metadata': result.get('metadata', {})
            }
        else:
            logging.error(f"Document Parsing API error for {pdf_path}:")
            logging.error(f"Status code: {response.status_code}")
            logging.error(f"Response headers: {dict(response.headers)}")
            logging.error(f"Response text: {response.text}")
            return {'text': '', 'tables': [], 'metadata': {}}
            
    except Exception as e:
        logging.error(f"Error extracting text from PDF {pdf_path}: {str(e)}")
        return {'text': '', 'tables': [], 'metadata': {}}

def save_document_data(doc_data: dict, output_dir: str, base_filename: str):
    """
    문서 데이터를 JSON 파일로 저장합니다.
    """
    # 문서 메타데이터와 텍스트 저장
    doc_json = {
        'filename': base_filename,
        'text': doc_data['text'],
        'metadata': doc_data['metadata'],
        'processed_at': datetime.now().isoformat()
    }
    
    # 테이블이 있는 경우 별도로 저장
    if doc_data['tables']:
        tables_dir = os.path.join(output_dir, 'tables')
        os.makedirs(tables_dir, exist_ok=True)
        
        for i, table in enumerate(doc_data['tables']):
            if table:  # 테이블이 비어있지 않은 경우에만 저장
                table_file = os.path.join(tables_dir, f"{base_filename}_table_{i+1}.json")
                with open(table_file, 'w', encoding='utf-8') as f:
                    json.dump(table, f, ensure_ascii=False, indent=2)
        
        # 테이블 메타데이터를 문서 JSON에 추가
        doc_json['tables'] = [f"{base_filename}_table_{i+1}.json" for i in range(len(doc_data['tables']))]
    
    # 문서 JSON 저장
    doc_file = os.path.join(output_dir, f"{base_filename}.json")
    with open(doc_file, 'w', encoding='utf-8') as f:
        json.dump(doc_json, f, ensure_ascii=False, indent=2)
    
    # HTML 원본 저장 (content.html 필드가 있는 경우)
    if 'content' in doc_data and doc_data['content']:
        html_content = []
        for item in doc_data['content']:
            if 'content' in item and 'html' in item['content']:
                html_content.append(item['content']['html'])
        if html_content:
            html_file = os.path.join(output_dir, f"{base_filename}.html")
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(html_content))
    
    # 순수 텍스트 저장
    if doc_data['text']:
        txt_file = os.path.join(output_dir, f"{base_filename}.txt")
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write(doc_data['text'])

def main():
    # 설정
    pdf_dir = os.path.join(PROJECT_ROOT, 'data', 'processed', 'pdfs')
    output_dir = os.path.join(PROJECT_ROOT, 'data', 'processed', 'documents')
    
    # 출력 디렉토리 생성
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(PROJECT_ROOT, 'data', 'logs'), exist_ok=True)
    
    # PDF 파일 목록 가져오기
    pdf_files = [f for f in os.listdir(pdf_dir) if f.endswith('.pdf')]
    logging.info(f"Found {len(pdf_files)} PDF files to process")
    
    # 모든 PDF 파일 처리
    for pdf_file in tqdm(pdf_files, desc="Processing PDFs"):
        pdf_path = os.path.join(pdf_dir, pdf_file)
        base_filename = os.path.splitext(pdf_file)[0]

        logging.info(f"Processing PDF file: {pdf_file}")
        
        # Document Parsing 수행
        result = extract_text_with_upstage(pdf_path)
        
        # 텍스트가 추출되었는지 확인
        if result['text'].strip():  # 빈 문자열이 아닌 경우
            # 문서 데이터 저장
            save_document_data(result, output_dir, base_filename)
            logging.info(f"Successfully processed {pdf_file}")
        else:
            logging.warning(f"Failed to extract text from {pdf_file}")
    
    logging.info("Document parsing completed!")

if __name__ == "__main__":
    main() 