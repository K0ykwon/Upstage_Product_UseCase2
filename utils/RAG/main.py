from langchain_community.vectorstores import FAISS
from .embedding_manager import EmbeddingManager
from collections import defaultdict

class rag:
    def __init__(self, documents, api_key, create_embeddings=True):
        """
        documents: [{"filename": "파일명", "content": "내용"}, ...] 형태의 리스트
        api_key: Upstage API 키
        create_embeddings: 새로운 임베딩 생성 여부
        """
        self.embedding_manager = EmbeddingManager(api_key, create_embeddings=create_embeddings)
        self.update_documents(documents)

    def update_documents(self, documents):
        """
        documents: [{"filename": "파일명", "content": "내용"}, ...] 형태의 리스트
        """
        self.documents = documents
        
        # 각 문서의 내용과 메타데이터 준비
        texts = []
        metadatas = []
        filenames = []
        
        for doc in documents:
            # 문서를 청크로 분할
            chunks = self.embedding_manager.text_splitter.split_text(doc["content"])
            texts.extend(chunks)
            # 각 청크에 대해 동일한 메타데이터 추가
            metadatas.extend([{"filename": doc["filename"]}] * len(chunks))
            # 각 청크에 대한 파일명 추가
            filenames.extend([doc["filename"]] * len(chunks))
        
        # 임베딩 생성
        embeddings = self.embedding_manager.get_embeddings(texts, filenames)
        
        # FAISS에 저장
        self.vector_store = FAISS.from_embeddings(
            text_embeddings=list(zip(texts, embeddings)),
            metadatas=metadatas,
            embedding=self.embedding_manager
        )
        
    def __call__(self, prompt, k=3):
        # 프롬프트의 임베딩 생성
        chunk_embeddings = self.embedding_manager.get_embedding_for_prompt(prompt)
        
        # 모든 청크에 대한 검색 결과 수집
        all_results = []
        for chunk_embedding in chunk_embeddings:
            docs_and_scores = self.vector_store.similarity_search_with_score_by_vector(
                chunk_embedding,
                k=3  # 충분히 많은 결과를 가져옴
            )
            all_results.extend(docs_and_scores)
        
        # 문서별 최고 유사도 집계
        doc_max_scores = defaultdict(float)
        for doc, score in all_results:
            filename = doc.metadata["filename"]
            # 최고 유사도만 저장
            doc_max_scores[filename] = max(doc_max_scores[filename], float(score))
        
        # 문서별 최고 유사도로 정렬하여 상위 k개 문서 선택
        sorted_docs = sorted(
            doc_max_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )[:k]  # 상위 k개 문서만 선택
        
        # 최종 결과 생성
        results = []
        for filename, doc_score in sorted_docs:
            # 해당 문서의 모든 청크 찾기
            doc_chunks = [
                (doc.page_content, score)
                for doc, score in all_results
                if doc.metadata["filename"] == filename
            ]
            
            # 원본 문서 내용 찾기
            original_doc = next(
                doc for doc in self.documents 
                if doc["filename"] == filename
            )
            
            # 결과 추가
            results.append({
                "filename": filename,
                "content": original_doc["content"],  # 원본 문서 전체 내용
                "document_similarity": doc_score,  # 문서의 최고 유사도
                "chunk_similarities": [  # 각 청크별 유사도
                    {
                        "content": chunk,
                        "similarity": score
                    }
                    for chunk, score in doc_chunks
                ]
            })
        
        return results
