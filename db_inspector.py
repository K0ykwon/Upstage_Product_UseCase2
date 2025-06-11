#!/usr/bin/env python3
"""
데이터베이스 로그 및 내용 확인 스크립트
사용법: python db_inspector.py
"""

import sqlite3
import json
from datetime import datetime
import os

DB_PATH = "frontend/data/chat_history.db"

def check_db_exists():
    """데이터베이스 파일 존재 확인"""
    if not os.path.exists(DB_PATH):
        print(f"❌ 데이터베이스 파일을 찾을 수 없습니다: {DB_PATH}")
        return False
    
    file_size = os.path.getsize(DB_PATH)
    print(f"📊 데이터베이스 파일: {DB_PATH}")
    print(f"📏 파일 크기: {file_size:,} bytes")
    return True

def show_sessions():
    """세션 목록 표시"""
    print("\n" + "="*60)
    print("📋 세션 목록 (최신순)")
    print("="*60)
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT session_id, session_name, created_at, updated_at, message_count
            FROM sessions
            ORDER BY updated_at DESC
        """)
        
        sessions = cursor.fetchall()
        
        if not sessions:
            print("📝 세션이 없습니다.")
            return
        
        for i, session in enumerate(sessions, 1):
            session_id, session_name, created_at, updated_at, message_count = session
            print(f"{i:2d}. {session_name}")
            print(f"    📅 생성: {created_at}")
            print(f"    🕒 수정: {updated_at}")
            print(f"    💬 메시지: {message_count}개")
            print(f"    🆔 ID: {session_id[:8]}...")
            print()

def show_messages(session_id=None, limit=10):
    """메시지 내역 표시"""
    print("\n" + "="*60)
    print(f"💬 메시지 내역 (최근 {limit}개)")
    print("="*60)
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        if session_id:
            cursor.execute("""
                SELECT role, content, timestamp
                FROM messages 
                WHERE session_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (session_id, limit))
        else:
            cursor.execute("""
                SELECT m.role, m.content, m.timestamp, s.session_name
                FROM messages m
                JOIN sessions s ON m.session_id = s.session_id
                ORDER BY m.timestamp DESC
                LIMIT ?
            """, (limit,))
        
        messages = cursor.fetchall()
        
        if not messages:
            print("📝 메시지가 없습니다.")
            return
        
        for i, msg in enumerate(messages, 1):
            if session_id:
                role, content, timestamp = msg
                session_name = ""
            else:
                role, content, timestamp, session_name = msg
                session_name = f" ({session_name})"
            
            role_emoji = "👤" if role == "user" else "🤖"
            print(f"{i:2d}. {role_emoji} {role.upper()}{session_name}")
            print(f"    🕒 {timestamp}")
            print(f"    📄 {content[:100]}{'...' if len(content) > 100 else ''}")
            print()

def show_documents():
    """문서 목록 표시"""
    print("\n" + "="*60)
    print("📄 문서 목록")
    print("="*60)
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT d.filename, d.uploaded_at, s.session_name, 
                   LENGTH(d.content) as content_size
            FROM documents d
            JOIN sessions s ON d.session_id = s.session_id
            ORDER BY d.uploaded_at DESC
        """)
        
        documents = cursor.fetchall()
        
        if not documents:
            print("📝 업로드된 문서가 없습니다.")
            return
        
        for i, (filename, uploaded, session_name, size) in enumerate(documents, 1):
            print(f"{i:2d}. 📄 {filename}")
            print(f"    📅 업로드: {uploaded}")
            print(f"    💬 세션: {session_name}")
            print(f"    📏 크기: {size:,} 문자")
            print()

def show_statistics():
    """통계 정보 표시"""
    print("\n" + "="*60)
    print("📊 데이터베이스 통계")
    print("="*60)
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # 세션 수
        cursor.execute("SELECT COUNT(*) FROM sessions")
        session_count = cursor.fetchone()[0]
        
        # 전체 메시지 수
        cursor.execute("SELECT COUNT(*) FROM messages")
        message_count = cursor.fetchone()[0]
        
        # 문서 수
        cursor.execute("SELECT COUNT(*) FROM documents")
        document_count = cursor.fetchone()[0]
        
        # 가장 활발한 세션
        cursor.execute("""
            SELECT session_name, message_count 
            FROM sessions 
            ORDER BY message_count DESC 
            LIMIT 1
        """)
        most_active = cursor.fetchone()
        
        # 최근 활동
        cursor.execute("""
            SELECT session_name, updated_at 
            FROM sessions 
            ORDER BY updated_at DESC 
            LIMIT 1
        """)
        recent_activity = cursor.fetchone()
        
        print(f"📋 총 세션 수: {session_count:,}개")
        print(f"💬 총 메시지 수: {message_count:,}개")
        print(f"📄 총 문서 수: {document_count:,}개")
        
        if most_active:
            print(f"🔥 가장 활발한 세션: {most_active[0]} ({most_active[1]}개 메시지)")
        
        if recent_activity:
            print(f"⏰ 최근 활동: {recent_activity[0]} ({recent_activity[1]})")

def main():
    """메인 함수"""
    print("🔍 AI Document Assistant - 데이터베이스 검사기")
    print("=" * 60)
    
    if not check_db_exists():
        return
    
    try:
        show_statistics()
        show_sessions()
        show_documents()
        show_messages(limit=5)
        
        print("\n" + "="*60)
        print("✅ 데이터베이스 검사 완료!")
        print("="*60)
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    main() 