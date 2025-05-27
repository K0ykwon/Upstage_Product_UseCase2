from langgraph.graph import StateGraph, END
from langchain_core.runnables import Runnable
from .generate_summary import (
    WorkflowState,
    summarize_text,
    translate_summary,
    embed_text,
)

def build_workflow() -> Runnable:
    graph = StateGraph(WorkflowState)

    graph.add_node("summarize", summarize_text)
    graph.add_node("translate", translate_summary)

    graph.set_entry_point("summarize")
    graph.add_edge("summarize", "translate")
    graph.add_edge("translate", END)

    return graph.compile()


def run_pipeline(text: str):
    wf = build_workflow()
    return wf.invoke({"original_text": text})
