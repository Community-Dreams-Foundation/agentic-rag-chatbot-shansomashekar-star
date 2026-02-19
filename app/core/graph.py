import asyncio
import os
import pickle
from typing import Any, Dict, List, Optional

import networkx as nx
from langchain_ollama import ChatOllama
from langchain_core.documents import Document
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate

from app.config import settings

GRAPH_EXTRACT_PROMPT = """Extract entities and relationships from the text below.
Return ONLY valid JSON. No text outside the JSON.

{
  "entities": [
    {"id": "lowercase_id", "label": "Display Name", "type": "person|org|concept|term"}
  ],
  "relationships": [
    {"source": "entity_id", "target": "entity_id", "relation": "short_verb_phrase"}
  ]
}

Rules:
- Extract 3-10 entities maximum per chunk. Quality over quantity.
- Only extract entities clearly present in the text.
- relation must be a short verb phrase: "developed_by", "part_of", "cites", "related_to"
- Normalize ids to lowercase with underscores, no special chars.

TEXT:
{text}"""


def _get_graph_llm():
    if settings.sanity_mock:
        return None
    return ChatOllama(
        model=settings.ollama_json_model,
        base_url=settings.ollama_base_url,
        temperature=0.0,
        format="json",
    )


async def extract_graph_data(text: str, doc_source: str) -> dict:
    llm = _get_graph_llm()
    if not llm:
        return {"entities": [], "relationships": []}
    prompt = PromptTemplate(template=GRAPH_EXTRACT_PROMPT, input_variables=["text"])
    chain = prompt | llm | JsonOutputParser()
    try:
        result = await asyncio.to_thread(
            chain.invoke,
            {"text": (text or "")[:2000]},
        )
        return result
    except Exception:
        return {"entities": [], "relationships": []}


async def update_user_graph(
    user_id: str,
    chunks: List[Document],
    graph_store: Optional[Dict[str, nx.Graph]] = None,
) -> None:
    """Extract entities from all parent chunks and build/update user's graph."""
    if graph_store is None:
        graph_store = _get_graph_store()
    G = graph_store.get(user_id, nx.Graph())

    parent_chunks = [c for c in chunks if c.metadata.get("type") == "parent"]
    if not parent_chunks:
        return

    tasks = [
        extract_graph_data(chunk.page_content, chunk.metadata.get("source", "unknown"))
        for chunk in parent_chunks
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for chunk, result in zip(parent_chunks, results):
        if isinstance(result, Exception):
            continue
        for entity in result.get("entities", []):
            node_id = str(entity.get("id", "")).strip()
            if not node_id:
                continue
            label = entity.get("label", node_id)
            etype = entity.get("type", "concept")
            if etype not in ("person", "org", "concept", "term"):
                etype = "concept"
            doc_src = chunk.metadata.get("source", "unknown")
            if G.has_node(node_id):
                if "doc_sources" not in G.nodes[node_id]:
                    G.nodes[node_id]["doc_sources"] = []
                G.nodes[node_id]["doc_sources"].append(doc_src)
            else:
                G.add_node(node_id, label=label, type=etype, doc_sources=[doc_src])

        for rel in result.get("relationships", []):
            src = str(rel.get("source", "")).strip()
            tgt = str(rel.get("target", "")).strip()
            if not src or not tgt:
                continue
            if not G.has_node(src) or not G.has_node(tgt):
                continue
            doc_src = chunk.metadata.get("source", "unknown")
            if G.has_edge(src, tgt):
                G[src][tgt]["weight"] = G[src][tgt].get("weight", 1) + 1.0
            else:
                G.add_edge(src, tgt, relation=rel.get("relation", "related_to"), weight=1.0, doc_source=doc_src)

    graph_store[user_id] = G
    graph_path = f"vectorstore/user_{user_id}/knowledge_graph.pkl"
    os.makedirs(os.path.dirname(graph_path), exist_ok=True)

    def _dump():
        with open(graph_path, "wb") as f:
            pickle.dump(G, f)

    await asyncio.to_thread(_dump)


_graph_store: Dict[str, nx.Graph] = {}


def _get_graph_store() -> Dict[str, nx.Graph]:
    return _graph_store


def get_graph_store() -> Dict[str, nx.Graph]:
    return _graph_store


async def get_graph_context(
    query: str,
    user_id: str,
    graph_store: Dict[str, nx.Graph],
    max_hops: int = 2,
    max_nodes: int = 8,
) -> str:
    """Extract query entities, walk graph, format as structured context for LLM."""
    G = graph_store.get(user_id)
    if not G or G.number_of_nodes() == 0:
        return ""

    query_data = await extract_graph_data(query, "query")
    query_entity_ids = {str(e.get("id", "")).strip() for e in query_data.get("entities", []) if e.get("id")}

    matched_nodes = set()
    for qe in query_entity_ids:
        if not qe:
            continue
        for node in G.nodes:
            if qe in node or node in qe:
                matched_nodes.add(node)

    if not matched_nodes:
        return ""

    subgraph_nodes = set(matched_nodes)
    frontier = set(matched_nodes)
    for _ in range(max_hops):
        next_frontier = set()
        for node in frontier:
            neighbors = list(G.neighbors(node))
            ranked = sorted(
                neighbors,
                key=lambda n: G[node][n].get("weight", 1),
                reverse=True,
            )[:3]
            next_frontier.update(ranked)
        subgraph_nodes.update(next_frontier)
        frontier = next_frontier
        if len(subgraph_nodes) >= max_nodes:
            break

    subgraph_nodes = list(subgraph_nodes)[:max_nodes]

    lines = ["=== Knowledge Graph Context ==="]
    for node in subgraph_nodes:
        data = G.nodes[node]
        doc_sources = data.get("doc_sources", [])
        sources_str = ", ".join(list(set(doc_sources))[:3])
        lines.append(f"ENTITY: {data.get('label', node)} (type: {data.get('type', '?')}, sources: {sources_str})")

    lines.append("\nRELATIONSHIPS:")
    for u, v, data in G.edges(data=True):
        if u in subgraph_nodes and v in subgraph_nodes:
            u_label = G.nodes[u].get("label", u)
            v_label = G.nodes[v].get("label", v)
            lines.append(
                f"  {u_label} --[{data.get('relation', '?')}]--> {v_label} "
                f"(weight: {data.get('weight', 1):.1f}, source: {data.get('doc_source', '?')})"
            )

    return "\n".join(lines)
