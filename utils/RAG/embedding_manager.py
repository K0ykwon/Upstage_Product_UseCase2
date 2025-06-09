import requests
import json
import os
import hashlib
from .textsplitter import get_text_splitter
import logging

class EmbeddingManager:
    def __init__(self, api_key, cache_dir="embedding_cache", create_embeddings=True):
        """
        api_key: Upstage API 키
        cache_dir: 임베딩 캐시를 저장할 디렉토리
        create_embeddings: 새로운 임베딩 생성 여부
        """
        self.api_key = api_key
        self.api_url = "https://api.upstage.ai/v1/embeddings"
        self.cache_dir = cache_dir
        self.create_embeddings = create_embeddings
        os.makedirs(cache_dir, exist_ok=True)
        
        self.text_splitter = get_text_splitter(
            'recursive',
            separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""],
            chunk_size=1024,
            chunk_overlap=128
        )
        
        # 로깅 설정
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def get_cache_path(self, text, filename):
        """
        텍스트의 해시값을 기반으로 캐시 파일 경로 생성
        각 문서별로 하위 폴더 생성
        """
        # 문서별 하위 폴더 생성
        doc_cache_dir = os.path.join(self.cache_dir, filename)
        os.makedirs(doc_cache_dir, exist_ok=True)
        
        # 텍스트의 해시값 생성
        text_hash = hashlib.md5(text.encode()).hexdigest()
        return os.path.join(doc_cache_dir, f"{text_hash}.json")

    def get_embeddings(self, texts, filenames):
        """
        배치 처리를 사용하여 텍스트들의 임베딩을 생성
        캐시된 임베딩이 있으면 재사용
        create_embeddings가 False인 경우 새로운 임베딩 생성하지 않음
        """
        # 최대 100개씩 배치 처리
        batch_size = 100
        all_embeddings = []
        texts_to_embed = []
        text_to_index = {}  # 임베딩할 텍스트와 원래 인덱스 매핑
        
        # 캐시 확인 및 미캐시된 텍스트 수집
        for i, (text, filename) in enumerate(zip(texts, filenames)):
            if i%1000 == 0:
                print(f"{i} / {len(texts)}")
            cache_path = self.get_cache_path(text, filename)

            if os.path.exists(cache_path):
                with open(cache_path, 'r') as f:
                    embedding = json.load(f)
                all_embeddings.append(embedding)
            else:
                if self.create_embeddings:
                    texts_to_embed.append(text)
                    text_to_index[text] = i
                    print(f"파일 '{filename}'의 새로운 임베딩을 생성합니다.")
                else:
                    print(f"파일 '{filename}'의 임베딩이 없어 처리하지 않습니다.")
        
        # 미캐시된 텍스트들에 대해 임베딩 생성 (create_embeddings가 True인 경우에만)
        if self.create_embeddings and texts_to_embed:
            for i in range(0, len(texts_to_embed), batch_size):
                batch_texts = texts_to_embed[i:i + batch_size]
                self.logger.info(f"배치 처리 중: {i+1}~{min(i+batch_size, len(texts_to_embed))} / {len(texts_to_embed)} 청크")
                
                response = requests.post(
                    self.api_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "embedding-passage",
                        "input": batch_texts
                    }
                )
                
                if response.status_code == 200:
                    batch_result = response.json()["data"]
                    
                    # 임베딩 결과 저장 및 캐시
                    for text, result in zip(batch_texts, batch_result):
                        embedding = result["embedding"]
                        # 원본 텍스트의 인덱스를 찾아 해당하는 파일명 사용
                        original_index = text_to_index[text]
                        cache_path = self.get_cache_path(text, filenames[original_index])
                        with open(cache_path, 'w') as f:
                            json.dump(embedding, f)
                        all_embeddings.append(embedding)
                else:
                    self.logger.error(f"임베딩 생성 실패: {response.status_code} - {response.text}")
        
        return all_embeddings

    def get_embedding_for_prompt(self, prompt):
        """프롬프트의 임베딩을 생성"""
        # 프롬프트를 청크로 분할
        prompt_chunks = self.text_splitter.split_text(prompt)
        # 각 청크의 임베딩 생성 (프롬프트는 'prompt' 폴더에 저장)
        return self.get_embeddings(prompt_chunks, ['prompt'] * len(prompt_chunks)) 
