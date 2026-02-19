"""
Persistent Memory (Feature B)

Writes selective, high-signal knowledge to:
- USER_MEMORY.md: User-specific facts (role, preferences, workflow habits)
  Examples: "User is a Project Finance Analyst", "Prefers weekly summaries on Mondays"
- COMPANY_MEMORY.md: Org-wide learnings (team interfaces, bottlenecks, patterns)
  Examples: "Asset Management interfaces often with Project Finance", "Recurring workflow bottleneck is X"

Rules:
- Selective: No transcript dumping. One concise fact per turn at most.
- High-signal and reusable: Only facts that help future answers.
- Never store secrets, PII, or sensitive information.
- Decision: {should_write, target, summary, confidence} — append only when confidence >= 0.80.
"""
import asyncio
import os
from datetime import datetime
from typing import Optional

import aiofiles
from langchain_ollama import ChatOllama
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from app.config import settings
from app.schemas import MemoryEntry

MEMORY_PROMPT = """Analyze this conversation turn. Decide if it contains a high-signal fact worth storing.
Respond with valid JSON only. No preamble.
{{
  "should_write": true or false,
  "target": "USER_MEMORY" or "COMPANY_MEMORY" or null,
  "summary": "one-sentence fact",
  "confidence": 0.0 to 1.0,
  "reason": "brief justification"
}}

RULES:
- Selective: Do NOT dump transcripts. Extract ONE reusable fact at most.
- USER_MEMORY: User-specific facts — role, preferences, workflow habits.
  Examples: "User is a Project Finance Analyst", "Prefers weekly summaries on Mondays"
- COMPANY_MEMORY: Org-wide learnings useful to colleagues.
  Examples: "Asset Management interfaces often with Project Finance", "Recurring workflow bottleneck is X"
- Only write if confidence > 0.80. Prefer NOT writing over noise.
- NEVER store secrets, PII, passwords, or sensitive personal data.

User: {query}
Assistant: {answer}
"""


def _get_memory_llm():
    if settings.sanity_mock:
        from langchain_community.chat_models import FakeListChatModel
        return FakeListChatModel(responses=['{"should_write": false, "target": null, "summary": "", "confidence": 0, "reason": "test"}'])
    return ChatOllama(
        model=settings.ollama_json_model,
        base_url=settings.ollama_base_url,
        temperature=0.0,
        format="json",
    )


async def extract_and_store_memory(user_id: str, query: str, answer: str) -> dict:
    llm = _get_memory_llm()
    parser = JsonOutputParser(pydantic_object=MemoryEntry)
    prompt = PromptTemplate(template=MEMORY_PROMPT, input_variables=["query", "answer"])
    chain = prompt | llm | parser

    def _invoke():
        return chain.invoke({"query": query, "answer": answer})

    result = await asyncio.to_thread(_invoke)
    entry = MemoryEntry(**result)

    if not entry.should_write or entry.confidence < settings.memory_confidence_threshold or not entry.target:
        return {"written": False, "target": None, "summary": ""}

    mem_dir = f"memory/user_{user_id}"
    os.makedirs(mem_dir, exist_ok=True)
    filename = "USER_MEMORY.md" if entry.target == "USER_MEMORY" else "COMPANY_MEMORY.md"
    filepath = os.path.join(mem_dir, filename)

    if not os.path.exists(filepath):
        async with aiofiles.open(filepath, "w") as f:
            await f.write(f"# {filename.replace('.md', '').replace('_', ' ')}\n\n")

    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"- [{ts}] {entry.summary}\n"

    async with aiofiles.open(filepath, "a") as f:
        await f.write(line)

    return {"written": True, "target": entry.target, "summary": entry.summary}


async def read_user_memory(user_id: str) -> str:
    """Read raw user memory content for RAG context injection."""
    mem_dir = f"memory/user_{user_id}"
    path = os.path.join(mem_dir, "USER_MEMORY.md")
    if not os.path.exists(path):
        return ""
    async with aiofiles.open(path, "r") as f:
        return await f.read()


INSIGHTS_PROMPT = """Summarize the following memory files into concise bullet points for a UI panel.
Return ONLY a bullet list (one line per bullet, start with -). No preamble.
If a section is empty, return "No entries yet" for that section.

USER MEMORY:
{user_memory}

COMPANY MEMORY:
{company_memory}

Output format:
• User: [bullet points]
• Company: [bullet points]
"""


async def get_memory_insights(user_id: str) -> str:
    """Use LLM to summarize both memory files into bullet points for the UI right panel."""
    mem_dir = f"memory/user_{user_id}"
    user_mem, company_mem = "", ""
    for name in ("USER_MEMORY.md", "COMPANY_MEMORY.md"):
        path = os.path.join(mem_dir, name)
        if os.path.exists(path):
            async with aiofiles.open(path, "r") as f:
                content = await f.read()
                if name == "USER_MEMORY.md":
                    user_mem = content
                else:
                    company_mem = content

    if not user_mem.strip() and not company_mem.strip():
        return "• User: No entries yet\n• Company: No entries yet"

    llm = _get_memory_llm()
    prompt = PromptTemplate(template=INSIGHTS_PROMPT, input_variables=["user_memory", "company_memory"])
    chain = prompt | llm

    def _invoke():
        return chain.invoke({"user_memory": user_mem or "(empty)", "company_memory": company_mem or "(empty)"})

    result = await asyncio.to_thread(_invoke)
    text = result.content if hasattr(result, "content") else str(result)
    return text.strip() if text else "• User: No entries yet\n• Company: No entries yet"
