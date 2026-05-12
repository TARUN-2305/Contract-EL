"""
Qdrant Vector Store — replaces pgvector for semantic clause search.
Falls back to in-memory numpy search if Qdrant unavailable.
"""
import json
import uuid
from typing import Optional
import numpy as np


def _cosine_sim(a, b):
    a, b = np.array(a), np.array(b)
    n = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / n) if n else 0.0


class QdrantVectorStore:
    COLLECTION = "contract_clauses"

    def __init__(self):
        from config import settings
        self.url = settings.qdrant_url
        self.api_key = settings.qdrant_api_key
        self._client = None
        self._fallback = {}  # in-memory fallback: contract_id -> list of (chunk, embedding)

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams, PointStruct
            c = QdrantClient(url=self.url, api_key=self.api_key, timeout=10)
            # Ensure collection exists
            try:
                c.get_collection(self.COLLECTION)
            except Exception:
                c.create_collection(
                    self.COLLECTION,
                    vectors_config=VectorParams(size=384, distance=Distance.COSINE)
                )
            self._client = c
            return c
        except Exception as e:
            print(f"[Qdrant] Client init failed: {e} — using in-memory fallback")
            return None

    def store_chunks(self, contract_id: str, chunks: list, embeddings: list):
        client = self._get_client()
        if client is None:
            # In-memory fallback
            self._fallback[contract_id] = list(zip(chunks, embeddings))
            print(f"[Qdrant] Stored {len(chunks)} chunks (in-memory) for {contract_id}")
            return

        try:
            from qdrant_client.models import PointStruct
            points = []
            for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
                points.append(PointStruct(
                    id=str(uuid.uuid4()),
                    vector=emb if isinstance(emb, list) else emb.tolist(),
                    payload={
                        "contract_id": contract_id,
                        "clause_id": chunk.get("clause_id"),
                        "section_type": chunk.get("section_type"),
                        "page_number": chunk.get("page_number"),
                        "text": chunk["text"][:2000],  # Qdrant payload limit
                    }
                ))
            client.upsert(collection_name=self.COLLECTION, points=points)
            print(f"[Qdrant] Stored {len(chunks)} chunks for {contract_id}")
        except Exception as e:
            print(f"[Qdrant] store error: {e} — falling back to memory")
            self._fallback[contract_id] = list(zip(chunks, embeddings))

    def search(self, contract_id: str, query_embedding: list, top_k: int = 5) -> list:
        client = self._get_client()

        if client is None or contract_id in self._fallback:
            # In-memory search
            items = self._fallback.get(contract_id, [])
            scored = [(_cosine_sim(query_embedding, emb), chunk) for chunk, emb in items]
            scored.sort(key=lambda x: x[0], reverse=True)
            return [c for _, c in scored[:top_k]]

        try:
            results = client.search(
                collection_name=self.COLLECTION,
                query_vector=query_embedding if isinstance(query_embedding, list) else query_embedding.tolist(),
                query_filter={"must": [{"key": "contract_id", "match": {"value": contract_id}}]},
                limit=top_k
            )
            return [
                {
                    "clause_id": r.payload.get("clause_id"),
                    "section_type": r.payload.get("section_type"),
                    "page_number": r.payload.get("page_number"),
                    "text": r.payload.get("text", ""),
                    "score": r.score,
                }
                for r in results
            ]
        except Exception as e:
            print(f"[Qdrant] search error: {e}")
            return []

    def delete_contract(self, contract_id: str):
        """Remove all chunks for a contract (on re-parse)."""
        self._fallback.pop(contract_id, None)
        client = self._get_client()
        if client:
            try:
                from qdrant_client.models import Filter, FieldCondition, MatchValue
                client.delete(
                    collection_name=self.COLLECTION,
                    points_selector=Filter(
                        must=[FieldCondition(key="contract_id", match=MatchValue(value=contract_id))]
                    )
                )
            except Exception as e:
                print(f"[Qdrant] delete error: {e}")


# Singleton
_qdrant_store: Optional[QdrantVectorStore] = None

def get_qdrant_store() -> QdrantVectorStore:
    global _qdrant_store
    if _qdrant_store is None:
        _qdrant_store = QdrantVectorStore()
    return _qdrant_store
