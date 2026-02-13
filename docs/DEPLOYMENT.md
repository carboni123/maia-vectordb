# Deployment Guide

This guide covers deploying MAIA VectorDB to production environments.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Environment Configuration](#environment-configuration)
- [Database Setup](#database-setup)
- [Docker Deployment](#docker-deployment)
- [Cloud Deployment](#cloud-deployment)
- [Monitoring and Logging](#monitoring-and-logging)
- [Security Best Practices](#security-best-practices)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Services

- **PostgreSQL 14+** with pgvector extension installed
- **OpenAI API Key** for embedding generation
- **Docker** (for containerized deployment)

### System Requirements

- **Memory:** Minimum 2GB RAM (4GB+ recommended for production)
- **Storage:** Depends on dataset size (1M chunks ≈ 8GB for vectors + index)
- **CPU:** 2+ cores recommended
- **Network:** HTTPS-capable environment for production

## Environment Configuration

### Required Environment Variables

Create a `.env` file with the following variables:

```bash
# Database connection (use asyncpg driver)
DATABASE_URL=postgresql+asyncpg://username:password@hostname:5432/database_name

# OpenAI API credentials
OPENAI_API_KEY=sk-your-production-api-key-here

# Optional: Embedding configuration
EMBEDDING_MODEL=text-embedding-3-small  # or text-embedding-3-large
CHUNK_SIZE=800                          # Max tokens per chunk
CHUNK_OVERLAP=200                       # Overlapping tokens
```

### Production Considerations

**Database URL Format:**
- Use SSL/TLS for database connections: `?sslmode=require`
- Example: `postgresql+asyncpg://user:pass@host:5432/db?sslmode=require`

**API Key Security:**
- Never commit `.env` file to version control
- Use environment variables or secret management services (AWS Secrets Manager, HashiCorp Vault, etc.)
- Rotate API keys regularly

## Database Setup

### 1. Install pgvector Extension

Connect to your PostgreSQL database and run:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### 2. Create Database User

```sql
-- Create dedicated user for the application
CREATE USER maia_app WITH PASSWORD 'strong_password_here';

-- Create database
CREATE DATABASE maia_vectordb OWNER maia_app;

-- Grant necessary permissions
GRANT ALL PRIVILEGES ON DATABASE maia_vectordb TO maia_app;
```

### 3. Run Database Migrations

```bash
# Set DATABASE_URL environment variable
export DATABASE_URL="postgresql+asyncpg://maia_app:password@host:5432/maia_vectordb"

# Run Alembic migrations
uv run alembic upgrade head
```

### 4. Verify Database Setup

```bash
# Check that pgvector extension is installed
psql $DATABASE_URL -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"

# Verify tables were created
psql $DATABASE_URL -c "\dt"
```

## Docker Deployment

### Quick Start with Makefile

The project includes a Makefile with common Docker commands:

```bash
# Build the Docker image
make build

# Start the service with docker-compose
make up

# Stop the service
make down

# View logs
docker compose logs -f api
```

### 1. Build Docker Image

**Using Makefile:**
```bash
make build
```

**Or manually:**
```bash
docker build -t maia-vectordb:latest .

# Tag for your registry (optional)
docker tag maia-vectordb:latest your-registry.com/maia-vectordb:0.1.0
```

**Image Specifications:**
- Multi-stage build (builder + runtime)
- Base: `python:3.12-slim`
- Size: ~243MB (includes numpy, SQLAlchemy, asyncpg, uvloop)
- Non-root user: `appuser` (uid 1000)
- Built-in health check (10s interval, 30s start period)

### 2. Run with Docker

**Using Environment File:**
```bash
docker run -d \
  --name maia-vectordb \
  --env-file .env \
  --add-host host.docker.internal:host-gateway \
  -p 8000:8000 \
  maia-vectordb:latest
```

**Using Environment Variables:**
```bash
docker run -d \
  --name maia-vectordb \
  -e DATABASE_URL="postgresql+asyncpg://user:pass@host.docker.internal:5432/db" \
  -e OPENAI_API_KEY="sk-your-key" \
  --add-host host.docker.internal:host-gateway \
  -p 8000:8000 \
  maia-vectordb:latest
```

**Note:** `--add-host host.docker.internal:host-gateway` allows the container to connect to PostgreSQL running on the host machine.

### 3. Docker Compose (Recommended)

The included `docker-compose.yml` is configured for development with existing PostgreSQL:

```yaml
services:
  api:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    extra_hosts:
      - "host.docker.internal:host-gateway"
    depends_on: []
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 10s
      timeout: 5s
      start_period: 30s
      retries: 3
```

**Start the service:**
```bash
make up
# Or: docker compose up -d
```

**View logs:**
```bash
docker compose logs -f api
```

**Stop the service:**
```bash
make down
# Or: docker compose down
```

**Production docker-compose.yml example:**

For production, you may want to add resource limits:

```yaml
services:
  api:
    image: maia-vectordb:latest
    ports:
      - "8000:8000"
    env_file:
      - .env
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 10s
      timeout: 5s
      start_period: 30s
      retries: 3
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

## Cloud Deployment

### AWS (Elastic Container Service)

**1. Push image to ECR:**
```bash
# Authenticate to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Tag and push
docker tag maia-vectordb:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/maia-vectordb:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/maia-vectordb:latest
```

**2. Database Setup:**
- Use Amazon RDS for PostgreSQL with pgvector extension
- Enable SSL/TLS connections
- Use AWS Secrets Manager for DATABASE_URL and OPENAI_API_KEY

**3. Deploy to ECS:**
- Create ECS task definition with the image
- Configure environment variables from Secrets Manager
- Set up Application Load Balancer
- Enable auto-scaling based on CPU/memory

### Google Cloud (Cloud Run)

**1. Build and push to Artifact Registry:**
```bash
# Authenticate
gcloud auth configure-docker

# Build and push
docker tag maia-vectordb:latest gcr.io/<project-id>/maia-vectordb:latest
docker push gcr.io/<project-id>/maia-vectordb:latest
```

**2. Deploy to Cloud Run:**
```bash
gcloud run deploy maia-vectordb \
  --image gcr.io/<project-id>/maia-vectordb:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars DATABASE_URL="postgresql+asyncpg://..." \
  --set-secrets OPENAI_API_KEY=openai-key:latest \
  --port 8000 \
  --memory 2Gi \
  --cpu 2 \
  --min-instances 1 \
  --max-instances 10
```

**Database:**
- Use Cloud SQL for PostgreSQL with pgvector
- Enable Cloud SQL Proxy for secure connections
- Use Secret Manager for credentials

### Azure (Container Instances)

**1. Push to Azure Container Registry:**
```bash
# Login
az acr login --name <registry-name>

# Tag and push
docker tag maia-vectordb:latest <registry-name>.azurecr.io/maia-vectordb:latest
docker push <registry-name>.azurecr.io/maia-vectordb:latest
```

**2. Deploy:**
```bash
az container create \
  --resource-group <resource-group> \
  --name maia-vectordb \
  --image <registry-name>.azurecr.io/maia-vectordb:latest \
  --dns-name-label maia-vectordb \
  --ports 8000 \
  --environment-variables \
    DATABASE_URL="postgresql+asyncpg://..." \
  --secure-environment-variables \
    OPENAI_API_KEY="sk-..." \
  --cpu 2 \
  --memory 4
```

**Database:**
- Use Azure Database for PostgreSQL Flexible Server
- Install pgvector extension
- Use Azure Key Vault for secrets

## Monitoring and Logging

### Health Checks

The `/health` endpoint provides service health status:

```bash
curl https://your-domain.com/health
```

**Response (healthy):**
```json
{
  "status": "ok",
  "version": "0.1.0",
  "database": {"status": "ok", "detail": null},
  "openai_api_key_set": true
}
```

### Application Logs

**Structured logging format:**
```
2026-02-13T10:30:45 INFO [maia_vectordb.core.middleware] GET /v1/vector_stores 200 45.2ms [request_id=abc-123]
```

**Log levels:**
- `INFO` - Normal operation (requests, responses)
- `WARNING` - Rate limits, retries
- `ERROR` - Failures, exceptions

**Centralized logging (recommended):**
- AWS CloudWatch Logs
- Google Cloud Logging
- Azure Monitor
- Elasticsearch + Kibana (ELK Stack)
- Datadog, New Relic, or similar

### Metrics to Monitor

**Application Metrics:**
- Request rate (requests/second)
- Response time (p50, p95, p99)
- Error rate (4xx, 5xx responses)
- Request ID tracking for debugging

**Database Metrics:**
- Connection pool utilization
- Query response time
- Active connections
- Dead tuples (index bloat)

**OpenAI API Metrics:**
- Embedding API call rate
- Retry rate (429 errors)
- API response time
- Token usage/costs

## Security Best Practices

### 1. Environment Variables

**Production:**
- Use secret management services (AWS Secrets Manager, Google Secret Manager, Azure Key Vault)
- Never hardcode credentials
- Rotate secrets regularly

### 2. Database Security

- **Encryption:** Enable SSL/TLS for connections (`?sslmode=require`)
- **Network:** Restrict database access to application IPs only
- **Passwords:** Use strong, random passwords (32+ characters)
- **User Permissions:** Grant minimum required privileges

### 3. API Security

- **CORS:** Restrict allowed origins in production (update `main.py`)
- **Rate Limiting:** Implement rate limiting (e.g., slowapi, fastapi-limiter)
- **Authentication:** Add API key authentication for public endpoints
- **HTTPS:** Always use HTTPS in production (terminate SSL at load balancer)

### 4. Docker Security

- **Non-root user:** Container runs as non-root (user 1000)
- **Image scanning:** Scan images for vulnerabilities (Trivy, Snyk)
- **Minimal base:** Uses `python:3.12-slim` (minimal attack surface)

### 5. Data Security

- **PII:** Avoid storing sensitive personal data in metadata fields
- **Embeddings:** Embeddings may preserve semantic information from original text
- **Backups:** Encrypt database backups at rest

## Troubleshooting

### Database Connection Issues

**Symptom:** `503 Service Unavailable` from `/health` endpoint

**Solutions:**
1. Verify DATABASE_URL is correct
2. Check database server is running
3. Verify network connectivity (firewall, security groups)
4. Check SSL/TLS requirements (`sslmode=require`)
5. Verify pgvector extension is installed

### OpenAI API Errors

**Symptom:** File upload fails with 502 error

**Solutions:**
1. Verify OPENAI_API_KEY is valid
2. Check API key has sufficient quota
3. Review rate limits (retry logic handles 429 automatically)
4. Check OpenAI service status

### Performance Issues

**Symptom:** Slow search queries

**Solutions:**
1. Verify HNSW index exists on `file_chunks.embedding`
2. Check connection pool settings (increase pool_size)
3. Monitor database query performance
4. Consider increasing `ef_search` parameter for HNSW index
5. Review query filters (metadata filtering can be slow on large datasets)

### Memory Issues

**Symptom:** Container crashes or OOM errors

**Solutions:**
1. Increase container memory limits
2. Reduce batch sizes for embedding API calls
3. Limit concurrent file uploads
4. Review connection pool size (fewer connections = less memory)

### Migration Failures

**Symptom:** Alembic migration fails

**Solutions:**
1. Check database permissions
2. Verify pgvector extension is installed
3. Review migration logs for specific errors
4. Manually apply migrations if needed:
   ```bash
   uv run alembic upgrade head --sql > migration.sql
   psql $DATABASE_URL < migration.sql
   ```

## Rollback Procedure

If deployment fails, rollback to previous version:

**Docker:**
```bash
docker stop maia-vectordb
docker rm maia-vectordb
docker run -d --name maia-vectordb ... maia-vectordb:previous-tag
```

**Cloud Services:**
- AWS ECS: Update service to use previous task definition revision
- Google Cloud Run: Rollback to previous revision via console or CLI
- Azure: Redeploy previous container image

**Database Migrations:**
```bash
# Rollback one migration
uv run alembic downgrade -1

# Rollback to specific revision
uv run alembic downgrade <revision_id>
```

## Performance Tuning

### Database Optimization

**Connection Pool:**
```python
# config.py
class Settings(BaseSettings):
    database_pool_size: int = 20        # Increase for high traffic
    database_max_overflow: int = 40
    database_pool_timeout: int = 30
```

**HNSW Index Tuning:**
```sql
-- Increase ef_search for better recall (default: 40)
SET hnsw.ef_search = 100;

-- Rebuild index with higher quality
CREATE INDEX CONCURRENTLY ix_file_chunks_embedding_hnsw
ON file_chunks USING hnsw (embedding vector_cosine_ops)
WITH (m = 32, ef_construction = 128);
```

### Application Optimization

- **Caching:** Implement Redis cache for frequent queries
- **Background Tasks:** Use Celery for async processing of large files
- **CDN:** Serve static assets via CDN
- **Load Balancing:** Use multiple instances behind load balancer

---

## Support

For issues or questions:
- Open an issue on GitHub
- Check existing documentation in `/docs`
- Review logs for error details

**Happy deploying!** 🚀
