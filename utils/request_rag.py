import requests
import os
from dotenv import load_dotenv
from .RAG import rag
from .translation import translate_text_direct
import re
load_dotenv()

RAG_ENDPOINT = os.getenv("RAG_ENDPOINT", "http://localhost:8000/query")

# 전역 rag_instance 변수 선언
rag_instance = None

def is_korean(text: str) -> bool:
    """
    텍스트가 한국어를 포함하는지 확인합니다.
    
    Args:
        text (str): 확인할 텍스트
        
    Returns:
        bool: 한국어 포함 여부
    """
    # 한글 유니코드 범위: AC00-D7A3 (완성형), 1100-11FF (자모)
    korean_pattern = re.compile('[가-힣ㄱ-ㅎㅏ-ㅣ]')
    return bool(korean_pattern.search(text))

def initialize_rag_instance():
    """
    RAG 인스턴스를 초기화합니다.
    """
    global rag_instance
    if rag_instance is None:
        print("RAG 인스턴스 초기화 중...")
        # 현재 파일의 디렉토리를 기준으로 상대 경로 계산
        current_dir = os.path.dirname(os.path.abspath(__file__))
        documents_dir = os.path.join(os.path.dirname(current_dir), "documents")
        
        # documents 디렉토리가 없으면 생성
        if not os.path.exists(documents_dir):
            os.makedirs(documents_dir)
            print(f"documents 디렉토리 생성됨: {documents_dir}")
        
        rag_instance = rag(
            documents=load_documents_from_directory(documents_dir),
            api_key=os.getenv("UPSTAGE_API_KEY"),
            create_embeddings=True
        )
        print("RAG 인스턴스 초기화 완료")

def load_documents_from_directory(directory_path):
    """
    디렉토리에서 txt 파일들을 읽어서 {filename, content} 형태의 딕셔너리 리스트로 반환
    """
    documents = []
    
    # 디렉토리 내의 모든 파일 검색
    for filename in os.listdir(directory_path):
        # txt 파일만 처리
        if filename.endswith('.txt'):
            file_path = os.path.join(directory_path, filename)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # 확장자를 제외한 파일 이름
                    name_without_ext = os.path.splitext(filename)[0]
                    documents.append({
                        "filename": name_without_ext,
                        "content": content
                    })
            except Exception as e:
                print(f"파일 {filename} 읽기 실패: {e}")
    
    return documents

def call_rag_api(prompt: str, top_k: int = 3):
    """
    RAG API를 호출하여 유사한 문서를 검색
    """
    print("RAG 호출됨!")
    try:
        # RAG 인스턴스 초기화 확인
        initialize_rag_instance()
        
        # 프롬프트가 한국어인 경우에만 영어로 번역
        if is_korean(prompt):
            print("한국어 프롬프트 감지됨, 영어로 번역합니다.")
            english_prompt = translate_text_direct(prompt, source_lang='ko', target_lang='en')
            print(f"원본 프롬프트: {prompt}")
            print(f"번역된 프롬프트: {english_prompt}")
        else:
            print("영어 프롬프트 감지됨, 번역 없이 진행합니다.")
            english_prompt = prompt
        
        # RAG 검색 수행
        responses = rag_instance(english_prompt, k=top_k)
        
        # 결과 포맷팅
        out = [{'filename': response['filename'].replace("_summarized", ""),
        'content': translate_text_direct(response['content'], source_lang='en', target_lang='ko'),
        'similarity': response['document_similarity']} for response in responses]
        
        print(f"검색 결과 수: {len(out)}")
        return {'results': out}
    except Exception as e:
        print(f"RAG API 호출 중 오류 발생: {e}")
        return None