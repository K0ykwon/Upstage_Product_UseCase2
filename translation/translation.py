''' eng => kor txt translation 진행 '''

import os
from dotenv import load_dotenv
from openai import OpenAI
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
import logging
import textwrap
import nltk
from transformers import AutoTokenizer

nltk.download('punkt')
nltk.download('punkt_tab')
from nltk.tokenize import sent_tokenize

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("translation.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# env file 로드
load_dotenv()

# client 생성
client = OpenAI(
    api_key=os.getenv("UPSTAGE_API_KEY"),
    base_url="https://api.upstage.ai/v1"
)

# 영어 txt 파일 경로 지정
DOCUMENTS_FOLDER = "../documents"
OUTPUT_FOLDER = "translated_text2"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

txt_files = [f for f in os.listdir(DOCUMENTS_FOLDER) if f.endswith('.txt')]

for txt_file in txt_files:
    input_path = os.path.join(DOCUMENTS_FOLDER, txt_file)
    output_path = os.path.join(OUTPUT_FOLDER, f"translated_{txt_file}")
    logging.info(f"Processing file: {input_path}")

    # 영어 파일 읽어오기 (token-based sentence chunking 사용)
    loader = TextLoader(input_path, encoding='utf-8')
    data = loader.load()
    text = data[0].page_content if isinstance(data, list) else data.page_content

    # Tokenizer for token counting (using a multilingual model)
    tokenizer = AutoTokenizer.from_pretrained('bert-base-multilingual-cased')
    max_token_limit = 2000

    sentences = sent_tokenize(text)
    chunks = []
    current_chunk = ""
    current_tokens = 0
    for sentence in sentences:
        sentence_tokens = len(tokenizer.tokenize(sentence))
        if current_tokens + sentence_tokens <= max_token_limit:
            current_chunk += (" " if current_chunk else "") + sentence
            current_tokens += sentence_tokens
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = sentence
            current_tokens = sentence_tokens
    if current_chunk:
        chunks.append(current_chunk)

    translated_chunks = []
    for i, chunk_text in enumerate(chunks):
        prompt = f"""
Translate the following English text into **KOREAN** using only formal report tone (다나까체, 합니다/합니까). Respond only with the Korean translation.

English Text:
{chunk_text}

Korean Text:
"""
        response = client.chat.completions.create(
            model="solar-pro",
            messages=[{"role": "user", "content": prompt}]
        )
        kor_text = response.choices[0].message.content.strip()
        # 긴 줄을 80자 단위로 줄바꿈
        wrapped_kor_text = "\n".join(textwrap.wrap(kor_text, width=80))
        translated_chunks.append(wrapped_kor_text)
        logging.info(f"Translated chunk {i+1}/{len(chunks)} for {txt_file}")

    # 번역된 청크 합치기 및 저장 (한 줄 띄우기)
    full_korean_text = "\n".join(translated_chunks)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(full_korean_text)
    logging.info(f"Saved translated file to: {output_path}")