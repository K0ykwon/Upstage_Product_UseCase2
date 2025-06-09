from langchain.text_splitter import (
    CharacterTextSplitter,
    RecursiveCharacterTextSplitter,
    MarkdownTextSplitter,
    TokenTextSplitter,
    HTMLHeaderTextSplitter,
    LatexTextSplitter,
    PythonCodeTextSplitter
)

def get_text_splitter(splitter_type: str, **kwargs):
    if splitter_type == 'recursive':
        kwargs['separators'] = kwargs.get('separators', ["\n\n", "\n", ".", "!", "?", ",", " ", ""])
        
    default_params = {
        'chunk_size': 512,
        'chunk_overlap': 64
    }
    
    # 기본 파라미터와 사용자 파라미터 병합
    params = {**default_params, **kwargs}
    
    splitters = {
        'character': CharacterTextSplitter,
        'recursive': RecursiveCharacterTextSplitter,
        'markdown': MarkdownTextSplitter,
        'token': TokenTextSplitter,
        'html': HTMLHeaderTextSplitter,
        'latex': LatexTextSplitter,
        'python': PythonCodeTextSplitter
    }
    
    if splitter_type not in splitters:
        raise ValueError(f"unsupported splitter type: {splitter_type}")
        
    return splitters[splitter_type](**params)
