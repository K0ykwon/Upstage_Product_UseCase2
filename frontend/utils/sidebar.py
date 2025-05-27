import streamlit as st
from .database import db
from datetime import datetime

def render_sidebar():
    """사이드바 렌더링 및 세션 관리"""
    
    with st.sidebar:
        st.title("📄 Document Assistant")
        
        # 사용자 프로필 섹션
        st.markdown("---")
        st.markdown("### 👤 사용자 프로필")
        
        # 사용자 프로필 정보 표시
        profile = db.get_user_profile()
        
        # 프로필 정보가 있는 경우 표시
        if any([profile['interests'], profile['personality_traits'], profile['preferred_response_style']]):
            with st.expander("🔍 내 프로필 보기", expanded=False):
                if profile['interests']:
                    st.markdown(f"**관심사:** {', '.join(profile['interests'])}")
                
                if profile['personality_traits']:
                    st.markdown(f"**성향:** {', '.join(profile['personality_traits'])}")
                
                if profile['preferred_response_style']:
                    st.markdown(f"**선호 스타일:** {profile['preferred_response_style']}")
                
                if profile['communication_patterns']:
                    st.markdown(f"**소통 패턴:** {', '.join(profile['communication_patterns'])}")
                
                st.caption("💡 이 정보는 모든 세션에서 공유되어 개인화된 답변을 제공합니다.")
        else:
            st.info("💬 대화를 나누면서 자동으로 프로필이 생성됩니다!")
        
        # 세션 관리 섹션
        st.markdown("---")
        st.markdown("### 💬 대화 세션")
        
        # 현재 세션 표시
        if "current_session_id" not in st.session_state:
            # 첫 방문 시 새 세션 생성
            session_id = db.create_session()
            st.session_state.current_session_id = session_id
        
        # 새 대화 버튼 (현재 대화에 메시지가 있을 때만 활성화)
        current_message_count = len(st.session_state.messages) // 2
        if current_message_count > 0:
            if st.button("➕ 새 대화", use_container_width=True, type="primary"):
                session_id = db.create_session()
                st.session_state.current_session_id = session_id
                st.session_state.messages = []
                st.session_state.processed_pdf = None
                st.session_state.pdf_summary = None
                st.rerun()
        else:
            st.button("➕ 새 대화", use_container_width=True, disabled=True, 
                     help="현재 대화에서 메시지를 보낸 후 새 대화를 시작할 수 있습니다")
        
        # 히스토리 섹션
        st.markdown("---")
        st.markdown("### 📋 히스토리")
        
        # 세션 목록 조회
        sessions = db.get_sessions()
        
        if sessions:
            for session in sessions[:15]:  # 최근 15개 표시
                # 현재 세션인지 확인
                is_current = session['session_id'] == st.session_state.current_session_id
                
                # 모든 세션을 클릭 가능한 버튼으로 만들기
                col1, col2 = st.columns([5, 1])
                
                with col1:
                    # 현재 세션인지에 따라 다른 스타일 적용
                    button_type = "primary" if is_current else "secondary"
                    button_label = f"🔹 {session['session_name']}\n{session['message_count']}개 메시지" if is_current else f"{session['session_name']}\n{session['message_count']}개 메시지"
                    
                    if st.button(
                        button_label,
                        key=f"session_{session['session_id']}", 
                        use_container_width=True,
                        type=button_type,
                        help="현재 선택된 대화" if is_current else "클릭하여 이 대화로 전환"
                    ):
                        # 세션 전환 (현재 세션 클릭 시에도 새로고침하여 새 대화 버튼 활성화)
                        st.session_state.current_session_id = session['session_id']
                        load_session_data(session['session_id'])
                        st.rerun()
                
                with col2:
                    # 삭제 버튼 (현재 세션이 아닌 경우에만)
                    if not is_current:
                        if st.button("🗑️", key=f"delete_{session['session_id']}", 
                                   help="대화 삭제", use_container_width=True):
                            db.delete_session(session['session_id'])
                            st.rerun()
                    else:
                        # 현재 세션인 경우 빈 공간
                        st.write("")
        else:
            st.info("아직 대화 기록이 없습니다. 새 대화를 시작해보세요!")
        
        # 메모리 관리 정보
        st.markdown("---")
        st.markdown("### 🧠 메모리 상태")
        
        # 현재 세션 메모리 상태
        message_count = len(st.session_state.messages) // 2
        
        # 간결한 상태 표시
        if message_count >= 5:
            st.success(f"💾 DB 저장 중 ({message_count}개 대화)")
        elif message_count > 0:
            st.info(f"💭 메모리 사용 중 ({message_count}개 대화)")
        else:
            st.info("💬 새 대화 시작")
        
        # 프로필 공유 정보 (간결하게)
        if any([profile['interests'], profile['personality_traits'], profile['preferred_response_style']]):
            st.caption("🔗 사용자 프로필이 모든 대화에서 활용됩니다")
        
        # 사용 방법
        st.markdown("---")
        st.markdown("### 📖 사용법")
        with st.expander("자세히 보기", expanded=False):
            st.markdown("""
            **기본 사용법:**
            1. **PDF + 질문**: PDF와 질문을 함께 입력
            2. **PDF만**: PDF 업로드 시 자동 요약
            3. **텍스트만**: 일반 질문 답변
            
            **메모리 특징:**
            - 각 대화는 독립적으로 관리
            - 사용자 성향은 모든 대화에서 공유
            - 5개 대화부터 DB에 자동 저장
            """)
        
        # AI 모델 정보
        st.markdown("---")
        st.markdown("### 🤖 AI 모델")
        st.caption("**Upstage Solar Pro2 Preview**")
        st.caption("OpenAI 호환 API • 개인화 응답 지원")
        
        # 데이터베이스 관리 (개발용)
        if st.checkbox("🔧 개발자 모드"):
            st.markdown("#### 데이터베이스 관리")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🗑️ 모든 데이터 삭제", type="secondary"):
                    db.clear_all_data()
                    st.session_state.clear()
                    st.success("모든 데이터가 삭제되었습니다.")
                    st.rerun()
            
            with col2:
                if st.button("👤 프로필 초기화", type="secondary"):
                    # 프로필만 초기화
                    db.update_user_profile(
                        interests=[],
                        personality_traits=[],
                        preferred_response_style="",
                        communication_patterns=[]
                    )
                    st.success("사용자 프로필이 초기화되었습니다.")
                    st.rerun()
    
    return None  # 더 이상 사이드바에서 파일 업로드를 처리하지 않음

def load_session_data(session_id: str):
    """세션 데이터 로드 - 세션별 메모리 상태 관리"""
    # 현재 세션의 메모리 상태를 저장
    if "current_session_id" in st.session_state and st.session_state.current_session_id != session_id:
        # 현재 세션의 상태를 세션별 메모리에 저장
        if "session_memory" not in st.session_state:
            st.session_state.session_memory = {}
        
        st.session_state.session_memory[st.session_state.current_session_id] = {
            "messages": st.session_state.messages.copy(),
            "processed_pdf": st.session_state.get("processed_pdf"),
            "pdf_summary": st.session_state.get("pdf_summary")
        }
    
    # 새 세션의 데이터 로드
    if "session_memory" not in st.session_state:
        st.session_state.session_memory = {}
    
    # 세션별 메모리에 저장된 데이터가 있는지 확인
    if session_id in st.session_state.session_memory:
        # 메모리에서 복원
        session_data = st.session_state.session_memory[session_id]
        st.session_state.messages = session_data["messages"]
        st.session_state.processed_pdf = session_data["processed_pdf"]
        st.session_state.pdf_summary = session_data["pdf_summary"]
    else:
        # DB에서 로드
        db_messages = db.get_messages(session_id)
        st.session_state.messages = db_messages
        
        # 문서 정보 로드
        document = db.get_document(session_id)
        if document:
            st.session_state.processed_pdf = document['content']
            st.session_state.pdf_summary = document['summary']
        else:
            st.session_state.processed_pdf = None
            st.session_state.pdf_summary = None
        
        # 로드한 데이터를 세션별 메모리에 저장
        st.session_state.session_memory[session_id] = {
            "messages": st.session_state.messages.copy(),
            "processed_pdf": st.session_state.processed_pdf,
            "pdf_summary": st.session_state.pdf_summary
        }

def save_message_to_db(role: str, content: str):
    """메시지를 데이터베이스에 저장"""
    if "current_session_id" in st.session_state:
        # 현재 세션의 메시지 수 확인 (DB 저장 전)
        current_message_count = len(st.session_state.messages)
        is_first_user_message = (role == "user" and current_message_count == 1)
        
        # 메시지 저장
        db.save_message(st.session_state.current_session_id, role, content)
        
        # 세션별 메모리도 업데이트
        if "session_memory" not in st.session_state:
            st.session_state.session_memory = {}
        
        st.session_state.session_memory[st.session_state.current_session_id] = {
            "messages": st.session_state.messages.copy(),
            "processed_pdf": st.session_state.get("processed_pdf"),
            "pdf_summary": st.session_state.get("pdf_summary")
        }
        
        # 첫 번째 사용자 메시지인 경우 세션 제목 자동 생성
        if is_first_user_message:
            # PDF 업로드 메시지인 경우 파일명 기반으로 제목 생성
            if content.startswith("📄"):
                # PDF 파일명 추출
                if "PDF 파일 업로드:" in content:
                    filename = content.split("PDF 파일 업로드:")[-1].strip()
                    # 확장자 제거하고 제목으로 사용
                    title = filename.replace('.pdf', '').replace('.PDF', '')[:15]
                    db.update_session_name(st.session_state.current_session_id, title)
                elif "**Document:**" in content:
                    # PDF + 질문 형태인 경우 질문 부분 추출
                    parts = content.split("**Query:**")
                    if len(parts) > 1:
                        query = parts[1].strip()
                        db.update_session_title_from_first_message(st.session_state.current_session_id, query)
            else:
                # 일반 텍스트 메시지인 경우 AI로 제목 생성
                db.update_session_title_from_first_message(st.session_state.current_session_id, content)
            
            # 첫 번째 사용자 메시지 저장 시 플래그 설정 (AI 응답 완료 후 새로고침)
            st.session_state.first_message_saved = True
        
        # AI 응답 완료 후 새로고침 (assistant 메시지이고 첫 대화 완료 시)
        if role == "assistant" and st.session_state.get("first_message_saved", False):
            st.session_state.first_message_saved = False
            st.rerun()

def save_document_to_db(filename: str, content: str = None, summary: str = None):
    """문서 정보를 데이터베이스에 저장"""
    if "current_session_id" in st.session_state:
        db.save_document(st.session_state.current_session_id, filename, content, summary)
        
        # 세션별 메모리도 업데이트
        if "session_memory" not in st.session_state:
            st.session_state.session_memory = {}
        
        st.session_state.session_memory[st.session_state.current_session_id] = {
            "messages": st.session_state.messages.copy(),
            "processed_pdf": st.session_state.get("processed_pdf"),
            "pdf_summary": st.session_state.get("pdf_summary")
        } 