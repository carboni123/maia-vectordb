"""Set up a MAIA VectorDB knowledge base with sample documents.

This script:
1. Creates a vector store
2. Uploads sample documents (text about Python, FastAPI, and pgvector)
3. Verifies the documents are searchable

Run this before the multi-provider examples to have data to search against.

Prerequisites:
    - MAIA VectorDB server running: ``uvicorn maia_vectordb.main:app``
    - PostgreSQL with pgvector at localhost:5432

Usage::

    python examples/setup_knowledge_base.py

    # Or with a custom API URL:
    MAIA_API_BASE=http://localhost:9000 python examples/setup_knowledge_base.py
"""

from __future__ import annotations

import os
import sys

import httpx

API_BASE = os.environ.get("MAIA_API_BASE", "http://localhost:8000").rstrip("/")

# Sample documents to upload
SAMPLE_DOCUMENTS = [
    {
        "filename": "python_overview.txt",
        "content": (
            "Python is a high-level, general-purpose programming language. "
            "Its design philosophy emphasizes code readability with the use "
            "of significant indentation. Python is dynamically typed and "
            "garbage-collected. It supports multiple programming paradigms, "
            "including structured, object-oriented and functional programming. "
            "Python was conceived in the late 1980s by Guido van Rossum and "
            "first released in 1991. Python consistently ranks as one of the "
            "most popular programming languages."
        ),
    },
    {
        "filename": "fastapi_guide.txt",
        "content": (
            "FastAPI is a modern, fast web framework for building APIs with "
            "Python based on standard Python type hints. Key features include "
            "automatic API documentation with Swagger UI and ReDoc, data "
            "validation using Pydantic, dependency injection system, async "
            "support with ASGI, and high performance comparable to NodeJS "
            "and Go. FastAPI was created by Sebastian Ramirez and first "
            "released in 2018. It uses Starlette for the web parts and "
            "Pydantic for the data parts."
        ),
    },
    {
        "filename": "pgvector_guide.txt",
        "content": (
            "pgvector is an open-source extension for PostgreSQL that adds "
            "support for vector similarity search. It provides vector data "
            "types, distance operators (L2, inner product, cosine), and "
            "indexing methods (IVFFlat, HNSW) for efficient nearest-neighbor "
            "queries. pgvector is commonly used for AI applications like "
            "semantic search, recommendation systems, and retrieval-augmented "
            "generation (RAG). HNSW indexes provide excellent query "
            "performance with approximate nearest neighbor search."
        ),
    },
    {
        "filename": "maia_vectordb_docs.txt",
        "content": (
            "MAIA VectorDB is an OpenAI-compatible vector store API for "
            "document storage, chunking, embedding, and semantic search. "
            "It provides a drop-in replacement for OpenAI's vector store "
            "endpoints, but stores data in your own PostgreSQL database "
            "with pgvector. This means any LLM provider (Anthropic Claude, "
            "Google Gemini, xAI Grok) can perform vector store search, "
            "not just OpenAI. The API supports vector store management, "
            "file upload with automatic chunking and embedding, and fast "
            "cosine similarity search with HNSW indexes."
        ),
    },
]


def main() -> None:
    client = httpx.Client(base_url=API_BASE, timeout=30)

    # 1. Health check
    print(f"Connecting to MAIA VectorDB at {API_BASE}...")
    try:
        resp = client.get("/health")
        resp.raise_for_status()
        health = resp.json()
        print(f"  Status: {health.get('status', 'unknown')}")
    except httpx.ConnectError:
        print(f"ERROR: Cannot connect to {API_BASE}. Is the server running?")
        print("  Start it with: uvicorn maia_vectordb.main:app")
        sys.exit(1)

    # 2. Create vector store
    print("\nCreating vector store 'example-knowledge-base'...")
    resp = client.post(
        "/v1/vector_stores",
        json={
            "name": "example-knowledge-base",
            "metadata": {"purpose": "llm-factory-toolkit examples"},
        },
    )
    resp.raise_for_status()
    store = resp.json()
    store_id = store["id"]
    print(f"  Created: {store_id}")

    # 3. Upload documents
    print(f"\nUploading {len(SAMPLE_DOCUMENTS)} documents...")
    for doc in SAMPLE_DOCUMENTS:
        resp = client.post(
            f"/v1/vector_stores/{store_id}/files",
            data={"text": doc["content"]},
        )
        resp.raise_for_status()
        file_info = resp.json()
        status = file_info.get("status", "unknown")
        chunks = file_info.get("chunk_count", 0)
        print(f"  {doc['filename']}: status={status}, chunks={chunks}")

    # 4. Verify search works
    print("\nVerifying search...")
    test_query = "What is pgvector?"
    resp = client.post(
        f"/v1/vector_stores/{store_id}/search",
        json={"query": test_query, "max_results": 3},
    )
    resp.raise_for_status()
    search_results = resp.json()
    result_count = len(search_results.get("data", []))
    print(f"  Query: '{test_query}' -> {result_count} results")

    if result_count > 0:
        top = search_results["data"][0]
        print(f"  Top result score: {top['score']:.4f}")
        print(f"  Content preview: {top['content'][:80]}...")

    # 5. Summary
    print("\n" + "=" * 60)
    print("Setup complete!")
    print(f"  Vector Store ID: {store_id}")
    print(f"  API Base:        {API_BASE}")
    print()
    print("Use this in your examples:")
    print(f'  VECTOR_STORE_ID = "{store_id}"')
    print(f'  MAIA_API_BASE = "{API_BASE}"')
    print()
    print("Or set environment variables:")
    print(f"  export VECTOR_STORE_ID={store_id}")
    print(f"  export MAIA_API_BASE={API_BASE}")
    print("=" * 60)


if __name__ == "__main__":
    main()
