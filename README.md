# ContractGuard AI — Production v2.0

Intelligent compliance system for Indian public infrastructure contracts (EPC + CPWD GCC 2023).

## Quick Start

```bash
# 1. Copy and configure environment
cp .env.example .env
# Edit .env — add your Groq API keys

# 2. Start all services (DB, Redis, Qdrant, API, Celery, Frontend, Ollama)
docker compose up -d

# 3. Open browser
# Frontend: http://localhost:5173
# API docs:  http://localhost:8000/docs
# Qdrant:    http://localhost:6333/dashboard
```

## Services

| Service    | Port  | Description                          |
|-----------|-------|--------------------------------------|
| Frontend  | 5173  | React dashboard (role-gated UI)      |
| API       | 8000  | FastAPI backend                      |
| PostgreSQL| 5432  | Relational + audit store             |
| Redis     | 6379  | Celery broker + job cache            |
| Qdrant    | 6333  | Vector DB for clause search          |
| Ollama    | 11434 | Local LLM fallback (CPU)             |

## LLM Fallback Chain

Groq API → Ollama gemma3:1b → Ollama phi3:mini

Without Groq keys, the system uses Ollama (slower, CPU-based, no rate limits).

## Workflow

1. **Contract Manager** uploads contract PDF → rule store extracted
2. **Site Engineer** uploads Monthly Progress Report (.md) → 15 compliance checks run
3. **Project Manager** views risk score + S-curve on dashboard
4. **Auditor** downloads PDF compliance reports
5. **Contractor** views their LD calculations and FM claim status

## Stack

- Backend: FastAPI, SQLAlchemy, Celery, pgvector
- Vector DB: Qdrant (with in-memory fallback)
- ML: XGBoost + SHAP
- LLM: Groq (cloud) → Ollama (local CPU fallback)
- Frontend: React + Vite
