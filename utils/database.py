import sqlite3
import json
import uuid
from datetime import datetime
from typing import List, Dict, Optional
import os

class ChatDatabase:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = os.path.join("/tmp", "chat_history.db")
        self.db_path = db_path
        
        # 데이터베이스 디렉토리 생성
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # 데이터베이스 초기화
        self.init_database()
    
    def init_database(self):
        """데이터베이스 테이블 초기화"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 세션 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    session_name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    message_count INTEGER DEFAULT 0
                )
            """)
            
            # 메시지 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions (session_id)
                )
            """)
            
            # 문서 테이블 (PDF 정보)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    content TEXT,
                    summary TEXT,
                    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions (session_id)
                )
            """)
            
            conn.commit()
    
    def create_session(self, session_name: str = None) -> str:
        """새 세션 생성 (최대 10개 세션 유지)"""
        session_id = str(uuid.uuid4())
        
        if not session_name:
            session_name = "새 대화"
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 현재 세션 수 확인
            cursor.execute("SELECT COUNT(*) FROM sessions")
            session_count = cursor.fetchone()[0]
            
            # 10개 이상인 경우 가장 오래된 세션 삭제
            if session_count >= 10:
                cursor.execute("""
                    SELECT session_id FROM sessions 
                    ORDER BY updated_at ASC 
                    LIMIT ?
                """, (session_count - 9,))  # 10개를 유지하므로 초과분 삭제
                
                old_sessions = cursor.fetchall()
                
                for (old_session_id,) in old_sessions:
                    # 관련 데이터 모두 삭제
                    cursor.execute("DELETE FROM messages WHERE session_id = ?", (old_session_id,))
                    cursor.execute("DELETE FROM documents WHERE session_id = ?", (old_session_id,))
                    cursor.execute("DELETE FROM sessions WHERE session_id = ?", (old_session_id,))
                    print(f"🗑️ 오래된 세션 삭제: {old_session_id[:8]}...")
            
            # 새 세션 생성
            cursor.execute("""
                INSERT INTO sessions (session_id, session_name)
                VALUES (?, ?)
            """, (session_id, session_name))
            conn.commit()
        
        return session_id
    
    def get_sessions(self) -> List[Dict]:
        """모든 세션 목록 조회 (마지막 대화 시간순)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT session_id, session_name, created_at, updated_at, message_count
                FROM sessions
                ORDER BY updated_at DESC
            """)
            
            sessions = []
            for row in cursor.fetchall():
                sessions.append({
                    'session_id': row[0],
                    'session_name': row[1],
                    'created_at': row[2],
                    'updated_at': row[3],
                    'message_count': row[4]
                })
            
            return sessions
    
    def update_session_name(self, session_id: str, new_name: str):
        """세션 이름 업데이트"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE sessions 
                SET session_name = ?, updated_at = CURRENT_TIMESTAMP
                WHERE session_id = ?
            """, (new_name, session_id))
            conn.commit()
    
    def delete_session(self, session_id: str):
        """세션 삭제 (메시지와 문서도 함께 삭제)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 관련 데이터 모두 삭제
            cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            cursor.execute("DELETE FROM documents WHERE session_id = ?", (session_id,))
            cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            
            conn.commit()
    
    def save_message(self, session_id: str, role: str, content: str):
        """모든 메시지를 데이터베이스에 저장"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 메시지 수 업데이트 및 메시지 저장 (모든 메시지)
            cursor.execute("""
                UPDATE sessions 
                SET message_count = message_count + 1, updated_at = CURRENT_TIMESTAMP
                WHERE session_id = ?
            """, (session_id,))
            
            # 모든 메시지를 DB에 저장
            cursor.execute("""
                INSERT INTO messages (session_id, role, content)
                VALUES (?, ?, ?)
            """, (session_id, role, content))
            
            conn.commit()
    
    def get_messages(self, session_id: str) -> List[Dict]:
        """세션의 모든 메시지 조회"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT role, content, timestamp
                FROM messages
                WHERE session_id = ?
                ORDER BY timestamp ASC
            """, (session_id,))
            
            messages = []
            for row in cursor.fetchall():
                messages.append({
                    'role': row[0],
                    'content': row[1],
                    'timestamp': row[2]
                })
            
            return messages
    
    def save_document(self, session_id: str, filename: str, content: str = None, summary: str = None):
        """문서 정보 저장"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO documents (session_id, filename, content, summary)
                VALUES (?, ?, ?, ?)
            """, (session_id, filename, content, summary))
            conn.commit()
    
    def get_document(self, session_id: str) -> Optional[Dict]:
        """세션의 문서 정보 조회"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT filename, content, summary, uploaded_at
                FROM documents
                WHERE session_id = ?
                ORDER BY uploaded_at DESC
                LIMIT 1
            """, (session_id,))
            
            row = cursor.fetchone()
            if row:
                return {
                    'filename': row[0],
                    'content': row[1],
                    'summary': row[2],
                    'uploaded_at': row[3]
                }
            return None
    
    def clear_all_data(self):
        """모든 데이터 삭제 (개발/테스트용)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM messages")
            cursor.execute("DELETE FROM documents")
            cursor.execute("DELETE FROM sessions")
            conn.commit()

    def update_session_title_from_first_message(self, session_id: str, first_user_message: str):
        """첫 번째 사용자 메시지를 기반으로 세션 제목 생성 및 업데이트"""
        try:
            # OpenAI 클라이언트를 직접 사용하여 제목 생성
            from openai import OpenAI
            import os
            from dotenv import load_dotenv
            
            load_dotenv()
            
            client = OpenAI(
                api_key=os.getenv("UPSTAGE_API_KEY"),
                base_url="https://api.upstage.ai/v1"
            )
            
            # 문서 업로드가 포함된 메시지인지 확인
            document_info = ""
            if "**Document:**" in first_user_message:
                parts = first_user_message.split("**Document:**")
                if len(parts) > 1:
                    doc_part = parts[1].split("**Query:**")[0].strip()
                    document_info = f"\n문서 정보: {doc_part}"
            
            title_prompt = f"""다음 사용자의 첫 번째 메시지를 바탕으로 대화 세션의 창의적이고 구체적인 제목을 생성해주세요.

사용자 메시지: "{first_user_message}"{document_info}

제목 생성 규칙:
1. 8-15글자 사이로 작성
2. 구체적인 주제나 핵심 키워드 포함
3. 창의적이고 기억하기 쉬운 제목
4. 특수문자나 이모지 사용 금지
5. 명사형으로 작성
6. 일반적인 표현보다는 구체적인 표현 선호

좋은 제목 예시:
- "안녕하세요" → "AI 어시스턴트 첫 만남"
- "이 문서를 요약해줘" → "문서 핵심 내용 분석"
- "마케팅 전략에 대해 알려줘" → "마케팅 전략 가이드"
- "파이썬 코딩 질문이 있어" → "파이썬 프로그래밍 도움"
- "건강한 식단 추천해줘" → "건강 식단 설계"
- "회사 보고서 분석" → "비즈니스 리포트 분석"

피해야 할 제목:
- "질문", "요청", "문의" 같은 일반적 표현
- "인사", "안녕" 같은 단순한 표현
- "도움", "설명" 같은 모호한 표현

사용자의 의도와 목적을 파악하여 구체적이고 매력적인 제목을 만들어주세요. 제목만 답변해주세요."""

            messages = [
                {"role": "system", "content": "당신은 창의적인 제목 생성 전문가입니다. 사용자의 의도를 파악하여 기억하기 쉽고 구체적인 제목을 만들어주세요."},
                {"role": "user", "content": title_prompt}
            ]
            
            response = client.chat.completions.create(
                model="solar-pro2-preview",
                messages=messages
            )
            
            generated_title = response.choices[0].message.content
            
            if generated_title and len(generated_title.strip()) > 0:
                # 생성된 제목 정리 (따옴표, 개행 등 제거)
                clean_title = generated_title.strip().replace('"', '').replace("'", "").replace('\n', ' ')
                
                # 길이 제한 (최대 20자)
                if len(clean_title) > 20:
                    clean_title = clean_title[:20]
                
                # 세션 제목 업데이트
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE sessions 
                        SET session_name = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE session_id = ?
                    """, (clean_title, session_id))
                    conn.commit()
                
                return clean_title
            
        except Exception as e:
            print(f"제목 생성 중 오류: {e}")
        
        # AI 제목 생성 실패 시 기본 제목 생성
        try:
            # 간단한 키워드 기반 제목 생성
            message_lower = first_user_message.lower()
            
            # 문서 관련
            if any(word in message_lower for word in ['pdf', '문서', '파일', '요약', '분석']):
                return "문서 분석 요청"
            # 질문 관련
            elif any(word in message_lower for word in ['질문', '궁금', '어떻게', '무엇', '왜']):
                return "전문 상담 요청"
            # 추천 관련
            elif any(word in message_lower for word in ['추천', '제안', '알려줘', '소개']):
                return "정보 추천 요청"
            # 인사 관련
            elif any(word in message_lower for word in ['안녕', '하이', '헬로', '처음']):
                return "AI 어시스턴트 첫 만남"
            else:
                return "새로운 대화"
                
        except:
            return "새로운 대화"

# 전역 데이터베이스 인스턴스
db = ChatDatabase() 
