"""
LangGraph ICR pipeline graph definition.

Graph structure:
  classify_documents
       ↓
  extract_documents
       ↓
    run_rules
       ↓
  ⟨needs_attention?⟩
    ↙           ↘
human_review   finalize → END
    ↓
  run_rules  (loops back after reviewer corrections)

The graph is compiled once at module load and reused across requests.
MemorySaver is used for the prototype — swap for SqliteSaver / PostgresSaver
in production to persist case state across server restarts.
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from state import CaseState
from nodes import (
    classify_documents,
    extract_documents,
    run_rules,
    route_after_rules,
    human_review,
    finalize,
)


def build_graph():
    builder = StateGraph(CaseState)

    # ── Nodes ──────────────────────────────────────────────────────────────────
    builder.add_node("classify_documents", classify_documents)
    builder.add_node("extract_documents", extract_documents)
    builder.add_node("run_rules", run_rules)
    builder.add_node("human_review", human_review)
    builder.add_node("finalize", finalize)

    # ── Edges ──────────────────────────────────────────────────────────────────
    builder.set_entry_point("classify_documents")
    builder.add_edge("classify_documents", "extract_documents")
    builder.add_edge("extract_documents", "run_rules")

    builder.add_conditional_edges(
        "run_rules",
        route_after_rules,
        {
            "human_review": "human_review",
            "finalize": "finalize",
        },
    )

    # After human review, re-run the rules engine with corrected values
    builder.add_edge("human_review", "run_rules")
    builder.add_edge("finalize", END)

    # ── Compile ────────────────────────────────────────────────────────────────
    checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)


# Module-level singleton — built once, shared across all requests
icr_graph = build_graph()
