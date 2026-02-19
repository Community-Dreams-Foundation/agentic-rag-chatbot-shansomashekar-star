import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langchain_core.documents import Document
from app.core.retriever import apply_metadata_filters, expand_to_parents


def make_doc(source="doc.pdf", section="Methods", page=3):
    return Document(
        page_content="sample content",
        metadata={
            "source": source,
            "section": section,
            "page": page,
            "doc_id": "d1",
            "parent_idx": 0,
            "child_idx": 0,
        },
    )


def test_filter_by_source():
    docs = [make_doc("paper1.pdf"), make_doc("paper2.pdf"), make_doc("paper1.pdf")]
    result = apply_metadata_filters(docs, filter_source="paper1.pdf")
    assert len(result) == 2
    assert all(d.metadata["source"] == "paper1.pdf" for d in result)


def test_filter_by_section_case_insensitive():
    docs = [
        make_doc(section="Introduction"),
        make_doc(section="Methods"),
        make_doc(section="methods details"),
    ]
    result = apply_metadata_filters(docs, filter_section="methods")
    assert len(result) == 2


def test_filter_by_page():
    docs = [make_doc(page=1), make_doc(page=2), make_doc(page=3)]
    result = apply_metadata_filters(docs, filter_page=2)
    assert len(result) == 1
    assert result[0].metadata["page"] == 2


def test_filter_no_match_returns_original():
    docs = [make_doc("paper1.pdf"), make_doc("paper2.pdf")]
    result = apply_metadata_filters(docs, filter_source="nonexistent.pdf")
    assert result == docs


def test_filter_combined():
    docs = [
        make_doc("a.pdf", "Methods", 1),
        make_doc("a.pdf", "Methods", 2),
        make_doc("a.pdf", "Results", 1),
        make_doc("b.pdf", "Methods", 1),
    ]
    result = apply_metadata_filters(docs, filter_source="a.pdf", filter_section="Methods")
    assert len(result) == 2
    assert all(d.metadata["source"] == "a.pdf" for d in result)
    assert all("methods" in d.metadata["section"].lower() for d in result)


def test_filter_none_params_returns_all():
    docs = [make_doc(), make_doc(), make_doc()]
    result = apply_metadata_filters(docs)
    assert result == docs


@pytest.mark.asyncio
async def test_expand_to_parents_deduplicates():
    children = [
        Document(
            page_content="child 1",
            metadata={"doc_id": "d1", "parent_idx": 0, "source": "f.pdf"},
        ),
        Document(
            page_content="child 2",
            metadata={"doc_id": "d1", "parent_idx": 0, "source": "f.pdf"},
        ),
        Document(
            page_content="child 3",
            metadata={"doc_id": "d1", "parent_idx": 1, "source": "f.pdf"},
        ),
    ]

    parent_texts = ["Parent text 0", "Parent text 1"]
    conn = MagicMock()
    conn.close = AsyncMock()

    with patch("app.core.retriever.get_db", new_callable=AsyncMock) as mock_get_db:
        mock_get_db.return_value = conn
        with patch("app.core.retriever.get_parent_texts", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = parent_texts

            result = await expand_to_parents("user1", children)

    assert len(result) == 3
    assert result[0].page_content == "Parent text 0"
    assert result[1].page_content == "Parent text 0"
    assert result[2].page_content == "Parent text 1"


@pytest.mark.asyncio
async def test_expand_to_parents_preserves_metadata():
    children = [
        Document(
            page_content="child",
            metadata={
                "doc_id": "d1",
                "parent_idx": 0,
                "source": "file.pdf",
                "section": "Methods",
                "page": 2,
            },
        )
    ]

    conn = MagicMock()
    conn.close = AsyncMock()

    with patch("app.core.retriever.get_db", new_callable=AsyncMock) as mock_get_db:
        mock_get_db.return_value = conn
        with patch("app.core.retriever.get_parent_texts", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = ["Full parent paragraph text here."]

            result = await expand_to_parents("user1", children)

    assert len(result) == 1
    assert result[0].metadata["section"] == "Methods"
    assert result[0].metadata["page"] == 2
    assert result[0].page_content == "Full parent paragraph text here."
