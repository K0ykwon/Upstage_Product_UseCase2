''' eng => kor txt translation 진행 '''

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
    base_url="https://api.upstage.ai/v1"
)

# 영어 txt 파일 경로 지정
DOCUMENTS_FOLDER = "./documents"
OUTPUT_FOLDER = "translated_text2"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

txt_files = [f for f in os.listdir(DOCUMENTS_FOLDER) if f.endswith('.txt')]

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

def translate_text(current_file_name, current_sentence_index, total_sentences, text, context_size = 50):
    translated_chunks = []
    sentences = split_into_sentences(text)
    for i, sentence in enumerate(sentences):
        print(f"Translating sentence {i+1} of {len(sentences)} in {current_file_name} progress: {(current_sentence_index/total_sentences + i/len(sentences) * (1/total_sentences))*100:.2f}%")
        context = "\n".join(translated_chunks[max(0, i - context_size):i])
        prompt = f"""
다음 영어 문장을 한국어로 번역해 주세요. 다만 "하십시오체(-습니다., -습니까?, -(으)십시오)" 등의 "일관된 말투"로 변역해 주어야합니다.
번역된 문장에는 한국어 이외의 언어를 포함하지 마십시오.
* 특히 한자 등 외국어 문자는 절대 포함하지 마십시오. *
용이한 번역을 위해서 번역할 문장의 이전 문장들을 함께 제공하겠습니다. 다만, 이 문장들은 내용 참고용으로만 사용하고, 실제로 번역에 적용하지는 말아주세요.

이전 문장들:
{context}

번역할 영어 문장:
{sentence}

번역된 문장:

"""
        response = client.chat.completions.create(
            model="solar-pro",
            messages=[{"role": "user", "content": prompt}]
        )
        kor_text = response.choices[0].message.content.strip()
        # 긴 줄을 80자 단위로 줄바꿈
        wrapped_kor_text = "\n".join(textwrap.wrap(kor_text, width=80))
        translated_chunks.append(wrapped_kor_text)
    return translated_chunks

for i, txt_file in enumerate(txt_files[1:]):
    input_path = os.path.join(DOCUMENTS_FOLDER, txt_file)
    output_path = os.path.join(OUTPUT_FOLDER, f"translated_{txt_file}")

    # 영어 파일 읽어오기 (token-based sentence chunking 사용)
    loader = TextLoader(input_path, encoding='utf-8')
    data = loader.load()
    text = data[0].page_content if isinstance(data, list) else data.page_content

    # Tokenizer for token counting (using a multilingual model)
    tokenizer = AutoTokenizer.from_pretrained('bert-base-multilingual-cased')
    max_token_limit = 2000

    translated_chunks = translate_text(txt_file + f"_[{i+1}/{len(txt_files)}]", i, len(txt_files), text)

    # 번역된 청크 합치기 및 저장 (한 줄 띄우기)
    full_korean_text = "\n".join(translated_chunks)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(full_korean_text)
    logging.info(f"Saved translated file to: {output_path}")