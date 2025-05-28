''' eng => kor txt translation 진행 '''

import os
from dotenv import load_dotenv
from openai import OpenAI
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
import logging
import textwrap

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
DOCUMENTS_FOLDER = "documents"
OUTPUT_FOLDER = "translated_text"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

txt_files = [f for f in os.listdir(DOCUMENTS_FOLDER) if f.endswith('.txt')]

for txt_file in txt_files:
    input_path = os.path.join(DOCUMENTS_FOLDER, txt_file)
    output_path = os.path.join(OUTPUT_FOLDER, f"translated_{txt_file}")
    logging.info(f"Processing file: {input_path}")

    # 영어 파일 읽어오기 (chunking 사용)
    loader = TextLoader(input_path, encoding='utf-8')
    data = loader.load()
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=100,
        length_function=len,
    )
    chunks = text_splitter.split_documents(data)

    translated_chunks = []
    for i, chunk in enumerate(chunks):
        chunk_text = chunk.page_content
        prompt = f"""
Translate the following English text into **KOREAN**. Respond only with the Korean translation.

English Text:
{chunk_text}

**Korean Text:**
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



