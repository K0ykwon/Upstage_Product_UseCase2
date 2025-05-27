import streamlit as st
from utils.pdf_upload import process_document
from utils.request_rag import call_rag_api
from utils.openai_chat import (
    summarize_document, 
    answer_question_with_memory, 
    document_based_qa_with_memory, 
    stream_chat_response_with_memory
)
import time

# 페이지 설정
st.set_page_config(
    page_title="AI Document Assistant",
    page_icon="🤖",
    layout="wide"
)

# 세션 상태 초기화 (먼저 실행)
if "messages" not in st.session_state:
    st.session_state.messages = []
if "processed_pdf" not in st.session_state:
    st.session_state.processed_pdf = None
if "pdf_summary" not in st.session_state:
    st.session_state.pdf_summary = None

# 사이드바 설정
with st.sidebar:
    st.title("📄 Document Assistant")
    st.markdown("---")
    
    # PDF 업로드
    uploaded_file = st.file_uploader(
        "PDF 파일 업로드", 
        type=["pdf"],
        help="분석할 PDF 파일을 업로드하세요"
    )
    
    force_ocr = st.checkbox(
        "강제 OCR 사용", 
        value=False,
        help="이미지 기반 PDF의 경우 체크하세요"
    )
    
    # 스트리밍 옵션 추가
    use_streaming = st.checkbox(
        "실시간 응답 (스트리밍)", 
        value=True,
        help="응답을 실시간으로 받아보기"
    )
    
    if uploaded_file:
        st.success(f"✅ {uploaded_file.name} 업로드됨")
    
    st.markdown("---")
    st.markdown("### 사용 방법")
    st.markdown("""
    1. **PDF 업로드 후 요청**: PDF 업로드 → "문서 요약해줘" 입력
    2. **텍스트만 입력**: 질문에 대한 답변 제공
    3. **PDF + 구체적 질문**: 문서 기반 맞춤 답변
    
    💡 **팁**: PDF 업로드 후 원하는 요청사항을 함께 입력하세요!
    """)
    
    st.markdown("---")
    st.markdown("### 🤖 AI 모델")
    st.info("**Upstage Solar Pro2 Preview**\n- OpenAI 호환 API 사용\n- 고성능 추론 엔진\n- 🧠 스마트 메모리 관리")
    
    # 메모리 상태 표시
    if len(st.session_state.messages) > 14:  # 7개 대화 = 14개 메시지
        st.warning(f"💾 **메모리 관리 활성화**\n- 최근 7개 대화: 전체 보관\n- 이전 대화: 요약 저장\n- 총 {len(st.session_state.messages)//2}개 대화")
    else:
        st.success(f"💾 **전체 대화 보관 중**\n- 현재 {len(st.session_state.messages)//2}개 대화\n- 8개째부터 요약 저장")

# 메인 화면
st.title("🤖 AI Document Assistant")
st.markdown("PDF 문서 분석과 질문 답변을 도와드립니다.")

# 채팅 히스토리 표시
chat_container = st.container()
with chat_container:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# 사용자 입력
user_input = st.chat_input("질문을 입력하세요... (PDF만 업로드한 경우 '문서 요약해줘' 등을 입력하세요)")

# 메시지 처리 - 사용자가 텍스트를 입력했을 때만 실행
if user_input:
    # 케이스 판단
    has_pdf = uploaded_file is not None
    has_text = user_input is not None and user_input.strip() != ""
    
    if has_pdf and has_text and any(keyword in user_input.lower() for keyword in ['요약', '분석', '정리', '설명', '내용']):
        # 케이스 1: PDF 업로드 + 문서 관련 요청
        with st.chat_message("user"):
            st.markdown(f"📄 **문서:** {uploaded_file.name}\n\n💬 **요청:** {user_input}")
        
        st.session_state.messages.append({
            "role": "user", 
            "content": f"📄 **문서:** {uploaded_file.name}\n\n💬 **요청:** {user_input}"
        })
        
        with st.chat_message("assistant"):
            with st.spinner("PDF를 분석하고 요약하는 중..."):
                try:
                    # PDF 처리
                    file_bytes = uploaded_file.read()
                    plain_text, error = process_document(file_bytes, force_ocr)
                    
                    if error:
                        st.error(f"PDF 처리 중 오류가 발생했습니다: {error}")
                    elif plain_text:
                        # 사용자 요청에 따른 문서 처리
                        st.session_state.processed_pdf = plain_text
                        response = ""
                        
                        if '요약' in user_input.lower():
                            summary = summarize_document(plain_text)
                            if summary:
                                st.session_state.pdf_summary = summary
                                response = f"""
## 📋 문서 요약

{summary}

---

### 🔍 유사 보고서 검색 중...
"""
                        else:
                            # 기타 요청 (분석, 정리, 설명 등)
                            doc_response = document_based_qa_with_memory(
                                plain_text[:2000],  # 문서 일부만 사용
                                user_input,
                                st.session_state.messages[:-1]  # 현재 메시지 제외
                            )
                            
                            if doc_response:
                                response = f"""
## 📋 {user_input}

{doc_response}

---

### 🔍 유사 보고서 검색 중...
"""
                            else:
                                # 기본 요약으로 대체
                                summary = summarize_document(plain_text)
                                if summary:
                                    st.session_state.pdf_summary = summary
                                    response = f"""
## 📋 문서 요약

{summary}

---

### 🔍 유사 보고서 검색 중...
"""
                        
                        if response:
                            # RAG API 호출로 유사 보고서 검색
                            try:
                                search_query = st.session_state.pdf_summary if st.session_state.pdf_summary else user_input
                                rag_response = call_rag_api(f"유사한 보고서나 문서를 찾아주세요: {search_query}")
                                
                                if rag_response and "results" in rag_response:
                                    similar_docs = "### 📚 유사 보고서/문서\n\n"
                                    for i, result in enumerate(rag_response["results"][:3], 1):
                                        similar_docs += f"**{i}. {result.get('title', '제목 없음')}**\n"
                                        similar_docs += f"{result.get('content', '내용 없음')[:200]}...\n\n"
                                    
                                    st.markdown(similar_docs)
                                    response += similar_docs
                                else:
                                    fallback = "### 📚 유사 문서를 찾을 수 없습니다."
                                    st.markdown(fallback)
                                    response += fallback
                                    
                            except Exception as e:
                                error_msg = f"### ⚠️ 유사 문서 검색 중 오류: {str(e)}"
                                st.markdown(error_msg)
                                response += error_msg
                            
                            st.session_state.messages.append({
                                "role": "assistant", 
                                "content": response
                            })
                        else:
                            error_msg = "문서 처리를 완료할 수 없습니다."
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
    
    elif not has_pdf and has_text:
        # 케이스 2: 텍스트만 입력
        with st.chat_message("user"):
            st.markdown(user_input)
        
        st.session_state.messages.append({
            "role": "user", 
            "content": user_input
        })
        
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
                    
                    for chunk in stream_chat_response_with_memory(st.session_state.messages, system_prompt, user_input):
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
    
    elif has_pdf and has_text:
        # 케이스 3: PDF + 구체적 질문
        with st.chat_message("user"):
            st.markdown(f"📄 **문서:** {uploaded_file.name}\n\n💬 **질문:** {user_input}")
        
        st.session_state.messages.append({
            "role": "user", 
            "content": f"📄 **문서:** {uploaded_file.name}\n\n💬 **질문:** {user_input}"
        })
        
        with st.chat_message("assistant"):
            try:
                # PDF 처리 (아직 처리되지 않은 경우)
                if st.session_state.processed_pdf is None:
                    with st.spinner("문서를 분석하는 중..."):
                        file_bytes = uploaded_file.read()
                        plain_text, error = process_document(file_bytes, force_ocr)
                        
                        if error:
                            st.error(f"PDF 처리 중 오류가 발생했습니다: {error}")
                            st.stop()
                        
                        if plain_text:
                            summary = summarize_document(plain_text)
                            st.session_state.processed_pdf = plain_text
                            st.session_state.pdf_summary = summary
                
                # 문서 기반 질문 답변
                if use_streaming:
                    # 스트리밍 문서 기반 답변 (메모리 포함)
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
{st.session_state.pdf_summary or st.session_state.processed_pdf[:1000]}"""
                    
                    response_placeholder = st.empty()
                    full_response = ""
                    
                    for chunk in stream_chat_response_with_memory(st.session_state.messages, system_prompt, user_input):
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
                else:
                    # 일반 문서 기반 답변 (메모리 포함)
                    with st.spinner("문서를 분석하고 맞춤 답변을 생성하는 중..."):
                        response = document_based_qa_with_memory(
                            st.session_state.pdf_summary or st.session_state.processed_pdf[:1000], 
                            user_input,
                            st.session_state.messages
                        )
                        
                        if response:
                            response += f"""

---

### 📄 참조된 문서 정보
- **파일명:** {uploaded_file.name}
- **분석 완료:** ✅
"""
                            
                            # RAG API로 추가 참고 자료 검색
                            try:
                                rag_response = call_rag_api(f"문서: {st.session_state.pdf_summary} 질문: {user_input}")
                                
                                if rag_response and "results" in rag_response and rag_response["results"]:
                                    response += "\n### 📚 추가 참고 자료:\n"
                                    for i, result in enumerate(rag_response["results"][:2], 1):
                                        response += f"**{i}.** {result.get('content', '내용 없음')[:150]}...\n\n"
                            except:
                                pass
                            
                            st.markdown(response)
                            st.session_state.messages.append({
                                "role": "assistant", 
                                "content": response
                            })
                        else:
                            error_msg = "문서 기반 답변을 생성할 수 없습니다."
                            st.error(error_msg)
                            st.session_state.messages.append({
                                "role": "assistant", 
                                "content": f"❌ {error_msg}"
                            })
                    
            except Exception as e:
                error_msg = f"문서 기반 답변 생성 중 오류가 발생했습니다: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": f"❌ {error_msg}"
                })

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

