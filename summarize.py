import os
from dotenv import load_dotenv
from openai import OpenAI
import logging

# 로그 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("summarize.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

load_dotenv()

client = OpenAI(
    api_key=os.getenv("UPSTAGE_API_KEY"),
    base_url="https://api.upstage.ai/v1"
)

# 1. 한글 텍스트 파일 읽기
input_file = "output_korean.txt"
with open(input_file, "r", encoding="utf-8") as f:
    korean_text = f.read()

logging.info(f"입력 파일 '{input_file}'에서 텍스트를 읽었습니다. (길이: {len(korean_text)}자)")

# 2. 요약 프롬프트 생성
prompt = f"""
다음 한국어 텍스트를 간결하게 요약해 주세요. (최대한 핵심만 남기고, 한국어로만 답변하세요.)\n\n텍스트:\n{korean_text}
"""

# 3. Solar LLM에 요약 요청
response = client.chat.completions.create(
    model="solar-pro",
    messages=[{"role": "user", "content": prompt}]
)
summary = response.choices[0].message.content.strip()

logging.info("요약 결과:")
logging.info(summary)

# 4. 요약 결과 저장
output_file = "summary_korean.txt"
with open(output_file, "w", encoding="utf-8") as f:
    f.write(summary)
logging.info(f"요약 결과를 '{output_file}'에 저장했습니다.")



