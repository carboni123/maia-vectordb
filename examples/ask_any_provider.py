"""Use MAIA VectorDB as a tool with any LLM provider via llm-factory-toolkit.

This example demonstrates how MAIA VectorDB replaces OpenAI's built-in
``file_search`` with a provider-agnostic vector store search tool.

Instead of being locked to OpenAI::

    # OpenAI only - file_search is a built-in tool
    result = await client.generate(
        input=messages,
        file_search={"vector_store_ids": ["vs_abc"]},
    )

You can now use ANY provider with MAIA VectorDB::

    # Works with Anthropic, Gemini, xAI, OpenAI — any provider
    result = await client.generate(
        input=messages,
        tool_execution_context={
            "vector_store_id": "your-store-id",
            "maia_api_base": "http://localhost:8000",
        },
    )

Prerequisites:
    1. MAIA VectorDB server running with data loaded::

        uvicorn maia_vectordb.main:app
        python examples/setup_knowledge_base.py

    2. llm-factory-toolkit installed::

        pip install llm-factory-toolkit

    3. At least one LLM API key set::

        export OPENAI_API_KEY=sk-...
        export ANTHROPIC_API_KEY=sk-ant-...
        export GOOGLE_API_KEY=AI...
        export XAI_API_KEY=xai-...

Usage::

    # Use default provider (OpenAI)
    python examples/ask_any_provider.py

    # Specify a provider
    python examples/ask_any_provider.py --provider anthropic
    python examples/ask_any_provider.py --provider gemini
    python examples/ask_any_provider.py --provider xai

    # Custom question
    python examples/ask_any_provider.py --provider anthropic --query "What is pgvector?"

    # Run all providers
    python examples/ask_any_provider.py --all
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

# Add examples dir to path for local imports
sys.path.insert(0, os.path.dirname(__file__))

from llm_factory_toolkit import LLMClient, ToolFactory
from maia_tool import register_vector_store_search

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

VECTOR_STORE_ID = os.environ.get("VECTOR_STORE_ID", "")
MAIA_API_BASE = os.environ.get("MAIA_API_BASE", "http://localhost:8000")

# Provider -> default model mapping
PROVIDER_MODELS = {
    "openai": "openai/gpt-4o-mini",
    "anthropic": "anthropic/claude-sonnet-4-20250514",
    "gemini": "gemini/gemini-2.5-flash",
    "xai": "xai/grok-3-mini-fast",
}

SYSTEM_PROMPT = (
    "You are a helpful assistant with access to a knowledge base. "
    "When the user asks a question, use the vector_store_search tool "
    "to find relevant information before answering. "
    "Always cite the source documents in your response. "
    "If the search returns no results, say so and answer from your "
    "general knowledge."
)


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------


async def ask_with_provider(
    provider: str,
    query: str,
    vector_store_id: str,
    api_base: str,
) -> str | None:
    """Send a query to a specific LLM provider using MAIA VectorDB for RAG."""
    model = PROVIDER_MODELS.get(provider)
    if not model:
        print(f"  Unknown provider: {provider}")
        return None

    # 1. Set up the tool factory with the MAIA search tool
    factory = ToolFactory()
    register_vector_store_search(factory)

    # 2. Create the LLM client
    try:
        client = LLMClient(model=model, tool_factory=factory)
    except Exception as exc:
        print(f"  Failed to create client for {provider}: {exc}")
        return None

    # 3. Build the conversation
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": query},
    ]

    # 4. Generate with tool execution context
    #    The vector_store_id and maia_api_base are injected into the tool
    #    function automatically — the LLM never sees these values.
    print(f"  Generating response with {model}...")
    try:
        result = await client.generate(
            input=messages,
            tool_execution_context={
                "vector_store_id": vector_store_id,
                "maia_api_base": api_base,
            },
        )
    except Exception as exc:
        print(f"  Generation failed: {exc}")
        return None

    return result.content


async def run_single(
    provider: str,
    query: str,
    vector_store_id: str,
    api_base: str,
) -> None:
    """Run a single provider query."""
    print(f"\n{'=' * 60}")
    print(f"Provider: {provider.upper()}")
    print(f"Model:    {PROVIDER_MODELS.get(provider, '?')}")
    print(f"Query:    {query}")
    print(f"{'=' * 60}")

    response = await ask_with_provider(provider, query, vector_store_id, api_base)

    if response:
        print(f"\nResponse:\n{response}")
    else:
        print("\n  (no response)")


async def run_all(
    query: str,
    vector_store_id: str,
    api_base: str,
) -> None:
    """Run the same query across all providers for comparison."""
    print("\n" + "#" * 60)
    print("# Multi-Provider Vector Store Search Comparison")
    print(f"# Query: {query}")
    print("#" * 60)

    for provider in PROVIDER_MODELS:
        try:
            await run_single(provider, query, vector_store_id, api_base)
        except Exception as exc:
            print(f"\n  {provider} failed: {exc}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Query a MAIA VectorDB knowledge base with any LLM provider.",
    )
    parser.add_argument(
        "--provider",
        choices=list(PROVIDER_MODELS.keys()),
        default="openai",
        help="LLM provider to use (default: openai)",
    )
    parser.add_argument(
        "--query",
        default="What is MAIA VectorDB and how does it work?",
        help="The question to ask",
    )
    parser.add_argument(
        "--vector-store-id",
        default=VECTOR_STORE_ID,
        help="UUID of the MAIA VectorDB vector store",
    )
    parser.add_argument(
        "--api-base",
        default=MAIA_API_BASE,
        help="MAIA VectorDB API base URL",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run the query with all providers for comparison",
    )

    args = parser.parse_args()

    if not args.vector_store_id:
        print("ERROR: No vector store ID provided.")
        print()
        print("Either:")
        print("  1. Run setup first:  python examples/setup_knowledge_base.py")
        print("  2. Set env var:      export VECTOR_STORE_ID=<uuid>")
        print("  3. Pass as argument: --vector-store-id <uuid>")
        sys.exit(1)

    if args.all:
        asyncio.run(run_all(args.query, args.vector_store_id, args.api_base))
    else:
        asyncio.run(
            run_single(args.provider, args.query, args.vector_store_id, args.api_base)
        )


if __name__ == "__main__":
    main()
