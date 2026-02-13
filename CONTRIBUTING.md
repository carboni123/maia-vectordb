# Contributing to MAIA VectorDB

Thank you for your interest in contributing to MAIA VectorDB! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Code Standards](#code-standards)
- [Testing Requirements](#testing-requirements)
- [Submitting Changes](#submitting-changes)
- [Code Review Process](#code-review-process)

## Getting Started

### Prerequisites

- Python 3.12 or higher
- PostgreSQL 14+ with pgvector extension
- [uv](https://github.com/astral-sh/uv) package manager
- Docker (optional, for containerized development)

### Setting Up Your Development Environment

1. **Fork and clone the repository:**
   ```bash
   git clone https://github.com/yourusername/maia-vectordb.git
   cd maia-vectordb
   ```

2. **Install dependencies:**
   ```bash
   uv sync --extra dev
   ```

3. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your actual DATABASE_URL and OPENAI_API_KEY
   ```

4. **Verify setup:**
   ```bash
   make lint  # Run linter and type checker
   make test  # Run test suite
   ```

## Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
```

Use descriptive branch names:
- `feature/add-metadata-search` - for new features
- `fix/embedding-retry-logic` - for bug fixes
- `docs/update-api-guide` - for documentation
- `refactor/chunking-service` - for refactoring

### 2. Make Your Changes

Follow the [code standards](#code-standards) outlined below.

### 3. Write Tests

All new features and bug fixes must include tests. See [Testing Requirements](#testing-requirements).

### 4. Run Quality Checks

Before committing, ensure all checks pass:

```bash
# Lint code
uv run ruff check src tests

# Format code
uv run ruff format src tests

# Type check
uv run mypy src

# Run tests
uv run pytest tests -v

# Or use the Makefile
make lint
make test
```

### 5. Commit Your Changes

Use clear, descriptive commit messages:

```bash
git add .
git commit -m "feat: add metadata filtering to search endpoint"
```

**Commit Message Format:**
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `test:` - Adding or updating tests
- `refactor:` - Code refactoring
- `chore:` - Maintenance tasks

### 6. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a pull request on GitHub.

## Code Standards

### Python Style

- **Line Length:** 88 characters (Black-compatible)
- **Import Order:** Standard library → Third-party → Local application
- **Type Hints:** All functions must have type hints
- **Docstrings:** All public functions, classes, and modules must have docstrings

### Code Quality Tools

We use the following tools (all configured in `pyproject.toml`):

- **Ruff:** Linting and formatting
- **mypy:** Static type checking (strict mode)
- **pytest:** Testing framework

### File Organization

```
src/maia_vectordb/
├── api/              # FastAPI route handlers
├── models/           # SQLAlchemy ORM models
├── schemas/          # Pydantic request/response schemas
├── services/         # Business logic
├── core/             # Configuration and utilities
└── db/               # Database setup
```

### Naming Conventions

- **Modules:** `snake_case.py`
- **Classes:** `PascalCase`
- **Functions:** `snake_case()`
- **Constants:** `UPPER_SNAKE_CASE`
- **Private:** `_leading_underscore()`

## Testing Requirements

### Test Coverage

- **Minimum:** 80% overall coverage
- **New Features:** Must have 100% coverage
- **Critical Paths:** API routes and business logic must have 100% coverage

### Writing Tests

**Location:** Place tests in `tests/` directory with naming convention `test_*.py`

**Example:**
```python
"""Tests for vector store API endpoints."""

from fastapi.testclient import TestClient
from maia_vectordb.main import app

client = TestClient(app)


def test_create_vector_store() -> None:
    """Creating a vector store returns 201 with valid response."""
    response = client.post(
        "/v1/vector_stores",
        json={"name": "Test Store"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["object"] == "vector_store"
    assert data["name"] == "Test Store"
```

### Running Tests

```bash
# Run all tests
uv run pytest tests -v

# Run specific test file
uv run pytest tests/test_vector_store_crud.py -v

# Run with coverage
uv run pytest tests --cov=maia_vectordb --cov-report=html

# Run integration tests (requires API keys)
uv run pytest tests -v -m integration
```

## Submitting Changes

### Pull Request Checklist

Before submitting a pull request, ensure:

- [ ] Code follows the style guidelines
- [ ] All tests pass (`make test`)
- [ ] Linting passes (`uv run ruff check src tests`)
- [ ] Type checking passes (`uv run mypy src`)
- [ ] New features have tests
- [ ] Documentation is updated
- [ ] Commit messages are clear and descriptive
- [ ] No sensitive information (API keys, passwords) in code

### Pull Request Template

When creating a pull request, include:

**Title:** Clear, concise description (e.g., "Add metadata filtering to search endpoint")

**Description:**
```markdown
## Summary
Brief description of changes

## Motivation
Why is this change needed?

## Changes
- List of changes made
- Each change on its own line

## Testing
How were the changes tested?

## Screenshots (if applicable)
Add screenshots for UI changes
```

## Code Review Process

1. **Automated Checks:** All PRs must pass automated linting, type checking, and tests
2. **Peer Review:** At least one maintainer must approve the PR
3. **Response Time:** We aim to review PRs within 2-3 business days
4. **Revisions:** Address feedback and push new commits to the same branch

### Review Criteria

Reviewers will check for:
- Code quality and readability
- Test coverage
- Performance implications
- Security considerations
- Documentation completeness

## Questions or Issues?

- **Bug Reports:** Open an issue with the `bug` label
- **Feature Requests:** Open an issue with the `enhancement` label
- **Questions:** Open a discussion or reach out to maintainers

## License

By contributing to MAIA VectorDB, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to MAIA VectorDB! 🚀
