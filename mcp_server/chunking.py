"""Document chunking for RAG ingestion.

Splits files into embeddable chunks with metadata for vector storage.
"""

import logging
import os
import re

logger = logging.getLogger(__name__)

MAX_CHUNK_CHARS = 2000
OVERLAP_CHARS = 200

# Extension → collection mapping
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

# Extension → human-readable file type
_FILE_TYPE_MAP = {
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
    """Return a deterministic chunk ID: '{repo}:{relative_path}:{chunk_index}'."""
    return f"{repo}:{relative_path}:{chunk_index}"


def detect_collection(file_path: str) -> str:
    """Return the collection name based on file extension."""
    _, ext = os.path.splitext(file_path)
    return _COLLECTION_MAP.get(ext.lower(), "project_docs")


def _split_markdown(text: str) -> list[str]:
    """Split markdown on '## ' headings, keeping each heading with its content."""
    parts = re.split(r"(?=^## )", text, flags=re.MULTILINE)
    # Filter empty parts and strip
    return [p for p in parts if p.strip()]


def _split_by_size(text: str, max_chars: int = MAX_CHUNK_CHARS,
                   overlap: int = OVERLAP_CHARS) -> list[str]:
    """Split text into chunks of max_chars with overlap between them."""
    if len(text) <= max_chars:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap
    return chunks


def chunk_file(abs_path: str, repo: str, relative_path: str) -> list[dict]:
    """Split a file into embeddable chunks with metadata.

    Args:
        abs_path: Absolute path to the file on disk.
        repo: Repository name for ID generation.
        relative_path: Relative path within the repo.

    Returns:
        List of chunk dicts, each with 'id', 'document', and 'metadata'.
    """
    _, ext = os.path.splitext(abs_path)
    ext_lower = ext.lower()
    file_type = _FILE_TYPE_MAP.get(ext_lower, "text")

    try:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except OSError:
        logger.error("Failed to read file: %s", abs_path)
        return []

    mtime = os.path.getmtime(abs_path)

    # Decide how to split
    if ext_lower in (".md",) and len(content) > MAX_CHUNK_CHARS:
        raw_chunks = _split_markdown(content)
        # Further split any oversized sections
        final_chunks = []
        for section in raw_chunks:
            if len(section) > MAX_CHUNK_CHARS:
                final_chunks.extend(_split_by_size(section))
            else:
                final_chunks.append(section)
    elif len(content) > MAX_CHUNK_CHARS:
        final_chunks = _split_by_size(content)
    else:
        final_chunks = [content]

    results = []
    for i, chunk_text in enumerate(final_chunks):
        results.append({
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

    logger.info("Chunked %s into %d chunk(s)", relative_path, len(results))
    return results
