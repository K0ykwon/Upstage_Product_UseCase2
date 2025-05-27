# AI Document Assistant Frontend

PDF 문서 분석과 질문 답변을 제공하는 Streamlit 기반 챗봇 애플리케이션입니다.

## 주요 기능

### 3가지 사용 케이스

1. **PDF만 업로드**: PDF 요약 + 유사 보고서 검색
2. **텍스트만 입력**: 질문에 대한 답변 제공  
3. **PDF + 텍스트**: 문서 기반 맞춤 답변

## 설치 및 실행

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. 환경 변수 설정
`.env` 파일을 생성하고 다음 내용을 추가하세요:

```env
# Upstage API Key
UPSTAGE_API_KEY=your_upstage_api_key_here

# RAG API Endpoint  
RAG_ENDPOINT=http://localhost:8000/query
```

### 3. 애플리케이션 실행
```bash
streamlit run main.py
```

## 사용 방법

### 사이드바
- **PDF 파일 업로드**: 분석할 PDF 파일을 업로드
- **강제 OCR 사용**: 이미지 기반 PDF의 경우 체크

### 메인 화면
- **채팅 인터페이스**: 하단 입력창에 질문 입력
- **대화 기록**: 이전 대화 내용 확인
- **상태 표시**: 현재 문서 처리 상태 확인

## 기능 상세

### 케이스 1: PDF만 업로드
- PDF 텍스트 추출 및 요약 생성
- 유사 보고서/문서 검색 (RAG API 활용)
- 문서 분석 결과 표시

### 케이스 2: 텍스트만 입력
- 사용자 질문에 대한 답변 생성
- RAG API를 통한 관련 정보 검색
- 참고 자료 제공

### 케이스 3: PDF + 텍스트
- 업로드된 문서 내용 분석
- 문서 기반 맞춤 답변 생성
- 추가 참고 자료 제공

## 기술 스택

- **Frontend**: Streamlit
- **PDF 처리**: Upstage Document AI
- **텍스트 요약**: LangChain + Upstage Solar
- **RAG**: 외부 RAG API 연동
- **UI/UX**: 모던 챗봇 인터페이스

## 파일 구조

```
frontend/
├── main.py              # 메인 Streamlit 앱
├── requirements.txt     # 의존성 목록
├── README.md           # 사용 설명서
└── utils/              # 유틸리티 모듈
    ├── pdf_upload.py   # PDF 처리
    ├── graph.py        # 워크플로우 실행
    ├── generate_summary.py  # 텍스트 요약
    └── request_rag.py  # RAG API 호출
```

## 주의사항

- Upstage API 키가 필요합니다
- RAG API 서버가 실행 중이어야 합니다
- PDF 파일은 텍스트 추출이 가능한 형태여야 합니다
- 이미지 기반 PDF의 경우 "강제 OCR 사용" 옵션을 체크하세요 