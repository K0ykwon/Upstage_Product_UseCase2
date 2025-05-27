from openai import OpenAI
import os
import json
from dotenv import load_dotenv

load_dotenv()

# OpenAI 호환 클라이언트 초기화
client = OpenAI(
    api_key=os.getenv("UPSTAGE_API_KEY"),
    base_url="https://api.upstage.ai/v1"
)

def chat_with_upstage(messages, model="solar-pro2-preview", stream=False, reasoning_effort="medium"):
    """
    Upstage OpenAI 호환 API를 사용한 채팅 함수
    
    Args:
        messages: 채팅 메시지 리스트 [{"role": "user", "content": "..."}]
        model: 사용할 모델 (기본값: solar-pro2-preview)
        stream: 스트리밍 여부 (기본값: False)
        reasoning_effort: 추론 강도 ("low", "medium", "high")
    
    Returns:
        응답 텍스트 또는 스트림 객체
    """
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            reasoning_effort=reasoning_effort,
            stream=stream,
        )
        
        if stream:
            return response
        else:
            return response.choices[0].message.content
            
    except Exception as e:
        print(f"채팅 API 호출 중 오류: {e}")
        return None

def summarize_conversation_history(chat_history):
    """
    대화 기록을 요약하는 함수
    
    Args:
        chat_history: 요약할 대화 기록 리스트
    
    Returns:
        요약된 대화 내용
    """
    if not chat_history:
        return ""
    
    # 대화 내용을 텍스트로 변환
    conversation_text = ""
    for msg in chat_history:
        if msg["role"] in ["user", "assistant"]:
            role_name = "사용자" if msg["role"] == "user" else "AI"
            content = msg["content"]
            # 특수 형식 메시지 제외
            if not content.startswith("📄") and not content.startswith("❌"):
                conversation_text += f"{role_name}: {content}\n\n"
    
    if not conversation_text.strip():
        return ""
    
    # 요약 생성
    messages = [
        {
            "role": "system",
            "content": """당신은 대화 요약 전문가입니다. 
주어진 대화 내용을 간결하고 핵심적으로 요약해주세요.
요약은 다음 형식으로 작성해주세요:

**이전 대화 요약:**
- 주요 질문과 답변 내용을 불릿 포인트로 정리
- 중요한 맥락이나 정보를 포함
- 3-5개 문장으로 간결하게 작성

대화의 흐름과 핵심 내용을 유지하면서 간결하게 요약해주세요."""
        },
        {
            "role": "user",
            "content": f"다음 대화를 요약해주세요:\n\n{conversation_text}"
        }
    ]
    
    try:
        summary = chat_with_upstage(messages, reasoning_effort="medium")
        return summary if summary else ""
    except:
        return ""

def build_conversation_messages(chat_history, system_prompt, current_input, recent_count=7):
    """
    대화 기록을 포함한 메시지 구성 (최근 7개는 그대로, 이전 것들은 요약)
    
    Args:
        chat_history: Streamlit 세션의 메시지 히스토리
        system_prompt: 시스템 프롬프트
        current_input: 현재 사용자 입력
        recent_count: 그대로 유지할 최근 대화 수 (기본값: 7)
    
    Returns:
        OpenAI 형식의 메시지 리스트
    """
    messages = [{"role": "system", "content": system_prompt}]
    
    # 대화 기록이 recent_count*2 개를 초과하는 경우
    if len(chat_history) > recent_count * 2:
        # 이전 대화들 (요약 대상)
        old_history = chat_history[:-recent_count*2]
        # 최근 대화들 (그대로 유지)
        recent_history = chat_history[-recent_count*2:]
        
        # 이전 대화 요약 생성
        conversation_summary = summarize_conversation_history(old_history)
        
        # 요약이 있으면 시스템 메시지에 추가
        if conversation_summary:
            enhanced_system_prompt = f"""{system_prompt}

{conversation_summary}

위는 이전 대화의 요약입니다. 이를 참고하여 답변해주세요."""
            messages[0]["content"] = enhanced_system_prompt
        
        # 최근 대화만 메시지에 추가
        target_history = recent_history
    else:
        # 대화가 적으면 모든 대화 유지
        target_history = chat_history
    
    # 대화 기록을 OpenAI 형식으로 변환
    for msg in target_history:
        if msg["role"] in ["user", "assistant"]:
            content = msg["content"]
            # 특수 형식 메시지 제외
            if not content.startswith("📄") and not content.startswith("❌"):
                messages.append({
                    "role": msg["role"],
                    "content": content
                })
    
    # 현재 입력 추가
    messages.append({"role": "user", "content": current_input})
    
    return messages

def summarize_document(text, language="Korean"):
    """
    문서 요약 함수
    
    Args:
        text: 요약할 텍스트
        language: 요약 언어 (기본값: Korean)
    
    Returns:
        요약된 텍스트
    """
    messages = [
        {
            "role": "system",
            "content": f"""당신은 문서 요약 전문가입니다. 
주어진 텍스트를 {language}로 간결하고 핵심적인 내용으로 요약해주세요.
요약은 다음 형식으로 작성해주세요:

## 주요 내용
- 핵심 포인트들을 불릿 포인트로 정리

## 결론
- 문서의 주요 결론이나 시사점

요약은 원문의 20% 이내 길이로 작성해주세요."""
        },
        {
            "role": "user", 
            "content": f"다음 문서를 요약해주세요:\n\n{text}"
        }
    ]
    
    return chat_with_upstage(messages, reasoning_effort="high")

def answer_question_with_memory(question, chat_history, context=None):
    """
    대화 기록을 고려한 질문 답변 함수
    
    Args:
        question: 사용자 질문
        chat_history: 이전 대화 기록
        context: 참고할 문맥 (선택사항)
    
    Returns:
        답변 텍스트
    """
    if context:
        system_prompt = f"""당신은 도움이 되는 AI 어시스턴트입니다. 
주어진 문맥과 이전 대화 내용을 바탕으로 사용자의 질문에 정확하고 유용한 답변을 제공해주세요.
답변은 한국어로 작성하고, 가능한 한 구체적이고 실용적인 정보를 포함해주세요.

참고 문맥: {context}"""
    else:
        system_prompt = """당신은 도움이 되는 AI 어시스턴트입니다.
이전 대화 내용을 참고하여 사용자의 질문에 정확하고 유용한 답변을 한국어로 제공해주세요.
대화의 맥락을 이해하고 연속성 있는 답변을 해주세요.
모르는 내용에 대해서는 솔직하게 모른다고 답변해주세요."""
    
    messages = build_conversation_messages(chat_history, system_prompt, question)
    return chat_with_upstage(messages, reasoning_effort="high")

def document_based_qa_with_memory(document_summary, user_question, chat_history):
    """
    대화 기록을 고려한 문서 기반 질문 답변 함수
    
    Args:
        document_summary: 문서 요약
        user_question: 사용자 질문
        chat_history: 이전 대화 기록
    
    Returns:
        문서 기반 답변
    """
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
{document_summary}"""
    
    messages = build_conversation_messages(chat_history, system_prompt, user_question)
    return chat_with_upstage(messages, reasoning_effort="high")

def stream_chat_response_with_memory(chat_history, system_prompt, current_input):
    """
    대화 기록을 고려한 스트리밍 채팅 응답 함수
    
    Args:
        chat_history: 이전 대화 기록
        system_prompt: 시스템 프롬프트
        current_input: 현재 사용자 입력
    
    Yields:
        스트리밍 텍스트 청크
    """
    try:
        messages = build_conversation_messages(chat_history, system_prompt, current_input)
        stream = chat_with_upstage(messages, stream=True, reasoning_effort="medium")
        
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content
                
    except Exception as e:
        yield f"스트리밍 중 오류가 발생했습니다: {e}"

# 기존 함수들 (하위 호환성 유지)
def answer_question(question, context=None):
    """
    질문 답변 함수 (메모리 없음 - 하위 호환성)
    """
    return answer_question_with_memory(question, [], context)

def document_based_qa(document_summary, user_question):
    """
    문서 기반 질문 답변 함수 (메모리 없음 - 하위 호환성)
    """
    return document_based_qa_with_memory(document_summary, user_question, [])

def stream_chat_response(messages):
    """
    스트리밍 채팅 응답 함수 (메모리 없음 - 하위 호환성)
    """
    try:
        stream = chat_with_upstage(messages, stream=True, reasoning_effort="medium")
        
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content
                
    except Exception as e:
        yield f"스트리밍 중 오류가 발생했습니다: {e}" 