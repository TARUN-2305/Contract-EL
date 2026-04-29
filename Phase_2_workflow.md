# Phase 2: Contract Parser Agent + RAG Pipeline

## Objective
Build the Contract Parser Agent (Module 01) — the source of truth for the entire system. It ingests a contract PDF, extracts rules via Hierarchical RAG + LLM tool-calling, and writes a structured `rule_store` to the database and pgvector.

## Execution Steps

1. **pgvector Setup:** Install the `pgvector` PostgreSQL extension at the system level. Add a `clause_embeddings` table with a `vector(384)` column to store contract chunk embeddings.

2. **PDF Preprocessing Pipeline:** Build `agents/parser_agent.py`:
   - Use `pypdf` / `pdfplumber` to extract raw text from uploaded contract PDFs.
   - Split text into semantic chunks (respect article/clause boundaries, not fixed-size).
   - Tag each chunk with `{source_clause, page_number, section_type}`.

3. **Embedding Pipeline:** Use `sentence-transformers` (`all-MiniLM-L6-v2`) to embed chunks into 384-dim vectors. Write to `pgvector` with metadata.

4. **Hierarchical Extraction:** Implement the `EXTRACTION_PLAN` from `01_CONTRACT_PARSER.md`:
   - For each target (milestones, LD, FM, EoT, etc.), query pgvector for top-5 relevant chunks.
   - Send retrieved chunks to `gemma4:e2b` via Ollama with the few-shot extraction prompts defined in the EL spec.
   - Parse the LLM JSON output and validate using the `VALIDATION_RULES`.

5. **Rule Store Assembly:** Merge all extracted fields into the full `rule_store_{contract_id}.json` schema as defined in `01_CONTRACT_PARSER.md`. Store in `rule_store` DB table (JSONB) and write to `data/rule_store/`.

6. **Mock Contract PDF:** Create a mock PDF from the spec in `01_CONTRACT_PARSER.md` (NH-44 Karnataka project) for end-to-end testing.

7. **Wire to Orchestrator:** Register the Parser Agent in the Orchestrator's routing logic so `CONTRACT_UPLOADED` triggers invoke it.

8. **FastAPI Endpoint:** Add `POST /upload-contract` to accept PDF + metadata, trigger the parser pipeline.

## Verification
- Upload the mock contract PDF via the API.
- Verify the generated `rule_store` JSON matches the expected schema from `01_CONTRACT_PARSER.md`.
- Verify embeddings exist in pgvector.
