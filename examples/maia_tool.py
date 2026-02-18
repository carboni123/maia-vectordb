"""MAIA VectorDB search tool for llm-factory-toolkit.

Provides a reusable tool that any LLM provider (OpenAI, Anthropic, Gemini, xAI)
can use to perform semantic search over a MAIA VectorDB vector store.

This replaces OpenAI's built-in ``file_search`` with a provider-agnostic
alternative powered by PostgreSQL + pgvector.

Usage (function-based)::

    from llm_factory_toolkit import LLMClient, ToolFactory
    from maia_tool import register_vector_store_search

    factory = ToolFactory()
    register_vector_store_search(factory)

    client = LLMClient(model="anthropic/claude-sonnet-4", tool_factory=factory)
    result = await client.generate(
        input=[{"role": "user", "content": "What is MAIA VectorDB?"}],
        tool_execution_context={
            "vector_store_id": "your-store-id",
            "maia_api_base": "http://localhost:8000",
        },
    )

Usage (class-based)::

    from llm_factory_toolkit import ToolFactory
    from maia_tool import VectorStoreSearchTool

    factory = ToolFactory()
    factory.register_tool_class(VectorStoreSearchTool)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx
from llm_factory_toolkit.tools.base_tool import BaseTool
from llm_factory_toolkit.tools.models import ToolExecutionResult

logger = logging.getLogger(__name__)

_DEFAULT_API_BASE = "http://localhost:8000"


# ---------------------------------------------------------------------------
# Class-based tool (BaseTool subclass)
# ---------------------------------------------------------------------------


class VectorStoreSearchTool(BaseTool):
    """Semantic search over a MAIA VectorDB vector store.

    Calls the ``POST /v1/vector_stores/{id}/search`` endpoint and returns
    matching document chunks ranked by cosine similarity.

    Context-injected parameters (via ``tool_execution_context``):
        vector_store_id: UUID of the target vector store.
        maia_api_base: Base URL of the MAIA VectorDB API (default localhost:8000).
    """

    NAME = "vector_store_search"
    DESCRIPTION = (
        "Search a knowledge base for relevant document chunks. "
        "Use this tool when the user asks a question that may be "
        "answered by stored documents, files, or knowledge base content. "
        "Returns the most relevant text passages ranked by similarity."
    )
    PARAMETERS: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "The search query. Use natural language to describe "
                    "what information you're looking for."
                ),
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return (1-20).",
                "default": 5,
            },
        },
        "required": ["query"],
    }
    CATEGORY = "knowledge"
    TAGS = ["search", "vector", "rag", "knowledge-base"]

    def execute(
        self,
        query: str,
        max_results: int = 5,
        vector_store_id: Optional[str] = None,
        maia_api_base: Optional[str] = None,
    ) -> ToolExecutionResult:
        """Execute a semantic search against MAIA VectorDB.

        ``vector_store_id`` and ``maia_api_base`` are injected from
        ``tool_execution_context`` — the LLM never sees them.
        """
        if not vector_store_id:
            return ToolExecutionResult(
                content="Error: No vector_store_id configured. "
                "Set it in tool_execution_context.",
                error="missing_vector_store_id",
            )

        base = (maia_api_base or _DEFAULT_API_BASE).rstrip("/")
        url = f"{base}/v1/vector_stores/{vector_store_id}/search"

        payload = {
            "query": query,
            "max_results": min(max(max_results, 1), 20),
        }

        try:
            with httpx.Client(timeout=30) as http:
                resp = http.post(url, json=payload)
                resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            msg = f"MAIA API error {exc.response.status_code}: {exc.response.text}"
            logger.error(msg)
            return ToolExecutionResult(content=msg, error=msg)
        except httpx.ConnectError:
            msg = f"Cannot connect to MAIA VectorDB at {base}. Is the server running?"
            logger.error(msg)
            return ToolExecutionResult(content=msg, error=msg)

        data = resp.json()
        results = data.get("data", [])

        if not results:
            return ToolExecutionResult(
                content="No relevant documents found for that query.",
                payload=data,
            )

        # Format results for the LLM
        formatted = _format_search_results(results, query)

        return ToolExecutionResult(
            content=formatted,
            payload=data,
        )


# ---------------------------------------------------------------------------
# Function-based registration helper
# ---------------------------------------------------------------------------


def vector_store_search(
    query: str,
    max_results: int = 5,
    vector_store_id: Optional[str] = None,
    maia_api_base: Optional[str] = None,
) -> ToolExecutionResult:
    """Search a MAIA VectorDB vector store for relevant documents.

    Parameters visible to the LLM (in PARAMETERS schema):
        query: Natural language search query.
        max_results: How many results to return.

    Context-injected (not visible to LLM):
        vector_store_id: UUID of the vector store.
        maia_api_base: API base URL.
    """
    tool = VectorStoreSearchTool()
    return tool.execute(
        query=query,
        max_results=max_results,
        vector_store_id=vector_store_id,
        maia_api_base=maia_api_base,
    )


def register_vector_store_search(factory: Any) -> None:
    """Register the vector_store_search tool on a ToolFactory.

    This is the simplest way to add MAIA VectorDB search capability::

        factory = ToolFactory()
        register_vector_store_search(factory)
    """
    factory.register_tool(
        function=vector_store_search,
        name="vector_store_search",
        description=VectorStoreSearchTool.DESCRIPTION,
        parameters=VectorStoreSearchTool.PARAMETERS,
        category="knowledge",
        tags=["search", "vector", "rag", "knowledge-base"],
    )


# ---------------------------------------------------------------------------
# Formatting helper
# ---------------------------------------------------------------------------


def _format_search_results(results: list[dict], query: str) -> str:
    """Format search results into a readable string for the LLM."""
    lines = [f"Found {len(results)} relevant document chunks:\n"]

    for i, r in enumerate(results, 1):
        score = r.get("score", 0)
        filename = r.get("filename", "unknown")
        content = r.get("content", "")
        chunk_idx = r.get("chunk_index", 0)

        header = f"--- Result {i} (score: {score:.3f}, "
        header += f"file: {filename}, chunk: {chunk_idx}) ---"
        lines.append(header)
        lines.append(content.strip())
        lines.append("")

    return "\n".join(lines)
