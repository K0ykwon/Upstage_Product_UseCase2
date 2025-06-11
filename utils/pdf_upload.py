import streamlit as st
import requests
import os
import json
import io
import tiktoken
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from PyPDF2 import PdfReader, PdfWriter
from langchain_upstage import ChatUpstage
load_dotenv()

UPSTAGE_API_KEY = os.getenv("UPSTAGE_API_KEY")
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB in bytes
MAX_PAGES_PER_CHUNK = 90  # Upstage Synchronous API 제한: 100페이지 (안정성을 위해 90페이지로 설정)
MAX_TOKENS = 30000  # 토큰 제한

upstage_llm = ChatUpstage(
    api_key=UPSTAGE_API_KEY,
    model="solar-pro2-preview"
)

def count_tokens(text: str) -> int:
    """Upstage 모델을 사용하여 텍스트의 토큰 수를 계산합니다."""
    return upstage_llm.get_num_tokens(text)

def truncate_text_by_tokens(text: str, max_tokens: int) -> tuple[str, int, int]:
    """Upstage 토큰 카운팅을 사용하여 텍스트를 자릅니다."""
    original_token_count = count_tokens(text)
    
    if original_token_count <= max_tokens:
        return text, original_token_count, original_token_count
    
    # 이진 탐색으로 적절한 길이 찾기
    left, right = 0, len(text)
    best_text = text[:right//2]
    
    while left < right:
        mid = (left + right + 1) // 2
        candidate_text = text[:mid]
        token_count = count_tokens(candidate_text)
        
        if token_count <= max_tokens:
            best_text = candidate_text
            left = mid
        else:
            right = mid - 1
    
    # 문장이 중간에 잘리는 것을 방지
    sentences = best_text.split('.')
    if len(sentences) > 1:
        best_text = '.'.join(sentences[:-1]) + '.'
    
    final_token_count = count_tokens(best_text)
    return best_text, original_token_count, final_token_count

def split_pdf_by_pages(file_bytes, max_size_bytes):
    """PDF를 페이지별로 분할하여 각 부분이 최대 크기와 페이지 수를 넘지 않도록 합니다."""
    try:
        pdf_reader = PdfReader(io.BytesIO(file_bytes))
        total_pages = len(pdf_reader.pages)
        
        if total_pages == 0:
            return None, "PDF에 페이지가 없습니다."
        
        # 총 페이지 수 확인 및 경고
        if total_pages > MAX_PAGES_PER_CHUNK:
            st.warning(f"⚠️ 총 {total_pages}페이지입니다. {MAX_PAGES_PER_CHUNK}페이지씩 분할하여 처리합니다.")
        
        # 평균 페이지 크기 추정
        avg_page_size = len(file_bytes) / total_pages
        pages_per_chunk_by_size = max(1, int(max_size_bytes / avg_page_size))
        
        # 페이지 제한과 크기 제한 중 더 작은 값 사용
        pages_per_chunk = min(pages_per_chunk_by_size, MAX_PAGES_PER_CHUNK)
        
        chunks = []
        current_chunk_start = 0
        
        while current_chunk_start < total_pages:
            # 청크 생성
            pdf_writer = PdfWriter()
            current_chunk_end = min(current_chunk_start + pages_per_chunk, total_pages)
            
            # 페이지 추가
            for page_num in range(current_chunk_start, current_chunk_end):
                pdf_writer.add_page(pdf_reader.pages[page_num])
            
            # 메모리에 PDF 작성
            output_buffer = io.BytesIO()
            pdf_writer.write(output_buffer)
            chunk_bytes = output_buffer.getvalue()
            output_buffer.close()
            
            # 청크 크기가 여전히 너무 큰 경우 페이지를 더 줄임
            if len(chunk_bytes) > max_size_bytes and pages_per_chunk > 1:
                pages_per_chunk = max(1, min(pages_per_chunk // 2, MAX_PAGES_PER_CHUNK))
                continue
            
            # 페이지 수 제한 체크
            actual_pages = current_chunk_end - current_chunk_start
            if actual_pages > MAX_PAGES_PER_CHUNK:
                return None, f"청크 크기가 페이지 제한({MAX_PAGES_PER_CHUNK}페이지)을 초과합니다."
            
            chunks.append({
                'data': chunk_bytes,
                'pages': f"{current_chunk_start + 1}-{current_chunk_end}",
                'page_count': actual_pages,
                'size': len(chunk_bytes)
            })
            
            current_chunk_start = current_chunk_end
        
        return chunks, None
        
    except Exception as e:
        return None, f"PDF 분할 중 오류 발생: {str(e)}"

def process_single_document(file_bytes, force_ocr: bool, chunk_info=None):
    """단일 문서(또는 문서 청크)를 처리합니다."""
    url = "https://api.upstage.ai/v1/document-digitization"
    headers = {"Authorization": f"Bearer {UPSTAGE_API_KEY}"}
    files = {
        "document": ("document.pdf", file_bytes, "application/pdf")
    }
    data = {
        "ocr": "force" if force_ocr else "auto",
        "coordinates": "true",
        "chart_recognition": "false",
        "output_formats": json.dumps(["html"]),
        "model": "document-parse",
        "base64_encoding": json.dumps([])
    }

    try:
        response = requests.post(url, headers=headers, files=files, data=data)
        response.raise_for_status()
        result = response.json()

        html_content = result.get("content", {}).get("html", "").strip()

        if not html_content:
            return None, f"청크에서 텍스트를 찾을 수 없습니다. {chunk_info or ''}"
        
        soup = BeautifulSoup(html_content, "html.parser")
        plain_text = soup.get_text("\n")

        # 토큰 수 계산 및 제한 적용
        original_token_count = count_tokens(plain_text)
        
        if original_token_count > MAX_TOKENS:
            truncated_text, original_tokens, final_tokens = truncate_text_by_tokens(plain_text, MAX_TOKENS)
            st.warning(f"⚠️ 텍스트가 토큰 제한을 초과하여 잘림: {original_tokens:,} → {final_tokens:,} 토큰 {chunk_info or ''}")
            return truncated_text, None
        else:
            st.info(f"📊 추출된 텍스트: {original_token_count:,} 토큰 {chunk_info or ''}")
            return plain_text, None
    
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 413:
            return None, f"파일 크기가 너무 큽니다 (413 오류). {chunk_info or ''}"
        else:
            return None, f"HTTP 오류 {e.response.status_code}: {str(e)} {chunk_info or ''}"
    except Exception as e:
        return None, f"처리 중 오류 발생: {str(e)} {chunk_info or ''}"

def process_document(file_bytes, force_ocr: bool):
    """
    문서를 처리합니다. 파일 크기가 20MB를 초과하거나 페이지가 90페이지를 초과하면 자동으로 분할합니다.
    """
    file_size_mb = len(file_bytes) / (1024 * 1024)
    
    # 먼저 페이지 수 확인 (분할 필요성 판단을 위해)
    try:
        pdf_reader = PdfReader(io.BytesIO(file_bytes))
        total_pages = len(pdf_reader.pages)
    except Exception as e:
        return None, f"PDF 페이지 정보를 읽을 수 없습니다: {str(e)}"
    
    # 파일 크기와 페이지 수 체크
    needs_splitting = len(file_bytes) > MAX_FILE_SIZE or total_pages > MAX_PAGES_PER_CHUNK
    
    if not needs_splitting:
        # 20MB 이하이고 90페이지 이하인 경우 직접 처리
        st.info(f"📄 파일 정보: {file_size_mb:.2f}MB, {total_pages}페이지 - 직접 처리합니다.")
        return process_single_document(file_bytes, force_ocr)
    
    # 20MB 초과이거나 90페이지 초과인 경우 분할 처리
    split_reasons = []
    if len(file_bytes) > MAX_FILE_SIZE:
        split_reasons.append(f"파일 크기 {file_size_mb:.2f}MB > 20MB")
    if total_pages > MAX_PAGES_PER_CHUNK:
        split_reasons.append(f"페이지 수 {total_pages}페이지 > {MAX_PAGES_PER_CHUNK}페이지")
    
    st.warning(f"📄 분할 처리 사유: {', '.join(split_reasons)}")
    
    # PDF 분할
    with st.spinner("PDF를 분할하는 중..."):
        chunks, error = split_pdf_by_pages(file_bytes, MAX_FILE_SIZE)
        
        if error:
            return None, error
        
        if not chunks:
            return None, "PDF 분할에 실패했습니다."
    
    st.info(f"📑 PDF를 {len(chunks)}개 부분으로 분할했습니다.")
    
    # 각 청크를 처리
    all_text_parts = []
    total_tokens = 0
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, chunk in enumerate(chunks):
        progress = (i + 1) / len(chunks)
        status_text.text(f"📄 처리 중: {chunk['pages']} 페이지 ({chunk['page_count']}페이지, {chunk['size'] / (1024*1024):.2f}MB)")
        progress_bar.progress(progress)
        
        chunk_info = f"(페이지 {chunk['pages']}, {chunk['page_count']}페이지)"
        text_part, error = process_single_document(chunk['data'], force_ocr, chunk_info)
        
        if error:
            st.error(f"청크 {i+1} 처리 실패: {error}")
            continue
        
        if text_part:
            # 각 청크의 토큰 수 누적 계산
            chunk_tokens = count_tokens(text_part)
            total_tokens += chunk_tokens
            
            all_text_parts.append(f"\n\n=== 페이지 {chunk['pages']} ({chunk['page_count']}페이지, {chunk_tokens:,} 토큰) ===\n\n{text_part}")
    
    # 진행률 바 정리
    progress_bar.empty()
    status_text.empty()
    
    if not all_text_parts:
        return None, "모든 PDF 청크 처리에 실패했습니다."
    
    # 모든 텍스트 합치기
    combined_text = "\n".join(all_text_parts)
    
    # 전체 텍스트의 토큰 수 최종 확인 및 제한 적용
    final_token_count = count_tokens(combined_text)
    
    if final_token_count > MAX_TOKENS:
        st.warning(f"⚠️ 전체 텍스트가 토큰 제한을 초과하여 잘림: {final_token_count:,} → {MAX_TOKENS:,} 토큰")
        truncated_text, original_tokens, final_tokens = truncate_text_by_tokens(combined_text, MAX_TOKENS)
        combined_text = truncated_text
        final_token_count = final_tokens
    
    processed_pages = sum(chunk['page_count'] for chunk in chunks if any(f"페이지 {chunk['pages']}" in part for part in all_text_parts))
    st.success(f"✅ {len(chunks)}개 부분 중 {len(all_text_parts)}개 성공적으로 처리완료! (총 {processed_pages}페이지, {final_token_count:,} 토큰)")
    
    return combined_text, None
    
