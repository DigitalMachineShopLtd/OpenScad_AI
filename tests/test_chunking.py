"""Tests for document chunking — RAG ingestion pipeline."""

import json
import os
import tempfile

import pytest

from mcp_server.chunking import chunk_file, detect_collection, make_doc_id


# ── make_doc_id ──────────────────────────────────────────────────────────────

def test_make_doc_id():
    """make_doc_id returns deterministic '{repo}:{path}:{index}' string."""
    result = make_doc_id("my_repo", "src/main.scad", 0)
    assert result == "my_repo:src/main.scad:0"

    result2 = make_doc_id("my_repo", "src/main.scad", 3)
    assert result2 == "my_repo:src/main.scad:3"


# ── detect_collection ────────────────────────────────────────────────────────

def test_detect_collection_scad():
    """.scad files map to 'openscad_code'."""
    assert detect_collection("models/cube.scad") == "openscad_code"


def test_detect_collection_markdown():
    """.md files map to 'project_docs'."""
    assert detect_collection("docs/README.md") == "project_docs"


def test_detect_collection_json():
    """.json files map to 'schemas_config'."""
    assert detect_collection("config/settings.json") == "schemas_config"


def test_detect_collection_shell():
    """.sh files map to 'schemas_config'."""
    assert detect_collection("scripts/deploy.sh") == "schemas_config"


def test_detect_collection_mermaid():
    """.mmd files map to 'project_docs'."""
    assert detect_collection("docs/flow.mmd") == "project_docs"


# ── chunk_file ───────────────────────────────────────────────────────────────

def test_chunk_small_markdown():
    """Small markdown file produces a single chunk with correct metadata."""
    with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
        f.write("# Title\n\nShort content here.\n")
        f.flush()
        abs_path = f.name

    try:
        chunks = chunk_file(abs_path, "test_repo", "docs/short.md")
        assert len(chunks) == 1

        chunk = chunks[0]
        assert chunk["id"] == "test_repo:docs/short.md:0"
        assert "Short content here" in chunk["document"]
        assert chunk["metadata"]["source_repo"] == "test_repo"
        assert chunk["metadata"]["file_path"] == "docs/short.md"
        assert chunk["metadata"]["file_type"] == "markdown"
        assert chunk["metadata"]["chunk_index"] == 0
        assert "modified" in chunk["metadata"]
    finally:
        os.unlink(abs_path)


def test_chunk_large_markdown_splits_on_headings():
    """Large markdown with ## headings splits into multiple chunks."""
    sections = []
    for i in range(6):
        sections.append(f"## Section {i}\n\n{'Lorem ipsum dolor sit amet. ' * 40}\n")
    content = "# Main Title\n\n" + "\n".join(sections)

    # Verify the content is large enough to trigger splitting
    assert len(content) > 2000

    with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
        f.write(content)
        f.flush()
        abs_path = f.name

    try:
        chunks = chunk_file(abs_path, "test_repo", "docs/large.md")
        assert len(chunks) > 1

        # Each chunk should have sequential IDs
        for i, chunk in enumerate(chunks):
            assert chunk["id"] == f"test_repo:docs/large.md:{i}"
            assert chunk["metadata"]["chunk_index"] == i
            assert chunk["metadata"]["file_type"] == "markdown"

        # No chunk should exceed ~2000 chars significantly
        for chunk in chunks:
            assert len(chunk["document"]) <= 2500
    finally:
        os.unlink(abs_path)


def test_chunk_json_whole_file():
    """Small JSON file produces a single chunk."""
    data = {"key": "value", "number": 42}
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        json.dump(data, f)
        f.flush()
        abs_path = f.name

    try:
        chunks = chunk_file(abs_path, "test_repo", "config/settings.json")
        assert len(chunks) == 1
        assert chunks[0]["metadata"]["file_type"] == "json"
    finally:
        os.unlink(abs_path)


def test_chunk_scad_file():
    """SCAD file is typed as 'scad'."""
    with tempfile.NamedTemporaryFile(suffix=".scad", mode="w", delete=False) as f:
        f.write("cube([10, 10, 10]);\n")
        f.flush()
        abs_path = f.name

    try:
        chunks = chunk_file(abs_path, "test_repo", "models/cube.scad")
        assert len(chunks) == 1
        assert chunks[0]["metadata"]["file_type"] == "scad"
    finally:
        os.unlink(abs_path)


def test_chunk_shell_file():
    """Shell file is typed as 'shell'."""
    with tempfile.NamedTemporaryFile(suffix=".sh", mode="w", delete=False) as f:
        f.write("#!/bin/bash\necho 'hello'\n")
        f.flush()
        abs_path = f.name

    try:
        chunks = chunk_file(abs_path, "test_repo", "scripts/run.sh")
        assert len(chunks) == 1
        assert chunks[0]["metadata"]["file_type"] == "shell"
    finally:
        os.unlink(abs_path)
