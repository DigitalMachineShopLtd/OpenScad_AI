# RAG Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a unified RAG system that ingests content from OpenScad_AI and AI_IoT_Lab_v2, integrated into the MCP server with 3 new tools and auto-injection on 3 existing tools.

**Architecture:** Hybrid — direct ChromaDB HTTP client for reads (low latency), MQTT for writes (protocol compliant). New module `mcp_server/rag_client.py` handles chunking, metadata, querying, and ingestion. Graceful degradation when ChromaDB or MQTT unavailable.

**Tech Stack:** chromadb-client 1.5.3 (HTTP-only), paho-mqtt 2.1.0 (existing), pytest (existing)

**Design Doc:** `docs/plans/2026-03-08-rag-integration-design.md`

---

### Task 1: Install chromadb-client Dependency

**Files:**
- Modify: `requirements.txt`

**Step 1: Install chromadb-client in the venv**

```bash
source .venv/bin/activate
pip install chromadb-client==1.5.3
```

**Step 2: Freeze the new dependency into requirements.txt**

```bash
pip freeze > requirements.txt
```

**Step 3: Verify import works**

```bash
python -c "import chromadb; print('chromadb-client OK')"
```

Expected: `chromadb-client OK`

**Step 4: Verify existing tests still pass**

Run: `python -m pytest tests/ -v`
Expected: All 7 tests PASS

**Step 5: Commit**

```bash
git add requirements.txt
git commit -m "deps: add chromadb-client 1.5.3 for RAG integration"
```

---

### Task 2: Chunking Module — Core Logic

**Files:**
- Create: `mcp_server/chunking.py`
- Create: `tests/test_chunking.py`

**Step 1: Write the failing tests**

```python
"""Tests for document chunking logic."""
import tempfile
from pathlib import Path

from mcp_server.chunking import (
    chunk_file,
    detect_collection,
    make_doc_id,
)


def test_make_doc_id():
    """Deterministic doc IDs for deduplication."""
    doc_id = make_doc_id("openscad_ai", "docs/README.md", 0)
    assert doc_id == "openscad_ai:docs/README.md:0"

    doc_id2 = make_doc_id("ai_iot_lab_v2", "config/schemas/rag-request.schema.json", 2)
    assert doc_id2 == "ai_iot_lab_v2:config/schemas/rag-request.schema.json:2"


def test_detect_collection_scad():
    """SCAD files go to openscad_code."""
    assert detect_collection("designs/bracket.scad") == "openscad_code"


def test_detect_collection_markdown():
    """Markdown files go to project_docs."""
    assert detect_collection("docs/HOW-TO-USE.md") == "project_docs"


def test_detect_collection_json():
    """JSON files go to schemas_config."""
    assert detect_collection("config/schemas/rag-request.schema.json") == "schemas_config"


def test_detect_collection_shell():
    """Shell scripts go to schemas_config."""
    assert detect_collection("scripts/setup.sh") == "schemas_config"


def test_detect_collection_mermaid():
    """Mermaid diagrams go to project_docs."""
    assert detect_collection("docs/diagrams/system.mmd") == "project_docs"


def test_chunk_small_markdown():
    """Small markdown files produce a single chunk."""
    with tempfile.TemporaryDirectory() as tmpdir:
        f = Path(tmpdir) / "small.md"
        f.write_text("# Title\n\nShort content here.")

        chunks = chunk_file(str(f), "openscad_ai", "small.md")
        assert len(chunks) == 1
        assert chunks[0]["id"] == "openscad_ai:small.md:0"
        assert chunks[0]["document"] == "# Title\n\nShort content here."
        assert chunks[0]["metadata"]["source_repo"] == "openscad_ai"
        assert chunks[0]["metadata"]["file_path"] == "small.md"
        assert chunks[0]["metadata"]["file_type"] == "markdown"
        assert chunks[0]["metadata"]["chunk_index"] == 0


def test_chunk_large_markdown_splits_on_headings():
    """Large markdown files split on ## headings."""
    with tempfile.TemporaryDirectory() as tmpdir:
        f = Path(tmpdir) / "big.md"
        sections = []
        for i in range(5):
            sections.append(f"## Section {i}\n\n" + "Lorem ipsum. " * 100)
        f.write_text("\n\n".join(sections))

        chunks = chunk_file(str(f), "openscad_ai", "big.md")
        assert len(chunks) > 1
        # Each chunk should have correct metadata
        for i, chunk in enumerate(chunks):
            assert chunk["metadata"]["chunk_index"] == i
            assert chunk["id"] == f"openscad_ai:big.md:{i}"


def test_chunk_json_whole_file():
    """Small JSON files are ingested as a single chunk."""
    with tempfile.TemporaryDirectory() as tmpdir:
        f = Path(tmpdir) / "schema.json"
        f.write_text('{"type": "object", "properties": {"name": {"type": "string"}}}')

        chunks = chunk_file(str(f), "ai_iot_lab_v2", "config/schema.json")
        assert len(chunks) == 1
        assert chunks[0]["metadata"]["file_type"] == "json"


def test_chunk_scad_file():
    """SCAD files are chunked as code."""
    with tempfile.TemporaryDirectory() as tmpdir:
        f = Path(tmpdir) / "bracket.scad"
        f.write_text('include <BOSL2/std.scad>\n\ncuboid([30,20,10]);')

        chunks = chunk_file(str(f), "openscad_ai", "designs/bracket.scad")
        assert len(chunks) == 1
        assert chunks[0]["metadata"]["file_type"] == "scad"


def test_chunk_shell_file():
    """Shell scripts are chunked correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        f = Path(tmpdir) / "setup.sh"
        f.write_text("#!/bin/bash\necho hello\n")

        chunks = chunk_file(str(f), "ai_iot_lab_v2", "scripts/setup.sh")
        assert len(chunks) == 1
        assert chunks[0]["metadata"]["file_type"] == "shell"
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_chunking.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mcp_server.chunking'`

**Step 3: Write minimal implementation**

```python
"""Document chunking for RAG ingestion — splits files into embeddable chunks with metadata."""

import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)

# Max approximate tokens per chunk (1 token ≈ 4 chars)
MAX_CHUNK_CHARS = 2000  # ~500 tokens
OVERLAP_CHARS = 200     # ~50 tokens

# File extension → collection mapping
_COLLECTION_MAP = {
    ".scad": "openscad_code",
    ".md": "project_docs",
    ".mmd": "project_docs",
    ".json": "schemas_config",
    ".sh": "schemas_config",
    ".html": "schemas_config",
    ".txt": "schemas_config",
    ".py": "schemas_config",
    ".conf": "schemas_config",
}

# File extension → file_type label
_TYPE_MAP = {
    ".scad": "scad",
    ".md": "markdown",
    ".mmd": "mermaid",
    ".json": "json",
    ".sh": "shell",
    ".html": "html",
    ".txt": "text",
    ".py": "python",
    ".conf": "config",
}


def make_doc_id(repo: str, relative_path: str, chunk_index: int) -> str:
    """Create a deterministic document ID for deduplication."""
    return f"{repo}:{relative_path}:{chunk_index}"


def detect_collection(file_path: str) -> str:
    """Determine the ChromaDB collection for a file based on extension."""
    ext = Path(file_path).suffix.lower()
    return _COLLECTION_MAP.get(ext, "project_docs")


def _detect_file_type(file_path: str) -> str:
    """Determine the file type label from extension."""
    ext = Path(file_path).suffix.lower()
    return _TYPE_MAP.get(ext, "text")


def chunk_file(
    abs_path: str,
    repo: str,
    relative_path: str,
) -> list[dict]:
    """Read a file, split into chunks, and return chunk dicts ready for ChromaDB.

    Each chunk dict has: id, document, metadata.
    """
    path = Path(abs_path)
    if not path.is_file():
        log.warning("File not found for chunking: %s", abs_path)
        return []

    text = path.read_text(errors="replace")
    if not text.strip():
        return []

    file_type = _detect_file_type(relative_path)
    mtime = path.stat().st_mtime

    # Choose splitting strategy
    if file_type == "markdown":
        raw_chunks = _split_markdown(text)
    else:
        raw_chunks = _split_generic(text)

    chunks = []
    for i, chunk_text in enumerate(raw_chunks):
        chunks.append({
            "id": make_doc_id(repo, relative_path, i),
            "document": chunk_text,
            "metadata": {
                "source_repo": repo,
                "file_path": relative_path,
                "file_type": file_type,
                "modified": mtime,
                "chunk_index": i,
            },
        })

    return chunks


def _split_markdown(text: str) -> list[str]:
    """Split markdown on ## headings, respecting max chunk size."""
    # Split on ## headings (keep the heading with its content)
    sections = re.split(r"(?=^## )", text, flags=re.MULTILINE)
    sections = [s.strip() for s in sections if s.strip()]

    # If the whole file is small enough, return as one chunk
    if len(text) <= MAX_CHUNK_CHARS:
        return [text]

    # Merge small sections, split large ones
    chunks = []
    for section in sections:
        if len(section) <= MAX_CHUNK_CHARS:
            chunks.append(section)
        else:
            chunks.extend(_split_by_size(section))

    return chunks if chunks else [text]


def _split_generic(text: str) -> list[str]:
    """Split code/config files by size if needed."""
    if len(text) <= MAX_CHUNK_CHARS:
        return [text]
    return _split_by_size(text)


def _split_by_size(text: str) -> list[str]:
    """Split text into chunks of MAX_CHUNK_CHARS with OVERLAP_CHARS overlap."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + MAX_CHUNK_CHARS

        # Try to break at a newline
        if end < len(text):
            newline_pos = text.rfind("\n", start, end)
            if newline_pos > start:
                end = newline_pos + 1

        chunks.append(text[start:end].strip())
        start = end - OVERLAP_CHARS

    return [c for c in chunks if c]
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_chunking.py -v`
Expected: All 12 tests PASS

**Step 5: Commit**

```bash
git add mcp_server/chunking.py tests/test_chunking.py
git commit -m "feat: add document chunking module for RAG ingestion"
```

---

### Task 3: RAG Client Module — ChromaDB Reads + MQTT Writes

**Files:**
- Create: `mcp_server/rag_client.py`
- Create: `tests/test_rag_client.py`

**Step 1: Write the failing tests**

```python
"""Tests for RAG client — ChromaDB reads and MQTT writes."""
import os
from unittest.mock import MagicMock, patch

from mcp_server.rag_client import (
    is_rag_enabled,
    search,
    store_chunks,
    auto_inject,
)


def test_rag_disabled_by_env():
    """RAG_ENABLED=false disables all RAG features."""
    with patch.dict(os.environ, {"RAG_ENABLED": "false"}):
        assert is_rag_enabled() is False


def test_rag_enabled_by_default():
    """RAG is enabled by default."""
    with patch.dict(os.environ, {}, clear=True):
        assert is_rag_enabled() is True


def test_search_returns_empty_when_disabled():
    """search() returns empty results when RAG is disabled."""
    with patch.dict(os.environ, {"RAG_ENABLED": "false"}):
        result = search("mounting holes")
        assert result["results"] == []
        assert result["count"] == 0


def test_search_returns_empty_when_chromadb_unavailable():
    """search() gracefully returns empty when ChromaDB is down."""
    with patch("mcp_server.rag_client._get_chroma_client", return_value=None):
        result = search("mounting holes")
        assert result["results"] == []
        assert "error" in result


def test_search_queries_specific_collection():
    """search() can target a specific collection."""
    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        "ids": [["id1"]],
        "documents": [["doc content"]],
        "distances": [[0.3]],
        "metadatas": [[{"file_path": "test.scad"}]],
    }

    mock_client = MagicMock()
    mock_client.get_collection.return_value = mock_collection

    with patch("mcp_server.rag_client._get_chroma_client", return_value=mock_client):
        result = search("holes", collection="openscad_code", n_results=3)
        assert result["count"] == 1
        assert result["results"][0]["document"] == "doc content"
        assert result["results"][0]["distance"] == 0.3
        mock_collection.query.assert_called_once_with(
            query_texts=["holes"], n_results=3
        )


def test_search_queries_all_collections_when_none():
    """search() queries all 4 collections when collection=None."""
    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        "ids": [[]], "documents": [[]], "distances": [[]], "metadatas": [[]],
    }

    mock_client = MagicMock()
    mock_client.get_or_create_collection.return_value = mock_collection

    with patch("mcp_server.rag_client._get_chroma_client", return_value=mock_client):
        result = search("test query")
        # Should have called get_or_create_collection for each of the 4 collections
        assert mock_client.get_or_create_collection.call_count == 4


def test_store_chunks_publishes_mqtt():
    """store_chunks() publishes each chunk via MQTT."""
    chunks = [
        {"id": "repo:file:0", "document": "content", "metadata": {"file_path": "f"}},
        {"id": "repo:file:1", "document": "more", "metadata": {"file_path": "f"}},
    ]

    with patch("mcp_server.rag_client.mqtt_client") as mock_mqtt:
        mock_mqtt.publish.return_value = True
        result = store_chunks(chunks, "openscad_code")
        assert result["success"] is True
        assert result["chunks_sent"] == 2
        assert mock_mqtt.publish.call_count == 2


def test_store_chunks_handles_mqtt_failure():
    """store_chunks() reports failure when MQTT is down."""
    chunks = [{"id": "repo:file:0", "document": "content", "metadata": {}}]

    with patch("mcp_server.rag_client.mqtt_client") as mock_mqtt:
        mock_mqtt.publish.return_value = False
        result = store_chunks(chunks, "openscad_code")
        assert result["success"] is False


def test_auto_inject_adds_rag_context():
    """auto_inject() adds rag_context to a response dict."""
    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        "ids": [["id1"]],
        "documents": [["relevant context"]],
        "distances": [[0.2]],
        "metadatas": [[{"file_path": "test.scad"}]],
    }

    mock_client = MagicMock()
    mock_client.get_or_create_collection.return_value = mock_collection

    response = {"success": True, "file_path": "test.scad"}

    with patch("mcp_server.rag_client._get_chroma_client", return_value=mock_client):
        enriched = auto_inject(response, "bracket design", "openscad_code")
        assert "rag_context" in enriched
        assert len(enriched["rag_context"]) > 0


def test_auto_inject_skips_when_disabled():
    """auto_inject() returns response unchanged when RAG is disabled."""
    with patch.dict(os.environ, {"RAG_ENABLED": "false"}):
        response = {"success": True}
        result = auto_inject(response, "query", "openscad_code")
        assert "rag_context" not in result


def test_auto_inject_skips_when_auto_inject_disabled():
    """auto_inject() returns response unchanged when RAG_AUTO_INJECT=false."""
    with patch.dict(os.environ, {"RAG_AUTO_INJECT": "false"}):
        response = {"success": True}
        result = auto_inject(response, "query", "openscad_code")
        assert "rag_context" not in result
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_rag_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mcp_server.rag_client'`

**Step 3: Write minimal implementation**

```python
"""RAG client — direct ChromaDB HTTP reads, MQTT writes, auto-injection helper."""

import json
import logging
import os
import uuid
from datetime import datetime, timezone

import chromadb

from mcp_server import mqtt_client

log = logging.getLogger(__name__)

COLLECTIONS = ["openscad_code", "project_docs", "schemas_config", "design_history"]

_chroma_client: chromadb.HttpClient | None = None
_chroma_checked = False


def is_rag_enabled() -> bool:
    """Check if RAG features are enabled via environment."""
    return os.environ.get("RAG_ENABLED", "true").lower() != "false"


def _is_auto_inject_enabled() -> bool:
    """Check if auto-injection is enabled via environment."""
    return os.environ.get("RAG_AUTO_INJECT", "true").lower() != "false"


def _get_chroma_client() -> chromadb.HttpClient | None:
    """Get or create ChromaDB HTTP client. Returns None if unavailable."""
    global _chroma_client, _chroma_checked

    if not is_rag_enabled():
        return None

    if _chroma_checked:
        return _chroma_client

    host = os.environ.get("CHROMADB_HOST", "10.0.1.81")
    port = int(os.environ.get("CHROMADB_PORT", "8000"))

    try:
        client = chromadb.HttpClient(host=host, port=port)
        client.heartbeat()  # verify connection
        _chroma_client = client
        _chroma_checked = True
        log.info("ChromaDB connected: %s:%d", host, port)
        return _chroma_client
    except Exception as e:
        log.warning("ChromaDB unavailable (%s:%d): %s — RAG reads disabled", host, port, e)
        _chroma_checked = True
        return None


def search(
    query: str,
    collection: str | None = None,
    n_results: int | None = None,
) -> dict:
    """Search the knowledge base. Returns results from one or all collections.

    Args:
        query: Semantic search text
        collection: Specific collection name, or None for all
        n_results: Max results per collection (default from RAG_N_RESULTS env)

    Returns:
        {"results": [...], "count": int, "error": str | None}
    """
    if not is_rag_enabled():
        return {"results": [], "count": 0}

    if n_results is None:
        n_results = int(os.environ.get("RAG_N_RESULTS", "5"))

    client = _get_chroma_client()
    if client is None:
        return {"results": [], "count": 0, "error": "ChromaDB unavailable"}

    collections_to_search = [collection] if collection else COLLECTIONS
    all_results = []

    for coll_name in collections_to_search:
        try:
            coll = client.get_or_create_collection(name=coll_name)
            raw = coll.query(query_texts=[query], n_results=n_results)

            if raw["ids"] and raw["ids"][0]:
                for i, doc_id in enumerate(raw["ids"][0]):
                    item = {
                        "id": doc_id,
                        "collection": coll_name,
                    }
                    if raw["documents"] and raw["documents"][0]:
                        item["document"] = raw["documents"][0][i]
                    if raw["distances"] and raw["distances"][0]:
                        item["distance"] = raw["distances"][0][i]
                    if raw["metadatas"] and raw["metadatas"][0]:
                        item["metadata"] = raw["metadatas"][0][i]
                    all_results.append(item)
        except Exception as e:
            log.warning("RAG search failed on collection %s: %s", coll_name, e)

    # Sort by distance (lower = more relevant)
    all_results.sort(key=lambda r: r.get("distance", float("inf")))

    # Trim to n_results total
    all_results = all_results[:n_results]

    mqtt_client.publish_event("rag", "search", {
        "query": query[:100],
        "collection": collection,
        "result_count": len(all_results),
    })

    return {"results": all_results, "count": len(all_results)}


def store_chunks(chunks: list[dict], collection: str) -> dict:
    """Store chunks via MQTT (protocol compliant writes).

    Each chunk is published to ailab/rag/store/{request_id}.

    Args:
        chunks: List of {"id": str, "document": str, "metadata": dict}
        collection: Target ChromaDB collection name

    Returns:
        {"success": bool, "chunks_sent": int}
    """
    sent = 0
    for chunk in chunks:
        request_id = f"rag_{uuid.uuid4().hex[:12]}"
        payload = {
            "request_id": request_id,
            "operation": "store",
            "collection": collection,
            "id": chunk["id"],
            "document": chunk["document"],
            "metadata": chunk.get("metadata", {}),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if mqtt_client.publish(f"ailab/rag/store/{request_id}", payload):
            sent += 1

    success = sent == len(chunks)
    if not success:
        log.warning("RAG store: sent %d/%d chunks to %s", sent, len(chunks), collection)

    return {"success": success, "chunks_sent": sent}


def auto_inject(
    response: dict,
    query: str,
    collection: str,
    n_results: int = 3,
) -> dict:
    """Enrich a tool response with RAG context. Returns response unchanged if RAG disabled.

    Args:
        response: The existing tool response dict
        query: Semantic search query
        collection: Collection to search
        n_results: Max context items to inject

    Returns:
        response dict, possibly with added "rag_context" key
    """
    if not is_rag_enabled() or not _is_auto_inject_enabled():
        return response

    try:
        result = search(query, collection=collection, n_results=n_results)
        if result["results"]:
            response["rag_context"] = [
                {
                    "document": r.get("document", ""),
                    "file_path": r.get("metadata", {}).get("file_path", ""),
                    "distance": r.get("distance"),
                }
                for r in result["results"]
            ]
    except Exception as e:
        log.warning("RAG auto-inject failed: %s", e)

    return response
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_rag_client.py -v`
Expected: All 11 tests PASS

**Step 5: Run all tests to verify no regressions**

Run: `python -m pytest tests/ -v`
Expected: All 30 tests PASS (7 existing + 12 chunking + 11 rag_client)

**Step 6: Commit**

```bash
git add mcp_server/rag_client.py tests/test_rag_client.py
git commit -m "feat: add RAG client with ChromaDB reads and MQTT writes"
```

---

### Task 4: MCP Tools — search_knowledge_base, ingest_document, ingest_directory

**Files:**
- Modify: `mcp_server/server.py`

**Step 1: Add imports to server.py**

Add to the import section at the top of `mcp_server/server.py`, after the existing versioning imports:

```python
from mcp_server import rag_client
from mcp_server.chunking import chunk_file, detect_collection
```

**Step 2: Add the three new tools**

Add after the `get_latest_design_iteration` tool (before the resources section):

```python
@mcp.tool()
def search_knowledge_base(
    query: str,
    collection: str | None = None,
    n_results: int = 5,
) -> dict:
    """Search the unified knowledge base for relevant context.
    Searches across OpenScad_AI and AI_IoT_Lab_v2 code, docs, schemas, and design history.
    Use this to find BOSL2 patterns, hardware specs, past designs, or project documentation.

    Args:
        query: Semantic search text (e.g., "M3 mounting holes", "MQTT schema", "Pi 5 enclosure")
        collection: Optional specific collection: "openscad_code", "project_docs", "schemas_config", "design_history". Omit to search all.
        n_results: Maximum results to return (default: 5)
    """
    return rag_client.search(query, collection=collection, n_results=n_results)


@mcp.tool()
def ingest_document(file_path: str, collection: str | None = None) -> dict:
    """Ingest a single file into the RAG knowledge base.
    The file is chunked, tagged with metadata, and stored via MQTT.

    Args:
        file_path: Path to file (relative to project root or absolute)
        collection: Target collection. Auto-detected from file extension if omitted.
    """
    resolved = _resolve_path(file_path)
    p = Path(resolved)

    if not p.is_file():
        return {"success": False, "error": f"File not found: {file_path}"}

    # Determine repo and relative path
    repo, rel_path = _classify_file(p)
    target_collection = collection or detect_collection(rel_path)

    chunks = chunk_file(resolved, repo, rel_path)
    if not chunks:
        return {"success": False, "error": "No content to ingest (file empty or unreadable)"}

    result = rag_client.store_chunks(chunks, target_collection)

    mqtt_client.publish_event("rag", "ingested", {
        "file": rel_path,
        "repo": repo,
        "collection": target_collection,
        "chunks": len(chunks),
    })

    return {
        "success": result["success"],
        "file": rel_path,
        "collection": target_collection,
        "chunks": len(chunks),
    }


@mcp.tool()
def ingest_directory(
    directory: str,
    pattern: str = "**/*",
    collection: str | None = None,
) -> dict:
    """Bulk ingest files from a directory into the RAG knowledge base.
    Recursively finds files matching the pattern, chunks them, and stores via MQTT.

    Args:
        directory: Directory path (relative to project root or absolute)
        pattern: Glob pattern for file matching (default: all files)
        collection: Target collection. Auto-detected per file if omitted.
    """
    resolved = _resolve_path(directory)
    dir_path = Path(resolved)

    if not dir_path.is_dir():
        return {"success": False, "error": f"Directory not found: {directory}"}

    # Supported extensions
    supported = {".scad", ".md", ".mmd", ".json", ".sh", ".html", ".txt", ".py", ".conf"}

    total_files = 0
    total_chunks = 0
    errors = []

    for f in sorted(dir_path.glob(pattern)):
        if not f.is_file():
            continue
        if f.suffix.lower() not in supported:
            continue
        # Skip hidden files and directories
        if any(part.startswith(".") for part in f.parts):
            continue

        repo, rel_path = _classify_file(f)
        target = collection or detect_collection(rel_path)

        chunks = chunk_file(str(f), repo, rel_path)
        if not chunks:
            continue

        result = rag_client.store_chunks(chunks, target)
        if result["success"]:
            total_files += 1
            total_chunks += len(chunks)
        else:
            errors.append(rel_path)

    mqtt_client.publish_event("rag", "bulk_ingested", {
        "directory": directory,
        "files": total_files,
        "chunks": total_chunks,
    })

    return {
        "success": len(errors) == 0,
        "files": total_files,
        "chunks": total_chunks,
        "errors": errors or None,
    }
```

**Step 3: Add the _classify_file helper**

Add to the Helpers section at the bottom of `server.py`:

```python
# Known repo roots for classification
_AI_IOT_LAB_DIR = Path("/home/tie/AI_IoT_Lab_v2")


def _classify_file(abs_path: Path) -> tuple[str, str]:
    """Determine repo name and relative path for a file."""
    try:
        if abs_path.is_relative_to(_AI_IOT_LAB_DIR):
            return "ai_iot_lab_v2", str(abs_path.relative_to(_AI_IOT_LAB_DIR))
    except (ValueError, TypeError):
        pass
    try:
        if abs_path.is_relative_to(PROJECT_DIR):
            return "openscad_ai", str(abs_path.relative_to(PROJECT_DIR))
    except (ValueError, TypeError):
        pass
    return "unknown", abs_path.name
```

**Step 4: Verify MCP server starts and registers 14 tools**

```bash
source .venv/bin/activate
printf '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0.1"}}}\n{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}\n' | python -m mcp_server 2>/dev/null | tail -1 | python3 -c "import sys,json; d=json.load(sys.stdin); tools=d['result']['tools']; print(f'Tools: {len(tools)}'); [print(f'  - {t[\"name\"]}') for t in tools]"
```

Expected:
```
Tools: 14
  - validate_design
  - render_stl_file
  - render_png_preview
  - render_design_views
  - list_designs
  - create_from_template
  - get_design_status
  - check_environment
  - save_design_iteration
  - list_design_iterations
  - get_latest_design_iteration
  - search_knowledge_base
  - ingest_document
  - ingest_directory
```

**Step 5: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add mcp_server/server.py
git commit -m "feat: add RAG tools — search_knowledge_base, ingest_document, ingest_directory"
```

---

### Task 5: Auto-Injection on Existing Tools

**Files:**
- Modify: `mcp_server/server.py` (3 existing tool functions)

**Step 1: Modify validate_design to auto-inject hardware context**

In `validate_design()`, replace the final `return asdict(result)` with:

```python
    response = asdict(result)
    response = rag_client.auto_inject(
        response,
        f"hardware specs for {Path(resolved).stem}",
        "schemas_config",
    )
    return response
```

**Step 2: Modify create_from_template to auto-inject similar designs**

In `create_from_template()`, replace the final return block (the success return) with:

```python
    response = {
        "success": True,
        "file_path": str(dest.relative_to(PROJECT_DIR)),
        "template_used": template,
    }
    response = rag_client.auto_inject(
        response,
        f"{template} {name} design patterns",
        "openscad_code",
    )
    return response
```

**Step 3: Modify render_design_views to auto-inject design history**

In `render_design_views()`, replace the final `return result` with:

```python
    result = rag_client.auto_inject(
        result,
        f"design iteration history for {Path(resolved).stem}",
        "design_history",
    )
    return result
```

**Step 4: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS (auto-inject is a no-op when ChromaDB is unavailable)

**Step 5: Verify existing 7 tests still pass**

Run: `python -m pytest tests/test_openscad.py tests/test_versioning.py -v`
Expected: 7 PASS

**Step 6: Commit**

```bash
git add mcp_server/server.py
git commit -m "feat: add RAG auto-injection to validate, create_from_template, render_design_views"
```

---

### Task 6: Batch Ingestion Script

**Files:**
- Create: `scripts/ingest-rag.sh`

**Step 1: Write the ingestion script**

```bash
#!/usr/bin/env bash
# ingest-rag.sh — Batch ingest both repos into the RAG knowledge base
# Usage: ./scripts/ingest-rag.sh [--openscad-only | --iotlab-only]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV="${PROJECT_DIR}/.venv/bin/python"
AI_IOT_LAB="/home/tie/AI_IoT_Lab_v2"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

ingest_openscad() {
    echo -e "${GREEN}Ingesting OpenScad_AI...${NC}"

    # Designs and templates
    "$VENV" -c "
from mcp_server.chunking import chunk_file, detect_collection
from mcp_server.rag_client import store_chunks
from pathlib import Path
import sys

project = Path('$PROJECT_DIR')
count = 0
for pattern in ['designs/**/*.scad', 'templates/*.scad']:
    for f in sorted(project.glob(pattern)):
        rel = str(f.relative_to(project))
        chunks = chunk_file(str(f), 'openscad_ai', rel)
        if chunks:
            result = store_chunks(chunks, detect_collection(rel))
            count += len(chunks)
            print(f'  {rel}: {len(chunks)} chunks')

# Docs
for f in sorted(project.glob('docs/**/*.md')):
    rel = str(f.relative_to(project))
    chunks = chunk_file(str(f), 'openscad_ai', rel)
    if chunks:
        result = store_chunks(chunks, 'project_docs')
        count += len(chunks)
        print(f'  {rel}: {len(chunks)} chunks')

print(f'OpenScad_AI total: {count} chunks')
"
}

ingest_iotlab() {
    if [ ! -d "$AI_IOT_LAB" ]; then
        echo -e "${RED}AI_IoT_Lab_v2 not found at $AI_IOT_LAB${NC}"
        return 1
    fi

    echo -e "${GREEN}Ingesting AI_IoT_Lab_v2...${NC}"

    "$VENV" -c "
from mcp_server.chunking import chunk_file, detect_collection
from mcp_server.rag_client import store_chunks
from pathlib import Path

lab = Path('$AI_IOT_LAB')
supported = {'.md', '.json', '.sh', '.mmd', '.html', '.txt', '.conf', '.py'}
count = 0

for f in sorted(lab.rglob('*')):
    if not f.is_file():
        continue
    if f.suffix.lower() not in supported:
        continue
    if any(p.startswith('.') for p in f.relative_to(lab).parts):
        continue
    if 'node_modules' in str(f) or '__pycache__' in str(f):
        continue

    rel = str(f.relative_to(lab))
    chunks = chunk_file(str(f), 'ai_iot_lab_v2', rel)
    if chunks:
        collection = detect_collection(rel)
        result = store_chunks(chunks, collection)
        count += len(chunks)
        print(f'  {rel}: {len(chunks)} chunks -> {collection}')

print(f'AI_IoT_Lab_v2 total: {count} chunks')
"
}

case "${1:-all}" in
    --openscad-only) ingest_openscad ;;
    --iotlab-only)   ingest_iotlab ;;
    all|*)
        ingest_openscad
        echo ""
        ingest_iotlab
        echo ""
        echo -e "${GREEN}Batch ingestion complete.${NC}"
        ;;
esac
```

**Step 2: Make it executable and verify syntax**

```bash
chmod +x scripts/ingest-rag.sh
bash -n scripts/ingest-rag.sh && echo "Syntax OK"
```

Expected: `Syntax OK`

**Step 3: Commit**

```bash
git add scripts/ingest-rag.sh
git commit -m "feat: add batch RAG ingestion script for both repos"
```

---

### Task 7: Git Post-Commit Hook

**Files:**
- Create: `scripts/hooks/post-commit-rag.sh`

**Step 1: Write the hook script**

```bash
#!/usr/bin/env bash
# post-commit-rag.sh — Re-index changed files in RAG after each commit
# Install: cp scripts/hooks/post-commit-rag.sh .git/hooks/post-commit
#
# This hook re-ingests only the files that changed in the latest commit.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Determine project root (works from .git/hooks/ or scripts/hooks/)
if [ -f "$SCRIPT_DIR/../../mcp_server/server.py" ]; then
    PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
elif [ -f "$SCRIPT_DIR/../../scripts/hooks/post-commit-rag.sh" ]; then
    PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
else
    exit 0
fi

VENV="${PROJECT_DIR}/.venv/bin/python"

# Only run if venv exists
[ -x "$VENV" ] || exit 0

# Get changed files from the latest commit
CHANGED_FILES=$(git diff --name-only HEAD~1 HEAD 2>/dev/null || true)
[ -z "$CHANGED_FILES" ] && exit 0

# Supported extensions
SUPPORTED_EXTS="\.scad$|\.md$|\.json$|\.sh$|\.mmd$|\.html$|\.txt$|\.py$|\.conf$"

# Filter to supported file types
FILES_TO_INGEST=$(echo "$CHANGED_FILES" | grep -E "$SUPPORTED_EXTS" || true)
[ -z "$FILES_TO_INGEST" ] && exit 0

# Re-ingest each changed file (runs in background to not block the commit)
(
    cd "$PROJECT_DIR"
    echo "$FILES_TO_INGEST" | while read -r rel_path; do
        abs_path="${PROJECT_DIR}/${rel_path}"
        [ -f "$abs_path" ] || continue
        "$VENV" -c "
from mcp_server.chunking import chunk_file, detect_collection
from mcp_server.rag_client import store_chunks
chunks = chunk_file('$abs_path', 'openscad_ai', '$rel_path')
if chunks:
    store_chunks(chunks, detect_collection('$rel_path'))
    print('RAG re-indexed: $rel_path ({} chunks)'.format(len(chunks)))
" 2>/dev/null
    done
) &

exit 0
```

**Step 2: Make it executable**

```bash
chmod +x scripts/hooks/post-commit-rag.sh
```

**Step 3: Commit**

```bash
git add scripts/hooks/post-commit-rag.sh
git commit -m "feat: add git post-commit hook for automatic RAG re-indexing"
```

---

### Task 8: Update check_environment for RAG Status

**Files:**
- Modify: `mcp_server/server.py` (check_environment function)

**Step 1: Add RAG status to check_environment**

In the `check_environment()` function, add after the MQTT lines:

```python
    # RAG status
    env["rag_enabled"] = rag_client.is_rag_enabled()
    env["chromadb_host"] = os.environ.get("CHROMADB_HOST", "10.0.1.81")
    env["chromadb_port"] = int(os.environ.get("CHROMADB_PORT", "8000"))
    try:
        chroma = rag_client._get_chroma_client()
        env["chromadb_ok"] = chroma is not None
    except Exception:
        env["chromadb_ok"] = False
```

**Step 2: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS

**Step 3: Commit**

```bash
git add mcp_server/server.py
git commit -m "feat: add RAG/ChromaDB status to check_environment tool"
```

---

### Task 9: Auto-Store on Design Iteration Save

**Files:**
- Modify: `mcp_server/server.py` (save_design_iteration function)

**Step 1: Add auto-store to save_design_iteration**

In `save_design_iteration()`, add after the MQTT publish and before the return:

```python
    # Auto-store iteration in RAG design_history
    try:
        from mcp_server.chunking import chunk_file
        chunks = chunk_file(
            result["file_path"],
            "openscad_ai",
            f"iterations/{Path(result['file_path']).name}",
        )
        if chunks:
            rag_client.store_chunks(chunks, "design_history")
    except Exception as e:
        log.warning("RAG auto-store on iteration save failed: %s", e)
```

**Step 2: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS

**Step 3: Commit**

```bash
git add mcp_server/server.py
git commit -m "feat: auto-store design iterations in RAG design_history collection"
```

---

### Task 10: Update Documentation

**Files:**
- Modify: `docs/mcp-api-reference.md`
- Modify: `README.md`

**Step 1: Add the 3 new tools to mcp-api-reference.md**

Add after the `get_latest_design_iteration` section:

```markdown
---

### search_knowledge_base

Search the unified RAG knowledge base for relevant context. Searches across code, documentation, schemas, and design history from both OpenScad_AI and AI_IoT_Lab_v2.

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `query` | string | yes | — | Semantic search text |
| `collection` | string | no | all | Specific collection: `"openscad_code"`, `"project_docs"`, `"schemas_config"`, `"design_history"` |
| `n_results` | int | no | 5 | Maximum results to return |

**Returns:**

```json
{
  "results": [
    {
      "id": "openscad_ai:docs/bosl2-quickref.md:2",
      "collection": "openscad_code",
      "document": "## Mounting Holes...",
      "distance": 0.23,
      "metadata": {"file_path": "docs/bosl2-quickref.md", "source_repo": "openscad_ai"}
    }
  ],
  "count": 1
}
```

**MQTT event:** `openscad/rag/search`

---

### ingest_document

Ingest a single file into the RAG knowledge base via MQTT.

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `file_path` | string | yes | — | Path to file |
| `collection` | string | no | auto-detect | Target collection |

**Returns:**

```json
{
  "success": true,
  "file": "designs/bracket.scad",
  "collection": "openscad_code",
  "chunks": 3
}
```

**MQTT event:** `openscad/rag/ingested`

---

### ingest_directory

Bulk ingest files from a directory into the RAG knowledge base.

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `directory` | string | yes | — | Directory path |
| `pattern` | string | no | `"**/*"` | Glob pattern |
| `collection` | string | no | auto-detect | Target collection |

**Returns:**

```json
{
  "success": true,
  "files": 42,
  "chunks": 187,
  "errors": null
}
```

**MQTT event:** `openscad/rag/bulk_ingested`
```

**Step 2: Update README.md tools table**

Update the tools table in README.md to include the 3 new tools (14 total) and add a RAG section.

**Step 3: Commit**

```bash
git add docs/mcp-api-reference.md README.md
git commit -m "docs: add RAG tools to API reference and README"
```

---

### Task 11: Final Verification

**Step 1: Run the full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS

**Step 2: Verify MCP server registers 14 tools and 7 resources**

```bash
source .venv/bin/activate
printf '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0.1"}}}\n{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}\n' | python -m mcp_server 2>/dev/null | tail -1 | python3 -c "import sys,json; d=json.load(sys.stdin); tools=d['result']['tools']; print(f'Tools: {len(tools)}'); [print(f'  - {t[\"name\"]}') for t in tools]"
```

Expected: 14 tools listed

```bash
printf '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0.1"}}}\n{"jsonrpc":"2.0","id":2,"method":"resources/list","params":{}}\n' | python -m mcp_server 2>/dev/null | tail -1 | python3 -c "import sys,json; d=json.load(sys.stdin); res=d['result']['resources']; print(f'Resources: {len(res)}'); [print(f'  - {r[\"uri\"]}') for r in res]"
```

Expected: 7 resources listed

**Step 3: Verify graceful degradation (ChromaDB not reachable from this machine)**

```bash
python -c "
from mcp_server.rag_client import search, is_rag_enabled
print('RAG enabled:', is_rag_enabled())
result = search('test query')
print('Search result:', result)
print('Graceful:', 'error' in result or result['count'] == 0)
"
```

Expected: RAG enabled, search returns empty with error (ChromaDB not reachable), no crash.

**Step 4: Push to remote**

```bash
git push origin master
```

---

## Verification Checklist

After all tasks are complete:

- [ ] `chromadb-client` installed in venv
- [ ] `mcp_server/chunking.py` — chunking with 5 file types, dedup IDs, metadata
- [ ] `mcp_server/rag_client.py` — ChromaDB reads, MQTT writes, auto-inject helper
- [ ] `search_knowledge_base` tool registered and working
- [ ] `ingest_document` tool registered and working
- [ ] `ingest_directory` tool registered and working
- [ ] Auto-injection on `validate_design`, `create_from_template`, `render_design_views`
- [ ] `save_design_iteration` auto-stores to `design_history`
- [ ] `check_environment` reports RAG/ChromaDB status
- [ ] `scripts/ingest-rag.sh` batch ingestion script
- [ ] `scripts/hooks/post-commit-rag.sh` git hook
- [ ] 14 tools registered (11 existing + 3 new)
- [ ] 7 resources registered (unchanged)
- [ ] All existing 7 tests still pass
- [ ] All new tests pass
- [ ] Graceful degradation when ChromaDB unavailable
- [ ] `RAG_ENABLED=false` disables all RAG features
- [ ] Documentation updated
