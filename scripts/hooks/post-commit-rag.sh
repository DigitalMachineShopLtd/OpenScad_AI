#!/usr/bin/env bash
# post-commit-rag.sh — Re-index changed files in RAG after each commit
# Install: cp scripts/hooks/post-commit-rag.sh .git/hooks/post-commit

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Determine project root
if [ -f "$SCRIPT_DIR/../../mcp_server/server.py" ]; then
    PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
elif [ -f "$SCRIPT_DIR/../../scripts/hooks/post-commit-rag.sh" ]; then
    PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
else
    exit 0
fi

VENV="${PROJECT_DIR}/.venv/bin/python"

[ -x "$VENV" ] || exit 0

CHANGED_FILES=$(git diff --name-only HEAD~1 HEAD 2>/dev/null || true)
[ -z "$CHANGED_FILES" ] && exit 0

SUPPORTED_EXTS="\.scad$|\.md$|\.json$|\.sh$|\.mmd$|\.html$|\.txt$|\.py$|\.conf$"

FILES_TO_INGEST=$(echo "$CHANGED_FILES" | grep -E "$SUPPORTED_EXTS" || true)
[ -z "$FILES_TO_INGEST" ] && exit 0

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
