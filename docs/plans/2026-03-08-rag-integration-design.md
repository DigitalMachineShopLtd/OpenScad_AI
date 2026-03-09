# RAG Integration Design — Unified Knowledge Base for OpenScad_AI

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:writing-plans to create the implementation plan from this design.

**Date:** 2026-03-08
**Status:** Approved
**Approach:** Hybrid — MQTT for writes, direct ChromaDB HTTP for reads

---

## Goal

Add a unified RAG (Retrieval-Augmented Generation) system that ingests all code, documentation, schemas, prompts, and design history from both OpenScad_AI and AI_IoT_Lab_v2. The RAG integrates into the MCP server workflow so Claude can query it for relevant context when designing parts, writing BOSL2 code, or iterating on designs.

## Architecture

Hybrid integration: direct ChromaDB HTTP for low-latency reads, MQTT for protocol-compliant writes. Uses the existing ChromaDB instance on AI-03 (10.0.1.81:8000) and the existing MQTT-ChromaDB bridge. Follows Pillar 1 ("Everything is a Message") for ingestion while keeping query latency low.

## Network Topology

```
┌─────────────────────────────────────────────────────┐
│  This Machine (OpenScad_AI MCP Server)              │
│                                                      │
│  mcp_server/rag_client.py                           │
│  ├── READS:  HTTP → ChromaDB (10.0.1.81:8000)      │
│  └── WRITES: MQTT → Broker (10.0.1.82:1883)        │
│              → chromadb-bridge → ChromaDB            │
└──────────┬──────────────┬───────────────────────────┘
           │              │
     Direct HTTP       MQTT pub
           │              │
           ▼              ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   AI-03      │  │  MQTT Broker │  │   AI-02      │
│  10.0.1.81   │  │  10.0.1.82   │  │  10.0.1.80   │
│              │  │  :1883       │  │              │
│  ChromaDB    │  │              │  │  Ollama      │
│  :8000       │  │              │  │  :11434      │
│              │  │              │  │  nomic-embed  │
└──────────────┘  └──────────────┘  └──────────────┘
```

---

## Data Model — ChromaDB Collections

| Collection | Content | Source | Chunk Strategy |
|---|---|---|---|
| `openscad_code` | .scad files, templates, BOSL2 patterns, inline MCP resources | Both repos | Per-file, function-level splits for large files |
| `project_docs` | Markdown docs, plans, how-tos, session logs, diagrams | Both repos | ~500 token chunks with 50 token overlap |
| `schemas_config` | JSON schemas, MQTT topics, Node-RED flows, configs, shell scripts | AI_IoT_Lab_v2 | Per-file (schemas are small) |
| `design_history` | Design iterations, render metadata, past prompts | OpenScad_AI runtime | Per-iteration with version/dimensions metadata |

### Metadata on Every Chunk

- `source_repo`: `"openscad_ai"` or `"ai_iot_lab_v2"`
- `file_path`: original file path relative to repo root
- `file_type`: `"scad"`, `"markdown"`, `"json"`, `"shell"`, `"mermaid"`, `"html"`
- `modified`: file mtime (float)
- `chunk_index`: position within file (0-based)

### Document IDs (Deduplication)

Deterministic: `{repo}:{relative_path}:{chunk_index}`

Re-ingesting the same file performs a ChromaDB upsert, keeping the index current without duplicates.

---

## MCP Integration

### New Tools (3)

#### search_knowledge_base

Explicit semantic search across all or specific collections.

```python
@mcp.tool()
def search_knowledge_base(
    query: str,
    collection: str | None = None,
    n_results: int = 5,
) -> dict:
```

- Backend: Direct ChromaDB HTTP (low latency)
- Returns: `{"results": [...], "count": N, "collection": str}`
- MQTT event: `openscad/rag/search`

#### ingest_document

On-demand ingestion of a single file.

```python
@mcp.tool()
def ingest_document(
    file_path: str,
    collection: str | None = None,
) -> dict:
```

- Backend: MQTT `ailab/rag/store/{request_id}` (protocol compliant)
- Auto-detects collection from file type if not specified
- Returns: `{"success": bool, "chunks": int, "collection": str}`
- MQTT event: `openscad/rag/ingested`

#### ingest_directory

Bulk ingest a directory with glob pattern filtering.

```python
@mcp.tool()
def ingest_directory(
    directory: str,
    pattern: str = "**/*",
    collection: str | None = None,
) -> dict:
```

- Backend: MQTT `ailab/rag/store/{request_id}` per chunk
- Returns: `{"success": bool, "files": int, "chunks": int}`
- MQTT event: `openscad/rag/bulk_ingested`

### Auto-Injection Points

Existing tools silently query the RAG and append a `rag_context` field to responses:

| Existing Tool | Auto-Query | Injected Context |
|---|---|---|
| `create_from_template` | `openscad_code` with template + description | Similar past designs, relevant BOSL2 patterns |
| `render_design_views` | `design_history` with file stem | Previous iteration notes, what changed |
| `validate_design` | `schemas_config` for hardware matches | Dimensions, mounting patterns, connector specs |

If ChromaDB is unreachable, `rag_context` is omitted — graceful degradation.

### New Module

```
mcp_server/
└── rag_client.py    # Direct ChromaDB HTTP reads
                     # MQTT-based writes (store/delete)
                     # Chunking and metadata logic
                     # Auto-injection helper
```

---

## Ingestion Pipeline

### Content Inventory

**From AI_IoT_Lab_v2 (~219 files):**

| Content | Count | Collection | Priority |
|---|---|---|---|
| Architecture docs, specs, plans | 44 | `project_docs` | Tier 1 |
| How-to guides, session logs | 42 | `project_docs` | Tier 2 |
| JSON schemas | 15 | `schemas_config` | Tier 1 |
| Node-RED flows | 13 | `schemas_config` | Tier 2 |
| Shell scripts | 41 | `schemas_config` | Tier 3 |
| LLM routing config, prompts | 8 | `schemas_config` | Tier 1 |
| MMBasic reference | 26 | `project_docs` | Tier 3 |
| Mermaid diagrams | 12 | `project_docs` | Tier 2 |
| HTML dashboards | 2 | `schemas_config` | Tier 3 |

**From OpenScad_AI:**

| Content | Count | Collection | Priority |
|---|---|---|---|
| .scad designs + templates | ~5 | `openscad_code` | Tier 1 |
| BOSL2 quickref + inline resources | 7 | `openscad_code` | Tier 1 |
| Docs (HOW-TO, API ref, image_to_code) | 5 | `project_docs` | Tier 1 |
| Design plans | 3 | `project_docs` | Tier 2 |

**Runtime (ongoing):**

| Content | Trigger | Collection |
|---|---|---|
| Design iterations (v001, v002...) | `save_design_iteration` auto-stores | `design_history` |
| Render metadata (views, dimensions) | `render_design_views` auto-stores | `design_history` |

### Chunking Strategy

```
Markdown:  Split on ## headings, max 500 tokens, 50 token overlap
Code:      Split on function/module boundaries, max 300 tokens
JSON:      Whole file if < 500 tokens, else top-level keys as chunks
Shell:     Whole file if < 500 tokens, else split on function definitions
Mermaid:   Whole file (diagrams are small)
```

### Ingestion Triggers

1. **Initial batch script** — `scripts/ingest-rag.sh` crawls both repos, calls ingestion via MQTT
2. **Git post-commit hook** — Re-indexes changed files only (`git diff --name-only HEAD~1`)
3. **MCP on-demand** — `ingest_document` or `ingest_directory` tools
4. **Auto on iteration save** — `save_design_iteration` triggers store to `design_history`

---

## Configuration

Environment variables (same pattern as existing MQTT config):

| Variable | Default | Purpose |
|---|---|---|
| `CHROMADB_HOST` | `10.0.1.81` | ChromaDB server address |
| `CHROMADB_PORT` | `8000` | ChromaDB HTTP port |
| `RAG_ENABLED` | `true` | Kill switch for all RAG features |
| `RAG_AUTO_INJECT` | `true` | Toggle auto-injection on tool calls |
| `RAG_N_RESULTS` | `5` | Default number of search results |

MQTT reuses existing `MQTT_BROKER` and `MQTT_PORT`.

### Dependencies

Add to `requirements.txt`:
- `chromadb-client` — Lightweight HTTP-only client (~2MB, no server components)

No Ollama dependency — ChromaDB handles its own embeddings via the existing bridge infrastructure.

---

## Graceful Degradation

Same pattern as existing MQTT client:

- ChromaDB unreachable → log warning, `search_knowledge_base` returns `{"results": [], "error": "ChromaDB unavailable"}`
- MQTT unreachable → log warning, ingestion silently fails
- Auto-injection skipped if either backend is down
- `RAG_ENABLED=false` disables all RAG features cleanly
- All 11 existing tools continue to work regardless of RAG state

---

## Testing Strategy

### Unit Tests (no cluster required)

| Test File | Coverage |
|---|---|
| `tests/test_rag_client.py` | Chunking logic, metadata generation, dedup IDs, graceful degradation |
| `tests/test_rag_ingestion.py` | File type detection, chunk splitting for all types, size limits |

Mock ChromaDB and MQTT connections.

### Integration Tests (require cluster)

| Test | Validates |
|---|---|
| Store → query round-trip | Ingest a .scad file, query for it, verify result |
| Auto-injection on `create_from_template` | Verify `rag_context` field in response |
| Dedup on re-ingest | Same file twice → single entry |
| Graceful degradation | Kill ChromaDB → tools still work |

### Verification Checklist

- [ ] `search_knowledge_base` returns relevant results for "mounting holes M3"
- [ ] `ingest_document` stores a file via MQTT and it's queryable
- [ ] `ingest_directory` processes both repos without errors
- [ ] Auto-injection adds `rag_context` to `create_from_template` response
- [ ] `RAG_ENABLED=false` disables all RAG features
- [ ] ChromaDB down → tools still work, warning logged
- [ ] Git post-commit hook re-indexes changed files only
- [ ] Dedup IDs prevent duplicate chunks
- [ ] All existing 7 tests still pass
- [ ] All existing 11 tools still registered
- [ ] All existing 7 resources still registered

---

## Existing Infrastructure Referenced

### ChromaDB (AI-03)
- Host: 10.0.1.81, Port: 8000
- Data: `/var/lib/chromadb`
- Service: `chromadb.service`
- Health: `http://10.0.1.81:8000/api/v1/heartbeat`

### MQTT-ChromaDB Bridge (AI-03)
- Service: `chromadb-bridge.service`
- Subscribe: `ailab/rag/store/#`, `ailab/rag/query/#`, `ailab/rag/delete/#`, `ailab/rag/list/#`
- Publish: `ailab/rag/response/{request_id}`
- Client: `/opt/ailab/services/chromadb_client.py`

### Ollama (AI-02)
- Host: 10.0.1.80, Port: 11434
- Embedding model: `nomic-embed-text`
- Inference model: `llama3.2:3b`

### MQTT Broker
- Host: 10.0.1.82, Port: 1883
- Existing schemas: `rag-request.schema.json`, `rag-response.schema.json`

### Existing RAG Request Schema
```json
{
  "request_id": "rag_<unique>",
  "operation": "store|query|delete|list",
  "collection": "default",
  "document": "text to store",
  "query": "search query",
  "metadata": {},
  "n_results": 5,
  "timestamp": "ISO 8601"
}
```
