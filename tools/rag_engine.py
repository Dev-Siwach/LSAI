import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
from config.settings import get_settings

class RagEngine:
    """Embedded Qdrant client & local embeddings engine for RAG."""
    
    def __init__(self):
        self.settings = get_settings()
        
        # Initialize Qdrant Client in local disk mode
        self.qdrant_path = str(self.settings.QDRANT_DIR)
        self.client = QdrantClient(path=self.qdrant_path)
        self.collection_name = self.settings.RAG_COLLECTION_NAME
        
        # Load embedding model (runs locally on CPU/GPU)
        self.encoder = SentenceTransformer(self.settings.EMBEDDING_MODEL)
        self.vector_size = self.encoder.get_sentence_embedding_dimension()
        
        self._ensure_collection()
        
    def _ensure_collection(self):
        """Ensure the target Qdrant collection exists."""
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)
        
        if not exists:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE
                )
            )
            
    def _chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """Simple text chunker (can be replaced by more advanced chunkers)."""
        words = text.split()
        chunks = []
        for i in range(0, len(words), chunk_size - overlap):
            chunk = " ".join(words[i:i + chunk_size])
            if chunk:
                chunks.append(chunk)
        return chunks

    def ingest_document(self, doc_id: str, text: str, metadata: Optional[Dict[str, Any]] = None):
        """Chunk, embed, and store a document into Qdrant."""
        if metadata is None:
            metadata = {}
            
        chunks = self._chunk_text(text)
        if not chunks:
            return
            
        embeddings = self.encoder.encode(chunks)
        
        points = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            point_id = f"{doc_id}_{i}"
            # Ensure UUID format or use an integer. For simplicity, we use string hash as integer or UUID string.
            # Qdrant accepts UUID strings or integers.
            import uuid
            point_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, point_id))
            
            payload = {
                "doc_id": doc_id,
                "text": chunk,
                "chunk_index": i,
                **metadata
            }
            
            points.append(
                PointStruct(
                    id=point_uuid,
                    vector=embedding.tolist(),
                    payload=payload
                )
            )
            
        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        
    def search(self, query: str, limit: int = 5, filter_dict: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Search the knowledge base for a given query."""
        query_vector = self.encoder.encode([query])[0].tolist()
        
        qdrant_filter = None
        if filter_dict:
            from qdrant_client.http.models import Filter, FieldCondition, MatchValue
            conditions = []
            for k, v in filter_dict.items():
                conditions.append(
                    FieldCondition(key=k, match=MatchValue(value=v))
                )
            qdrant_filter = Filter(must=conditions)
            
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            query_filter=qdrant_filter,
            limit=limit
        )
        
        return [
            {
                "score": hit.score,
                "text": hit.payload.get("text", ""),
                "metadata": {k: v for k, v in hit.payload.items() if k != "text"}
            }
            for hit in results
        ]
