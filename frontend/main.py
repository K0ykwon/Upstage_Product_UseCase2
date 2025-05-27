import streamlit as st
from utils.pdf_upload import process_document
from utils.request_rag import call_rag_api
from utils.chat import (
    summarize_document, 
    answer_question_with_memory, 
    document_based_qa_with_memory, 
    stream_chat_response_with_memory
)
from utils.sidebar import render_sidebar, save_message_to_db, save_document_to_db, load_session_data
import time

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

# 메인 화면
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
    col_opt1, col_opt2 = st.columns(2)
    with col_opt1:
        force_ocr = st.checkbox("Force OCR", value=False, help="Check if PDF is image-base")
    with col_opt2:
        use_streaming = st.checkbox("Streaming response", value=True, help="Get streaming response")
    
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
                            # 요약도 미리 생성
                            summary = summarize_document(plain_text)
                            st.session_state.pdf_summary = summary
                
                # 문서 기반 질문 답변
                if use_streaming:
                    # 스트리밍 응답
                    system_prompt = f"""당신은 문서 분석 전문가입니다.
업로드된 문서의 내용과 이전 대화 내용을 바탕으로 사용자의 질문에 답변해주세요.
답변은 다음 형식으로 작성해주세요:

## 답변
[구체적인 답변 내용]

## 근거
[문서에서 해당 답변의 근거가 되는 부분]

## 추가 정보
[관련된 추가 정보나 제안사항]

문서에 없는 내용에 대해서는 "문서에서 해당 정보를 찾을 수 없습니다"라고 명시해주세요.

참조 문서 요약:
{st.session_state.pdf_summary or st.session_state.processed_pdf[:1000] if st.session_state.processed_pdf else "문서 없음"}"""
                    
                    response_placeholder = st.empty()
                    full_response = ""
                    
                    for chunk in stream_chat_response_with_memory(st.session_state.messages[:-1], system_prompt, user_input):
                        full_response += chunk
                        response_placeholder.markdown(full_response + "▌")
                    
                    # 문서 정보 추가
                    doc_info = f"""

---

### 📄 참조된 문서 정보
- **파일명:** {uploaded_file.name}
- **분석 완료:** ✅
"""
                    full_response += doc_info
                    response_placeholder.markdown(full_response)
                    
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": full_response
                    })
                    save_message_to_db("assistant", full_response)
                else:
                    # 일반 응답
                    with st.spinner("문서 기반 답변을 생성하는 중..."):
                        response = document_based_qa_with_memory(
                            st.session_state.pdf_summary or st.session_state.processed_pdf[:1000] if st.session_state.processed_pdf else "문서 없음",
                            user_input,
                            st.session_state.messages[:-1]
                        )
                        
                        if response:
                            response += f"""

---

### 📄 참조된 문서 정보
- **파일명:** {uploaded_file.name}
- **분석 완료:** ✅
"""
                            
                            st.markdown(response)
                            st.session_state.messages.append({
                                "role": "assistant", 
                                "content": response
                            })
                            save_message_to_db("assistant", response)
                        else:
                            error_msg = "문서 기반 답변을 생성할 수 없습니다."
                            st.error(error_msg)
                            st.session_state.messages.append({
                                "role": "assistant", 
                                "content": f"❌ {error_msg}"
                            })
                
                # 문서 정보 저장
                if uploaded_file and st.session_state.processed_pdf:
                    save_document_to_db(
                        uploaded_file.name, 
                        st.session_state.processed_pdf, 
                        st.session_state.pdf_summary
                    )
                    
            except Exception as e:
                error_msg = f"처리 중 오류가 발생했습니다: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": f"❌ {error_msg}"
                })
    
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
                    # 스트리밍 응답 (메모리 포함)
                    system_prompt = """당신은 도움이 되는 AI 어시스턴트입니다. 
이전 대화 내용을 참고하여 사용자의 질문에 정확하고 유용한 답변을 한국어로 제공해주세요.
대화의 맥락을 이해하고 연속성 있는 답변을 해주세요.
모르는 내용에 대해서는 솔직하게 모른다고 답변해주세요."""
                    
                    response_placeholder = st.empty()
                    full_response = ""
                    
                    for chunk in stream_chat_response_with_memory(st.session_state.messages[:-1], system_prompt, user_input):
                        full_response += chunk
                        response_placeholder.markdown(full_response + "▌")
                    
                    response_placeholder.markdown(full_response)
                    
                    # RAG API로 추가 정보 검색
                    try:
                        with st.spinner("관련 정보를 검색하는 중..."):
                            rag_response = call_rag_api(user_input)
                            
                            if rag_response and "results" in rag_response and rag_response["results"]:
                                additional_info = "\n\n### 📚 참고 자료:\n"
                                for i, result in enumerate(rag_response["results"][:2], 1):
                                    additional_info += f"**{i}.** {result.get('content', '내용 없음')[:150]}...\n\n"
                                
                                full_response += additional_info
                                response_placeholder.markdown(full_response)
                    except:
                        pass  # RAG 검색 실패해도 기본 답변은 유지
                    
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": full_response
                    })
                    save_message_to_db("assistant", full_response)
                else:
                    # 일반 응답 (메모리 포함)
                    with st.spinner("답변을 생성하는 중..."):
                        response = answer_question_with_memory(user_input, st.session_state.messages)
                        
                        if response:
                            # RAG API로 추가 정보 검색
                            try:
                                rag_response = call_rag_api(user_input)
                                
                                if rag_response and "results" in rag_response and rag_response["results"]:
                                    response += "\n\n### 📚 참고 자료:\n"
                                    for i, result in enumerate(rag_response["results"][:2], 1):
                                        response += f"**{i}.** {result.get('content', '내용 없음')[:150]}...\n\n"
                            except:
                                pass  # RAG 검색 실패해도 기본 답변은 유지
                            
                            st.markdown(response)
                            st.session_state.messages.append({
                                "role": "assistant", 
                                "content": response
                            })
                            save_message_to_db("assistant", response)
                        else:
                            error_msg = "죄송합니다. 답변을 생성할 수 없습니다. 다시 시도해 주세요."
                            st.error(error_msg)
                            st.session_state.messages.append({
                                "role": "assistant", 
                                "content": f"❌ {error_msg}"
                            })
                    
            except Exception as e:
                error_msg = f"답변 생성 중 오류가 발생했습니다: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": f"❌ {error_msg}"
                })
    
    elif has_pdf and not has_text:
        # PDF만 업로드된 경우 - 기본 요약 제공
        with st.chat_message("user"):
            st.markdown(f"📄 PDF 파일 업로드: {uploaded_file.name}")
        
        user_message = f"📄 PDF 파일 업로드: {uploaded_file.name}"
        st.session_state.messages.append({
            "role": "user", 
            "content": user_message
        })
        save_message_to_db("user", user_message)
        
        with st.chat_message("assistant"):
            with st.spinner("PDF를 분석하고 요약하는 중..."):
                try:
                    # PDF 처리
                    file_bytes = uploaded_file.read()
                    plain_text, error = process_document(file_bytes, force_ocr)
                    
                    if error:
                        st.error(f"PDF 처리 중 오류가 발생했습니다: {error}")
                    elif plain_text:
                        # 기본 요약 생성
                        summary = summarize_document(plain_text)
                        if summary:
                            st.session_state.processed_pdf = plain_text
                            st.session_state.pdf_summary = summary
                            
                            response = f"""
## 📋 문서 요약

{summary}

---

### 📄 문서 정보
- **파일명:** {uploaded_file.name}
- **분석 완료:** ✅

💡 **다음 메시지에서 이 문서에 대해 질문해보세요!**
"""
                            st.markdown(response)
                            st.session_state.messages.append({
                                "role": "assistant", 
                                "content": response
                            })
                            save_message_to_db("assistant", response)
                            
                            # 문서 정보 저장
                            save_document_to_db(uploaded_file.name, plain_text, summary)
                        else:
                            error_msg = "문서 요약을 생성할 수 없습니다."
                            st.error(error_msg)
                            st.session_state.messages.append({
                                "role": "assistant", 
                                "content": f"❌ {error_msg}"
                            })
                    else:
                        error_msg = "PDF에서 텍스트를 추출할 수 없습니다."
                        st.error(error_msg)
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": f"❌ {error_msg}"
                        })
                        
                except Exception as e:
                    error_msg = f"처리 중 오류가 발생했습니다: {str(e)}"
                    st.error(error_msg)
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": f"❌ {error_msg}"
                    })
    
    elif not has_pdf and not has_text:
        # 아무것도 입력하지 않은 경우
        st.warning("📝 메시지를 입력하거나 PDF 파일을 업로드해주세요.")

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

