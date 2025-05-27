import os
import json
import numpy as np
import pandas as pd
from tqdm import tqdm
import faiss
import requests
import time
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class PolicyDataProcessor:
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        """
        정책 데이터 처리 및 벡터 DB 구축을 위한 클래스
        
        Args:
            model_name: 사용할 임베딩 모델 이름
        """
        self.model = SentenceTransformer(model_name)
        self.index = None
        self.documents = []
        self.solar_api_key = os.getenv('SOLAR_API_KEY')
        if not self.solar_api_key:
            raise ValueError("SOLAR_API_KEY environment variable is not set")
        self.solar_api_url = "https://api.upstage.ai/v1/solar/chat/completions"
        
    def _extract_text_from_structured_report(self, report_data: Any) -> str:
        """
        중첩된 구조의 보고서 데이터에서 텍스트 추출
        
        Args:
            report_data: 추출할 데이터
            
        Returns:
            추출된 텍스트
        """
        if isinstance(report_data, str):
            return report_data
        elif isinstance(report_data, list):
            return " ".join([self._extract_text_from_structured_report(item) for item in report_data])
        elif isinstance(report_data, dict):
            return " ".join([self._extract_text_from_structured_report(value) for value in report_data.values()])
        else:
            return ""
    
    def _clean_text(self, text: str) -> str:
        """
        텍스트 정제 함수
        
        Args:
            text: 정제할 텍스트
            
        Returns:
            정제된 텍스트
        """
        # 페이지 번호 제거
        text = ' '.join([line for line in text.split('\n') 
                        if not line.strip().isdigit()])
        
        # 머리말, 목차, 표 캡션 등 제거
        # TODO: 더 정교한 정제 규칙 추가
        
        return text.strip()
    
    def _translate_with_solar(self, text: str) -> str:
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
            "Authorization": f"Bearer {self.solar_api_key}",
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
                response = requests.post(self.solar_api_url, headers=headers, json=payload)
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
    
    def _summarize_with_solar(self, text: str) -> str:
        """
        Solar LLM을 사용하여 한국어 텍스트를 요약
        
        Args:
            text: 요약할 한국어 텍스트
            
        Returns:
            요약된 텍스트
        """
        if not text.strip():
            return ""
            
        headers = {
            "Authorization": f"Bearer {self.solar_api_key}",
            "Content-Type": "application/json"
        }
        
        # 텍스트가 너무 길면 청크로 나누어 요약
        max_chunk_size = 4000
        chunks = [text[i:i + max_chunk_size] for i in range(0, len(text), max_chunk_size)]
        summarized_chunks = []
        
        for chunk in chunks:
            payload = {
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a professional summarizer. Create a concise summary of the following Korean text. Focus on the main points and key information. Maintain the original meaning and tone."
                    },
                    {
                        "role": "user",
                        "content": chunk
                    }
                ],
                "temperature": 0.3,
                "max_tokens": 1000
            }
            
            try:
                response = requests.post(self.solar_api_url, headers=headers, json=payload)
                response.raise_for_status()
                summary = response.json()['choices'][0]['message']['content']
                summarized_chunks.append(summary)
                
                # API 호출 간 딜레이
                time.sleep(1)
                
            except Exception as e:
                print(f"Summarization error: {e}")
                # 에러 발생 시 원본 텍스트 반환
                summarized_chunks.append(chunk)
        
        return " ".join(summarized_chunks)
    
    def load_and_process_data(self, raw_data_dir: str) -> List[Dict]:
        """
        GovReport 데이터셋을 로드하고 전처리
        
        Args:
            raw_data_dir: 원본 데이터 디렉토리
            
        Returns:
            전처리된 문서 리스트
        """
        print("Loading and preprocessing data...")
        documents = []
        report_folders = ['crs', 'gao']
        
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
                    
                    # 텍스트 추출 및 정제
                    raw_report_text = doc_data.get('report', '')
                    cleaned_report_text = self._extract_text_from_structured_report(raw_report_text)
                    cleaned_report_text = self._clean_text(cleaned_report_text)
                    
                    # 번역
                    print(f"\nTranslating document {doc_id}...")
                    translated_text = self._translate_with_solar(cleaned_report_text)
                    
                    # 요약
                    print(f"Summarizing document {doc_id}...")
                    summary = self._summarize_with_solar(translated_text)
                    
                    metadata = {
                        'title': doc_data.get('title', ''),
                        'released_date': doc_data.get('released_date', ''),
                        'published_date': doc_data.get('published_date', ''),
                        'url': doc_data.get('url', ''),
                        'source_folder': folder_name
                    }
                    
                    documents.append({
                        'id': doc_id,
                        'text': translated_text,
                        'summary': summary,
                        'metadata': metadata
                    })
                    
                except Exception as e:
                    print(f"Error processing file {file_path}: {e}")
                    continue
                    
        self.documents = documents
        return documents
    
    def create_embeddings(self) -> np.ndarray:
        """
        문서들을 벡터로 임베딩
        
        Returns:
            임베딩 벡터 배열
        """
        print("Creating embeddings...")
        texts = [doc['text'] for doc in self.documents]
        embeddings = self.model.encode(texts, show_progress_bar=True)
        return embeddings
    
    def build_index(self, embeddings: np.ndarray):
        """
        FAISS 인덱스 구축
        
        Args:
            embeddings: 임베딩 벡터 배열
        """
        print("Building FAISS index...")
        dimension = embeddings.shape[1]
        
        # L2 정규화
        faiss.normalize_L2(embeddings)
        
        # FAISS 인덱스 생성
        self.index = faiss.IndexFlatIP(dimension)
        self.index.add(embeddings)
    
    def save_index(self, output_path: str):
        """
        인덱스와 문서 저장
        
        Args:
            output_path: 저장할 경로
        """
        print("Saving index and documents...")
        # 인덱스 저장
        faiss.write_index(self.index, os.path.join(output_path, 'policy_index.faiss'))
        
        # 문서 저장
        with open(os.path.join(output_path, 'documents.json'), 'w', encoding='utf-8') as f:
            json.dump(self.documents, f, ensure_ascii=False, indent=2)
    
    def process_and_build_index(self, raw_data_dir: str, output_path: str):
        """
        전체 파이프라인 실행
        
        Args:
            raw_data_dir: 원본 데이터 디렉토리
            output_path: 출력 저장 경로
        """
        # 데이터 로드 및 전처리
        self.load_and_process_data(raw_data_dir)
        
        # 임베딩 생성
        embeddings = self.create_embeddings()
        
        # 인덱스 구축
        self.build_index(embeddings)
        
        # 결과 저장
        os.makedirs(output_path, exist_ok=True)
        self.save_index(output_path)
        
        print(f"Processing complete. Results saved to {output_path}")

if __name__ == "__main__":
    # 환경 변수나 설정 파일에서 경로를 가져오도록 수정 필요
    RAW_DATA_DIR = "data/raw/gov-report"
    OUTPUT_PATH = "data/processed"
    
    processor = PolicyDataProcessor()
    processor.process_and_build_index(RAW_DATA_DIR, OUTPUT_PATH) 