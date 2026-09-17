import os
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional

from config.settings import get_settings


class RagEngine:
    """Embedded Qdrant client & local embeddings engine for air-gapped RAG."""

    def __init__(self, client: Optional[Any] = None, encoder: Optional[Any] = None):
        self.settings = get_settings()
        self.collection_name = self.settings.RAG_COLLECTION_NAME

        # Support dependency injection for unit testing without network/downloads
        if client is not None:
            self.client = client
        else:
            try:
                from qdrant_client import QdrantClient
                self.qdrant_path = str(self.settings.QDRANT_DIR)
                self.client = QdrantClient(path=self.qdrant_path)
            except ImportError:
                raise ImportError(
                    "qdrant-client is required for RagEngine. Please install qdrant-client."
                )

        if encoder is not None:
            self.encoder = encoder
            if hasattr(encoder, "get_sentence_embedding_dimension"):
                self.vector_size = encoder.get_sentence_embedding_dimension()
            else:
                self.vector_size = 384
        else:
            try:
                from sentence_transformers import SentenceTransformer
                self.encoder = SentenceTransformer(self.settings.EMBEDDING_MODEL)
                self.vector_size = self.encoder.get_sentence_embedding_dimension()
            except ImportError:
                raise ImportError(
                    "sentence-transformers is required for RagEngine. Please install sentence-transformers."
                )

        self._ensure_collection()

    def _ensure_collection(self):
        """Ensure the target Qdrant collection exists."""
        try:
            from qdrant_client.http.models import Distance, VectorParams
        except ImportError:
            return

        try:
            collections = self.client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)

            if not exists:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_size,
                        distance=Distance.COSINE,
                    ),
                )
        except Exception:
            pass

    def _chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """Chunk text into overlapping token windows safely."""
        if not text or not text.strip():
            return []

        words = text.split()
        if not words:
            return []

        step = max(1, chunk_size - overlap)
        chunks = []
        for i in range(0, len(words), step):
            chunk = " ".join(words[i : i + chunk_size])
            if chunk:
                chunks.append(chunk)
        return chunks

    def ingest_document(
        self, doc_id: str, text: str, metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """Chunk, embed, and store a document into Qdrant. Returns point count."""
        if not doc_id or not text or not text.strip():
            return 0

        if metadata is None:
            metadata = {}

        chunks = self._chunk_text(text)
        if not chunks:
            return 0

        embeddings = self.encoder.encode(chunks)

        try:
            from qdrant_client.http.models import PointStruct
        except ImportError:
            class PointStruct:  # type: ignore
                def __init__(self, id, vector, payload):
                    self.id = id
                    self.vector = vector
                    self.payload = payload

        points = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            point_id = f"{doc_id}_{i}"
            point_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, point_id))

            payload = {
                "doc_id": doc_id,
                "text": chunk,
                "chunk_index": i,
                **metadata,
            }

            vec = embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)

            points.append(
                PointStruct(
                    id=point_uuid,
                    vector=vec,
                    payload=payload,
                )
            )

        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )
        return len(points)

    def search(
        self, query: str, limit: int = 5, filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search the knowledge base for a given query."""
        if not query or not query.strip():
            return []

        query_vec = self.encoder.encode([query])[0]
        query_vector = query_vec.tolist() if hasattr(query_vec, "tolist") else list(query_vec)

        qdrant_filter = None
        if filter_dict:
            try:
                from qdrant_client.http.models import Filter, FieldCondition, MatchValue
                conditions = [
                    FieldCondition(key=k, match=MatchValue(value=v))
                    for k, v in filter_dict.items()
                ]
                qdrant_filter = Filter(must=conditions)
            except ImportError:
                qdrant_filter = None

        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            query_filter=qdrant_filter,
            limit=limit,
        )

        output = []
        for hit in results:
            payload = getattr(hit, "payload", {}) or {}
            score = getattr(hit, "score", 0.0)
            output.append({
                "score": score,
                "text": payload.get("text", ""),
                "metadata": {k: v for k, v in payload.items() if k != "text"},
            })

        return output
