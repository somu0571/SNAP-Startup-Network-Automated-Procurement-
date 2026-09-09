"""
RAG Indexer.
Chunks solution documents and stores embeddings in ChromaDB.
Used for CROSS-DOCUMENT semantic search (e.g. "find all startups using IoT sensors").
"""
import os
import re
import chromadb
from chromadb.config import Settings
import hashlib
import math
import numpy as np
from typing import Optional, Union
from sentence_transformers import SentenceTransformer
from config import CHROMA_PERSIST_DIR, EMBEDDING_MODEL, CHUNK_SIZE, CHUNK_OVERLAP

class OfflineEmbeddingModel:
    """Deterministic offline embedding model when HuggingFace is unreachable."""
    def __init__(self, dim: int = 384):
        self.dim = dim

    def encode(self, texts: list[str], show_progress_bar: bool = False):
        embeddings = []
        for text in texts:
            words = re.findall(r'\b\w+\b', text.lower())
            vec = np.zeros(self.dim, dtype=np.float32)
            if not words:
                embeddings.append(vec.tolist())
                continue
            for word in words:
                idx = int(hashlib.md5(word.encode('utf-8')).hexdigest(), 16) % self.dim
                sign = 1.0 if int(hashlib.sha256(word.encode('utf-8')).hexdigest(), 16) % 2 == 0 else -1.0
                vec[idx] += sign
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec /= norm
            embeddings.append(vec)
        return np.array(embeddings)

# Lazy-loaded globals
_embedding_model = None
_chroma_client = None


def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        try:
            print(f"[RAG] Attempting to load embedding model: {EMBEDDING_MODEL}")
            _embedding_model = SentenceTransformer(EMBEDDING_MODEL)
            print("[RAG] SentenceTransformer model loaded successfully.")
        except Exception as e:
            print(f"[RAG] Note: HuggingFace remote load failed ({e}). Using robust offline embedding engine.")
            _embedding_model = OfflineEmbeddingModel(dim=384)
    return _embedding_model


def _get_chroma_client() -> chromadb.PersistentClient:
    global _chroma_client
    if _chroma_client is None:
        os.makedirs(CHROMA_PERSIST_DIR, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    return _chroma_client


def _get_collection(problem_id: Union[int, str]):
    """Get or create a ChromaDB collection for a problem."""
    client = _get_chroma_client()
    collection_name = f"problem_{problem_id}"
    return client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"}
    )


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Split text into overlapping chunks by word count.
    Tries to split on paragraph boundaries first.
    """
    # Split on paragraphs first
    paragraphs = re.split(r'\n\s*\n', text)
    chunks = []
    current_chunk = []
    current_size = 0

    for para in paragraphs:
        words = para.split()
        if not words:
            continue

        if current_size + len(words) > chunk_size:
            if current_chunk:
                chunks.append(" ".join(current_chunk))
            # Start new chunk with overlap from end of previous
            overlap_words = current_chunk[-overlap:] if len(current_chunk) > overlap else current_chunk
            current_chunk = overlap_words + words
            current_size = len(current_chunk)
        else:
            current_chunk.extend(words)
            current_size += len(words)

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    # Ensure minimum chunk quality
    return [c for c in chunks if len(c.strip()) > 50]


def index_solution(problem_id: int, solution_id: int, startup_name: str, doc_text: str):
    """
    Chunk a solution document and store embeddings in ChromaDB.
    """
    model = _get_embedding_model()
    collection = _get_collection(problem_id)

    chunks = _chunk_text(doc_text)
    if not chunks:
        print(f"[RAG] No chunks generated for solution {solution_id}")
        return

    # Generate embeddings
    embeddings = model.encode(chunks, show_progress_bar=False).tolist()

    # Build IDs and metadata
    ids = [f"sol_{solution_id}_chunk_{i}" for i in range(len(chunks))]
    metadatas = [
        {
            "solution_id": solution_id,
            "startup_name": startup_name,
            "problem_id": problem_id,
            "chunk_index": i
        }
        for i in range(len(chunks))
    ]

    # Upsert into ChromaDB (safe to re-index)
    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=chunks,
        metadatas=metadatas
    )
    print(f"[RAG] Indexed {len(chunks)} chunks for '{startup_name}' (solution_id={solution_id})")


def search_solutions(problem_id: Optional[Union[int, str]] = None, query: str = "", top_k: int = 10) -> list[dict]:
    """
    Semantic search across indexed solutions.
    If problem_id is provided and its collection has documents, searches that problem's collection.
    If problem_id is None, empty, or its collection is empty, searches all indexed collections.
    Gracefully handles empty collections without throwing ChromaError.
    """
    if not query or not query.strip():
        return []

    model = _get_embedding_model()
    client = _get_chroma_client()
    query_embedding = model.encode([query], show_progress_bar=False).tolist()

    collections_to_search = []

    # If problem_id is specified, check if its specific collection has items
    if problem_id is not None:
        pid_str = str(problem_id).strip()
        if pid_str and pid_str.lower() not in ("none", "null", "all", "0"):
            target_name = f"problem_{pid_str}"
            try:
                coll = client.get_collection(target_name)
                if coll.count() > 0:
                    collections_to_search.append(coll)
            except Exception:
                pass

    # If no specific collection found with items, search all non-empty collections
    if not collections_to_search:
        try:
            for coll in client.list_collections():
                try:
                    if coll.count() > 0:
                        collections_to_search.append(coll)
                except Exception:
                    continue
        except Exception as e:
            print(f"[RAG] Error listing collections: {e}")

    if not collections_to_search:
        return []

    all_matches = []
    for coll in collections_to_search:
        try:
            total_items = coll.count()
            if total_items == 0:
                continue
            n_results = min(top_k, total_items)
            results = coll.query(
                query_embeddings=query_embedding,
                n_results=n_results,
                include=["documents", "metadatas", "distances"]
            )
            if results and results.get("documents") and len(results["documents"]) > 0:
                for doc, meta, dist in zip(
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0]
                ):
                    all_matches.append({
                        "startup_name": meta.get("startup_name", "Unknown"),
                        "solution_id": meta.get("solution_id"),
                        "problem_id": meta.get("problem_id"),
                        "chunk": doc,
                        "similarity_score": round(max(0.0, 1.0 - dist), 4)
                    })
        except Exception as query_err:
            print(f"[RAG] Search error on collection {coll.name}: {query_err}")

    # Deduplicate and sort descending by similarity score
    all_matches.sort(key=lambda x: x["similarity_score"], reverse=True)
    return all_matches[:top_k]


def delete_solution_index(problem_id: int, solution_id: int):
    """Remove all chunks for a specific solution from the index."""
    collection = _get_collection(problem_id)
    # Get IDs for this solution
    results = collection.get(where={"solution_id": solution_id})
    if results and results["ids"]:
        collection.delete(ids=results["ids"])
        print(f"[RAG] Removed {len(results['ids'])} chunks for solution_id={solution_id}")


if __name__ == "__main__":
    # Quick test
    sample_text = """
    TechSense Solutions provides an IoT-based pipeline monitoring system.
    We use acoustic sensors to detect leaks in water pipelines.
    Our technology stack includes Raspberry Pi, MQTT, and AWS IoT Core.
    The system provides real-time alerts within 2 minutes of leak detection.
    We have successfully deployed in Pune Municipal Corporation saving 30% water loss.
    """
    index_solution(problem_id=1, solution_id=1, startup_name="TechSense", doc_text=sample_text)
    results = search_solutions(problem_id=1, query="IoT sensors pipeline monitoring")
    for r in results:
        print(r)
