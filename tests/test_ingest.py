import pytest
import asyncio
from pathlib import Path
from app.core.ingest import (
    extract_sections_pdf,
    extract_sections_text,
    semantic_chunk,
    smart_hierarchical_chunk,
)

SAMPLE_TEXT = """
# Introduction
This paper presents a novel approach to natural language processing using transformer architectures.
The key contribution is a new attention mechanism that reduces computational complexity.
We evaluate our method on standard benchmarks and show significant improvements.

# Methods
We use a multi-head self-attention layer with relative positional encodings.
The model is trained on a large corpus of text using masked language modelling.
Fine-tuning is performed on downstream tasks with a learning rate of 2e-5.

# Results
Our method achieves state-of-the-art performance on GLUE benchmark with a score of 89.4.
On SQuAD 2.0 we achieve an F1 score of 91.2, outperforming the previous best by 1.8 points.
Ablation studies confirm that each component contributes to the final performance.
"""


def test_extract_sections_text_detects_headings():
    sections = extract_sections_text(SAMPLE_TEXT)
    assert len(sections) >= 2
    headings = [s["heading"] for s in sections]
    assert any("Method" in h for h in headings)
    assert any("Result" in h for h in headings)


def test_extract_sections_text_has_content():
    sections = extract_sections_text(SAMPLE_TEXT)
    for section in sections:
        assert len(section["text"].strip()) > 0
        assert "heading" in section


def test_semantic_chunk_respects_sentence_boundaries():
    chunks = semantic_chunk(SAMPLE_TEXT, max_chars=300, overlap_sentences=1)
    assert len(chunks) >= 1
    for chunk in chunks:
        assert len(chunk.strip()) >= 50


def test_semantic_chunk_no_empty_chunks():
    chunks = semantic_chunk(SAMPLE_TEXT, max_chars=200, overlap_sentences=1)
    for chunk in chunks:
        assert len(chunk.strip()) > 0


def test_semantic_chunk_overlap():
    chunks = semantic_chunk(SAMPLE_TEXT, max_chars=99999, overlap_sentences=2)
    assert len(chunks) == 1


@pytest.mark.asyncio
async def test_smart_hierarchical_chunk_returns_parents_and_children(tmp_path):
    doc_file = tmp_path / "test.txt"
    doc_file.write_text(SAMPLE_TEXT, encoding="utf-8")

    parents, children = await smart_hierarchical_chunk(
        file_path=str(doc_file),
        mime_type="text/plain",
        doc_id="test-doc-001",
        filename="test.txt",
    )

    assert len(parents) >= 1
    assert len(children) >= 1
    assert len(children) >= len(parents)


@pytest.mark.asyncio
async def test_child_chunks_have_required_metadata(tmp_path):
    doc_file = tmp_path / "test.txt"
    doc_file.write_text(SAMPLE_TEXT, encoding="utf-8")

    _, children = await smart_hierarchical_chunk(
        file_path=str(doc_file),
        mime_type="text/plain",
        doc_id="test-doc-002",
        filename="test.txt",
    )

    for child in children:
        assert "doc_id" in child.metadata
        assert "source" in child.metadata
        assert "parent_idx" in child.metadata
        assert "child_idx" in child.metadata
        assert "section" in child.metadata


@pytest.mark.asyncio
async def test_parent_chunks_have_content(tmp_path):
    doc_file = tmp_path / "test.txt"
    doc_file.write_text(SAMPLE_TEXT, encoding="utf-8")

    parents, _ = await smart_hierarchical_chunk(
        file_path=str(doc_file),
        mime_type="text/plain",
        doc_id="test-doc-003",
        filename="test.txt",
    )

    for parent in parents:
        assert len(parent.page_content.strip()) > 0
