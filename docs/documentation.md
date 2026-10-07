# AI Service --- Engineering Documentation

> ShopOnBot Production E-Commerce AI Platform\
> Service: AI Service\
> Status: Foundation and architecture setup in progress\
> Last Updated: September 2026

------------------------------------------------------------------------

## 1. Purpose

The AI Service is an independent FastAPI microservice responsible for
AI-related capabilities of the ShopOnBot e-commerce platform.

The service is intentionally separated from the main backend so
AI-specific functionality can evolve, scale, test, and deploy
independently.

Planned capabilities include:

-   Conversational AI / chatbot
-   Temporary chatbot sessions
-   LLM integration
-   Embeddings
-   Vector search
-   RAG
-   Tool calling
-   AI orchestration and workflows

This document is the engineering source of truth for the AI Service
architecture, setup, implementation decisions, and operational notes.

Update this document whenever a significant architectural or
implementation decision is introduced.

------------------------------------------------------------------------

# 2. High-Level Architecture

``` text
Client / Browser
       |
       v
    Nginx
       |
       +----------------------+
       |                      |
       v                      v
Main FastAPI Backend     AI FastAPI Service
       |                      |
       |                      +---- Redis
       |                      |
       +---- PostgreSQL       +---- LLM / AI APIs
       |
       +---- RabbitMQ
```

The AI Service is an independent FastAPI application.

The main backend remains the owner of core business data and business
logic.

------------------------------------------------------------------------

# 3. Service Responsibilities

  -----------------------------------------------------------------------
  Area                                Responsibility
  ----------------------------------- -----------------------------------
  Main backend                        Users, products, orders, payments,
                                      core business logic

  AI Service                          Chatbot, LLM orchestration, RAG,
                                      tools, AI workflows

  PostgreSQL                          Durable business data

  Redis                               Temporary AI/chat state

  RabbitMQ                            Asynchronous/background messaging
  -----------------------------------------------------------------------

The AI Service should not become a second source of truth for core
business entities.

When business information is required, the preferred design is for the
AI Service to call APIs exposed by the main backend.

``` text
AI Service
    |
    | HTTP/API
    v
Main Backend
    |
    v
PostgreSQL
```

------------------------------------------------------------------------

# 4. Docker Architecture

The platform uses the shared Docker network:

``` text
shoponbot-production-network
```

Relevant containers:

``` text
shoponbot-production-network
|
+-- nginx-server
+-- fastapi_app
+-- ai_service
+-- redis-fastapi
+-- postgres-fastapi
+-- rabbit_mq
+-- email_worker
```

The AI Service joins the existing network. It does not create a second
Redis container.

------------------------------------------------------------------------

# 5. AI Service Docker Compose

Current configuration:

``` yaml
services:

  ai_service:

    build: .

    container_name: ai_service

    expose:

      - "8001"

    env_file:

      - .env

    volumes:

      - .:/app

      - /app/.venv

    networks:

      - fastapi_app


networks:

  fastapi_app:

    external: true

    name: shoponbot-production-network
```

Important:

-   AI Service internal port: `8001`
-   Existing external Docker network is reused.
-   `localhost` must not be used to reach Redis or PostgreSQL from
    inside the AI container.

------------------------------------------------------------------------

# 6. Shared Infrastructure

The main backend provides the following infrastructure relevant to the
AI Service:

  Service        Docker hostname        Port
  -------------- -------------------- ------
  Redis          `redis-fastapi`        6379
  PostgreSQL     `postgres-fastapi`     5432
  Main FastAPI   `fastapi_app`          8000
  AI FastAPI     `ai_service`           8001

Redis is therefore reached from the AI Service using:

``` text
redis-fastapi:6379
```

not:

``` text
localhost:6379
```

Inside a Docker container, `localhost` refers to that same container.

------------------------------------------------------------------------

# 7. Environment Configuration

Current intended AI Service `.env`:

``` env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres-fastapi:5432/ShopOnBot_db

REDIS_URL=redis://redis-fastapi:6379/0
```

Real credentials and API keys must never be committed to source control.

------------------------------------------------------------------------

# 8. Settings Management

Configuration is centralized in:

``` text
app/core/config.py
```

Current implementation:

``` python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
```

Application code should consume:

``` python
settings.REDIS_URL
```

instead of hardcoding infrastructure URLs.

The same application code can therefore run against different Redis
instances in development, staging, and production.

------------------------------------------------------------------------

# 9. Database Architecture

The AI Service can connect to the existing PostgreSQL infrastructure
through:

``` text
postgres-fastapi:5432
```

The configured URL uses SQLAlchemy's async PostgreSQL driver:

``` text
postgresql+asyncpg://...
```

PostgreSQL remains the durable source of truth for business data.

------------------------------------------------------------------------

# 10. Chat Persistence Decision

A major architectural decision has been finalized:

> Chat messages will not be permanently stored in PostgreSQL.

Instead, active chatbot state will be stored temporarily in Redis.

``` text
Chat session
     |
     v
   Redis
     |
     v
Temporary expiration
```

This reduces unnecessary PostgreSQL writes for transient conversational
data.

------------------------------------------------------------------------

# 11. Chat Session Requirements

  Requirement                       Decision
  --------------------------------- -----------------------------
  Inactivity TTL                    30 minutes
  Maximum absolute lifetime         4 hours
  Guest access                      Yes
  Multiple tabs                     Separate sessions
  Message storage                   Temporary Redis storage
  Permanent `chat_messages` table   No
  Browser refresh                   Resume valid session
  Closing tab                       Let TTL expire
  Logout                            Invalidate/delete session
  Guest → authenticated             Same session may transition
  Session isolation                 Mandatory

------------------------------------------------------------------------

# 12. Why Two Session Limits?

A 30-minute inactivity TTL alone cannot enforce a maximum lifetime.

Example:

``` text
User activity every 20 minutes
        |
        v
TTL keeps being refreshed
        |
        v
Session could remain alive indefinitely
```

Therefore the chatbot has:

``` text
Inactivity timeout: 30 minutes
Absolute lifetime: 4 hours
```

The inactivity timeout handles abandoned sessions.

The absolute lifetime prevents indefinite session survival.

------------------------------------------------------------------------

# 13. Multiple Tabs

Each browser tab/session gets its own chatbot session.

``` text
Browser
|
+-- Tab 1 --> Session A
|
+-- Tab 2 --> Session B
|
+-- Tab 3 --> Session C
```

This prevents conversations from different tabs from mixing.

------------------------------------------------------------------------

# 14. Browser Refresh

Refresh should resume the same session when it is still valid.

``` text
Browser refresh
      |
      v
Existing session ID
      |
      v
Redis
      |
      v
Resume conversation
```

A refresh should not automatically create a new session.

------------------------------------------------------------------------

# 15. Browser Close

The system should not depend on a browser unload event to delete a
session.

Browser unload/network requests are not guaranteed.

Instead, Redis TTL provides automatic expiration for inactive sessions.

------------------------------------------------------------------------

# 16. Logout

Logout must invalidate the associated chatbot session.

Conceptually:

``` text
Logout
  |
  v
Invalidate session
  |
  v
Delete temporary Redis state
```

This prevents the old session from remaining usable after logout.

------------------------------------------------------------------------

# 17. Guest Users

Guests are allowed to use the chatbot.

A guest session may transition to an authenticated user session while
respecting:

-   session isolation
-   30-minute inactivity timeout
-   4-hour absolute lifetime

------------------------------------------------------------------------

# 18. Redis Key Namespace

AI-specific Redis keys should use an isolated namespace.

Logical structure:

``` text
ai:chat:session:{session_id}
ai:chat:messages:{session_id}
```

Example:

``` text
ai:chat:session:7d8a...
ai:chat:messages:7d8a...
```

This prevents collisions with Redis keys belonging to the main backend.

------------------------------------------------------------------------

# 19. Redis vs PostgreSQL

Redis and PostgreSQL have different responsibilities.

``` text
PostgreSQL
|
+-- Users
+-- Products
+-- Orders
+-- Payments
+-- Durable business data


Redis
|
+-- Temporary chat sessions
+-- Temporary chat messages
+-- TTL-based state
+-- Other ephemeral AI state
```

Redis is not intended to replace PostgreSQL as the durable source of
truth.

------------------------------------------------------------------------

# 20. Redis Concepts Learned Before Implementation

The following concepts were intentionally understood before adding the
Redis Python dependency.

### Redis Server

The actual Redis service running in the Redis container.

``` text
redis-fastapi:6379
```

### Redis Python Client

A Python library used by the AI Service to communicate with Redis.

### TCP Connection

The network communication channel between the AI Service and Redis
Server.

### Connection Pool

A managed collection of reusable Redis connections.

``` text
Redis Client
     |
     v
Connection Pool
   |   |   |
   v   v   v
  TCP TCP TCP
   |   |   |
   +---+---+
       |
       v
     Redis
```

### Connection Management

Creating, acquiring, reusing, releasing, handling, and closing
connections.

### Connection Reuse

A connection can be reused by later Redis operations instead of creating
a brand-new TCP connection for every request.

### FastAPI Lifespan

The application lifecycle mechanism that will be used to manage
resources during startup and shutdown.

------------------------------------------------------------------------

# 21. Redis Request Lifecycle

A typical request will conceptually follow:

``` text
Browser
   |
   v
Nginx
   |
   v
AI FastAPI
   |
   v
Redis Python Client
   |
   v
Connection Pool
   |
   v
TCP Connection
   |
   v
Redis Server
   |
   v
Redis Data
```

After the operation:

``` text
Redis
   |
   v
TCP Connection
   |
   v
Connection Pool
   |
   v
Redis Client
   |
   v
FastAPI
```

The connection can then be reused by another request.

------------------------------------------------------------------------

# 22. Redis Client Lifecycle

The planned production lifecycle is:

``` text
Application startup
        |
        v
Redis client / pool available
        |
        v
Application serves requests
        |
        v
Redis operations
        |
        v
Connections reused
        |
        v
Application shutdown
        |
        v
Redis resources cleaned up
```

Creating a Redis client/pool is conceptually different from establishing
a TCP connection.

Actual connections may be created when Redis operations need them.

A Redis `PING` can later be used to verify actual connectivity:

``` python
await redis_client.ping()
```

------------------------------------------------------------------------

# 23. PostgreSQL Chat Table Cleanup

The project previously created PostgreSQL chatbot tables and later
removed them after the architecture was changed to Redis-only temporary
chat storage.

Migration history:

``` text
<base>
   |
   v
527d87c22fd2
Create chat_sessions
   |
   v
d5d0d32ceb52
Create chat_messages
   |
   v
818ae070f32d
Remove chat tables
```

Current database revision:

``` text
818ae070f32d (head)
```

The cleanup migration removes:

``` text
chat_messages
chat_sessions
```

The migration files remain because Alembic migrations represent schema
history.

------------------------------------------------------------------------

# 24. Migration Safety Rule

Do not delete old Alembic migration files just because the corresponding
database tables no longer exist.

Migration files are part of the schema evolution history.

``` text
Migration files
      =
Database schema history
```

If the schema changes in the future, create a new migration instead of
rewriting history casually.

------------------------------------------------------------------------

# 25. Development Principles

## Understand before implementing

Infrastructure concepts should be understood before introducing code.

## Reuse existing infrastructure

The existing Redis service should be reused rather than creating another
Redis container without a strong architectural reason.

## Configuration must be external

Do not hardcode:

-   Database URLs
-   Redis URLs
-   LLM API keys
-   Secrets

## Keep ownership clear

The main backend owns core business logic and durable business data.

The AI Service owns AI orchestration and temporary AI state.

## Document why

Important architectural decisions should record:

-   What was decided
-   Why it was decided
-   Alternatives considered
-   Trade-offs
-   Operational implications

------------------------------------------------------------------------

# 26. Current Implementation Status

### Completed

-   [x] Independent AI FastAPI service
-   [x] Docker configuration
-   [x] Shared Docker network integration
-   [x] Existing Redis infrastructure identified and reused
-   [x] Existing PostgreSQL infrastructure identified and reused
-   [x] `.env` configuration
-   [x] `DATABASE_URL`
-   [x] `REDIS_URL`
-   [x] Pydantic Settings configuration
-   [x] Chat persistence architecture
-   [x] Redis temporary chat storage decision
-   [x] 30-minute inactivity TTL decision
-   [x] 4-hour absolute session lifetime decision
-   [x] Guest session decision
-   [x] Multi-tab session isolation decision
-   [x] PostgreSQL chat table cleanup
-   [x] Alembic migration history preserved
-   [x] Redis networking and connection concepts understood

### Next

-   [ ] Install Python Redis client
-   [ ] Create Redis service/client module
-   [ ] Configure Redis client lifecycle
-   [ ] Add Redis health/readiness check
-   [ ] Design session key schema
-   [ ] Implement session creation
-   [ ] Implement inactivity TTL
-   [ ] Implement absolute 4-hour lifetime
-   [ ] Implement session validation
-   [ ] Implement logout cleanup
-   [ ] Implement temporary chat message storage

------------------------------------------------------------------------

# 27. Planned AI Roadmap

``` text
Foundation
    |
    +-- FastAPI
    +-- Docker
    +-- PostgreSQL connectivity
    +-- Redis
    |
    v
Chatbot Session System
    |
    +-- Session lifecycle
    +-- TTL
    +-- Guest/authenticated users
    +-- Multi-tab isolation
    |
    v
LLM Integration
    |
    +-- Provider integration
    +-- Prompt architecture
    +-- Streaming
    |
    v
Tool Calling
    |
    +-- Product search
    +-- Order information
    +-- Backend API integration
    |
    v
RAG
    |
    +-- Embeddings
    +-- Vector database
    +-- Retrieval
    +-- Reranking
    |
    v
Production AI Platform
    |
    +-- Observability
    +-- Testing
    +-- Security
    +-- CI/CD
    +-- Scaling
```

------------------------------------------------------------------------

# 28. Change Log

## September 2026 --- Foundation

-   Created independent AI Service architecture.
-   Connected AI Service to the existing shared Docker network.
-   Confirmed use of the existing Redis container.
-   Added Redis environment configuration.
-   Created Pydantic Settings configuration.
-   Finalized Redis-based temporary chatbot storage.
-   Finalized 30-minute inactivity timeout.
-   Finalized 4-hour absolute session lifetime.
-   Finalized guest access.
-   Finalized multi-tab session isolation.
-   Removed permanent PostgreSQL chatbot storage.
-   Preserved Alembic migration history.
-   Documented Redis client, TCP, connection pooling, and lifecycle
    concepts.

------------------------------------------------------------------------

# 29. Documentation Maintenance

This document should be updated when any of the following changes:

-   Architecture
-   Docker configuration
-   Environment variables
-   Database design
-   Redis design
-   API contracts
-   Authentication/session behavior
-   LLM provider
-   RAG architecture
-   Vector database
-   Tool calling
-   Security
-   Observability
-   CI/CD
-   Production deployment
-   Scaling strategy

For major architectural decisions, use this structure:

``` text
Decision
Context
Reasoning
Alternatives
Trade-offs
Implementation
Operational considerations
```

------------------------------------------------------------------------

# 30. Immediate Next Step

The next implementation step is to install the official Python Redis
client:

``` bash
uv add redis
```

After installation:

``` text
redis Python package
        |
        v
app/services/redis.py
        |
        v
Redis client
        |
        v
Connection pool
        |
        v
FastAPI lifecycle
```

Implementation should proceed one step at a time and this document
should be updated as the system evolves.

- [x] Redis Python client installed
- [x] Redis client module created
- [x] FastAPI lifespan integrated
- [x] Redis connectivity verified during application startup
- [x] Redis client cleanup configured during application shutdown
