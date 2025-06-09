''' 양방향 번역 (한국어 <-> 영어) '''

import os
from dotenv import load_dotenv
from openai import OpenAI
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
import logging
import textwrap
import nltk
from nltk.tokenize import sent_tokenize
from transformers import AutoTokenizer

# .env 파일 로드
load_dotenv()

# NLTK 데이터 다운로드
nltk.download('punkt')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("translation.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# OpenAI 클라이언트 설정
client = OpenAI(
    api_key=os.getenv("UPSTAGE_API_KEY"),
    base_url="https://api.upstage.ai/v1",
    http_client=None
)

def split_into_sentences(text):
    """
    텍스트를 문장 단위로 분리합니다.
    
    Args:
        text (str): 분리할 텍스트
        
    Returns:
        list: 문장 단위로 분리된 리스트
    """
    # 문장 분리
    sentences = sent_tokenize(text)
    
    # 각 문장의 앞뒤 공백 제거
    sentences = [sentence.strip() for sentence in sentences]
    
    # 빈 문장 제거
    sentences = [sentence for sentence in sentences if sentence]
    
    return sentences

def translate_text(text, target_language="ko"):
    """텍스트를 지정된 언어로 번역합니다."""
    try:
        response = client.chat.completions.create(
            model="solar-pro2-preview",
            messages=[
                {"role": "system", "content": f"다음 텍스트를 {target_language}로 번역해주세요."},
                {"role": "user", "content": text}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error in translate_text: {str(e)}")
        return text

def translate_file(input_path: str, output_path: str, source_lang: str = 'en', target_lang: str = 'ko'):
    """
    파일을 번역하여 저장합니다.
    
    Args:
        input_path (str): 입력 파일 경로
        output_path (str): 출력 파일 경로
        source_lang (str): 원본 언어 ('en' 또는 'ko')
        target_lang (str): 대상 언어 ('en' 또는 'ko')
    """
    try:
        # 파일 읽기
        loader = TextLoader(input_path, encoding='utf-8')
        data = loader.load()
        text = data[0].page_content if isinstance(data, list) else data.page_content
        
        # 번역 수행
        translated_text = translate_text(text, target_lang)
        
        # 번역된 텍스트 저장
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(translated_text)
        
        logging.info(f"Successfully translated and saved to: {output_path}")
        return True
        
    except Exception as e:
        logging.error(f"Error during translation: {str(e)}")
        return False

def translate_text_direct(text: str, source_lang: str = 'en', target_lang: str = 'ko') -> str:
    """
    텍스트를 직접 번역합니다 (파일 입출력 없이).
    
    Args:
        text (str): 번역할 텍스트
        source_lang (str): 원본 언어 ('en' 또는 'ko')
        target_lang (str): 대상 언어 ('en' 또는 'ko')
        
    Returns:
        str: 번역된 텍스트
    """
    try:
        return translate_text(text, target_lang)
    except Exception as e:
        logging.error(f"Error during direct translation: {str(e)}")
        return text  # 오류 발생시 원본 텍스트 반환
