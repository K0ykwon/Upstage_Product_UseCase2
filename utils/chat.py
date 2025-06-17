import os
import json
from dotenv import load_dotenv
from .database import db
from .request_rag import call_rag_api
import requests
from typing import Dict, List, Optional, Union, Generator

load_dotenv()

# 환경 변수에서 API 키 가져오기
API_KEY = os.getenv("UPSTAGE_API_KEY")
API_URL = "https://api.upstage.ai/v1/chat/completions"

def chat_with_upstage(messages, model="solar-pro2-preview", stream=False, reasoning_effort="medium"):
    """
    Upstage API를 사용한 채팅 함수
    
    Args:
        messages: 채팅 메시지 리스트 [{"role": "user", "content": "..."}]
        model: 사용할 모델 (기본값: solar-pro2-preview)
        stream: 스트리밍 여부 (기본값: False)
        reasoning_effort: 추론 강도 ("low", "medium", "high")
    
    Returns:
        응답 텍스트 또는 스트림 객체
    """
    try:
        response = requests.post(
            API_URL,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": messages,
                "reasoning_effort": reasoning_effort,
                "stream": stream
            }
        )
        
        if response.status_code == 200:
            if stream:
                return response
            else:
                return response.json()["choices"][0]["message"]["content"]
        else:
            print(f"API 호출 실패: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"채팅 API 호출 중 오류: {e}")
        return None



def summarize_conversation_history(chat_history):
    """
    대화 기록을 요약하는 함수 (현재 세션만)
    
    Args:
        chat_history: 요약할 대화 기록 리스트 (현재 세션만)
    
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

**현재 세션 대화 요약:**
- 주요 질문과 답변 내용을 불릿 포인트로 정리
- 중요한 맥락이나 정보를 포함
- 3-5개 문장으로 간결하게 작성

대화의 흐름과 핵심 내용을 유지하면서 간결하게 요약해주세요.
이 요약은 현재 세션의 맥락 유지를 위한 것입니다."""
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





def summarize_document(text, language="Korean"):
    """
    문서 요약 함수
    
    Args:
        text: 요약할 텍스트
        language: 요약 언어 (기본값: Korean)
    
    Returns:
        요약된 텍스트
    """
    system_content = f"""당신은 문서 요약 전문가입니다. 
주어진 텍스트를 {language}로 간결하고 핵심적인 내용으로 요약해주세요.
요약은 다음 형식으로 작성해주세요:

## 주요 내용
- 핵심 포인트들을 불릿 포인트로 정리

## 결론
- 문서의 주요 결론이나 시사점

요약은 원문의 20% 이내 길이로 작성해주세요."""
    
    messages = [
        {
            "role": "system",
            "content": system_content
        },
        {
            "role": "user", 
            "content": f"다음 문서를 요약해주세요:\n\n{text}"
        }
    ]
    
    return chat_with_upstage(messages, reasoning_effort="high")

def search_rag_documents(query):
    """RAG 시스템에서 관련 문서를 검색합니다."""
    try:
        rag_response = call_rag_api(query)
        if rag_response and "results" in rag_response and rag_response["results"]:
            return rag_response["results"]
        return []
    except Exception as e:
        print(f"RAG 문서 검색 중 오류 발생: {e}")
        return []

def get_rag_tools():
    """RAG 검색을 위한 도구를 반환합니다."""
    return [
        {
            "type": "function",
            "function": {
                "name": "search_documents",
                "description": "문서를 검색하여 관련 내용을 찾습니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "검색할 쿼리"
                        }
                    },
                    "required": ["query"]
                }
            }
        }
    ]

def process_rag_response(tool_calls):
    """RAG 응답을 처리합니다."""
    try:
        reference_info = ""
        rag_results = []
        
        if tool_calls:
            for tool_call in tool_calls:
                if tool_call.function.name == "search_documents":
                    results = json.loads(tool_call.function.arguments)
                    rag_results = results.get("results", [])
                    
                    if rag_results:
                        reference_info = "### 📚 참고 문서\n\n"
                        for i, result in enumerate(rag_results[:3], 1):
                            reference_info += f"**{i}. {result.get('filename', 'N/A')}**\n"
                            reference_info += f"{result.get('content', '내용 없음')}\n\n"
        
        return reference_info, rag_results
    except Exception as e:
        print(f"Error in process_rag_response: {str(e)}")
        return "", []

def should_use_rag(user_input: str, pdf_summary: str = None, conversation_history: List[Dict] = None) -> bool:
    """
    RAG 사용 여부를 판단하는 함수
    
    Args:
        user_input: 사용자 입력
        pdf_summary: PDF 요약 (선택)
        conversation_history: 대화 기록 (선택)
    
    Returns:
        bool: RAG 사용 여부
    """
    try:
        # RAG 필요성 판단을 위한 프롬프트 구성
        rag_decision_prompt = f"""다음 사용자 질문과 대화 맥락을 바탕으로 RAG(Retrieval Augmented Generation)가 필요한지 판단해주세요.

사용자 질문: {user_input}

{f'PDF 요약: {pdf_summary}' if pdf_summary else ''}

RAG가 필요한 경우는 다음과 같습니다:
1. 질문이 구체적인 정보나 사실을 요구하는 경우
2. 질문이 특정 문서나 자료의 내용을 참조해야 하는 경우
3. 질문이 전문적인 지식이나 구체적인 데이터가 필요한 경우
4. 질문이 검색이나 찾기와 관련된 경우

RAG가 필요하지 않은 경우는 다음과 같습니다:
1. 일반적인 대화나 인사인 경우
2. 추상적인 질문이나 의견을 묻는 경우
3. 간단한 설명이나 정의를 요구하는 경우
4. 대화의 맥락만으로 충분히 답변 가능한 경우

RAG가 필요한지 여부를 'yes' 또는 'no'로만 답변해주세요."""

        # LLM을 사용하여 RAG 필요성 판단
        response = requests.post(
            API_URL,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "solar-1-mini-chat",
                "messages": [
                    {"role": "system", "content": "당신은 RAG 필요성을 판단하는 전문가입니다."},
                    {"role": "user", "content": rag_decision_prompt}
                ],
                "temperature": 0.1,
                "max_tokens": 10
            }
        )
        
        decision = response.json()["choices"][0]["message"]["content"].lower().strip()
        return decision == 'yes'
        
    except Exception as e:
        print(f"RAG 필요성 판단 중 오류 발생: {str(e)}")
        return False

def get_chat_response(
    messages: List[Dict],
    system_prompt: str,
    user_input: str,
    use_rag: bool = False,
    pdf_summary: str = None
) -> Dict:
    """
    채팅 응답을 생성하는 함수
    
    Args:
        messages: 대화 기록
        system_prompt: 시스템 프롬프트
        user_input: 사용자 입력
        use_rag: RAG 사용 여부
        pdf_summary: PDF 요약
    
    Returns:
        Dict: 응답 정보
    """
    try:
        # RAG 필요성 판단
        should_use_rag_flag = should_use_rag(user_input, pdf_summary, messages) if use_rag else False
        
        if should_use_rag_flag:
            # PDF 요약이 있는 경우 검색 쿼리에 포함
            search_query = user_input
            if pdf_summary:
                search_query = f"PDF 내용: {pdf_summary}\n\n질문: {user_input}"
            
            # RAG API 호출
            rag_response = call_rag_api(search_query)
            
            if rag_response and "results" in rag_response and rag_response["results"]:
                # 시스템 프롬프트용 참고 자료 (원본)
                system_reference = '### 📚 참고 사례\n\n'
                system_reference += '아래는 참고용 사례입니다. 이 사례들은 답변의 참고 자료로만 사용되며, 직접적인 답변은 아닙니다.\n\n'
                
                # 사용자에게 보여줄 참고 자료 (요약)
                display_reference = '### 📚 참고 사례\n\n'
                
                for i, result in enumerate(rag_response["results"][:3], 1):
                    content = result.get("content", "내용 없음")
                    filename = result.get("filename", "N/A")
                    similarity = result.get("similarity", 0)
                    
                    # 시스템 프롬프트용 원본 내용
                    system_reference += f'**사례 {i}**\n'
                    system_reference += f'**파일명**: {filename}\n\n'
                    system_reference += f'**내용**:\n{content}\n\n'
                    system_reference += f'**유사도**: {similarity:.3f}\n\n'
                    system_reference += '---\n\n'
                    
                    # 사용자에게 보여줄 요약 내용
                    summarized_content = summarize_content(content)
                    display_reference += f'**사례 {i}**\n'
                    display_reference += f'**파일명**: {filename}\n\n'
                    display_reference += f'**내용**:\n{summarized_content}\n\n'
                    display_reference += f'**유사도**: {similarity:.3f}\n\n'
                    display_reference += '---\n\n'
                
                system_prompt = f"""{system_prompt}

아래의 참고 사례를 바탕으로 답변해주세요. 이 사례들은 참고용이며, 질문과는 관련이 없습니다. 
문서를 분석할 때 아래의 사례를 적절히 인용하여 답변하십시오.

{system_reference}"""
            else:
                system_reference = "참고할 수 있는 사례를 찾을 수 없습니다."
                display_reference = system_reference
        else:
            system_reference = ""
            display_reference = ""
            
        if pdf_summary:
            system_prompt += f"""아래의 사례는 유저가 직접적으로 입력한 pdf의 요약입니다. 위 사례를 바탕으로 아래 문서에 대한 유저의 질문에 답변해주세요.
            \n\n
{pdf_summary}"""

        response = requests.post(
            API_URL,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "solar-1-mini-chat",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    *messages,
                    {"role": "user", "content": user_input}
                ],
                "temperature": 0.7,
                "max_tokens": 1000
            }
        )
        
        if response.status_code == 200:
            response_data = response.json()
            if 'choices' in response_data and len(response_data['choices']) > 0:
                content = response_data['choices'][0]['message']['content']
                # 참고 자료가 있는 경우 마지막에 추가 (요약된 버전)
                if should_use_rag_flag and display_reference:
                    content += f"\n\n{display_reference}"
                return {
                    "response": content,
                    "reference": display_reference if should_use_rag_flag else ""
                }
        
        return {
            "response": "죄송합니다. 응답을 생성하는 중에 오류가 발생했습니다.",
            "reference": ""
        }
        
    except Exception as e:
        print(f"Error in get_chat_response: {str(e)}")
        return {
            "response": f"오류가 발생했습니다: {str(e)}",
            "reference": ""
        }

def summarize_content(content: str) -> str:
    try:
        response = requests.post(
            API_URL,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "solar-1-mini-chat",
                "messages": [
                    {"role": "system", "content": "주어진 내용을 1-2줄로 요약해주세요."},
                    {"role": "user", "content": content}
                ],
                "temperature": 0.7,
                "max_tokens": 500
            }
        )
        
        if response.status_code == 200:
            response_data = response.json()
            if 'choices' in response_data and len(response_data['choices']) > 0:
                return response_data['choices'][0]['message']['content']
        return content[:100] + "..."
    except Exception as e:
        print(f"요약 중 오류 발생: {str(e)}")
        return content[:100] + "..."

def stream_chat_response_with_memory(
    messages: List[Dict],
    system_prompt: str,
    user_input: str,
    use_rag: bool = False,
    pdf_summary: str = None
) -> Generator[str, None, None]:
    try:
        # RAG 필요성 판단
        should_use_rag_flag = should_use_rag(user_input, pdf_summary, messages) if use_rag else False
        
        if should_use_rag_flag:
            # PDF 요약이 있는 경우 검색 쿼리에 포함
            search_query = user_input
            if pdf_summary:
                search_query = f"PDF 내용: {pdf_summary}\n\n질문: {user_input}"
            
            # RAG API 호출
            rag_response = call_rag_api(search_query)
            
            if rag_response and "results" in rag_response and rag_response["results"]:
                # 시스템 프롬프트용 참고 자료 (원본)
                system_reference = '### 📚 참고 사례\n\n'
                system_reference += '아래는 참고용 사례입니다. 이 사례들은 답변의 참고 자료로만 사용되며, 직접적인 답변은 아닙니다.\n\n'
                
                # 사용자에게 보여줄 참고 자료 (요약)
                display_reference = '### 📚 참고 사례\n\n'
                
                for i, result in enumerate(rag_response["results"][:3], 1):
                    content = result.get("content", "내용 없음")
                    filename = result.get("filename", "N/A")
                    similarity = result.get("similarity", 0)
                    
                    # 시스템 프롬프트용 원본 내용
                    system_reference += f'**사례 {i}**\n'
                    system_reference += f'**파일명**: {filename}\n\n'
                    system_reference += f'**내용**:\n{content}\n\n'
                    system_reference += f'**유사도**: {similarity:.3f}\n\n'
                    system_reference += '---\n\n'
                    
                    # 사용자에게 보여줄 요약 내용
                    summarized_content = summarize_content(content)
                    display_reference += f'**사례 {i}**\n'
                    display_reference += f'**파일명**: {filename}\n\n'
                    display_reference += f'**내용**:\n{summarized_content}\n\n'
                    display_reference += f'**유사도**: {similarity:.3f}\n\n'
                    display_reference += '---\n\n'
                
                system_prompt = f"""{system_prompt}

아래의 참고 사례를 바탕으로 답변해주세요. 이 사례들은 참고용이며, 질문과는 관련이 없습니다. 
문서를 분석할 때 아래의 사례를 적절히 인용하여 답변하십시오.

{system_reference}"""
            else:
                system_reference = "참고할 수 있는 사례를 찾을 수 없습니다."
                display_reference = system_reference
        else:
            system_reference = ""
            display_reference = ""
            
        if pdf_summary:
            system_prompt += f"""아래의 사례는 유저가 직접적으로 입력한 pdf의 요약입니다. 위 사례를 바탕으로 아래 문서에 대한 유저의 질문에 답변해주세요.
            \n\n
{pdf_summary}"""

        # Upstage API 호출
        response = requests.post(
            API_URL,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "solar-1-mini-chat",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    *messages,
                    {"role": "user", "content": user_input}
                ],
                "temperature": 0.7,
                "max_tokens": 1000,
                "stream": True
            },
            stream=True
        )
        
        if response.status_code == 200:
            for line in response.iter_lines():
                if line:
                    try:
                        line = line.decode('utf-8')
                        if line.startswith('data: '):
                            data = line[6:]  # 'data: ' 제거
                            if data == '[DONE]':
                                break
                            try:
                                chunk = json.loads(data)
                                if 'choices' in chunk and len(chunk['choices']) > 0:
                                    delta = chunk['choices'][0].get('delta', {})
                                    if 'content' in delta:
                                        yield delta['content']
                            except json.JSONDecodeError as e:
                                print(f"JSON 디코딩 오류: {e}")
                                continue
                    except UnicodeDecodeError as e:
                        print(f"유니코드 디코딩 오류: {e}")
                        continue
            
            # 참고 자료가 있는 경우 마지막에 추가 (요약된 버전)
            if should_use_rag_flag and display_reference:
                yield f"\n\n{display_reference}"
        else:
            print(f"API 호출 실패: {response.status_code} - {response.text}")
            yield "죄송합니다. 응답을 생성하는 중에 오류가 발생했습니다."
            
    except Exception as e:
        print(f"Error in stream_chat_response_with_memory: {str(e)}")
        yield f"오류가 발생했습니다: {str(e)}"

def summarize_document(content):
    """문서를 요약합니다."""
    try:
        response = requests.post(
            API_URL,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "solar-pro2-preview",
                "messages": [
                    {"role": "system", "content": "문서의 내용을 간단히 한국어로로 요약해주세요."},
                    {"role": "user", "content": content}
                ]
            }
        )
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"문서 요약 중 오류가 발생했습니다: {str(e)}"

def document_based_qa_with_memory(document_content, user_input, messages, system_prompt, use_rag=False):
    """문서 기반 질문 답변을 생성합니다."""
    try:
        reference_info = ""
        
        # RAG 검색이 필요한 경우
        if use_rag:
            # 먼저 agent에게 RAG 검색이 필요한지 물어봄
            agent_response = requests.post(
                API_URL,
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "solar-pro2-preview",
                    "messages": [
                        {"role": "system", "content": "당신은 사용자의 질문에 답변하기 위해 추가 정보가 필요한지 판단하는 AI 어시스턴트입니다. 'yes' 또는 'no'로만 답변해주세요."},
                        {"role": "user", "content": f"다음 질문에 답변하기 위해 추가 정보나 참고 자료가 필요할까요?\n\n문서: {document_content}\n\n질문: {user_input}"}
                    ]
                }
            )
            
            needs_rag = agent_response.json()["choices"][0]["message"]["content"].lower().strip() == "yes"
            
            if needs_rag:
                # RAG 검색 실행
                response = requests.post(
                    API_URL,
                    headers={
                        "Authorization": f"Bearer {API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "solar-pro2-preview",
                        "messages": [{"role": "user", "content": user_input}],
                        "tools": get_rag_tools(),
                        "tool_choice": "auto"
                    }
                )
                
                response_message = response.json()["choices"][0]["message"]
                tool_calls = response_message.get("tool_calls", [])
                
                reference_info, _ = process_rag_response(tool_calls)
                
                # RAG 결과를 시스템 프롬프트에 추가
                if reference_info:
                    system_prompt += f"\n\n참고 자료:\n{reference_info}"
        
        # 문서 기반 응답 생성
        response = requests.post(
            API_URL,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "solar-pro2-preview",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    *messages,
                    {"role": "user", "content": f"문서 내용:\n{document_content}\n\n질문: {user_input}"}
                ]
            }
        )
        
        return {
            "content": response.json()["choices"][0]["message"]["content"],
            "reference_info": reference_info if use_rag else ""
        }
    except Exception as e:
        return {
            "content": f"오류가 발생했습니다: {str(e)}",
            "reference_info": ""
        }

# 기존 함수들 (하위 호환성 유지)
def build_conversation_messages(chat_history, system_prompt, current_input, recent_count=7):
    """
    대화 기록을 포함한 메시지 구성 (프로필 기능 없음)
    
    Args:
        chat_history: 현재 세션의 메시지 히스토리
        system_prompt: 기본 시스템 프롬프트
        current_input: 현재 사용자 입력
        recent_count: 그대로 유지할 최근 대화 수 (기본값: 7)
    
    Returns:
        OpenAI 형식의 메시지 리스트
    """
    messages = [{"role": "system", "content": system_prompt}]
    
    # 현재 세션의 대화 기록이 recent_count*2 개를 초과하는 경우
    if len(chat_history) > recent_count * 2:
        # 이전 대화들 (요약 대상) - 현재 세션만
        old_history = chat_history[:-recent_count*2]
        # 최근 대화들 (그대로 유지) - 현재 세션만
        recent_history = chat_history[-recent_count*2:]
        
        # 현재 세션의 이전 대화 요약 생성
        conversation_summary = summarize_conversation_history(old_history)
        
        # 요약이 있으면 시스템 메시지에 추가
        if conversation_summary:
            enhanced_system_prompt = f"""{system_prompt}

{conversation_summary}

위는 현재 세션의 이전 대화 요약입니다. 이를 참고하여 답변해주세요."""
            messages[0]["content"] = enhanced_system_prompt
        
        # 최근 대화만 메시지에 추가
        target_history = recent_history
    else:
        # 대화가 적으면 현재 세션의 모든 대화 유지
        target_history = chat_history
    
    # 현재 세션의 대화 기록을 OpenAI 형식으로 변환
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

def answer_question(question, context=None):
    """
    질문 답변 함수 (메모리 없음 - 하위 호환성)
    """
    return answer_question_with_memory(question, [], context)

def document_based_qa(document_summary, user_question):
    """
    문서 기반 질문 답변 함수 (메모리 없음 - 하위 호환성)
    """
    return document_based_qa_with_memory(document_summary, user_question, [], "")

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

def summarize_text(text, max_length=100):
    """텍스트를 간단히 요약합니다."""
    try:
        response = requests.post(
            API_URL,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "solar-pro2-preview",
                "messages": [
                    {"role": "system", "content": f"다음 텍스트를 {max_length}자 이내로 간단히 요약해주세요. 핵심 내용만 포함해주세요."},
                    {"role": "user", "content": text}
                ]
            }
        )
        return response.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"Error in summarize_text: {str(e)}")
        return text[:max_length] + "..."

def get_llm_response(system_prompt, user_input):
    """LLM을 사용하여 응답을 생성합니다."""
    try:
        response = requests.post(
            API_URL,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "solar-pro2-preview",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input}
                ]
            }
        )
        return response.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"Error in get_llm_response: {str(e)}")
        return "죄송합니다. 응답을 생성하는 중에 오류가 발생했습니다."

def stream_llm_response(system_prompt, user_input):
    """LLM을 사용하여 스트리밍 응답을 생성합니다."""
    try:
        response = requests.post(
            API_URL,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "solar-pro2-preview",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input}
                ],
                "stream": True
            }
        )
        
        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception as e:
        print(f"Error in stream_llm_response: {str(e)}")
        yield "죄송합니다. 응답을 생성하는 중에 오류가 발생했습니다." 