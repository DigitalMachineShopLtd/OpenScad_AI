"""Tests for RAG client — hybrid ChromaDB reads + MQTT writes."""

import os
from unittest.mock import MagicMock, patch

import pytest


# ── is_rag_enabled ──────────────────────────────────────────────────────────

def test_rag_disabled_by_env():
    """RAG_ENABLED=false → is_rag_enabled() returns False."""
    with patch.dict(os.environ, {"RAG_ENABLED": "false"}):
        from mcp_server.rag_client import is_rag_enabled
        assert is_rag_enabled() is False


def test_rag_enabled_by_default():
    """No RAG_ENABLED env → is_rag_enabled() returns True."""
    env = os.environ.copy()
    env.pop("RAG_ENABLED", None)
    with patch.dict(os.environ, env, clear=True):
        from mcp_server.rag_client import is_rag_enabled
        assert is_rag_enabled() is True


# ── search ──────────────────────────────────────────────────────────────────

def test_search_returns_empty_when_disabled():
    """RAG disabled → search returns empty results."""
    with patch.dict(os.environ, {"RAG_ENABLED": "false"}):
        from mcp_server.rag_client import search
        result = search("test query")
        assert result["results"] == []
        assert result["count"] == 0


def test_search_returns_empty_when_chromadb_unavailable():
    """ChromaDB unavailable → empty results with error."""
    env = os.environ.copy()
    env.pop("RAG_ENABLED", None)
    with patch.dict(os.environ, env, clear=True):
        with patch("mcp_server.rag_client._get_chroma_client", return_value=None):
            from mcp_server.rag_client import search
            result = search("test query")
            assert result["results"] == []
            assert result["count"] == 0
            assert "error" in result


def test_search_queries_specific_collection():
    """Mock client → verify query called correctly and results formatted."""
    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        "ids": [["id1", "id2"]],
        "documents": [["doc1", "doc2"]],
        "distances": [[0.3, 0.1]],
        "metadatas": [[{"source": "a"}, {"source": "b"}]],
    }

    mock_client = MagicMock()
    mock_client.get_collection.return_value = mock_collection

    env = os.environ.copy()
    env.pop("RAG_ENABLED", None)
    with patch.dict(os.environ, env, clear=True):
        with patch("mcp_server.rag_client._get_chroma_client", return_value=mock_client):
            with patch("mcp_server.rag_client.publish"):
                from mcp_server.rag_client import search
                result = search("test query", collection="openscad_code", n_results=2)

    mock_client.get_collection.assert_called_once_with(name="openscad_code")
    mock_collection.query.assert_called_once_with(query_texts=["test query"], n_results=2)
    assert result["count"] == 2
    # Results should be sorted by distance (ascending)
    assert result["results"][0]["distance"] <= result["results"][1]["distance"]


def test_search_queries_all_collections_when_none():
    """collection=None → queries all 4 collections via get_or_create_collection."""
    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        "ids": [["id1"]],
        "documents": [["doc1"]],
        "distances": [[0.5]],
        "metadatas": [[{"source": "a"}]],
    }

    mock_client = MagicMock()
    mock_client.get_or_create_collection.return_value = mock_collection

    env = os.environ.copy()
    env.pop("RAG_ENABLED", None)
    with patch.dict(os.environ, env, clear=True):
        with patch("mcp_server.rag_client._get_chroma_client", return_value=mock_client):
            with patch("mcp_server.rag_client.publish"):
                from mcp_server.rag_client import search
                result = search("test query")

    assert mock_client.get_or_create_collection.call_count == 4
    expected_collections = {"openscad_code", "project_docs", "schemas_config", "design_history"}
    called_collections = {
        call.kwargs.get("name") or call.args[0]
        for call in mock_client.get_or_create_collection.call_args_list
    }
    # Handle both positional and keyword arguments
    actual = set()
    for call in mock_client.get_or_create_collection.call_args_list:
        if call.kwargs.get("name"):
            actual.add(call.kwargs["name"])
        elif call.args:
            actual.add(call.args[0])
    assert actual == expected_collections
    assert result["count"] == 4  # one result per collection


# ── store_chunks ────────────────────────────────────────────────────────────

def test_store_chunks_publishes_mqtt():
    """Each chunk published via MQTT."""
    chunks = [
        {"id": "chunk1", "document": "hello world", "metadata": {"source": "test"}},
        {"id": "chunk2", "document": "foo bar", "metadata": {"source": "test"}},
    ]

    with patch("mcp_server.rag_client.publish", return_value=True) as mock_publish:
        from mcp_server.rag_client import store_chunks
        result = store_chunks(chunks, collection="openscad_code")

    assert result["success"] is True
    assert result["chunks_sent"] == 2
    assert mock_publish.call_count == 2


def test_store_chunks_handles_mqtt_failure():
    """MQTT returns False → success=False."""
    chunks = [
        {"id": "chunk1", "document": "hello", "metadata": {}},
    ]

    with patch("mcp_server.rag_client.publish", return_value=False):
        from mcp_server.rag_client import store_chunks
        result = store_chunks(chunks, collection="openscad_code")

    assert result["success"] is False


# ── auto_inject ─────────────────────────────────────────────────────────────

def test_auto_inject_adds_rag_context():
    """Mock client → rag_context added to response."""
    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        "ids": [["id1"]],
        "documents": [["relevant doc"]],
        "distances": [[0.2]],
        "metadatas": [[{"source": "test"}]],
    }

    mock_client = MagicMock()
    mock_client.get_collection.return_value = mock_collection

    response = {"content": "some response"}

    env = os.environ.copy()
    env.pop("RAG_ENABLED", None)
    env.pop("RAG_AUTO_INJECT", None)
    with patch.dict(os.environ, env, clear=True):
        with patch("mcp_server.rag_client._get_chroma_client", return_value=mock_client):
            with patch("mcp_server.rag_client.publish"):
                from mcp_server.rag_client import auto_inject
                result = auto_inject(response, query="test", collection="openscad_code")

    assert "rag_context" in result
    assert result["content"] == "some response"


def test_auto_inject_skips_when_disabled():
    """RAG_ENABLED=false → response unchanged."""
    response = {"content": "some response"}

    with patch.dict(os.environ, {"RAG_ENABLED": "false"}):
        from mcp_server.rag_client import auto_inject
        result = auto_inject(response, query="test", collection="openscad_code")

    assert result == response
    assert "rag_context" not in result


def test_auto_inject_skips_when_auto_inject_disabled():
    """RAG_AUTO_INJECT=false → response unchanged."""
    response = {"content": "some response"}

    env = os.environ.copy()
    env.pop("RAG_ENABLED", None)
    with patch.dict(os.environ, {**env, "RAG_AUTO_INJECT": "false"}, clear=True):
        from mcp_server.rag_client import auto_inject
        result = auto_inject(response, query="test", collection="openscad_code")

    assert result == response
    assert "rag_context" not in result
