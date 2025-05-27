from dotenv import load_dotenv
import os
from langchain_community.vectorstores import FAISS

from textsplitter import get_text_splitter
# 환경 변수 로드


    

class rag:
    def __init__(self, documents, embedding_model):
        self.embedding_model = embedding_model
        self.text_splitter = get_text_splitter(
        'recursive',
        separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""]
        )
        self.update_documents(documents)

    def set_test_splitter(self, splitter_type, **kwargs):
        self.text_splitter = get_text_splitter(splitter_type, **kwargs)
        self.update_documents(self.documents)

    def update_documents(self, documents):
        self.documents = documents
        self.split_documents = self.text_splitter.split_text(self.documents)
        self.vector_store = FAISS.from_texts(self.split_documents, embedding=self.embedding_model)
        
    def __call__(self, prompt, k=3):
        return "\n".join([c.page_content for c in self.vector_store.similarity_search(prompt, k)])
