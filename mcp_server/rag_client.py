"""RAG client — hybrid approach: direct ChromaDB HTTP for reads, MQTT for writes."""

import logging
import os
import uuid
from datetime import datetime, timezone

import chromadb

from mcp_server.mqtt_client import publish

log = logging.getLogger(__name__)

ALL_COLLECTIONS = ["openscad_code", "project_docs", "schemas_config", "design_history"]

_chroma_client = None
_chroma_init_done = False


def is_rag_enabled() -> bool:
    """Returns False if env RAG_ENABLED=false, else True."""
    return os.environ.get("RAG_ENABLED", "true").lower() != "false"


def _is_auto_inject_enabled() -> bool:
    """Returns False if env RAG_AUTO_INJECT=false, else True."""
    return os.environ.get("RAG_AUTO_INJECT", "true").lower() != "false"


def _get_chroma_client():
    """Lazy singleton ChromaDB HTTP client. Returns None if unavailable."""
    global _chroma_client, _chroma_init_done
    if _chroma_init_done:
        return _chroma_client

    _chroma_init_done = True
    host = os.environ.get("CHROMADB_HOST", "10.0.1.81")
    port = int(os.environ.get("CHROMADB_PORT", "8000"))

    try:
        client = chromadb.HttpClient(host=host, port=port)
        client.heartbeat()
        _chroma_client = client
        log.info("ChromaDB connected: %s:%d", host, port)
        return _chroma_client
    except Exception as e:
        log.warning("ChromaDB unavailable (%s:%d): %s", host, port, e)
        return None


def search(query: str, collection: str | None = None, n_results: int | None = None) -> dict:
    """Search ChromaDB collections. Returns dict with results, count, optional error."""
    if not is_rag_enabled():
        return {"results": [], "count": 0}

    if n_results is None:
        n_results = int(os.environ.get("RAG_N_RESULTS", "5"))

    client = _get_chroma_client()
    if client is None:
        return {"results": [], "count": 0, "error": "ChromaDB unavailable"}

    all_results = []

    if collection is not None:
        try:
            col = client.get_collection(name=collection)
            raw = col.query(query_texts=[query], n_results=n_results)
            all_results.extend(_format_results(raw, collection))
        except Exception as e:
            log.warning("Search failed on collection %s: %s", collection, e)
            return {"results": [], "count": 0, "error": str(e)}
    else:
        for col_name in ALL_COLLECTIONS:
            try:
                col = client.get_or_create_collection(name=col_name)
                raw = col.query(query_texts=[query], n_results=n_results)
                all_results.extend(_format_results(raw, col_name))
            except Exception as e:
                log.warning("Search failed on collection %s: %s", col_name, e)

    all_results.sort(key=lambda r: r["distance"])

    result = {"results": all_results, "count": len(all_results)}

    publish("openscad/rag/search", {
        "query": query,
        "collection": collection,
        "n_results": n_results,
        "count": len(all_results),
    })

    return result


def _format_results(raw: dict, collection: str) -> list[dict]:
    """Convert raw ChromaDB query results to flat list of result dicts."""
    results = []
    if not raw.get("ids") or not raw["ids"][0]:
        return results

    ids = raw["ids"][0]
    documents = raw["documents"][0] if raw.get("documents") else [None] * len(ids)
    distances = raw["distances"][0] if raw.get("distances") else [0.0] * len(ids)
    metadatas = raw["metadatas"][0] if raw.get("metadatas") else [{}] * len(ids)

    for i, doc_id in enumerate(ids):
        results.append({
            "id": doc_id,
            "document": documents[i],
            "distance": distances[i],
            "metadata": metadatas[i],
            "collection": collection,
        })

    return results


def store_chunks(chunks: list[dict], collection: str) -> dict:
    """Publish chunks via MQTT for RAG storage. Returns dict with success, chunks_sent."""
    sent = 0
    all_ok = True

    for chunk in chunks:
        request_id = str(uuid.uuid4())
        topic = f"ailab/rag/store/{request_id}"
        payload = {
            "request_id": request_id,
            "operation": "store",
            "collection": collection,
            "id": chunk.get("id", str(uuid.uuid4())),
            "document": chunk.get("document", ""),
            "metadata": chunk.get("metadata", {}),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        ok = publish(topic, payload)
        if ok:
            sent += 1
        else:
            all_ok = False
            log.warning("Failed to publish chunk %s to MQTT", chunk.get("id"))

    return {"success": all_ok, "chunks_sent": sent}


def auto_inject(response: dict, query: str, collection: str, n_results: int = 3) -> dict:
    """Enrich response with RAG context if enabled. Returns response unchanged if disabled."""
    if not is_rag_enabled():
        return response

    if not _is_auto_inject_enabled():
        return response

    search_result = search(query, collection=collection, n_results=n_results)

    if search_result.get("results"):
        response["rag_context"] = search_result["results"]

    return response
