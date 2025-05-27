from typing import TypedDict, Literal, List
from pydantic import BaseModel, Field
from langchain_upstage import ChatUpstage, UpstageEmbeddings
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import HumanMessage
import os, dotenv; dotenv.load_dotenv()


class WorkflowState(TypedDict):
    original_text: str
    summary: str
    translated_summary: str
    reviewed_summary: str
    embeddings: List[float]
    language: Literal["English", "Korean"]


llm = ChatUpstage(
    api_key=os.getenv("UPSTAGE_API_KEY"),
    model="solar-pro"
)

class SummaryResult(BaseModel):
    language: Literal["English", "Korean"]
    summary: str

summary_parser = PydanticOutputParser(pydantic_object=SummaryResult)
summary_prompt = PromptTemplate(
    template=(
        "{format_instructions}\n\n"
        "You are an agent that (1) detects language (English/Korean) and "
        "(2) returns a concise summary in the Korean.\n\n"
        "Text:\n{text}"
    ),
    input_variables=["text"],
    partial_variables={"format_instructions": summary_parser.get_format_instructions()},
)

def summarize_text(state: WorkflowState) -> WorkflowState:
    rendered = summary_prompt.format(text=state["original_text"])
    raw = llm.invoke([HumanMessage(content=rendered)])
    result: SummaryResult = summary_parser.invoke(raw.content)

    state.update(
        language=result.language,
        summary=result.summary,
        translated_summary="",
        reviewed_summary="",
        embeddings=[],
    )
    return state

translate_prompt = PromptTemplate(
    template=(
        "You are a translator. Detect the input language and translate the text "
        "into the *other* language (English ↔ Korean) preserving meaning.\n\n"
        "Text:\n{text}"
    ),
    input_variables=["text"],
)

def translate_summary(state: WorkflowState) -> WorkflowState:
    raw = llm.invoke([HumanMessage(content=translate_prompt.format(text=state["summary"]))])
    state["translated_summary"] = raw.content.strip()
    return state

emb_model = UpstageEmbeddings(
    api_key=os.getenv("UPSTAGE_API_KEY"),
    model="solar-embedding-1-large"
)

def embed_text(state: WorkflowState) -> WorkflowState:
    state["embeddings"] = emb_model.embed_documents([state["summary"]])[0]
    return state

