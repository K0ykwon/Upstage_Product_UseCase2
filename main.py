import streamlit as st
from utils.pdf_upload import process_document
from utils.request_rag import initialize_rag_instance
from utils.request_rag import call_rag_api
from utils.chat import (
    summarize_document, 
    get_chat_response,
    document_based_qa_with_memory, 
    stream_chat_response_with_memory,
    get_rag_tools,
    process_rag_response
)
from utils.sidebar import render_sidebar, save_message_to_db, save_document_to_db, load_session_data
import requests
import json
import time
import os
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

if 'initialized' not in st.session_state:
    st.session_state.initialized = True
    initialize_rag_instance()

# Page & Session setup
st.set_page_config(
    page_title="AI Document Assistant",
    page_icon="🤖",
    layout="wide"
)

# 세션 상태 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []
if "processed_pdf" not in st.session_state:
    st.session_state.processed_pdf = None
if "pdf_summary" not in st.session_state:
    st.session_state.pdf_summary = None

# 사이드바 렌더링
render_sidebar()

# 현재 세션의 데이터 로드 (세션이 변경된 경우)
if "current_session_id" in st.session_state:
    # 세션 변경 감지를 위한 이전 세션 ID 저장
    if "prev_session_id" not in st.session_state:
        st.session_state.prev_session_id = st.session_state.current_session_id
        load_session_data(st.session_state.current_session_id)
    elif st.session_state.prev_session_id != st.session_state.current_session_id:
        st.session_state.prev_session_id = st.session_state.current_session_id
        load_session_data(st.session_state.current_session_id)

# API 설정
API_KEY = os.getenv("UPSTAGE_API_KEY")
API_URL = os.getenv("UPSTAGE_API_URL", "https://api.upstage.ai/v1")

if not API_KEY:
    st.error("UPSTAGE_API_KEY 환경 변수가 설정되지 않았습니다.")
    st.stop()

def main():
    st.title("🤖 AI Document Assistant")

    # 채팅 히스토리 표시
    chat_container = st.container()
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    with st.form("chat_pdf_form", clear_on_submit=True):
        col1, col2 = st.columns([2, 3])
        
        with col1:
            uploaded_file = st.file_uploader(
                "📄 PDF Upload", 
                type=["pdf"],
                help="Upload PDF file to analyze",
            )
        
        with col2:
            user_input = st.text_area(
                "💬 Message",
                height=100,
                placeholder="질문이나 요청사항을 입력하세요...\n예: '이 문서를 요약해줘', '주요 내용이 뭐야?'"
            )
        
        # 옵션 설정
        col_opt1, col_opt2, col_opt3 = st.columns(3)
        with col_opt1:
            force_ocr = st.checkbox("Force OCR", value=False, help="Check if PDF is image-base")
        with col_opt2:
            use_streaming = st.checkbox("Streaming response", value=True, help="Get streaming response")
        with col_opt3:
            use_rag = st.checkbox("Use RAG", value=True, help="Use RAG for additional context")
        
        submitted = st.form_submit_button("📤 SUBMIT", use_container_width=True)

    # 메시지 처리 - 폼이 제출되었을 때 실행
    if submitted:
        # 케이스 판단
        has_pdf = uploaded_file is not None
        has_text = user_input is not None and user_input.strip() != ""
        
        if has_pdf and has_text:
            # 케이스 1: PDF + 텍스트 입력
            with st.chat_message("user"):
                st.markdown(f"📄 **Document:** {uploaded_file.name}\n\n💬 **Query:** {user_input}")
            
            user_message = f"📄 **Document:** {uploaded_file.name}\n\n💬 **Query:** {user_input}"
            st.session_state.messages.append({
                "role": "user", 
                "content": user_message
            })
            save_message_to_db("user", user_message)
            
            with st.chat_message("assistant"):
                try:
                    # PDF 처리 (새로 업로드된 경우)
                    if uploaded_file:
                        with st.spinner("Analyzing PDF..."):
                            file_bytes = uploaded_file.read()
                            plain_text, error = process_document(file_bytes, force_ocr)
                            
                            if error:
                                st.error(f"PDF 처리 중 오류가 발생했습니다: {error}")
                                st.stop()
                            
                            if plain_text:
                                st.session_state.processed_pdf = plain_text
                                # 기존 요약 함수 사용
                                summary = summarize_document(plain_text)
                                st.session_state.pdf_summary = summary
                    
                    # 문서 기반 질문 답변
                    if use_streaming:
                        # 기본 시스템 프롬프트 정의
                        system_prompt = """당신은 도움이 되는 AI 어시스턴트입니다. 
이전 대화 내용을 참고하여 사용자의 질문에 정확하고 유용한 답변을 한국어로 제공해주세요.
대화의 맥락을 이해하고 연속성 있는 답변을 해주세요.
모르는 내용에 대해서는 솔직하게 모른다고 답변해주세요."""
                        
                        # 채팅 응답 생성 (RAG 포함)
                        response_placeholder = st.empty()
                        full_response = ""
                        
                        with st.spinner("답변을 생성하는 중..."):
                            for chunk in stream_chat_response_with_memory(
                                st.session_state.messages[:-1], 
                                system_prompt, 
                                user_input,
                                use_rag=use_rag,
                                pdf_summary=st.session_state.processed_pdf if hasattr(st.session_state, 'processed_pdf') else None
                            ):
                                full_response += chunk
                                response_placeholder.markdown(full_response + "▌")
                        
                        response_placeholder.markdown(full_response)
                        
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": full_response
                        })
                        save_message_to_db("assistant", full_response)
                    else:
                        # 일반 응답
                        with st.spinner("문서 기반 답변을 생성하는 중..."):
                            system_prompt = """당신은 도움이 되는 AI 어시스턴트입니다. 
이전 대화 내용을 참고하여 사용자의 질문에 정확하고 유용한 답변을 한국어로 제공해주세요.
대화의 맥락을 이해하고 연속성 있는 답변을 해주세요.
모르는 내용에 대해서는 솔직하게 모른다고 답변해주세요."""
                            
                            response = get_chat_response(
                                st.session_state.messages[:-1],
                                system_prompt,
                                user_input,
                                use_rag=use_rag,
                                pdf_summary=st.session_state.processed_pdf if hasattr(st.session_state, 'processed_pdf') else None
                            )
                            
                            if response:
                                full_response = response["response"]
                                if response["reference"]:
                                    full_response += f"\n\n---\n\n참조 문서 요약:\n{response['reference']}"
                                
                                st.markdown(full_response)
                                
                                st.session_state.messages.append({
                                    "role": "assistant", 
                                    "content": full_response
                                })
                                save_message_to_db("assistant", full_response)
                            else:
                                st.error("응답을 생성하는 중에 오류가 발생했습니다.")
                    
                except Exception as e:
                    st.error(f"처리 중 오류가 발생했습니다: {str(e)}")
        
        elif not has_pdf and has_text:
            # 케이스 2: 텍스트만 입력
            with st.chat_message("user"):
                st.markdown(user_input)
            
            st.session_state.messages.append({
                "role": "user", 
                "content": user_input
            })
            save_message_to_db("user", user_input)
            
            with st.chat_message("assistant"):
                try:
                    if use_streaming:
                        # 기본 시스템 프롬프트 정의
                        system_prompt = """당신은 도움이 되는 AI 어시스턴트입니다. 
이전 대화 내용을 참고하여 사용자의 질문에 정확하고 유용한 답변을 한국어로 제공해주세요.
대화의 맥락을 이해하고 연속성 있는 답변을 해주세요.
모르는 내용에 대해서는 솔직하게 모른다고 답변해주세요."""
                        
                        # 채팅 응답 생성 (RAG 포함)
                        response_placeholder = st.empty()
                        full_response = ""
                        
                        with st.spinner("답변을 생성하는 중..."):
                            for chunk in stream_chat_response_with_memory(
                                st.session_state.messages[:-1],
                                system_prompt,
                                user_input,
                                use_rag=use_rag,
                                pdf_summary=st.session_state.processed_pdf if hasattr(st.session_state, 'processed_pdf') else None
                            ):
                                full_response += chunk
                                response_placeholder.markdown(full_response + "▌")
                        
                        response_placeholder.markdown(full_response)
                        
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": full_response
                        })
                        save_message_to_db("assistant", full_response)
                    else:
                        # 일반 응답
                        with st.spinner("답변을 생성하는 중..."):
                            system_prompt = """당신은 도움이 되는 AI 어시스턴트입니다. 
이전 대화 내용을 참고하여 사용자의 질문에 정확하고 유용한 답변을 한국어로 제공해주세요.
대화의 맥락을 이해하고 연속성 있는 답변을 해주세요.
모르는 내용에 대해서는 솔직하게 모른다고 답변해주세요."""
                            
                            response = get_chat_response(
                                st.session_state.messages[:-1],
                                system_prompt,
                                user_input,
                                use_rag=use_rag,
                                pdf_summary=st.session_state.processed_pdf if hasattr(st.session_state, 'processed_pdf') else None
                            )
                            
                            if response:
                                full_response = response["response"]
                                if response["reference"]:
                                    full_response += f"\n\n---\n\n참조 문서 요약:\n{response['reference']}"
                                
                                st.markdown(full_response)
                                
                                st.session_state.messages.append({
                                    "role": "assistant", 
                                    "content": full_response
                                })
                                save_message_to_db("assistant", full_response)
                            else:
                                st.error("응답을 생성하는 중에 오류가 발생했습니다.")
                    
                except Exception as e:
                    st.error(f"처리 중 오류가 발생했습니다: {str(e)}")

if __name__ == "__main__":
    main()

# 하단 정보
st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("🗑️ 대화 기록 삭제"):
        st.session_state.messages = []
        st.session_state.processed_pdf = None
        st.session_state.pdf_summary = None
        st.rerun()

with col2:
    st.markdown("**현재 상태:**")
    if st.session_state.processed_pdf:
        st.success("📄 문서 분석 완료")
    else:
        st.info("📄 문서 대기 중")

with col3:
    st.markdown(f"**대화 수:** {len(st.session_state.messages)//2}")

# 푸터
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666; font-size: 0.8em;'>
    🤖 Powered by Upstage Solar Pro2 Preview | OpenAI Compatible API
    </div>
    """, 
    unsafe_allow_html=True
)

# RAG 함수 정의
def search_rag_documents(query):
    """RAG 시스템에서 관련 문서를 검색합니다."""
    try:
        rag_response = call_rag_api(query)
        if rag_response and "results" in rag_response and rag_response["results"]:
            return json.dumps(rag_response["results"][:3])
        return json.dumps([])
    except Exception as e:
        return json.dumps({"error": str(e)})

# 문서 요약 함수 정의
def summarize_document_content(content):
    """문서 내용을 간단히 요약합니다."""
    try:
        response = requests.post(
            f"{API_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "solar-pro-preview",
                "messages": [
                    {"role": "system", "content": "문서의 내용을 1-2줄로 간단히 요약해주세요."},
                    {"role": "user", "content": content[:1000]}  # 처음 1000자만 사용
                ]
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            return result["choices"][0]["message"]["content"]
        else:
            return "문서 요약을 생성할 수 없습니다."
    except Exception as e:
        return "문서 요약을 생성할 수 없습니다."

