import sqlite3
import json
import uuid
from datetime import datetime
from typing import List, Dict, Optional
import os

class ChatDatabase:
    def __init__(self, db_path: str = "frontend/data/chat_history.db"):
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
            
            # 사용자 프로필 테이블 (모든 세션에서 공유되는 사용자 특성)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_profile (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT DEFAULT 'default_user',
                    interests TEXT,  -- JSON 형태로 관심사 저장
                    personality_traits TEXT,  -- JSON 형태로 성향 저장
                    preferred_response_style TEXT,  -- 선호하는 답변 스타일
                    communication_patterns TEXT,  -- JSON 형태로 소통 패턴 저장
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 기본 사용자 프로필 생성 (없는 경우)
            cursor.execute("""
                INSERT OR IGNORE INTO user_profile (user_id, interests, personality_traits, preferred_response_style, communication_patterns)
                VALUES ('default_user', '[]', '[]', '', '[]')
            """)
            
            conn.commit()
    
    def create_session(self, session_name: str = None) -> str:
        """새 세션 생성"""
        session_id = str(uuid.uuid4())
        
        if not session_name:
            session_name = "새 대화"
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sessions (session_id, session_name)
                VALUES (?, ?)
            """, (session_id, session_name))
            conn.commit()
        
        return session_id
    
    def get_sessions(self) -> List[Dict]:
        """모든 세션 목록 조회 (최신 생성순)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT session_id, session_name, created_at, message_count
                FROM sessions
                ORDER BY created_at DESC
            """)
            
            sessions = []
            for row in cursor.fetchall():
                sessions.append({
                    'session_id': row[0],
                    'session_name': row[1],
                    'created_at': row[2],
                    'message_count': row[3]
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
        """메시지 저장 (채팅 5개부터 저장)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 현재 세션의 메시지 수 확인
            cursor.execute("""
                SELECT message_count FROM sessions WHERE session_id = ?
            """, (session_id,))
            
            result = cursor.fetchone()
            current_count = result[0] if result else 0
            
            # 메시지 수 업데이트 (항상)
            cursor.execute("""
                UPDATE sessions 
                SET message_count = message_count + 1, updated_at = CURRENT_TIMESTAMP
                WHERE session_id = ?
            """, (session_id,))
            
            # 채팅 5개부터 DB에 저장
            if current_count >= 4:  # 5번째 메시지부터 저장 (0-based index)
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
    
    def update_user_profile(self, interests: List[str] = None, personality_traits: List[str] = None, 
                           preferred_response_style: str = None, communication_patterns: List[str] = None,
                           user_id: str = 'default_user'):
        """사용자 프로필 업데이트"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 현재 프로필 조회
            cursor.execute("""
                SELECT interests, personality_traits, preferred_response_style, communication_patterns
                FROM user_profile WHERE user_id = ?
            """, (user_id,))
            
            current = cursor.fetchone()
            if current:
                current_interests = json.loads(current[0]) if current[0] else []
                current_traits = json.loads(current[1]) if current[1] else []
                current_style = current[2] or ""
                current_patterns = json.loads(current[3]) if current[3] else []
                
                # 새로운 정보 병합
                if interests:
                    current_interests.extend([i for i in interests if i not in current_interests])
                if personality_traits:
                    current_traits.extend([t for t in personality_traits if t not in current_traits])
                if preferred_response_style:
                    current_style = preferred_response_style
                if communication_patterns:
                    current_patterns.extend([p for p in communication_patterns if p not in current_patterns])
                
                # 업데이트
                cursor.execute("""
                    UPDATE user_profile 
                    SET interests = ?, personality_traits = ?, preferred_response_style = ?, 
                        communication_patterns = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                """, (json.dumps(current_interests), json.dumps(current_traits), 
                      current_style, json.dumps(current_patterns), user_id))
            
            conn.commit()
    
    def get_user_profile(self, user_id: str = 'default_user') -> Dict:
        """사용자 프로필 조회"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT interests, personality_traits, preferred_response_style, communication_patterns
                FROM user_profile WHERE user_id = ?
            """, (user_id,))
            
            row = cursor.fetchone()
            if row:
                return {
                    'interests': json.loads(row[0]) if row[0] else [],
                    'personality_traits': json.loads(row[1]) if row[1] else [],
                    'preferred_response_style': row[2] or "",
                    'communication_patterns': json.loads(row[3]) if row[3] else []
                }
            return {
                'interests': [],
                'personality_traits': [],
                'preferred_response_style': "",
                'communication_patterns': []
            }
    
    def analyze_and_update_user_profile(self, session_messages: List[Dict]):
        """대화 내용을 분석하여 사용자 프로필 자동 업데이트"""
        if len(session_messages) < 6:  # 충분한 대화가 있을 때만 분석
            return
        
        # 사용자 메시지만 추출
        user_messages = [msg['content'] for msg in session_messages if msg['role'] == 'user']
        
        if len(user_messages) < 3:
            return
        
        # 간단한 키워드 기반 분석 (실제로는 더 정교한 NLP 분석 가능)
        interests_keywords = {
            '기술': ['AI', '인공지능', '프로그래밍', '코딩', '개발', '소프트웨어', '하드웨어'],
            '비즈니스': ['사업', '경영', '마케팅', '투자', '창업', '회사', '매출'],
            '교육': ['학습', '공부', '교육', '강의', '수업', '시험', '학교'],
            '건강': ['운동', '건강', '다이어트', '의료', '병원', '약'],
            '여행': ['여행', '관광', '휴가', '호텔', '항공', '해외'],
            '음식': ['요리', '맛집', '레시피', '음식', '카페', '레스토랑']
        }
        
        detected_interests = []
        for category, keywords in interests_keywords.items():
            for message in user_messages:
                if any(keyword in message for keyword in keywords):
                    detected_interests.append(category)
                    break
        
        # 성향 분석 (질문 패턴 기반)
        personality_traits = []
        question_count = sum(1 for msg in user_messages if '?' in msg or '뭐' in msg or '어떻게' in msg)
        if question_count > len(user_messages) * 0.6:
            personality_traits.append('호기심이 많음')
        
        detail_count = sum(1 for msg in user_messages if len(msg) > 50)
        if detail_count > len(user_messages) * 0.5:
            personality_traits.append('상세한 설명을 선호')
        
        # 프로필 업데이트
        if detected_interests or personality_traits:
            self.update_user_profile(
                interests=detected_interests,
                personality_traits=personality_traits
            )
    
    def clear_all_data(self):
        """모든 데이터 삭제 (개발/테스트용)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM messages")
            cursor.execute("DELETE FROM documents")
            cursor.execute("DELETE FROM sessions")
            cursor.execute("DELETE FROM user_profile")
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
            
            title_prompt = f"""다음 사용자의 첫 번째 메시지를 바탕으로 대화 세션의 간결한 제목을 생성해주세요.

사용자 메시지: "{first_user_message}"

규칙:
1. 10글자 이내로 간결하게
2. 핵심 주제나 키워드 포함
3. 특수문자나 이모지 사용 금지
4. 명사형으로 작성

예시:
- "파이썬 프로그래밍 질문" → "파이썬 프로그래밍"
- "마케팅 전략에 대해 알려줘" → "마케팅 전략"
- "건강한 식단 추천해줘" → "건강 식단"

제목만 답변해주세요."""

            messages = [
                {"role": "system", "content": "당신은 대화 제목 생성 전문가입니다. 간결하고 명확한 제목을 만들어주세요."},
                {"role": "user", "content": title_prompt}
            ]
            
            response = client.chat.completions.create(
                model="solar-pro2-preview",
                messages=messages,
                reasoning_effort="low"
            )
            
            generated_title = response.choices[0].message.content
            
            if generated_title and len(generated_title.strip()) > 0:
                # 생성된 제목 정리 (따옴표, 개행 등 제거)
                clean_title = generated_title.strip().replace('"', '').replace("'", "").replace('\n', ' ')[:15]
                
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
        
        # AI 제목 생성 실패 시 기본 제목 유지
        return None

# 전역 데이터베이스 인스턴스
db = ChatDatabase() 