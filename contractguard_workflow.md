# Phase 1: Infrastructure & Orchestrator Scaffolding

## Objective
Establish the primary environment, database, and the central Orchestrator Agent for ContractGuard AI based on the provided architecture.

## Execution Steps
1. **Environment:** Autonomously use the terminal to initialize a Python virtual environment and install `fastapi`, `streamlit`, `psycopg2-binary`, `pgvector`, `sentence-transformers`, `xgboost`, `shap`, `fpdf2`, and `ollama`.
2. **Database Setup:** Write and execute the SQL/Python scripts to initialize PostgreSQL with `pgvector`. Create the tables for `projects`, `users`, `rule_store` (JSONB), and `compliance_events` as defined in the architectural specs.
3. **The Orchestrator:** Build the central `Orchestrator Agent` in Python. It must be capable of receiving triggers (e.g., `MPR_UPLOADED`), maintaining project state, and preparing to route tasks to specialist agents.