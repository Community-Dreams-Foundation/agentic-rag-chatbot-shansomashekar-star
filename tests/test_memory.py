import pytest
from unittest.mock import patch
from app.core.memory import extract_and_store_memory, read_user_memory


@pytest.mark.asyncio
async def test_memory_not_written_sanity_mock():
    """With sanity_mock=True, fake LLM returns should_write=False."""
    with patch("app.core.memory.settings") as mock_settings:
        mock_settings.sanity_mock = True
        result = await extract_and_store_memory("user1", "hello", "hi there")
    assert result["written"] is False


@pytest.mark.asyncio
async def test_memory_not_written_neutral_query():
    """Neutral Q&A (what is X) typically yields no memory write."""
    with patch("app.core.memory.settings") as mock_settings:
        mock_settings.sanity_mock = True
        result = await extract_and_store_memory("user1", "what is AI?", "AI is...")
    assert result["written"] is False


@pytest.mark.asyncio
async def test_read_user_memory_empty():
    """When no memory file exists, returns empty string."""
    result = await read_user_memory("nonexistent-user-xyz-123")
    assert result == ""
