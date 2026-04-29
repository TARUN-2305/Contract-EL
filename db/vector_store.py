"""
Vector Store - Python-side vector similarity search.
Stores embeddings in PostgreSQL as JSON arrays.
When pgvector is installed, swap to native vector operations.
"""
import json
import numpy as np
from sqlalchemy import Column, Integer, String, Text, JSON
from sqlalchemy.orm import Session
from db.database import Base, engine


class ClauseEmbedding(Base):
    __tablename__ = "clause_embeddings"

    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(String, index=True, nullable=False)
    clause_id = Column(String, nullable=True)
    section_type = Column(String, nullable=True)
    page_number = Column(Integer, nullable=True)
    chunk_text = Column(Text, nullable=False)
    embedding = Column(JSON, nullable=False)  # stored as list[float]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    a_arr = np.array(a)
    b_arr = np.array(b)
    dot = np.dot(a_arr, b_arr)
    norm_a = np.linalg.norm(a_arr)
    norm_b = np.linalg.norm(b_arr)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


class VectorStore:
    def __init__(self, embed_model=None):
        self.embed_model = embed_model

    def store_chunks(self, db: Session, contract_id: str, chunks: list[dict], embeddings: list[list[float]]):
        """Store text chunks with their embeddings."""
        for chunk, emb in zip(chunks, embeddings):
            record = ClauseEmbedding(
                contract_id=contract_id,
                clause_id=chunk.get("clause_id"),
                section_type=chunk.get("section_type"),
                page_number=chunk.get("page_number"),
                chunk_text=chunk["text"],
                embedding=emb,
            )
            db.add(record)
        db.commit()
        print(f"[VectorStore] Stored {len(chunks)} chunks for contract {contract_id}")

    def search(self, db: Session, contract_id: str, query_embedding: list[float], top_k: int = 5) -> list[dict]:
        """Retrieve top-k most similar chunks by cosine similarity."""
        all_records = (
            db.query(ClauseEmbedding)
            .filter(ClauseEmbedding.contract_id == contract_id)
            .all()
        )

        scored = []
        for record in all_records:
            sim = cosine_similarity(query_embedding, record.embedding)
            scored.append({
                "chunk_text": record.chunk_text,
                "clause_id": record.clause_id,
                "section_type": record.section_type,
                "page_number": record.page_number,
                "similarity": sim,
            })

        scored.sort(key=lambda x: x["similarity"], reverse=True)
        return scored[:top_k]
