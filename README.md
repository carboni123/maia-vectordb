# MAIA VectorDB

OpenAI-compatible vector store API for document storage, chunking, embedding, and semantic search.

## Features

- **Vector Store Management**: Create, list, retrieve, and delete vector stores
- **File Upload & Processing**: Upload documents (text or multipart), automatic chunking and embedding
- **Background Processing**: Large files processed asynchronously with status tracking
- **Semantic Search**: Fast vector similarity search using pgvector HNSW indexes
- **OpenAI-Compatible API**: Drop-in replacement for OpenAI's vector store endpoints
- **Error Handling & Middleware**: Consistent error responses, request logging, and correlation IDs
- **Health Monitoring**: Built-in health check endpoint with database connectivity and configuration status
- **OpenAPI Documentation**: Interactive API docs at `/docs` with complete request/response examples

## Documentation

- **[Quick Start Guide](docs/SETUP.md)** - Installation and setup instructions
- **[Development Guide](docs/DEVELOPMENT.md)** - Development workflow, testing, and API documentation
- **[Deployment Guide](docs/DEPLOYMENT.md)** - Production deployment instructions
- **[Contributing Guide](CONTRIBUTING.md)** - Guidelines for contributing to the project
- **[Changelog](CHANGELOG.md)** - Version history and release notes

## Tech Stack

- **Framework**: FastAPI
- **Database**: PostgreSQL with pgvector extension
- **ORM**: SQLAlchemy 2.0 (async)
- **Embeddings**: OpenAI API (text-embedding-3-small)
- **Chunking**: Recursive text splitter with tiktoken

## License

MIT
