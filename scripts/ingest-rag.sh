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
