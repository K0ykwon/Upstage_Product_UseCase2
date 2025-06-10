# AI Document Assistant

PDF 문서 분석과 질문 답변을 제공하는 Streamlit 기반 지능형 문서 처리 시스템입니다.

## 개요

본 애플리케이션은 Upstage Document AI와 Solar LLM을 활용하여 복합적인 PDF 문서를 신속하고 정확하게 분석하고, RAG(Retrieval-Augmented Generation) 기법을 통해 맥락적인 질의응답을 제공하는 지능형 문서 처리 플랫폼입니다. 사용자는 직관적인 인터페이스를 통해 문서 업로드, 자연어 질문, 실시간 대화를 경험할 수 있으며, 다국어 지원과 세션 관리 기능을 통해 효율적인 문서 작업 환경을 제공받을 수 있습니다.

## 시스템 아키텍처

본 시스템은 세 가지 핵심 파이프라인으로 구성됩니다:

### 1. 문서 처리 파이프라인
PDF 업로드부터 Document Parse API를 통한 텍스트 추출, Solar LLM 요약, 한국어 번역 순으로 진행됩니다. 이미지 기반 PDF의 경우 OCR 자동 감지 및 처리가 수행되며, 추출된 텍스트는 세션별로 관리되어 대화 맥락을 유지합니다.

### 2. RAG 검색 파이프라인  
데이터 로드에서 시작하여 Solar LLM 요약, LangChain 청킹, 해시 기반 캐싱, Solar Embedding, FAISS 벡터 저장 순으로 처리됩니다. 사용자 질문 시 벡터 유사도 검색을 통해 관련 문서 3개를 추출하고 검색 결과를 한국어로 번역하여 컨텍스트를 제공합니다.

### 3. 통합 응답 생성
RAG 필요성을 LLM이 자동 판단하고, 검색된 참조 문서와 업로드된 PDF를 종합하여 최종 답변을 생성하며, 스트리밍 응답을 지원하여 실시간 피드백을 제공합니다.

## 주요 기능

### 3가지 사용 케이스

1. **PDF만 업로드**: PDF 요약 + 유사 보고서 검색
2. **텍스트만 입력**: 질문에 대한 답변 제공  
3. **PDF + 텍스트**: 문서 기반 맞춤 답변

## 시스템 요구사항

- **Python**: 3.8 이상
- **운영체제**: Windows, macOS, Linux 지원
- **메모리**: 최소 4GB RAM (대용량 문서 처리 시 8GB 권장)
- **저장공간**: 최소 2GB 여유 공간

## 설치 및 실행

### 1. 환경 설정
```bash
git clone [repository_url]
cd Upstage_Product_UseCase2
pip install -r requirements.txt
```

### 2. 환경 변수 설정
`.env` 파일을 생성하고 다음 내용을 추가하세요:

```env
# Upstage API Key
UPSTAGE_API_KEY=your_upstage_api_key_here
UPSTAGE_API_URL=https://api.upstage.ai/v1

# RAG API Endpoint  
RAG_ENDPOINT=http://localhost:8000/query
```

### 3. 애플리케이션 실행
```bash
streamlit run main.py
```

### 4. 브라우저 접속
자동으로 열리는 로컬 URL(통상 http://localhost:8501)에 접속하여 PDF 업로드 후 질문을 입력하여 테스트할 수 있습니다.

## 사용 방법

### 메인 인터페이스
- **PDF 업로드 섹션**: 드래그 앤 드롭 지원, 10MB 제한
- **메시지 입력창**: 자연어 질문 입력
- **옵션 체크박스**: Force OCR, Streaming Response, Use RAG
- **사이드바**: 세션 관리, 대화 히스토리

### 처리 상태 표시
- PDF 분석 진행률 표시
- RAG 검색 단계별 상태 업데이트  
- 실시간 응답 스트리밍

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
- **LLM**: Upstage Solar LLM
- **임베딩**: Solar Embedding
- **텍스트 처리**: LangChain
- **벡터 검색**: FAISS
- **RAG**: 커스텀 RAG 시스템

## 파일 구조

```
Upstage_Product_UseCase2/
├── main.py                    # 메인 Streamlit 애플리케이션
├── requirements.txt           # 의존성 패키지 목록
├── README.md                 # 프로젝트 설명서
├── .env                      # 환경 변수 (API 키 등)
│
├── utils/                    # 핵심 유틸리티 모듈
│   ├── chat.py              # 대화 관리 및 LLM 호출
│   ├── pdf_upload.py        # PDF 업로드 및 처리
│   ├── request_rag.py       # RAG API 호출 관리
│   ├── sidebar.py           # 세션 관리 및 UI
│   ├── translation.py       # 다국어 번역 처리
│   ├── database.py          # 데이터베이스 연동
│   └── RAG/                 # RAG 시스템 구현
│       ├── main.py          # RAG 메인 로직
│       ├── embedding_manager.py  # 임베딩 캐시 관리
│       └── textsplitter.py  # 텍스트 분할 처리
│
├── data/                     # 샘플 데이터셋
│   └── govreport_samples/   # 정부 보고서 샘플
│
├── documents/               # 업로드된 문서 저장소
├── embedding_cache/         # 임베딩 캐시 파일
└── frontend/               # 추가 프론트엔드 자원
```

## 주의사항

### 1. API 키 설정
- Upstage API 키를 `.env` 파일에 정확히 설정
- API 사용량 제한 확인 (Document Parse, Solar LLM, Solar Embedding)

### 2. 문서 처리 제한사항
- PDF 파일 크기: 최대 10MB
- 이미지 기반 PDF의 경우 OCR 처리 시간 증가 (1-5분)
- 한 번에 하나의 PDF만 처리 가능

### 3. 성능 최적화
- 임베딩 캐시 활용으로 재처리 시간 단축
- 벡터 데이터베이스는 세션별로 관리
- 대화 히스토리는 5개 이상 누적 시 자동 저장

### 4. 메모리 관리
- 대용량 문서 처리 시 충분한 메모리 확보
- 세션 변경 시 이전 데이터 자동 정리
- 캐시 파일 정기적 관리 권장

### 5. 언어 지원
- 한국어-영어 자동 번역 지원
- 다국어 문서의 경우 처리 시간 증가 가능
- 번역 품질은 Solar LLM 성능에 의존

## 라이선스

이 프로젝트는 학습 및 연구 목적으로 제공되며, 모든 데이터는 민감한 개인정보를 포함하지 않습니다. 